"""MCU profile registry.

The pipeline orchestration (planner / agents / metrics, all in ``app.graph``)
is chip-agnostic; everything chip-specific lives in a ``McuProfile``. Adding an
MCU is "drop ``knowledge_data/<mcu>.svd`` (+ optional vendor_docs/<mcu>.md),
define a profile, register it, rebuild the RAG index" — no pipeline edits.
"""

from .profile import McuProfile, get_profile, list_profiles, register_profile  # noqa: F401
from .esp32 import ESP32_PROFILE  # noqa: F401  (each module registers itself on import)
from .rp2040 import RP2040_PROFILE  # noqa: F401
from .stm32f103 import STM32F103_PROFILE  # noqa: F401
