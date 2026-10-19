from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks import BaseCallbackHandler

from app.config import get_settings
from app.graph.metrics import record_llm_usage
from app.knowledge.graph import current_mcu
from app.mcu import McuProfile, get_profile


class _UsageCaptureHandler(BaseCallbackHandler):
    """Forwards Anthropic per-call token usage into the metrics ContextVar."""

    def __init__(self, model: str) -> None:
        super().__init__()
        self.model = model

    def on_llm_end(self, response, **_: Any) -> None:  # type: ignore[override]
        # langchain-anthropic returns usage_metadata on each ChatGeneration; sum across.
        in_tokens = 0
        out_tokens = 0
        try:
            for gen_list in getattr(response, "generations", []) or []:
                for gen in gen_list:
                    msg = getattr(gen, "message", None)
                    usage = getattr(msg, "usage_metadata", None) if msg else None
                    if usage:
                        in_tokens += int(usage.get("input_tokens", 0) or 0)
                        out_tokens += int(usage.get("output_tokens", 0) or 0)
            llm_output = getattr(response, "llm_output", None) or {}
            tu = llm_output.get("token_usage") or llm_output.get("usage")
            if tu:
                in_tokens = in_tokens or int(tu.get("input_tokens", tu.get("prompt_tokens", 0)) or 0)
                out_tokens = out_tokens or int(
                    tu.get("output_tokens", tu.get("completion_tokens", 0)) or 0
                )
        except Exception:
            return
        if in_tokens or out_tokens:
            record_llm_usage(in_tokens, out_tokens, self.model)

def sonnet(max_tokens: int = 1024, temperature: float = 0) -> ChatAnthropic:
    settings = get_settings()
    return ChatAnthropic(
        model=settings.sonnet_model,
        api_key=settings.anthropic_api_key,
        max_tokens=max_tokens,
        temperature=temperature,
        callbacks=[_UsageCaptureHandler(settings.sonnet_model)],
    )


def haiku(max_tokens: int = 768, temperature: float = 0) -> ChatAnthropic:
    settings = get_settings()
    return ChatAnthropic(
        model=settings.haiku_model,
        api_key=settings.anthropic_api_key,
        max_tokens=max_tokens,
        temperature=temperature,
        callbacks=[_UsageCaptureHandler(settings.haiku_model)],
    )


def target_profile() -> McuProfile:
    """Profile of the MCU the running pipeline targets."""
    return get_profile(current_mcu())


def grounded_system_prompt(role: str, profile: McuProfile, peripheral_family: str, query: str) -> str:
    """Role prompt + scoped SVD summary + RAG-retrieved register specs and vendor docs."""
    return (
        f"{role}\n\n# Target MCU: {profile.display_name} on {profile.board_name}\n"
        f"Pin convention: {profile.valid_pin_label}\n\n"
        f"# {profile.display_name} SVD context\n{profile.svd_summary(peripheral_family)}\n\n"
        f"{profile.grounding(query)}"
    )
