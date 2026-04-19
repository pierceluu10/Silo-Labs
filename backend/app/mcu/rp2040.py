"""Raspberry Pi RP2040 profile.

Wraps the existing ``app.knowledge.graph`` + ``app.build.compiler`` +
``app.simulate.runner`` so they live behind the McuProfile interface. No
behaviour change for existing prompts.
"""

from __future__ import annotations

from typing import Any

from app.agents._common import svd_system_context
from app.build.compiler import build_firmware as _build_firmware_rp2040
from app.knowledge.graph import get_graph
from app.simulate.runner import run_simulation as _run_simulation_rp2040

from .profile import ClockPlanHint, McuProfile, register_profile


_PRIMARY_FAMILIES: tuple[str, ...] = ("I2C", "SPI", "UART", "PWM", "ADC", "GPIO")


_DEFAULT_CLOCK_ROWS: list[dict[str, Any]] = [
    {"clock_domain": "XOSC", "source": "XOSC", "freq_hz": 12_000_000, "divider": 1.0},
    {
        "clock_domain": "PLL_SYS",
        "source": "XOSC",
        "freq_hz": 125_000_000,
        "divider": 1.0,
        "pll_vco_freq_hz": 1_500_000_000,
    },
    {"clock_domain": "CLK_SYS", "source": "PLL_SYS", "freq_hz": 125_000_000, "divider": 1.0},
    {"clock_domain": "CLK_PERI", "source": "CLK_SYS", "freq_hz": 125_000_000, "divider": 1.0},
    {"clock_domain": "CLK_REF", "source": "XOSC", "freq_hz": 12_000_000, "divider": 1.0},
]


_CODE_COMPOSER_SYSTEM = """\
Target chip: Raspberry Pi RP2040 (Cortex-M0+ dual core).

Use the pico-sdk high-level APIs and idioms:
  - Includes: pico/stdlib.h, hardware/<peripheral>.h
  - Initialise stdio via pico_enable_stdio_usb so printf reaches USB serial in Wokwi.
  - Pin configuration via gpio_set_function / i2c_init / spi_init / etc.
  - main() runs forever with a sleep_ms cadence — printf any periodic readings.

Project layout: a single main.c plus any required driver source files. The
build wrapper supplies cmake_minimum_required, project(), pico_sdk_init().
You only emit the project-specific lines (add_executable, target_link_libraries,
pico_enable_stdio_usb, pico_add_extra_outputs) in CMakeLists.txt.
"""


class _Rp2040Profile:
    name = "rp2040"
    display_name = "Raspberry Pi RP2040"
    supported_peripheral_families = _PRIMARY_FAMILIES
    valid_pin_label = "GPIO numbers GP0..GP28 (avoid GP0/GP1; reserved for UART0 debug)"

    # Build + simulate are the existing async functions, lifted as attributes.
    build_firmware = staticmethod(_build_firmware_rp2040)
    run_simulation = staticmethod(_run_simulation_rp2040)

    def svd_summary(self, peripheral_family: str | None = None) -> str:
        return svd_system_context(peripheral_family)

    def pinout_options(self, peripheral_family: str, instance_idx: int) -> dict[str, list[int]]:
        return get_graph().get_peripheral_pins(peripheral_family, instance_idx)

    def list_peripheral_instances(self, peripheral_family: str) -> list[str]:
        return get_graph().list_peripherals(peripheral_family)

    def default_clock_hint(self) -> ClockPlanHint:
        return ClockPlanHint(
            description="125 MHz bring-up: XOSC -> PLL_SYS -> CLK_SYS / CLK_PERI; CLK_REF from XOSC",
            rows=_DEFAULT_CLOCK_ROWS,
        )

    def code_composer_system_prompt(self) -> str:
        return _CODE_COMPOSER_SYSTEM

    def wokwi_part_for(self, device_name: str) -> dict[str, Any] | None:
        return get_graph().get_wokwi_component(device_name.lower())


RP2040_PROFILE: McuProfile = _Rp2040Profile()  # type: ignore[assignment]
register_profile(RP2040_PROFILE)