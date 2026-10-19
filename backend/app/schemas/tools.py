from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field, model_validator

from app.knowledge.graph import (
    UnknownPeripheralError,
    UnknownRegisterError,
    current_mcu,
    get_graph,
)


def _target_profile():
    # Lazy: app.mcu imports this module, so a top-level import would cycle.
    from app.mcu import get_profile

    return get_profile(current_mcu())


class PinFunction(str, Enum):
    GPIO = "GPIO"
    I2C_SDA = "I2C_SDA"
    I2C_SCL = "I2C_SCL"
    SPI_RX = "SPI_RX"
    SPI_TX = "SPI_TX"
    SPI_SCK = "SPI_SCK"
    SPI_CSN = "SPI_CSn"
    UART_TX = "UART_TX"
    UART_RX = "UART_RX"
    UART_CTS = "UART_CTS"
    UART_RTS = "UART_RTS"
    PWM_A = "PWM_A"
    PWM_B = "PWM_B"
    ADC = "ADC"


class ClockSource(str, Enum):
    """RP2040 clock domains; other MCUs declare theirs on McuProfile.clock_domains."""

    XOSC = "XOSC"
    ROSC = "ROSC"
    GPIN0 = "GPIN0"
    GPIN1 = "GPIN1"
    PLL_SYS = "PLL_SYS"
    PLL_USB = "PLL_USB"
    CLK_REF = "CLK_REF"
    CLK_SYS = "CLK_SYS"
    CLK_PERI = "CLK_PERI"
    CLK_USB = "CLK_USB"
    CLK_ADC = "CLK_ADC"
    CLK_RTC = "CLK_RTC"


class WireColor(str, Enum):
    RED = "#d94a4a"
    BLACK = "#1a1a1a"
    YELLOW = "#e6c84a"
    BLUE = "#4a7fd9"
    GREEN = "#4ad97f"
    WHITE = "#f2f2f2"


HEX_COLOR = r"^#[0-9a-fA-F]{6}$"


class AssignPin(BaseModel):
    model_config = {"frozen": True}

    pin_number: Annotated[int, Field(ge=0, description="GPIO index in the target MCU's numbering")]
    function: PinFunction
    peripheral_instance: str
    label: Annotated[str, Field(max_length=32)]
    wire_color: Annotated[str, Field(pattern=HEX_COLOR)]
    pin_name: str = Field(default="", description="Derived from pin_number by the MCU profile (GP4, PB7, GPIO21).")

    @model_validator(mode="before")
    @classmethod
    def _resolve_pin_name(cls, data: Any) -> Any:
        if not isinstance(data, dict) or not isinstance(data.get("pin_number"), int):
            return data
        profile = _target_profile()
        if data["pin_number"] >= profile.gpio_count:
            raise ValueError(
                f"pin_number {data['pin_number']} out of range for {profile.display_name} "
                f"(0..{profile.gpio_count - 1})"
            )
        return {**data, "pin_name": profile.pin_name(data["pin_number"])}


class ConfigureClock(BaseModel):
    model_config = {"frozen": True}

    clock_domain: str
    source: str
    freq_hz: Annotated[int, Field(gt=0, le=250_000_000)]
    divider: Annotated[float, Field(gt=0.0)]
    pll_vco_freq_hz: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _check_domains(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        profile = _target_profile()
        normalized = dict(data)
        for key in ("clock_domain", "source"):
            raw = data.get(key)
            if raw is None:
                continue
            name = str(getattr(raw, "value", raw)).upper()
            if name not in profile.clock_domains:
                raise ValueError(
                    f"{key} {name!r} is not a {profile.display_name} clock domain "
                    f"({', '.join(profile.clock_domains)})"
                )
            normalized[key] = name
        return normalized

    @model_validator(mode="after")
    def _require_vco_when_pll(self) -> "ConfigureClock":
        # VCO frequency is a property of the PLL itself (rows where clock_domain is
        # a PLL), not of downstream clocks that source from a PLL.
        if self.clock_domain.startswith("PLL") and self.pll_vco_freq_hz is None:
            raise ValueError(f"pll_vco_freq_hz required when clock_domain is {self.clock_domain}")
        return self


class SetRegister(BaseModel):
    model_config = {"frozen": True}

    peripheral: str
    register: str
    address: int = 0
    field_name: str
    value: int
    bit_offset: Annotated[int, Field(ge=0, le=31)]
    bit_width: Annotated[int, Field(ge=1, le=32)]
    human_explanation: str

    @model_validator(mode="before")
    @classmethod
    def _resolve_from_graph(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        peripheral = data.get("peripheral")
        register = data.get("register")
        field_name = data.get("field_name")
        if not (peripheral and register and field_name):
            return data

        graph = get_graph()
        try:
            reg = graph.get_register(peripheral, register)
        except UnknownPeripheralError:
            raise
        except UnknownRegisterError:
            raise

        # Case-insensitive field lookup (LLM occasionally lowercases names).
        if field_name in reg["fields"]:
            fld = reg["fields"][field_name]
        else:
            upper = field_name.upper()
            fld = next(
                (v for k, v in reg["fields"].items() if k.upper() == upper),
                None,
            )
            if fld is None:
                raise UnknownRegisterError(f"{peripheral}.{register}.{field_name} not in SVD")

        data["address"] = reg["address"]
        data["bit_offset"] = fld["offset"]
        data["bit_width"] = fld["width"]

        if (value := data.get("value")) is not None:
            width = data["bit_width"]
            if value < 0 or value >= (1 << width):
                raise ValueError(
                    f"value {value} does not fit in {width} bits for {peripheral}.{register}.{field_name}"
                )
        return data


class AddWire(BaseModel):
    model_config = {"frozen": True}

    from_component: str
    from_pin: str
    to_component: str
    to_pin: str
    color: WireColor = WireColor.YELLOW
