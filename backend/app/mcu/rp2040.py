"""Raspberry Pi RP2040 profile — the only target with a real build (pico-sdk + arm-gcc)."""

from __future__ import annotations

from typing import Any

from app.build.compiler import build_firmware
from app.schemas.tools import ClockSource

from .profile import ClockPlanHint, McuProfile, register_profile

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

_CODE_COMPOSER_PROMPT = """\
Target chip: Raspberry Pi RP2040 (Cortex-M0+ dual core) on a Raspberry Pi Pico.

Use the pico-sdk high-level APIs and idioms:
  - Includes: pico/stdlib.h, hardware/<peripheral>.h
  - Initialise stdio via pico_enable_stdio_usb so printf reaches USB serial in Wokwi.
  - Pin configuration via gpio_set_function / i2c_init / spi_init / etc.
  - main() runs forever with a sleep_ms cadence — printf any periodic readings.

Required files: "main.c" and "CMakeLists.txt".

CMakeLists.txt rules — emit ONLY the project-specific lines below; nothing else:
  add_executable(firmware main.c drivers/foo.c ...)   # list every .c you ship
  target_link_libraries(firmware pico_stdlib hardware_i2c ...)  # only what you use
  pico_enable_stdio_usb(firmware 1)
  pico_enable_stdio_uart(firmware 0)
  pico_add_extra_outputs(firmware)
  # PIO programs need pico_generate_pio_header(firmware ${CMAKE_CURRENT_LIST_DIR}/foo.pio)

STRICTLY FORBIDDEN in CMakeLists.txt content:
- cmake_minimum_required(...)        — the wrapper sets it.
- project(...)                       — the wrapper sets it.
- include(pico_sdk_import.cmake)     — the wrapper adds it.
- pico_sdk_init()                    — the wrapper calls it.
- find_package(...)                  — pico-sdk libraries link by name.
- set(PICO_SDK_PATH ...) / set(PICO_BOARD ...)
"""

_PERIPHERAL_EXAMPLE = """\
For I2C master mode (e.g. BME280 at 400 kHz on I2C0):
  - RESETS.RESET clear bit for I2C0
  - I2C0.IC_ENABLE.ENABLE = 0   (disable before configuring)
  - I2C0.IC_CON.SPEED = 2       (fast mode)
  - I2C0.IC_CON.MASTER_MODE = 1
  - I2C0.IC_CON.IC_SLAVE_DISABLE = 1
  - I2C0.IC_CON.IC_RESTART_EN = 1
  - I2C0.IC_SS_SCL_HCNT / IC_SS_SCL_LCNT for timing
  - I2C0.IC_ENABLE.ENABLE = 1
"""

RP2040_PROFILE = McuProfile(
    name="rp2040",
    display_name="Raspberry Pi RP2040",
    board_name="Raspberry Pi Pico",
    board_part="pico",
    supported_peripheral_families=("I2C", "SPI", "UART", "PWM", "ADC", "GPIO"),
    valid_pin_label="pin_number is the GPIO number GP0..GP28 (avoid GP0/GP1; reserved for UART0 debug)",
    gpio_count=30,
    pin_name=lambda n: f"GP{n}",
    core_peripherals=("CLOCKS", "PLL_SYS", "PLL_USB", "XOSC", "ROSC", "RESETS", "IO_BANK0", "PADS_BANK0", "SIO"),
    clock_domains=tuple(c.value for c in ClockSource),
    clock_hint=ClockPlanHint(
        description="125 MHz bring-up: XOSC -> PLL_SYS -> CLK_SYS / CLK_PERI; CLK_REF from XOSC",
        rows=_DEFAULT_CLOCK_ROWS,
    ),
    sdk_label="pico-sdk",
    code_composer_prompt=_CODE_COMPOSER_PROMPT,
    peripheral_example=_PERIPHERAL_EXAMPLE,
    build_firmware=build_firmware,
)
register_profile(RP2040_PROFILE)
