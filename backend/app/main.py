from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.graph.event_bus import EventBus, set_bus
from app.demo_pipeline import DEMO_PROMPT, run_demo_pipeline
from app.graph.pipeline import resume_pipeline, run_pipeline
from app.knowledge.graph import DEFAULT_MCU, set_target_mcu
from app.mcu import get_profile, list_profiles
from app.schemas.state import DesignState

# Allow common dev hostnames; EventSource is strict about CORS.
_DEV_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)

app = FastAPI(title="Silo Labs API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_DEV_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_sessions: dict[str, DesignState] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


class GenerateRequest(BaseModel):
    prompt: str
    session_id: str | None = None
    mcu: str = DEFAULT_MCU


def _validate_mcu(mcu: str) -> None:
    if mcu not in list_profiles():
        raise HTTPException(status_code=400, detail=f"Unknown MCU {mcu!r}. Supported: {list_profiles()}")


async def _run(prompt: str, session_id: str, mcu: str) -> DesignState:
    """The canned DHT22 demo replays for its exact prompt on RP2040; everything else runs the agents."""
    set_target_mcu(mcu)
    if mcu == DEFAULT_MCU and prompt.strip() == DEMO_PROMPT:
        return await run_demo_pipeline(session_id)
    return await run_pipeline(prompt, session_id, target_mcu=mcu)


@app.get("/api/mcus")
async def mcus() -> list[dict[str, str | list[str] | bool]]:
    return [
        {
            "name": profile.name,
            "display_name": profile.display_name,
            "board_name": profile.board_name,
            "sdk": profile.sdk_label,
            "peripheral_families": list(profile.supported_peripheral_families),
            "buildable": profile.build_firmware is not None,
        }
        for profile in map(get_profile, list_profiles())
    ]


@app.post("/api/generate")
async def generate(req: GenerateRequest) -> DesignState:
    _validate_mcu(req.mcu)
    state = await _run(req.prompt, req.session_id or uuid.uuid4().hex, req.mcu)
    _sessions[state.session_id] = state
    return state


async def _stream_pipeline(prompt: str, session_id: str, mcu: str) -> AsyncIterator[dict]:
    bus = EventBus()
    set_bus(bus)

    async def _runner() -> None:
        # Re-bind so LangGraph/emit() in the same task can always reach the queue.
        set_bus(bus)
        started = time.monotonic()
        try:
            profile = get_profile(mcu)
            bus.emit(
                {
                    "type": "session_ready",
                    "session_id": session_id,
                    "target_mcu": profile.name,
                    "mcu_display_name": profile.display_name,
                    "board_name": profile.board_name,
                    "board_part": profile.board_part,
                    "sdk": profile.sdk_label,
                }
            )
            state = await _run(prompt, session_id, mcu)
            _sessions[state.session_id] = state
            bus.emit(
                {
                    "type": "pipeline_complete",
                    "session_id": session_id,
                    "duration_ms": int((time.monotonic() - started) * 1000),
                }
            )
        except Exception as exc:
            bus.emit({"type": "error", "message": str(exc), "recoverable": False})
        finally:
            bus.close()

    task = asyncio.create_task(_runner())
    try:
        async for ev in bus.aiter():
            yield {"event": ev["type"], "data": json.dumps(ev)}
    finally:
        if not task.done():
            task.cancel()


@app.get("/api/stream")
async def stream(
    prompt: str = Query(...), session_id: str | None = None, mcu: str = DEFAULT_MCU
) -> EventSourceResponse:
    _validate_mcu(mcu)
    sid = session_id or uuid.uuid4().hex
    return EventSourceResponse(_stream_pipeline(prompt, sid, mcu))


@app.get("/api/artifacts/{session_id}/firmware.uf2")
async def firmware(session_id: str):
    state = _sessions.get(session_id)
    if not state or not state.uf2_artifact_path:
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(
        state.uf2_artifact_path,
        media_type="application/octet-stream",
        filename="firmware.uf2",
    )


@app.get("/api/artifacts/{session_id}/firmware.elf")
async def firmware_elf(session_id: str):
    state = _sessions.get(session_id)
    if not state or not state.elf_artifact_path:
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(
        state.elf_artifact_path,
        media_type="application/octet-stream",
        filename="firmware.elf",
    )


@app.post("/api/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    """Resume a previously-checkpointed run from where it stopped."""

    result = await resume_pipeline(session_id)
    if result is None:
        return JSONResponse({"error": "no checkpoint for session"}, status_code=404)
    _sessions[result.session_id] = result
    return {
        "session_id": result.session_id,
        "pipeline_complete": result.pipeline_complete,
        "build_success": result.build_success,
    }


@app.get("/api/sessions/{session_id}/files")
async def session_files(session_id: str):
    """Return the multi-file project the code agent emitted for this session."""

    state = _sessions.get(session_id)
    if not state:
        return JSONResponse({"error": "session not found"}, status_code=404)
    return {
        "session_id": session_id,
        "files": [f.model_dump() for f in state.generated_files],
    }


@app.get("/api/sim-bundle/{session_id}")
async def sim_bundle(session_id: str):
    """Return the artifact set the in-page Wokwi embed needs to run a live sim.

    The embed posts a MessagePort back to this app; we then upload these files
    via WokwiClient.fileUpload and call simStart. Diagram + wokwi.toml are
    derived from session state; UF2/ELF binaries are served via separate
    artifact endpoints (the embed will fetch them by URL).
    """
    state = _sessions.get(session_id)
    if not state:
        return JSONResponse({"error": "session not found"}, status_code=404)
    has_uf2 = bool(state.uf2_artifact_path)
    has_elf = bool(state.elf_artifact_path)
    if not has_uf2:
        return JSONResponse({"error": "build artifact missing (no UF2)"}, status_code=409)
    diagram = state.wokwi_diagram or {}
    wokwi_toml = (
        '[wokwi]\nversion = 1\nfirmware = "firmware.uf2"\n'
        + ('elf = "firmware.elf"\n' if has_elf else "")
    )
    return {
        "session_id": session_id,
        "diagram_json": diagram,
        "wokwi_toml": wokwi_toml,
        "uf2_url": f"/api/artifacts/{session_id}/firmware.uf2",
        "elf_url": f"/api/artifacts/{session_id}/firmware.elf" if has_elf else None,
    }
