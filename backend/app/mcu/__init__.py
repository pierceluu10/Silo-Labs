"""MCU profile abstraction.

The pipeline used to assume RP2040 directly: Pico SDK calls hardcoded into
prompts, "GP4 / GP5 / 125 MHz" baked into reasoning text, build runner that
shelled out to cmake + arm-none-eabi-gcc no matter what.

This package separates the orchestration (planner / agents / metrics, all in
``app.graph``) from chip-specific knowledge. Adding a new MCU is
"implement ``McuProfile`` and register it" — no edits to the pipeline.
"""

from .profile import McuProfile, get_profile, list_profiles, register_profile  # noqa: F401
from .rp2040 import RP2040_PROFILE  # noqa: F401  (registers itself on import)