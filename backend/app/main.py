from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


class GenerateRequest(BaseModel):
    prompt: str
    session_id: str | None = None


@app.post("/api/generate")
async def generate(req: GenerateRequest) -> DesignState:
    return await run_pipeline(req.prompt, req.session_id)
