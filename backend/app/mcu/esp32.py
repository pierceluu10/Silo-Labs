"""Espressif ESP32 (DevKitC) profile — ESP-IDF project, code emitted without a build."""

from __future__ import annotations

from typing import Any

from .profile import ClockPlanHint, McuProfile, register_profile

_DEFAULT_CLOCK_ROWS: list[dict[str, Any]] = [
    {"clock_domain": "XTAL", "source": "XTAL", "freq_hz": 40_000_000, "divider": 1.0},
    {"clock_domain": "PLL", "source": "XTAL", "freq_hz": 240_000_000, "divider": 1.0, "pll_vco_freq_hz": 480_000_000},
    {"clock_domain": "CPU_CLK", "source": "PLL", "freq_hz": 240_000_000, "divider": 1.0},
    {"clock_domain": "APB_CLK", "source": "PLL", "freq_hz": 80_000_000, "divider": 1.0},
]

_CODE_COMPOSER_PROMPT = """\
Target chip: Espressif ESP32 (dual-core Xtensa LX6, 240 MHz) on an ESP32 DevKitC V4.

Write an ESP-IDF v5 project in C:
  - Entry point is void app_main(void) in "main/main.c".
  - Use ESP-IDF drivers (driver/gpio.h, driver/i2c_master.h, driver/ledc.h, esp_adc/adc_oneshot.h).
  - Delays via vTaskDelay(pdMS_TO_TICKS(ms)); microsecond waits via esp_rom_delay_us.
  - printf goes to the UART0 console at 115200 baud; app_main loops forever printing readings.

Required files:
  - "CMakeLists.txt": cmake_minimum_required(VERSION 3.16),
    include($ENV{IDF_PATH}/tools/cmake/project.cmake), project(firmware)
  - "main/CMakeLists.txt": idf_component_register(SRCS "main.c" ... INCLUDE_DIRS ".")
  - "main/main.c"
"""

_PERIPHERAL_EXAMPLE = """\
Most ESP32 bring-up goes through ESP-IDF drivers, so direct register writes are usually
unnecessary. Emit writes only for settings the drivers do not expose, e.g. routing a signal
with GPIO.FUNC<n>_OUT_SEL_CFG or IO_MUX pad configuration. An empty list is acceptable.
"""

ESP32_PROFILE = McuProfile(
    name="esp32",
    display_name="Espressif ESP32",
    board_name="ESP32 DevKitC V4",
    board_part="esp32-devkit",
    supported_peripheral_families=("I2C", "SPI", "UART", "LEDC", "ADC", "RMT", "GPIO"),
    valid_pin_label=(
        "pin_number is the GPIO number 0..39; never use GPIO6..11 (flash), "
        "GPIO34..39 are input-only, avoid strapping pins 0/2/5/12/15 and GPIO1/3 (console)"
    ),
    gpio_count=40,
    pin_name=lambda n: f"GPIO{n}",
    core_peripherals=("DPORT", "IO_MUX", "GPIO", "RTC_CNTL"),
    clock_domains=("XTAL", "PLL", "CPU_CLK", "APB_CLK", "RTC_SLOW_CLK", "RTC_FAST_CLK", "REF_TICK"),
    clock_hint=ClockPlanHint(
        description="240 MHz bring-up: 40 MHz XTAL -> PLL 480 MHz -> CPU 240 MHz; APB 80 MHz",
        rows=_DEFAULT_CLOCK_ROWS,
    ),
    sdk_label="ESP-IDF",
    code_composer_prompt=_CODE_COMPOSER_PROMPT,
    peripheral_example=_PERIPHERAL_EXAMPLE,
    build_firmware=None,
)
register_profile(ESP32_PROFILE)
