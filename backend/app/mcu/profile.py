"""MCU profile Protocol + small registry.

A profile bundles everything the pipeline needs that is chip-specific:
- supported peripheral families (used by supervisor + pinout)
- prompt fragments injected into agent system messages
- a default clock plan (used as a fallback / sanity reference)
- the build runner (compiles a generated project into a flashable artifact)
- the simulator runner (live or fixture)
- a knowledge-graph handle for SVD/pin lookups

Concrete profiles register themselves at import time.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.build.compiler import BuildResult
    from app.schemas.state import GeneratedFile


@dataclass(frozen=True)
class ClockPlanHint:
    """Default clock setup the profile suggests when prompts don't override."""

    description: str
    rows: list[dict[str, Any]] = field(default_factory=list)


class McuProfile(Protocol):
    """Everything chip-specific the pipeline orchestration needs."""

    name: str
    """Stable key, e.g. ``"rp2040"`` — used in DesignState.target_mcu."""

    display_name: str
    """Human label, e.g. ``"Raspberry Pi RP2040"``."""

    supported_peripheral_families: tuple[str, ...]
    """Used by the supervisor when classifying prompts."""

    valid_pin_label: str
    """Short hint for prompts: e.g. ``"GPIO numbers GP0..GP28"``."""

    # ----- Knowledge / prompt fragments -------------------------------------
    def svd_summary(self, peripheral_family: str | None = None) -> str:
        """Compact register summary the agents include in their system prompt."""

    def pinout_options(self, peripheral_family: str, instance_idx: int) -> dict[str, list[int]]:
        """Map signal -> candidate pin numbers for one instance of the family."""

    def list_peripheral_instances(self, peripheral_family: str) -> list[str]:
        """E.g. ``["I2C0", "I2C1"]``."""

    def default_clock_hint(self) -> ClockPlanHint:
        """Reasonable bring-up clock plan baked into the clock_configurator prompt."""

    def code_composer_system_prompt(self) -> str:
        """Chip-specific rules for the code generator (SDK, headers, idioms)."""

    # ----- Build / simulate -------------------------------------------------
    build_firmware: Callable[..., "Awaitable[BuildResult]"]
    """``async (files: list[GeneratedFile], project_dir: Path | None = None) -> BuildResult``."""

    run_simulation: Callable[..., Any]
    """``async (uf2_path, diagram_json, timeout_s) -> SimulationResult``."""

    # ----- Wokwi mapping ---------------------------------------------------
    def wokwi_part_for(self, device_name: str) -> dict[str, Any] | None:
        """Best-effort lookup; returns ``None`` if no part is known."""


_REGISTRY: dict[str, McuProfile] = {}


def register_profile(profile: McuProfile) -> None:
    _REGISTRY[profile.name] = profile


def get_profile(name: str) -> McuProfile:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown MCU profile {name!r}. Registered: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def list_profiles() -> list[str]:
    return sorted(_REGISTRY)