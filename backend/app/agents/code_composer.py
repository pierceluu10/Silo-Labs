from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.mcu import get_profile
from app.schemas.state import GeneratedFile, Requirements
from app.schemas.tools import AssignPin, ConfigureClock, SetRegister

from ._common import sonnet


class _GeneratedFileLLM(BaseModel):
    """LLM-side mirror of GeneratedFile (kept loose so the schema is permissive)."""

    path: str = Field(description="Path relative to project root, e.g. 'main.c' or 'drivers/ws2812.pio'.")
    content: str = Field(description="Full file contents.")
    language: str | None = Field(default=None, description="Optional syntax hint.")


class MultiFileProject(BaseModel):
    """Generated project as an explicit file map.

    main.c and CMakeLists.txt are required (the build wrapper expects them).
    Anything else is allowed: extra .c/.h drivers, .pio programs, even nested
    directories like ``drivers/ws2812.c``.
    """

    files: list[_GeneratedFileLLM] = Field(min_length=2)


SYSTEM_BASE = """You are the Code Composer.

Output a complete, compilable embedded firmware project as a list of files.
The project MUST include at minimum:
  - "main.c"          — entry point with a forever loop
  - "CMakeLists.txt"  — project-specific build lines only (see rules)

You MAY include any number of additional files when the task warrants it:
  - "drivers/<device>.c" + "drivers/<device>.h" for cleanly separated drivers
  - "<peripheral>.pio" for PIO programs
  - "include/config.h" for shared constants
Use realistic paths; the build wrapper writes them all into one project tree.

CMakeLists.txt rules — emit ONLY the project-specific lines below; nothing else:
  add_executable(firmware main.c drivers/foo.c ...)   # list every .c you ship
  target_link_libraries(firmware pico_stdlib hardware_i2c ...)  # only what you use
  pico_enable_stdio_usb(firmware 1)
  pico_enable_stdio_uart(firmware 0)
  pico_add_extra_outputs(firmware)
  # PIO programs need pico_generate_pio_header(firmware ${CMAKE_CURRENT_LIST_DIR}/foo.pio)

STRICTLY FORBIDDEN in CMakeLists.txt content:
- cmake_minimum_required(...)        — the wrapper sets it.
- project(...)                       — the wrapper sets it.
- include(pico_sdk_import.cmake)     — the wrapper adds it.
- pico_sdk_init()                    — the wrapper calls it.
- find_package(...)                  — pico-sdk libraries link by name.
- set(PICO_SDK_PATH ...) / set(PICO_BOARD ...)

Constraints across all files:
- Use the exact GP pin numbers from the pin assignments.
- Initialise stdio over USB so printf reaches the simulator.
- main() loops forever and prints periodic readings via printf.

NO markdown fences, NO prose, NO extra commentary — just file content in the structured output.
"""


async def compose_code(
    requirements: Requirements,
    pin_assignments: list[AssignPin],
    clock_configs: list[ConfigureClock],
    register_writes: list[SetRegister],
    *,
    target_mcu: str = "rp2040",
    build_error_hint: str | None = None,
) -> list[GeneratedFile]:
    """Generate a multi-file firmware project tailored to the given MCU profile.

    Returns a list of GeneratedFile rather than the legacy (main_c, cmake) pair
    so the build wrapper can write whatever the LLM produced.
    """

    profile = get_profile(target_mcu)
    sys_msg = (
        SYSTEM_BASE
        + "\n\n# Target MCU\n"
        + profile.code_composer_system_prompt()
        + "\n\n# Chip SVD context\n"
        + profile.svd_summary(requirements.peripheral_type)
    )
    if build_error_hint:
        sys_msg += (
            "\n\n# Previous attempt failed during build — fix it this time\n"
            + build_error_hint[-1500:]
        )

    user = (
        f"Task: {requirements.description}\n"
        f"Peripheral: {requirements.peripheral_type}\n"
        f"Device: {requirements.device_name} @ {requirements.device_address}\n"
        f"Pin assignments: {[p.model_dump() for p in pin_assignments]}\n"
        f"Clocks: {[c.model_dump() for c in clock_configs]}\n"
        f"Register plan (register, field, value): "
        f"{[(r.peripheral, r.register, r.field_name, r.value) for r in register_writes]}\n\n"
        f"Produce the full project file tree."
    )

    # The MultiFileProject schema is larger than the legacy ComposedProject
    # (variable-length files list, each with path/content/language). Sonnet
    # occasionally truncates the tool_use args when the budget is tight; 12k
    # leaves comfortable headroom for a 13 KB main.c + drivers + CMakeLists.
    llm = sonnet(max_tokens=12_288).with_structured_output(MultiFileProject)
    result = await llm.ainvoke([SystemMessage(content=sys_msg), HumanMessage(content=user)])
    if not isinstance(result, MultiFileProject):
        try:
            result = MultiFileProject.model_validate(result)
        except Exception:
            # Single retry with an explicit shape reminder. RetryPolicy on the
            # outer node also retries the whole call; this catches the common
            # "empty tool_use args" case without burning a second LLM round.
            nudge = HumanMessage(
                content=(
                    "Your previous reply did not match the schema. "
                    "Return JSON with a top-level 'files' array containing "
                    "at minimum {path: 'main.c', content: '...'} and "
                    "{path: 'CMakeLists.txt', content: '...'}. No prose."
                )
            )
            result = await llm.ainvoke([SystemMessage(content=sys_msg), HumanMessage(content=user), nudge])
            if not isinstance(result, MultiFileProject):
                result = MultiFileProject.model_validate(result)

    return [
        GeneratedFile(path=f.path, content=f.content, language=f.language)
        for f in result.files
    ]


def split_main_and_cmake(files: list[GeneratedFile]) -> tuple[str, str]:
    """Backwards-compat shim — returns (main_c, cmake) for callers that still want them."""

    main_c = ""
    cmake = ""
    for f in files:
        if f.path == "main.c":
            main_c = f.content
        elif f.path == "CMakeLists.txt":
            cmake = f.content
    return main_c, cmake