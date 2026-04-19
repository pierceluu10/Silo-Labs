from __future__ import annotations

from functools import lru_cache

from langchain_anthropic import ChatAnthropic

from app.config import get_settings
from app.knowledge.graph import get_graph

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
    )


def haiku(max_tokens: int = 768, temperature: float = 0) -> ChatAnthropic:
    settings = get_settings()
    return ChatAnthropic(
        model=settings.haiku_model,
        api_key=settings.anthropic_api_key,
        max_tokens=max_tokens,
        temperature=temperature,
    )
