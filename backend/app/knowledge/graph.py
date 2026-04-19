from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import networkx as nx

from .loader import (
    PeripheralSpec,
    load_clock_topology,
    load_errata,
    load_pin_functions,
    load_svd_peripherals,
    load_wokwi_components,
)

NODE_PERIPHERAL = "peripheral"
NODE_REGISTER = "register"
NODE_FIELD = "field"
NODE_PIN = "pin"
NODE_CLOCK = "clock"
NODE_ERRATUM = "erratum"
NODE_WOKWI = "wokwi_component"

PERIPHERAL_FAMILIES = ("I2C", "SPI", "UART", "PWM", "ADC", "SIO")


class PinConflictError(ValueError):
    """Raised when two requested GPIO assignments collide on the same pin."""


class UnknownRegisterError(LookupError):
    """Raised when a (peripheral, register) pair is not present in the SVD."""


class UnknownPeripheralError(LookupError):
    """Raised when an instance name (e.g. I2C7) is not present in the SVD."""


@dataclass(frozen=True)
class PinAssignment:
    pin_number: int
    function: str


class RPGraph:
    """NetworkX-backed knowledge graph for the RP2040.

    The graph composes three data sources:
      * `rp2040.svd` → peripherals, registers, and fields with real addresses.
      * `pin_functions.json` → GPIO mux options per pin.
      * `clock_topology.json` → clock sources, PLLs, and domain edges.

    Register addresses are authoritative — the LLM is never trusted to produce
    them. Agents request a register by (peripheral, register) name and the
    graph resolves the address.
    """

    def __init__(
        self,
        peripherals: dict[str, PeripheralSpec],
        pin_functions: dict[int, dict[str, Any]],
        clock_topology: dict,
        errata: list[dict],
        wokwi_components: dict[str, dict],
    ) -> None:
        self._peripherals = peripherals
        self._pin_functions = pin_functions
        self._clock_topology = clock_topology
        self._errata = errata
        self._wokwi_components = wokwi_components
        self._g = self._build_graph()

    @classmethod
    def load(cls) -> RPGraph:
        return cls(
            peripherals=load_svd_peripherals(),
            pin_functions=load_pin_functions(),
            clock_topology=load_clock_topology(),
            errata=load_errata(),
            wokwi_components=load_wokwi_components(),
        )

    def _build_graph(self) -> nx.DiGraph:
        g: nx.DiGraph = nx.DiGraph()

        for pe in self._peripherals.values():
            g.add_node(f"peripheral:{pe.name}", kind=NODE_PERIPHERAL, name=pe.name, base_address=pe.base_address)
            for reg in pe.registers.values():
                reg_node = f"register:{pe.name}.{reg.name}"
                g.add_node(reg_node, kind=NODE_REGISTER, peripheral=pe.name, name=reg.name, address=reg.address, reset_value=reg.reset_value)
                g.add_edge(f"peripheral:{pe.name}", reg_node, kind="has_register")
                for fld in reg.fields.values():
                    f_node = f"field:{pe.name}.{reg.name}.{fld.name}"
                    g.add_node(f_node, kind=NODE_FIELD, peripheral=pe.name, register=reg.name, name=fld.name, bit_offset=fld.bit_offset, bit_width=fld.bit_width, reset_value=fld.reset_value)
                    g.add_edge(reg_node, f_node, kind="has_field")

        for pin_number, funcs in self._pin_functions.items():
            pin_node = f"pin:{pin_number}"
            g.add_node(pin_node, kind=NODE_PIN, pin_number=pin_number, functions=funcs)
            for family, func_label in funcs.items():
                if family == "reserved_for" or not isinstance(func_label, str):
                    continue
                instance_name = _instance_from_function_label(family, func_label)
                if instance_name and f"peripheral:{instance_name}" in g:
                    g.add_edge(pin_node, f"peripheral:{instance_name}", kind="mux_to", function=func_label)

        for node in self._clock_topology["nodes"]:
            g.add_node(f"clock:{node['id']}", kind=NODE_CLOCK, data=node)
        for edge in self._clock_topology["edges"]:
            g.add_edge(f"clock:{edge['source']}", f"clock:{edge['target']}", kind=edge["kind"])

        for erratum in self._errata:
            g.add_node(f"erratum:{erratum['id']}", kind=NODE_ERRATUM, data=erratum)

        for name, data in self._wokwi_components.items():
            g.add_node(f"wokwi:{name}", kind=NODE_WOKWI, name=name, data=data)

        return g

    @property
    def nx(self) -> nx.DiGraph:
        return self._g

    def get_peripheral_pins(self, peripheral: str, instance: int) -> dict[str, list[int]]:
        """Return a map of logical signal (SDA/SCL/TX/RX/...) to allocatable GP numbers.

        'Allocatable' means the pin is exposed on the Pico board and not marked
        `reserved_for` in pin_functions.json. Pins with secondary roles (e.g. ADC)
        remain allocatable — the caller decides whether to use them.
        """
        target_instance = f"{peripheral.upper()}{instance}"
        by_signal: dict[str, list[int]] = {}

        for pin_number, funcs in sorted(self._pin_functions.items()):
            if funcs.get("reserved_for"):
                continue
            func_label = funcs.get(peripheral.upper())
            if not isinstance(func_label, str):
                continue
            resolved = _instance_from_function_label(peripheral.upper(), func_label)
            if resolved != target_instance:
                continue
            signal = _signal_from_function_label(peripheral.upper(), func_label)
            if signal is None:
                continue
            by_signal.setdefault(signal, []).append(pin_number)

        return by_signal

    def get_clock_sources(self, domain: str) -> list[str]:
        """Return upstream clock node IDs that can feed `domain` (e.g. CLK_SYS)."""
        node = f"clock:{domain.upper()}"
        if node not in self._g:
            return []
        return sorted(
            pred.split(":", 1)[1]
            for pred in self._g.predecessors(node)
            if self._g.nodes[pred]["kind"] == NODE_CLOCK
        )

    def check_pin_conflicts(self, assignments: Iterable[PinAssignment]) -> None:
        """Raise PinConflictError if two assignments target the same pin."""
        seen: dict[int, str] = {}
        for a in assignments:
            if a.pin_number in seen and seen[a.pin_number] != a.function:
                raise PinConflictError(
                    f"GP{a.pin_number} is assigned to both {seen[a.pin_number]!r} and {a.function!r}"
                )
            seen[a.pin_number] = a.function

    def get_register(self, peripheral: str, register: str) -> dict[str, Any]:
        """Resolve a (peripheral, register) pair to its authoritative address and fields.

        Lookup is case-insensitive: the LLM occasionally emits lowercased names
        (e.g. ``"pwm"`` vs SVD's ``"PWM"``). True typos (made-up names) still
        raise — this remains the tripwire that prevents the LLM from inventing
        addresses.
        """
        pe = self._peripherals.get(peripheral) or self._peripherals.get(peripheral.upper())
        if pe is None:
            raise UnknownPeripheralError(f"Unknown peripheral instance {peripheral!r}")
        reg = pe.registers.get(register) or pe.registers.get(register.upper())
        if reg is None:
            raise UnknownRegisterError(f"{peripheral}.{register} not in SVD")
        return {
            "address": reg.address,
            "offset": reg.offset,
            "reset_value": reg.reset_value,
            "size_bits": reg.size_bits,
            "fields": {
                name: {
                    "offset": f.bit_offset,
                    "width": f.bit_width,
                    "reset_value": f.reset_value,
                    "description": f.description,
                }
                for name, f in reg.fields.items()
            },
        }

    def get_field(self, peripheral: str, register: str, field_name: str) -> dict[str, Any]:
        reg = self.get_register(peripheral, register)
        if field_name in reg["fields"]:
            return reg["fields"][field_name]
        # Case-insensitive field lookup (LLM casing slip).
        upper = field_name.upper()
        for k, v in reg["fields"].items():
            if k.upper() == upper:
                return v
        raise UnknownRegisterError(f"{peripheral}.{register}.{field_name} not in SVD")

    def list_peripherals(self, family: str | None = None) -> list[str]:
        if family is None:
            return sorted(self._peripherals.keys())
        prefix = family.upper()
        return sorted(n for n in self._peripherals if n.startswith(prefix))

    def get_errata_by_trigger(self, triggers: Iterable[str]) -> list[dict]:
        matches: list[dict] = []
        needles = {t.upper() for t in triggers}
        for erratum in self._errata:
            entry_triggers = {t.upper() for t in erratum.get("triggers", [])}
            if entry_triggers & needles:
                matches.append(erratum)
        return matches

    def get_wokwi_component(self, name: str) -> dict | None:
        return self._wokwi_components.get(name)

    def svd_summary(
        self,
        peripherals: Iterable[str] | None = None,
        max_registers_per_peripheral: int = 6,
    ) -> str:
        """Render a compact text summary of the SVD used as cached agent context.

        If `peripherals` is provided, only those peripheral names (e.g. {"I2C0",
        "I2C1", "CLOCKS"}) are emitted. Unknown names are silently skipped.
        """
        if peripherals is None:
            names = sorted(self._peripherals)
        else:
            wanted = {p.upper() for p in peripherals}
            names = [n for n in sorted(self._peripherals) if n in wanted]
        lines: list[str] = ["# RP2040 peripheral summary (from SVD)"]
        for name in names:
            pe = self._peripherals[name]
            lines.append(f"\n## {name} @ 0x{pe.base_address:08x}")
            regs = list(pe.registers.values())[:max_registers_per_peripheral]
            for reg in regs:
                lines.append(f"  - {reg.name} (+0x{reg.offset:04x}, reset=0x{reg.reset_value:x})")
                for fld in list(reg.fields.values())[:6]:
                    lines.append(
                        f"      · {fld.name} [{fld.bit_offset + fld.bit_width - 1}:{fld.bit_offset}] reset={fld.reset_value}"
                    )
            if len(pe.registers) > max_registers_per_peripheral:
                lines.append(f"  - ... and {len(pe.registers) - max_registers_per_peripheral} more registers")
        return "\n".join(lines)


@lru_cache(maxsize=1)
def get_graph() -> RPGraph:
    return RPGraph.load()


_I2C_SIGNALS = {"SDA", "SCL"}
_SPI_SIGNALS = {"RX", "TX", "SCK", "CSn"}
_UART_SIGNALS = {"TX", "RX", "CTS", "RTS"}
_PWM_SIGNALS = {"A", "B"}


def _instance_from_function_label(family: str, label: str) -> str | None:
    """Turn 'I2C0_SDA' into 'I2C0'; 'PWM2_A' into 'PWM2'."""
    if "_" not in label:
        return label if label.startswith(family) else None
    return label.split("_", 1)[0]


def _signal_from_function_label(family: str, label: str) -> str | None:
    if "_" not in label:
        return None
    instance, signal = label.split("_", 1)
    if family == "I2C" and signal in _I2C_SIGNALS:
        return signal
    if family == "SPI" and signal in _SPI_SIGNALS:
        return signal
    if family == "UART" and signal in _UART_SIGNALS:
        return signal
    if family == "PWM" and signal in _PWM_SIGNALS:
        return signal
    return signal
