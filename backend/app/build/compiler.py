from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.schemas.state import GeneratedFile

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
PROJECT_NAME = "firmware"


@dataclass
class BuildResult:
    success: bool
    stdout: str
    uf2_path: str | None
    elf_path: str | None = None


_FORBIDDEN_CMAKE_PATTERNS = (
    "cmake_minimum_required",
    "project(",
    "include(pico_sdk_import",
    "pico_sdk_init",
    "find_package(",
    "set(PICO_SDK_PATH",
    "set(PICO_BOARD",
)


def _sanitize_composed_cmake(composed_cmake: str) -> str:
    """Drop LLM-emitted CMake lines that conflict with the wrapper template.

    The wrapper already provides cmake_minimum_required, project(), pico_sdk_init,
    etc. find_package(...) is never appropriate for pico-sdk targets and has
    historically caused 'find_package called with invalid argument "SDK"' errors.
    """
    kept: list[str] = []
    for raw in composed_cmake.splitlines():
        line = raw.strip()
        low = line.lower()
        if any(p in low for p in _FORBIDDEN_CMAKE_PATTERNS):
            continue
        kept.append(raw)
    return "\n".join(kept).strip()


def _render_cmakelists(composed_cmake: str) -> str:
    template = (TEMPLATES_DIR / "CMakeLists.txt.jinja").read_text()
    return template.replace("{{ project_name }}", PROJECT_NAME).replace(
        "{{ composed_cmake }}", _sanitize_composed_cmake(composed_cmake)
    )


async def _run(cmd: list[str], cwd: Path, env: dict) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await proc.communicate()
    return proc.returncode or 0, output.decode(errors="replace")


def _is_safe_relative(path_str: str) -> bool:
    """Reject absolute paths or anything climbing out of the project dir."""

    if not path_str or path_str.startswith("/") or ":" in path_str:
        return False
    parts = Path(path_str).parts
    return ".." not in parts


def _write_files(workdir: Path, files: "list[GeneratedFile]") -> None:
    """Write the LLM-emitted file map to disk under workdir."""

    cmake_seen = False
    main_seen = False
    for f in files:
        if not _is_safe_relative(f.path):
            # Quietly skip unsafe entries; alternative is to abort the build.
            continue
        target = workdir / f.path
        target.parent.mkdir(parents=True, exist_ok=True)
        if f.path == "CMakeLists.txt":
            target.write_text(_render_cmakelists(f.content))
            cmake_seen = True
        else:
            target.write_text(f.content)
            if f.path == "main.c":
                main_seen = True
    if not cmake_seen or not main_seen:
        raise ValueError(
            f"Generated project missing required files (main.c={main_seen}, CMakeLists.txt={cmake_seen})"
        )


async def build_firmware(
    files_or_main_c: "list[GeneratedFile] | str",
    composed_cmake: str | None = None,
    project_dir: Path | None = None,
    pico_sdk_path: str | None = None,
) -> BuildResult:
    """Build a firmware project.

    Two call styles for backwards compatibility:
      - ``await build_firmware(files=[GeneratedFile(...), ...])`` (multi-file).
      - ``await build_firmware(main_c, composed_cmake)`` (legacy two-file).
    """

    pico_sdk_path = pico_sdk_path or os.environ.get("PICO_SDK_PATH", "/opt/pico-sdk")
    if not Path(pico_sdk_path).exists():
        return BuildResult(
            success=False,
            stdout=f"PICO_SDK_PATH '{pico_sdk_path}' does not exist; cannot build.",
            uf2_path=None,
        )

    workdir = project_dir or Path(tempfile.mkdtemp(prefix="silo_build_"))
    workdir.mkdir(parents=True, exist_ok=True)

    if isinstance(files_or_main_c, str):
        # Legacy path: (main_c, composed_cmake) — build a synthetic file list.
        from app.schemas.state import GeneratedFile  # local import avoids cycle

        files: "list[GeneratedFile]" = [
            GeneratedFile(path="main.c", content=files_or_main_c),
            GeneratedFile(path="CMakeLists.txt", content=composed_cmake or ""),
        ]
    else:
        files = files_or_main_c
    _write_files(workdir, files)
    shutil.copy(TEMPLATES_DIR / "pico_sdk_import.cmake", workdir / "pico_sdk_import.cmake")

    build_dir = workdir / "build"
    build_dir.mkdir(exist_ok=True)

    env = os.environ.copy()
    env["PICO_SDK_PATH"] = pico_sdk_path
    env.setdefault("PICO_BOARD", "pico")

    cfg_rc, cfg_out = await _run(["cmake", "-S", ".", "-B", "build"], workdir, env)
    if cfg_rc != 0:
        return BuildResult(success=False, stdout=cfg_out, uf2_path=None)

    build_rc, build_out = await _run(
        ["cmake", "--build", "build", "--parallel"], workdir, env
    )
    combined = cfg_out + "\n" + build_out
    if build_rc != 0:
        return BuildResult(success=False, stdout=combined, uf2_path=None)

    uf2 = next(build_dir.rglob("*.uf2"), None)
    elf = next(build_dir.rglob("firmware.elf"), None) or next(build_dir.rglob("*.elf"), None)
    return BuildResult(
        success=uf2 is not None,
        stdout=combined,
        uf2_path=str(uf2) if uf2 else None,
        elf_path=str(elf) if elf else None,
    )
