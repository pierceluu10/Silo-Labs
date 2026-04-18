from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.schemas.state import Requirements
from app.schemas.tools import SetRegister

from ._common import sonnet, svd_system_context


class RegisterWriteList(BaseModel):
    writes: list[SetRegister] = Field(default_factory=list)


SYSTEM = """You are the Peripheral Configurator for the RP2040.

Emit the minimal set of register field writes needed to bring up the chosen peripheral.
Pick registers and fields by NAME from the SVD context. The system will look up the
authoritative address — you do NOT guess addresses.

For I2C master mode (e.g. BME280 at 400 kHz on I2C0):
  - RESETS.RESET clear bit for I2C0
  - I2C0.IC_ENABLE.ENABLE = 0   (disable before configuring)
  - I2C0.IC_CON.SPEED = 2       (fast mode)
  - I2C0.IC_CON.MASTER_MODE = 1
  - I2C0.IC_CON.IC_SLAVE_DISABLE = 1
  - I2C0.IC_CON.IC_RESTART_EN = 1
  - I2C0.IC_SS_SCL_HCNT / IC_SS_SCL_LCNT for timing
  - I2C0.IC_ENABLE.ENABLE = 1

Each entry needs: peripheral, register, field_name, value, human_explanation.
Set bit_offset=0 and bit_width=1 as placeholders — the SVD lookup overrides them.
"""


async def configure_peripheral(requirements: Requirements) -> list[SetRegister]:
    llm = sonnet(max_tokens=2048).with_structured_output(RegisterWriteList)
    result = await llm.ainvoke(
        [
            SystemMessage(content=f"{SYSTEM}\n\n# RP2040 SVD context\n{svd_system_context()}"),
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
