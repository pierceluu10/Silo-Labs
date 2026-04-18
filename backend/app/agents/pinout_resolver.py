from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.knowledge.graph import get_graph
from app.schemas.state import Requirements
from app.schemas.tools import AssignPin

from ._common import sonnet, svd_system_context


class PinAssignmentList(BaseModel):
    assignments: list[AssignPin] = Field(default_factory=list)


SYSTEM = """You are the Pinout Resolver for the RP2040. You pick GPIO pin assignments for the
required peripheral signals.

Constraints:
- Every pin_number must be a GPIO that supports the requested function on the RP2040 (use the
  provided pin options).
- Do NOT use GP0 or GP1 (reserved for UART0 debug).
- Each signal (SDA, SCL, TX, RX, SCK, CSn, etc.) must be assigned to exactly one pin.
- peripheral_instance is like "I2C0", "SPI1", "UART0" etc.
- label is a short human identifier ("SDA", "SCL", "TX", "RX").
- wire_color: #e6c84a for data (SDA/TX/MOSI), #4a7fd9 for clock (SCL/SCK), #4ad97f for aux.
- Use function enum values exactly: I2C_SDA, I2C_SCL, SPI_RX, SPI_TX, SPI_SCK, SPI_CSn,
  UART_TX, UART_RX, PWM_A, PWM_B, ADC, GPIO.
"""


async def resolve_pinout(requirements: Requirements) -> list[AssignPin]:
    graph = get_graph()
    family = requirements.peripheral_type.upper()

    if family in ("I2C", "SPI", "UART", "PWM"):
        options: dict[str, dict[str, list[int]]] = {}
        for inst in graph.list_peripherals(family):
            idx_str = inst[len(family):]
            if not idx_str.isdigit():
                continue
            options[inst] = graph.get_peripheral_pins(family, int(idx_str))
    else:
        options = {}

    user_msg = (
        f"User request: {requirements.description}\n"
        f"Peripheral: {requirements.peripheral_type}\n"
        f"Device: {requirements.device_name}\n"
        f"Available pin options per instance (signal -> candidate GP numbers):\n"
        f"{json.dumps(options, indent=2)}\n\n"
        f"Choose ONE peripheral instance and return the pin assignments."
    )

    llm = sonnet(max_tokens=1024).with_structured_output(PinAssignmentList)
    result = await llm.ainvoke(
        [
            SystemMessage(content=f"{SYSTEM}\n\n# RP2040 SVD context\n{svd_system_context()}"),
            HumanMessage(content=user_msg),
        ]
    )
    if not isinstance(result, PinAssignmentList):
        result = PinAssignmentList.model_validate(result)
    return list(result.assignments)
