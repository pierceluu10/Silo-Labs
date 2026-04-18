from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import get_settings
from app.schemas.state import Requirements

SYSTEM_PROMPT = """You are the Requirements Parser for an RP2040 firmware generator.

Your job: read a user's natural-language firmware request and extract a structured Requirements object.

Rules:
- peripheral_type must be one of: I2C, SPI, UART, PWM, ADC, GPIO
- device_name is the primary external part (e.g. "BME280", "SSD1306", "DS18B20", "MPU6050"). If multiple devices are mentioned, choose the sensor/input device as primary.
- device_address is the I2C address as a 0x-prefixed hex string if the device uses I2C and a standard address is known (BME280=0x76, SSD1306=0x3C, MPU6050=0x68, HD44780=0x27). Omit for non-I2C peripherals.
- baud_rate applies to UART only; omit otherwise.
- description is a single concise sentence describing what the firmware should do.

Never invent peripherals or devices not mentioned. If the user says "I2C" without a specific part, set device_name to "generic".
"""


def build_parser() -> ChatAnthropic:
    settings = get_settings()
    llm = ChatAnthropic(
        model=settings.haiku_model,
        api_key=settings.anthropic_api_key,
        max_tokens=512,
        temperature=0,
    )
    return llm.with_structured_output(Requirements)


async def parse_requirements(user_prompt: str) -> Requirements:
    parser = build_parser()
    result = await parser.ainvoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
    )
    if not isinstance(result, Requirements):
        result = Requirements.model_validate(result)
    return result
