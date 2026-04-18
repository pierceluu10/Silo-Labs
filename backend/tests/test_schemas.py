from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from app.knowledge.graph import UnknownPeripheralError, UnknownRegisterError
from app.schemas.events import SSEEvent
from app.schemas.state import DesignState, Requirements
from app.schemas.tools import (
    AddWire,
    AssignPin,
    ClockSource,
    ConfigureClock,
    PinFunction,
    SetRegister,
    WireColor,
)


def test_assign_pin_rejects_out_of_range_gpio() -> None:
    with pytest.raises(ValidationError):
        AssignPin(
            pin_number=30,
            function=PinFunction.I2C_SDA,
            peripheral_instance="I2C0",
            label="SDA",
            wire_color="#e6c84a",
        )


def test_assign_pin_rejects_invalid_color() -> None:
    with pytest.raises(ValidationError):
        AssignPin(
            pin_number=4,
            function=PinFunction.I2C_SDA,
            peripheral_instance="I2C0",
            label="SDA",
            wire_color="yellow",
        )


def test_configure_clock_pll_requires_vco() -> None:
    with pytest.raises(ValidationError):
        ConfigureClock(
            clock_domain=ClockSource.CLK_SYS,
            source=ClockSource.PLL_SYS,
            freq_hz=125_000_000,
            divider=1.0,
        )


def test_configure_clock_non_pll_does_not_require_vco() -> None:
    cfg = ConfigureClock(
        clock_domain=ClockSource.CLK_REF,
        source=ClockSource.XOSC,
        freq_hz=12_000_000,
        divider=1.0,
    )
    assert cfg.pll_vco_freq_hz is None


def test_set_register_resolves_address_from_svd() -> None:
    sr = SetRegister(
        peripheral="I2C0",
        register="IC_CON",
        field_name="SPEED",
        value=2,
        bit_offset=0,
        bit_width=0,
        human_explanation="Fast mode (400kHz) per I2C-bus spec",
    )
    assert sr.address == 0x40044000
    assert sr.bit_offset == 1
    assert sr.bit_width == 2


def test_set_register_rejects_unknown_peripheral() -> None:
    with pytest.raises(UnknownPeripheralError):
        SetRegister(
            peripheral="I2C9",
            register="IC_CON",
            field_name="SPEED",
            value=1,
            bit_offset=0,
            bit_width=0,
            human_explanation="bogus",
        )


def test_set_register_rejects_unknown_register() -> None:
    with pytest.raises(UnknownRegisterError):
        SetRegister(
            peripheral="I2C0",
            register="NOT_A_REG",
            field_name="SPEED",
            value=1,
            bit_offset=0,
            bit_width=0,
            human_explanation="bogus",
        )


def test_set_register_rejects_value_overflow() -> None:
    with pytest.raises(ValidationError):
        SetRegister(
            peripheral="I2C0",
            register="IC_CON",
            field_name="SPEED",
            value=4,
            bit_offset=0,
            bit_width=0,
            human_explanation="too wide for 2-bit field",
        )


def test_add_wire_defaults_to_yellow() -> None:
    wire = AddWire(from_component="pico", from_pin="GP4", to_component="bme280", to_pin="SDA")
    assert wire.color == WireColor.YELLOW


def test_design_state_round_trip() -> None:
    state = DesignState(
        session_id="s1",
        user_prompt="Read BME280 over I2C",
        requirements=Requirements(
            peripheral_type="I2C",
            device_name="BME280",
            device_address="0x76",
            description="read temperature/humidity/pressure",
        ),
    )
    payload = state.model_dump()
    restored = DesignState.model_validate(payload)
    assert restored.requirements is not None
    assert restored.requirements.device_name == "BME280"
    assert restored.pin_assignments == []
    assert restored.build_success is False


def test_sse_event_discriminates_on_type() -> None:
    adapter = TypeAdapter(SSEEvent)
    ev = adapter.validate_python({"type": "assign_pin", "pin_number": 4, "function": "I2C_SDA",
                                   "peripheral_instance": "I2C0", "label": "SDA", "wire_color": "#e6c84a"})
    assert ev.type == "assign_pin"
    ev2 = adapter.validate_python({"type": "code_chunk", "delta": "#include"})
    assert ev2.type == "code_chunk"
    with pytest.raises(ValidationError):
        adapter.validate_python({"type": "nonexistent"})
