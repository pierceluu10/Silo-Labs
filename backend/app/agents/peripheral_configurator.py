from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.schemas.state import Requirements
from app.schemas.tools import SetRegister

from ._common import grounded_system_prompt, sonnet, target_profile


class RegisterWriteList(BaseModel):
    writes: list[SetRegister] = Field(default_factory=list)


SYSTEM = """You are the Peripheral Configurator.

Emit the minimal set of register field writes needed to bring up the chosen peripheral on
the target MCU. Pick registers and fields by NAME from the SVD context and the retrieved
register specs. The system will look up the authoritative address — you do NOT guess
addresses. Writes naming a register or field that is not in the SVD are rejected.

Each entry needs: peripheral, register, field_name, value, human_explanation.
Set bit_offset=0 and bit_width=1 as placeholders — the SVD lookup overrides them.
"""


async def configure_peripheral(requirements: Requirements) -> list[SetRegister]:
    profile = target_profile()
    sys_msg = (
        grounded_system_prompt(
            SYSTEM,
            profile,
            requirements.peripheral_type,
            f"{requirements.peripheral_type} {requirements.device_name} enable configure registers "
            f"{requirements.description}",
        )
        + f"\n\n# Example\n{profile.peripheral_example}"
    )
    llm = sonnet(max_tokens=2048).with_structured_output(RegisterWriteList)
    result = await llm.ainvoke(
        [
            SystemMessage(content=sys_msg),
            HumanMessage(
                content=(
                    f"Peripheral family: {requirements.peripheral_type}\n"
                    f"Device: {requirements.device_name} @ {requirements.device_address}\n"
                    f"Task: {requirements.description}\n"
                    f"Return the register write list."
                )
            ),
        ]
    )
    if not isinstance(result, RegisterWriteList):
        result = RegisterWriteList.model_validate(result)
    return list(result.writes)
