from __future__ import annotations

from functools import lru_cache

from langchain_anthropic import ChatAnthropic

from app.config import get_settings
from app.knowledge.graph import get_graph


@lru_cache(maxsize=1)
def svd_system_context() -> str:
    """Compact SVD summary prepended to Sonnet agents' system prompts (cached)."""
    return get_graph().svd_summary(max_registers_per_peripheral=6)


def sonnet(max_tokens: int = 1024, temperature: float = 0) -> ChatAnthropic:
    settings = get_settings()
    return ChatAnthropic(
        model=settings.sonnet_model,
        api_key=settings.anthropic_api_key,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def haiku(max_tokens: int = 768, temperature: float = 0) -> ChatAnthropic:
    settings = get_settings()
    return ChatAnthropic(
        model=settings.haiku_model,
        api_key=settings.anthropic_api_key,
        max_tokens=max_tokens,
        temperature=temperature,
    )
