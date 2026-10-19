from __future__ import annotations

from pathlib import PurePosixPath

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

    The entry point and root CMakeLists.txt are required (per-MCU rules live in
    the profile prompt). Anything else is allowed: extra .c/.h drivers, .pio
    programs, nested directories like ``drivers/ws2812.c`` or ``main/main.c``.
    """

    files: list[_GeneratedFileLLM] = Field(min_length=2)


SYSTEM_BASE = """You are the Code Composer.

Output a complete, compilable embedded firmware project as a list of files.
The required files and build-file rules for the target are in the "Target MCU"
section below — follow them exactly.

You MAY include any number of additional files when the task warrants it:
  - "drivers/<device>.c" + "drivers/<device>.h" for cleanly separated drivers
  - "include/config.h" for shared constants
Use realistic paths; the build wrapper writes them all into one project tree.

Constraints across all files:
- Use the exact pins from the pin assignments (pin_name is the chip's own pin label).
- Ground register names, bit fields and pin functions in the retrieved documentation;
  never invent registers that are not in the SVD context.
- Route printf to the serial console the target section names.
- The main loop runs forever and prints periodic readings via printf.

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
        + profile.code_composer_prompt
        + "\n\n# Chip SVD context\n"
        + profile.svd_summary(requirements.peripheral_type)
        + "\n\n"
        + profile.grounding(
            f"{requirements.peripheral_type} {requirements.device_name} driver init "
            f"{requirements.description}"
        )
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
                    "every required file from the Target MCU section as "
                    "{path: '...', content: '...'}. No prose."
                )
            )
            result = await llm.ainvoke([SystemMessage(content=sys_msg), HumanMessage(content=user), nudge])
            if not isinstance(result, MultiFileProject):
                result = MultiFileProject.model_validate(result)

    return [
        GeneratedFile(path=f.path, content=f.content, language=f.language)
        for f in result.files
    ]


ENTRY_FILENAMES = ("main.c", "main.cpp")
ROOT_BUILD_FILE = "CMakeLists.txt"


def _is_entry(path: str) -> bool:
    # ESP-IDF puts the entry point in main/main.c; pico-sdk and bare-metal at the root.
    return PurePosixPath(path).name in ENTRY_FILENAMES


def is_core_file(path: str) -> bool:
    return path == ROOT_BUILD_FILE or _is_entry(path)


def split_main_and_cmake(files: list[GeneratedFile]) -> tuple[str, str]:
    """Return (entry-point source, root CMakeLists.txt) — the editor streams the former."""

    main_c = next((f.content for f in files if _is_entry(f.path)), "")
    cmake = next((f.content for f in files if f.path == ROOT_BUILD_FILE), "")
    return main_c, cmake