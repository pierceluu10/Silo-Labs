from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings


def _wokwi_token() -> str:
    """Read the Wokwi CLI token from settings (loads backend/.env)."""
    return get_settings().wokwi_cli_token

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
LINE_DELAY_MS = 50

# Fixtures are matched by a marker substring in the diagram JSON or peripheral
# hint. When no fixture matches, we DO NOT replay an unrelated capture (that
# would lie about the firmware's behaviour); instead we emit an honest
# build-only summary.
_FIXTURES: tuple[tuple[str, Path], ...] = (
    ("bme280", FIXTURE_DIR / "bme280_ssd1306_output.txt"),
)


def _select_fixture(diagram_json: dict | None) -> Path | None:
    if not diagram_json:
        return None
    blob = str(diagram_json).lower()
    for marker, path in _FIXTURES:
        if marker in blob and path.exists():
            return path
    return None


@dataclass
class SimulationResult:
    log: str
    mode: str


async def stream_simulation(
    uf2_path: str | None,
    diagram_json: dict | None = None,
    line_delay_ms: int = LINE_DELAY_MS,
    timeout_s: int = 15,
) -> AsyncIterator[str]:
    """Yield simulation output lines.

    1. If WOKWI_CLI_TOKEN is set and a UF2 exists, run wokwi-cli (live).
    2. Otherwise, if a fixture matches the diagram, replay it at realistic cadence.
    3. Otherwise, emit a short honest message (no fake serial output).
    """
    token = _wokwi_token()
    if token and uf2_path and Path(uf2_path).exists():
        async for line in _stream_live(uf2_path, timeout_s, token, diagram_json):
            yield line
        return

    fixture = _select_fixture(diagram_json)
    if fixture is not None:
        for line in fixture.read_text().splitlines():
            yield line
            await asyncio.sleep(line_delay_ms / 1000.0)
        return

    built = "(uf2 ready)" if (uf2_path and Path(uf2_path).exists()) else "(no uf2)"
    yield "[sim] No live simulator configured (set WOKWI_CLI_TOKEN to run wokwi-cli)."
    yield f"[sim] Build artifact: {built}. Skipping fixture replay (none matches this firmware)."


async def _stream_live(
    uf2_path: str,
    timeout_s: int,
    token: str,
    diagram_json: dict | None,
) -> AsyncIterator[str]:
    import json as _json
    import os as _os

    project_dir = Path(uf2_path).parent
    uf2_name = Path(uf2_path).name
    # wokwi-cli expects two files in the project dir:
    #   * diagram.json — the wiring (board + parts + connections)
    #   * wokwi.toml   — points at the firmware artifact to load into the simulator
    if diagram_json:
        try:
            (project_dir / "diagram.json").write_text(_json.dumps(diagram_json, indent=2))
        except Exception:
            pass
    try:
        (project_dir / "wokwi.toml").write_text(
            f'[wokwi]\nversion = 1\nfirmware = "{uf2_name}"\nelf = "{uf2_name}"\n'
        )
    except Exception:
        pass

    env = _os.environ.copy()
    env["WOKWI_CLI_TOKEN"] = token
    proc = await asyncio.create_subprocess_exec(
        "wokwi-cli",
        "--timeout",
        str(timeout_s * 1000),
        "--serial-log-file",
        "/dev/stdout",
        str(project_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )
    assert proc.stdout is not None
    async for raw in proc.stdout:
        line = raw.decode(errors="replace").rstrip()
        if line:
            yield line
    await proc.wait()


async def run_simulation(
    uf2_path: str | None,
    diagram_json: dict | None = None,
    timeout_s: int = 15,
) -> SimulationResult:
    lines: list[str] = []
    mode = "live" if (_wokwi_token() and uf2_path) else "fixture"
    async for line in stream_simulation(uf2_path, diagram_json, timeout_s=timeout_s):
        lines.append(line)
    return SimulationResult(log="\n".join(lines), mode=mode)
