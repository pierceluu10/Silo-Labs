from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.graph.event_bus import EventBus, set_bus
from app.graph.pipeline import run_pipeline
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


@app.post("/api/generate")
async def generate(req: GenerateRequest) -> DesignState:
    state = await run_pipeline(req.prompt, req.session_id)
    _sessions[state.session_id] = state
    return state


async def _stream_pipeline(prompt: str, session_id: str) -> AsyncIterator[dict]:
    bus = EventBus()
    set_bus(bus)

    async def _runner() -> None:
        # Re-bind so LangGraph/emit() in the same task can always reach the queue.
        set_bus(bus)
        started = time.monotonic()
        try:
            bus.emit({"type": "session_ready", "session_id": session_id})
            state = await run_pipeline(prompt, session_id)
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
async def stream(prompt: str = Query(...), session_id: str | None = None) -> EventSourceResponse:
    sid = session_id or uuid.uuid4().hex
    return EventSourceResponse(_stream_pipeline(prompt, sid))


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
