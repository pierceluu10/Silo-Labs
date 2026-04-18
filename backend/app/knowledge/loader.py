from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from cmsis_svd.parser import SVDParser

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge_data"
SVD_PATH = KNOWLEDGE_DIR / "rp2040.svd"
PIN_FUNCTIONS_PATH = KNOWLEDGE_DIR / "pin_functions.json"
CLOCK_TOPOLOGY_PATH = KNOWLEDGE_DIR / "clock_topology.json"
ERRATA_PATH = KNOWLEDGE_DIR / "errata.json"
WOKWI_COMPONENTS_PATH = KNOWLEDGE_DIR / "wokwi_components.json"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    bit_offset: int
    bit_width: int
    reset_value: int
    description: str = ""


@dataclass(frozen=True)
class RegisterSpec:
    name: str
    offset: int
    address: int
    reset_value: int
    size_bits: int
    description: str = ""
    fields: dict[str, FieldSpec] = field(default_factory=dict)


@dataclass(frozen=True)
class PeripheralSpec:
    name: str
    base_address: int
    description: str = ""
    registers: dict[str, RegisterSpec] = field(default_factory=dict)


def _slice_reset(register_reset: int, bit_offset: int, bit_width: int) -> int:
    mask = (1 << bit_width) - 1
    return (register_reset >> bit_offset) & mask


def load_svd_peripherals(svd_path: Path = SVD_PATH) -> dict[str, PeripheralSpec]:
    parser = SVDParser.for_xml_file(str(svd_path))
    device = parser.get_device()

    peripherals: dict[str, PeripheralSpec] = {}
    for pe in device.peripherals:
        registers: dict[str, RegisterSpec] = {}
        for reg in (pe.registers or []):
            reset = reg.reset_value or 0
            fields: dict[str, FieldSpec] = {}
            for f in reg.fields or []:
                fields[f.name] = FieldSpec(
                    name=f.name,
                    bit_offset=f.bit_offset,
                    bit_width=f.bit_width,
                    reset_value=_slice_reset(reset, f.bit_offset, f.bit_width),
                    description=(f.description or "").strip(),
                )
            registers[reg.name] = RegisterSpec(
                name=reg.name,
                offset=reg.address_offset,
                address=pe.base_address + reg.address_offset,
                reset_value=reset,
                size_bits=reg.size or 32,
                description=(reg.description or "").strip(),
                fields=fields,
            )
        peripherals[pe.name] = PeripheralSpec(
            name=pe.name,
            base_address=pe.base_address,
            description=(pe.description or "").strip(),
            registers=registers,
        )
    return peripherals


def load_pin_functions(path: Path = PIN_FUNCTIONS_PATH) -> dict[int, dict[str, str | list[str]]]:
    raw = json.loads(path.read_text())
    out: dict[int, dict[str, str | list[str]]] = {}
    for pin_str, funcs in raw["pins"].items():
        out[int(pin_str)] = funcs
    return out


def load_clock_topology(path: Path = CLOCK_TOPOLOGY_PATH) -> dict:
    return json.loads(path.read_text())


def load_errata(path: Path = ERRATA_PATH) -> list[dict]:
    return json.loads(path.read_text())["errata"]


def load_wokwi_components(path: Path = WOKWI_COMPONENTS_PATH) -> dict[str, dict]:
    return json.loads(path.read_text())["components"]
