from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
DEFAULT_FIXTURE = FIXTURE_DIR / "bme280_ssd1306_output.txt"
LINE_DELAY_MS = 50


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
    """Yield simulation output lines. Uses wokwi-cli if WOKWI_CLI_TOKEN is set and uf2 exists,
    otherwise replays the fixture at a realistic cadence."""
    if os.getenv("WOKWI_CLI_TOKEN") and uf2_path and Path(uf2_path).exists():
        async for line in _stream_live(uf2_path, timeout_s):
            yield line
        return

    for line in DEFAULT_FIXTURE.read_text().splitlines():
        yield line
        await asyncio.sleep(line_delay_ms / 1000.0)


async def _stream_live(uf2_path: str, timeout_s: int) -> AsyncIterator[str]:
    proc = await asyncio.create_subprocess_exec(
        "wokwi-cli",
        "--timeout",
        str(timeout_s * 1000),
        "--serial-log-file",
        "/dev/stdout",
        str(Path(uf2_path).parent),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
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
    mode = "live" if (os.getenv("WOKWI_CLI_TOKEN") and uf2_path) else "fixture"
    async for line in stream_simulation(uf2_path, diagram_json, timeout_s=timeout_s):
        lines.append(line)
    return SimulationResult(log="\n".join(lines), mode=mode)
