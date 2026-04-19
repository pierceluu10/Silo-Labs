from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks import BaseCallbackHandler

from app.config import get_settings
from app.graph.metrics import record_llm_usage
from app.knowledge.graph import get_graph


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

# Peripherals every Sonnet agent needs regardless of the requested user peripheral:
# clocks/PLL/oscillator domains, resets, GPIO bank/pad muxing, and SIO.
_ALWAYS_INCLUDED_SVD = (
    "CLOCKS",
    "PLL_SYS",
    "PLL_USB",
    "XOSC",
    "ROSC",
    "RESETS",
    "IO_BANK0",
    "PADS_BANK0",
    "SIO",
)


@lru_cache(maxsize=16)
def svd_system_context(peripheral_family: str | None = None) -> str:
    """Compact SVD summary prepended to Sonnet agents' system prompts (cached).

    When `peripheral_family` is given (e.g. "I2C", "SPI", "UART"), the SVD is
    scoped to instances of that family plus a small always-included core
    (clocks, resets, GPIO mux, SIO). This dramatically reduces input tokens
    per Sonnet call so we stay under the per-minute rate limit.
    """
    graph = get_graph()
    if not peripheral_family:
        return graph.svd_summary(max_registers_per_peripheral=6)
    fam = peripheral_family.strip().upper()
    instances = [name for name in graph._peripherals if name.startswith(fam)]
    wanted = set(_ALWAYS_INCLUDED_SVD) | set(instances)
    return graph.svd_summary(peripherals=wanted, max_registers_per_peripheral=6)


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
