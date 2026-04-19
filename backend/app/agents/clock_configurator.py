from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.schemas.state import Requirements
from app.schemas.tools import ConfigureClock

from ._common import sonnet, svd_system_context


class ClockConfigList(BaseModel):
    clocks: list[ConfigureClock] = Field(default_factory=list)


SYSTEM = """You are the Clock Configurator for the RP2040.

Return a minimal set of clock configurations for the requested peripheral. For a typical
I2C/SPI/UART application running the system at 125 MHz:
  - XOSC: source=XOSC, freq_hz=12_000_000, divider=1.0
  - PLL_SYS: source=XOSC, freq_hz=125_000_000, divider=1.0, pll_vco_freq_hz=1_500_000_000
  - CLK_SYS: source=PLL_SYS, freq_hz=125_000_000, divider=1.0
  - CLK_PERI: source=CLK_SYS, freq_hz=125_000_000, divider=1.0
  - CLK_REF: source=XOSC, freq_hz=12_000_000, divider=1.0

clock_domain values: XOSC, ROSC, PLL_SYS, PLL_USB, CLK_REF, CLK_SYS, CLK_PERI, CLK_USB, CLK_ADC, CLK_RTC.
pll_vco_freq_hz is required only on the PLL row itself (clock_domain=PLL_SYS or PLL_USB), not on downstream clocks that source from a PLL.
"""


async def configure_clocks(requirements: Requirements) -> list[ConfigureClock]:
    sys_msg = f"{SYSTEM}\n\n# RP2040 SVD context\n{svd_system_context(requirements.peripheral_type)}"
    llm = sonnet(max_tokens=1024).with_structured_output(ClockConfigList)
    result = await llm.ainvoke(
        [
            SystemMessage(content=sys_msg),
            HumanMessage(
                content=(
                    f"Peripheral: {requirements.peripheral_type}\n"
                    f"Device: {requirements.device_name}\n"
                    f"Baud/rate: {requirements.baud_rate}\n"
                    f"Return the clock configuration list."
                )
            ),
        ]
    )
    if not isinstance(result, ClockConfigList):
        result = ClockConfigList.model_validate(result)
    return list(result.clocks)
