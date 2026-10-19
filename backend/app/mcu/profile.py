"""MCU profile + small registry.

A profile bundles everything the pipeline needs that is chip-specific:
- supported peripheral families (used by supervisor + pinout)
- pin naming / numbering and the Wokwi board part
- prompt fragments injected into agent system messages
- a default clock plan (used as a fallback / sanity reference)
- the build runner, or ``None`` when no toolchain ships for this chip

Register/pin facts come from the per-MCU knowledge graph (SVD) and the
ChromaDB RAG index; profiles only carry what neither source can provide.
Concrete profiles register themselves at import time.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from app.knowledge.graph import get_graph
from app.knowledge.rag import grounding_context

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.build.compiler import BuildResult

MAX_REGISTERS_PER_PERIPHERAL = 6


@dataclass(frozen=True)
class ClockPlanHint:
    """Default clock setup the profile suggests when prompts don't override."""

    description: str
    rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, eq=False)
class McuProfile:
    name: str
    """Stable key, e.g. ``"rp2040"`` — used in DesignState.target_mcu and as the SVD file stem."""

    display_name: str
    board_name: str
    """Board the simulator runs, e.g. ``"Raspberry Pi Pico"``."""

    board_part: str
    """Key into wokwi_components.json; also the board's id in diagram.json."""

    supported_peripheral_families: tuple[str, ...]
    valid_pin_label: str
    """Short hint for prompts explaining pin numbering and reserved pins."""

    gpio_count: int
    pin_name: Callable[[int], str]
    core_peripherals: tuple[str, ...]
    """SVD peripherals every agent needs regardless of feature (clocks, resets, GPIO mux)."""

    clock_domains: tuple[str, ...]
    clock_hint: ClockPlanHint
    sdk_label: str
    """Firmware framework, e.g. ``"pico-sdk"`` or ``"ESP-IDF"``."""

    code_composer_prompt: str
    peripheral_example: str
    build_firmware: Callable[..., Awaitable[BuildResult]] | None
    """``async (files) -> BuildResult``; ``None`` means the code is emitted but not compiled."""

    def svd_summary(self, peripheral_family: str | None = None) -> str:
        return _svd_summary(self.name, self.core_peripherals, peripheral_family)

    def grounding(self, query: str) -> str:
        """RAG context: register specs + vendor docs most relevant to ``query``."""
        return grounding_context(query, self.name)

    def pinout_options(self, peripheral_family: str) -> dict[str, dict[str, list[int]]]:
        """Instance -> signal -> candidate pins, where the pin mux is hand-modeled."""
        graph = get_graph(self.name)
        family = peripheral_family.upper()
        options: dict[str, dict[str, list[int]]] = {}
        for inst in graph.list_peripherals(family):
            idx = inst[len(family):]
            if idx.isdigit() and (pins := graph.get_peripheral_pins(family, int(idx))):
                options[inst] = pins
        return options

    def wokwi_part_for(self, device_name: str) -> dict[str, Any] | None:
        return get_graph(self.name).get_wokwi_component(device_name.lower())


@lru_cache(maxsize=64)
def _svd_summary(mcu: str, core: tuple[str, ...], peripheral_family: str | None) -> str:
    """Compact SVD summary scoped to the feature's family plus the core peripherals.

    Scoping keeps Sonnet input tokens under the per-minute rate limit.
    """
    graph = get_graph(mcu)
    if not peripheral_family:
        return graph.svd_summary(max_registers_per_peripheral=MAX_REGISTERS_PER_PERIPHERAL)
    instances = graph.list_peripherals(peripheral_family.strip())
    return graph.svd_summary(
        peripherals=set(core) | set(instances),
        max_registers_per_peripheral=MAX_REGISTERS_PER_PERIPHERAL,
    )


_REGISTRY: dict[str, McuProfile] = {}


def register_profile(profile: McuProfile) -> None:
    _REGISTRY[profile.name] = profile


def get_profile(name: str) -> McuProfile:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown MCU profile {name!r}. Registered: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def list_profiles() -> list[str]:
    return sorted(_REGISTRY)
