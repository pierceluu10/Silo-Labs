from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
PROJECT_NAME = "firmware"


@dataclass
class BuildResult:
    success: bool
    stdout: str
    uf2_path: str | None


def _render_cmakelists(composed_cmake: str) -> str:
    template = (TEMPLATES_DIR / "CMakeLists.txt.jinja").read_text()
    return template.replace("{{ project_name }}", PROJECT_NAME).replace(
        "{{ composed_cmake }}", composed_cmake.strip()
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


async def build_firmware(
    main_c: str,
    composed_cmake: str,
    project_dir: Path | None = None,
    pico_sdk_path: str | None = None,
) -> BuildResult:
    pico_sdk_path = pico_sdk_path or os.environ.get("PICO_SDK_PATH", "/opt/pico-sdk")
    if not Path(pico_sdk_path).exists():
        return BuildResult(
            success=False,
            stdout=f"PICO_SDK_PATH '{pico_sdk_path}' does not exist; cannot build.",
            uf2_path=None,
        )

    workdir = project_dir or Path(tempfile.mkdtemp(prefix="silo_build_"))
    workdir.mkdir(parents=True, exist_ok=True)

    (workdir / "main.c").write_text(main_c)
    (workdir / "CMakeLists.txt").write_text(_render_cmakelists(composed_cmake))
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
    return BuildResult(
        success=uf2 is not None,
        stdout=combined,
        uf2_path=str(uf2) if uf2 else None,
    )
