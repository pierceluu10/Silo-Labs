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

app = FastAPI(title="Silo Labs API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
