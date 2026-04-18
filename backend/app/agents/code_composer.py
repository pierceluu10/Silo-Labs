from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.schemas.state import Requirements
from app.schemas.tools import AssignPin, ConfigureClock, SetRegister

from ._common import sonnet, svd_system_context


class ComposedProject(BaseModel):
    main_c: str = Field(description="Full contents of main.c using pico-sdk high-level APIs")
    cmake: str = Field(description="CMakeLists.txt content for this project (NO pico_sdk_import boilerplate)")


SYSTEM = """You are the Code Composer. You produce a complete, compilable pico-sdk C program
for the RP2040 plus a project-specific CMakeLists.txt.

Rules:
- Use pico-sdk high-level APIs (e.g. i2c_init, i2c_write_blocking, gpio_set_function, stdio_init_all).
- Include the correct headers (pico/stdlib.h, hardware/i2c.h, etc.).
- Use the exact GP pin numbers from the pin assignments.
- Initialize stdio over USB (pico_enable_stdio_usb) so serial output works in Wokwi.
- main() must loop forever reading the device and printing results via printf every ~1s.
- The CMakeLists.txt should define a single executable target named "firmware", link
  pico_stdlib + any required hardware libs, and call pico_add_extra_outputs.
- Do NOT include pico_sdk_import.cmake (the build wrapper adds that).
- NO markdown fences, NO prose — just code in the two fields.
"""


async def compose_code(
    requirements: Requirements,
    pin_assignments: list[AssignPin],
    clock_configs: list[ConfigureClock],
    register_writes: list[SetRegister],
) -> tuple[str, str]:
    llm = sonnet(max_tokens=4096).with_structured_output(ComposedProject)
    user = (
        f"Task: {requirements.description}\n"
        f"Peripheral: {requirements.peripheral_type}\n"
        f"Device: {requirements.device_name} @ {requirements.device_address}\n"
        f"Pin assignments: {[p.model_dump() for p in pin_assignments]}\n"
        f"Clocks: {[c.model_dump() for c in clock_configs]}\n"
        f"Register plan (register, field, value): "
        f"{[(r.peripheral, r.register, r.field_name, r.value) for r in register_writes]}\n\n"
        f"Produce main.c and CMakeLists.txt."
    )

    result = await llm.ainvoke(
        [
            SystemMessage(content=f"{SYSTEM}\n\n# RP2040 SVD context\n{svd_system_context()}"),
            HumanMessage(content=user),
        ]
    )
    if not isinstance(result, ComposedProject):
        result = ComposedProject.model_validate(result)
    return result.main_c, result.cmake
