from __future__ import annotations

import os

import pytest

from app.agents.requirements_parser import parse_requirements
from app.schemas.state import Requirements


needs_api_key = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping live API test",
)


@needs_api_key
@pytest.mark.asyncio
async def test_requirements_parser_bme280_ssd1306() -> None:
    req = await parse_requirements(
        "Read a BME280 temperature sensor over I2C and display the readings on an SSD1306 OLED."
    )
    assert isinstance(req, Requirements)
    assert req.peripheral_type.upper() == "I2C"
    assert req.device_name.upper().startswith("BME")
    assert req.device_address in ("0x76", "0x77")
    assert len(req.description) > 10
