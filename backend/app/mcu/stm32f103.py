"""STMicro STM32F103C8 (Blue Pill) profile — bare-metal CMSIS, code emitted without a build."""

from __future__ import annotations

from typing import Any

from .profile import ClockPlanHint, McuProfile, register_profile

PORT_SIZE = 16
PORT_LETTERS = "ABC"

_DEFAULT_CLOCK_ROWS: list[dict[str, Any]] = [
    {"clock_domain": "HSE", "source": "HSE", "freq_hz": 8_000_000, "divider": 1.0},
    {"clock_domain": "PLL", "source": "HSE", "freq_hz": 72_000_000, "divider": 1.0, "pll_vco_freq_hz": 72_000_000},
    {"clock_domain": "SYSCLK", "source": "PLL", "freq_hz": 72_000_000, "divider": 1.0},
    {"clock_domain": "HCLK", "source": "SYSCLK", "freq_hz": 72_000_000, "divider": 1.0},
    {"clock_domain": "PCLK1", "source": "HCLK", "freq_hz": 36_000_000, "divider": 2.0},
    {"clock_domain": "PCLK2", "source": "HCLK", "freq_hz": 72_000_000, "divider": 1.0},
]

_CODE_COMPOSER_PROMPT = """\
Target chip: STMicro STM32F103C8 (Cortex-M3, 72 MHz) on a Blue Pill board.

Write bare-metal C against the CMSIS device header "stm32f1xx.h":
  - Clock bring-up: HSE 8 MHz -> PLL x9 -> 72 MHz SYSCLK, FLASH_ACR.LATENCY=2, APB1 /2.
  - Enable every peripheral and GPIO port clock in RCC->APB1ENR / RCC->APB2ENR before use.
  - Configure pins through GPIOx->CRL / CRH with read-modify-write (never clobber other pins).
  - Retarget printf by implementing _write() over USART1 (PA9 TX, 115200 baud).
  - A SysTick 1 ms tick provides delay_ms(); main() loops forever printing readings.

Required files: "main.c" and "CMakeLists.txt". CMakeLists.txt is a complete standalone
project for arm-none-eabi-gcc (-mcpu=cortex-m3 -mthumb), compiling main.c, any drivers,
startup_stm32f103xb.s, and linking with STM32F103C8Tx_FLASH.ld; it produces firmware.elf
and firmware.bin.
"""

_PERIPHERAL_EXAMPLE = """\
For I2C master mode (e.g. BME280 at 400 kHz on I2C1, PB6/PB7):
  - RCC.APB1ENR.I2C1EN = 1, RCC.APB2ENR.IOPBEN = 1
  - I2C1.CR1.PE = 0            (disable before configuring)
  - I2C1.CR2.FREQ = 36         (APB1 MHz)
  - I2C1.CCR.F_S = 1, I2C1.CCR.CCR = 30
  - I2C1.TRISE.TRISE = 11
  - I2C1.CR1.PE = 1
"""


def _pin_name(n: int) -> str:
    return f"P{PORT_LETTERS[n // PORT_SIZE]}{n % PORT_SIZE}"


STM32F103_PROFILE = McuProfile(
    name="stm32f103",
    display_name="STMicro STM32F103C8",
    board_name="Blue Pill",
    board_part="bluepill",
    supported_peripheral_families=("I2C", "SPI", "USART", "TIM", "ADC", "GPIO"),
    valid_pin_label=(
        "pin_number = port_index*16 + pin, ports A=0 B=1 C=2 (PA9=9, PB6=22, PB7=23, PC13=45); "
        "avoid PA13/PA14 (SWD) and PA9/PA10 (USART1 console)"
    ),
    gpio_count=len(PORT_LETTERS) * PORT_SIZE,
    pin_name=_pin_name,
    core_peripherals=("RCC", "FLASH", "AFIO", "GPIOA", "GPIOB", "GPIOC"),
    clock_domains=("HSI", "HSE", "PLL", "SYSCLK", "HCLK", "PCLK1", "PCLK2", "ADCCLK", "LSI", "LSE"),
    clock_hint=ClockPlanHint(
        description="72 MHz bring-up: HSE 8 MHz -> PLL x9 -> SYSCLK; APB1 36 MHz, APB2 72 MHz",
        rows=_DEFAULT_CLOCK_ROWS,
    ),
    sdk_label="CMSIS bare-metal",
    code_composer_prompt=_CODE_COMPOSER_PROMPT,
    peripheral_example=_PERIPHERAL_EXAMPLE,
    build_firmware=None,
)
register_profile(STM32F103_PROFILE)
