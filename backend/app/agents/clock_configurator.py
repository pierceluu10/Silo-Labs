from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.schemas.state import Requirements
from app.schemas.tools import ConfigureClock

from ._common import grounded_system_prompt, sonnet, target_profile


class ClockConfigList(BaseModel):
    clocks: list[ConfigureClock] = Field(default_factory=list)


SYSTEM = """You are the Clock Configurator.

Return a minimal set of clock configurations that brings the target MCU up for the
requested peripheral. Start from the default plan below and change it only when the
peripheral needs it (e.g. ADC clock limits, USB 48 MHz).

clock_domain and source must be one of the allowed domain names listed below.
pll_vco_freq_hz is required only on PLL rows themselves, not on downstream clocks that
source from a PLL.
"""


async def configure_clocks(requirements: Requirements) -> list[ConfigureClock]:
    profile = target_profile()
    sys_msg = (
        grounded_system_prompt(
            SYSTEM,
            profile,
            requirements.peripheral_type,
            f"clock tree PLL oscillator bus prescaler {requirements.peripheral_type} clock",
        )
        + f"\n\n# Allowed clock domains\n{', '.join(profile.clock_domains)}"
        + f"\n\n# Default plan: {profile.clock_hint.description}\n{json.dumps(profile.clock_hint.rows)}"
    )
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
