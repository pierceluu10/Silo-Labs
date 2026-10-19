from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.schemas.state import Requirements
from app.schemas.tools import AssignPin

from ._common import grounded_system_prompt, sonnet, target_profile


class PinAssignmentList(BaseModel):
    assignments: list[AssignPin] = Field(default_factory=list)


SYSTEM = """You are the Pinout Resolver. You pick GPIO pin assignments for the
required peripheral signals on the target MCU.

Constraints:
- Every pin_number must be a GPIO that supports the requested function on the target MCU. Use
  the provided pin options when present; otherwise use the retrieved pin mux documentation.
- Follow the pin convention below exactly, including reserved pins.
- Each signal (SDA, SCL, TX, RX, SCK, CSn, etc.) must be assigned to exactly one pin.
- peripheral_instance is the SVD instance name, e.g. "I2C0", "I2C1", "SPI1", "USART2".
- label is a short human identifier ("SDA", "SCL", "TX", "RX").
- wire_color: #e6c84a for data (SDA/TX/MOSI), #4a7fd9 for clock (SCL/SCK), #4ad97f for aux.
- Use function enum values exactly: I2C_SDA, I2C_SCL, SPI_RX, SPI_TX, SPI_SCK, SPI_CSn,
  UART_TX, UART_RX, PWM_A, PWM_B, ADC, GPIO (USART signals use UART_TX / UART_RX).
- Leave pin_name empty; it is derived from pin_number.
"""


async def resolve_pinout(requirements: Requirements) -> list[AssignPin]:
    profile = target_profile()
    options = profile.pinout_options(requirements.peripheral_type)

    user_msg = (
        f"User request: {requirements.description}\n"
        f"Peripheral: {requirements.peripheral_type}\n"
        f"Device: {requirements.device_name}\n"
        f"Available pin options per instance (signal -> candidate pin numbers):\n"
        f"{json.dumps(options, indent=2) if options else 'not hand-modeled; use the retrieved pin mux docs'}\n\n"
        f"Choose ONE peripheral instance and return the pin assignments."
    )

    sys_msg = grounded_system_prompt(
        SYSTEM,
        profile,
        requirements.peripheral_type,
        f"{requirements.peripheral_type} pin mux {requirements.device_name} pins alternate function",
    )
    llm = sonnet(max_tokens=1024).with_structured_output(PinAssignmentList)
    result = await llm.ainvoke(
        [
            SystemMessage(content=sys_msg),
            HumanMessage(content=user_msg),
        ]
    )
    if not isinstance(result, PinAssignmentList):
        result = PinAssignmentList.model_validate(result)
    return list(result.assignments)
