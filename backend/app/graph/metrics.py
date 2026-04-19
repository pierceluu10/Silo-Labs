"""Per-node metrics collection.

Wraps every pipeline node so we capture wall-clock duration and (where the
node makes LLM calls) input/output token counts. Emits a ``metrics_update``
SSE event after each node so the UI can update live, and a final
``metrics_summary`` event with the full RunMetrics snapshot.

Cost model: the rates here are the public Anthropic per-token prices
(2026-04). Update if Anthropic's pricing changes.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from app.config import get_settings
from app.schemas.state import DesignState, NodeMetric, RunMetrics

from .event_bus import emit


# Per-1k-token rates (USD) for the models we use.
_PRICING_PER_1K: dict[str, tuple[float, float]] = {
    # (input_per_1k, output_per_1k)
    "claude-sonnet-4-6": (0.003, 0.015),
    "claude-haiku-4-5-20251001": (0.001, 0.005),
}


def _cost_for(model: str, input_tokens: int, output_tokens: int) -> float:
    rate = _PRICING_PER_1K.get(model)
    if rate is None:
        # Fall back to Sonnet rates so a missing entry doesn't silently zero out cost.
        rate = _PRICING_PER_1K["claude-sonnet-4-6"]
    in_rate, out_rate = rate
    return (input_tokens / 1000.0) * in_rate + (output_tokens / 1000.0) * out_rate


# A bag accumulating per-node token counts during one node execution.
class _NodeTokenBag:
    __slots__ = ("input", "output", "model")

    def __init__(self) -> None:
        self.input = 0
        self.output = 0
        self.model = ""

    def add(self, input_tokens: int, output_tokens: int, model: str = "") -> None:
        self.input += input_tokens
        self.output += output_tokens
        if model and not self.model:
            self.model = model


_CURRENT_BAG: ContextVar[_NodeTokenBag | None] = ContextVar("silo_node_token_bag", default=None)


def record_llm_usage(input_tokens: int, output_tokens: int, model: str = "") -> None:
    """Called by agents (or the @instrumented_llm wrapper) after each LLM round-trip."""

    bag = _CURRENT_BAG.get()
    if bag is None:
        return
    bag.add(input_tokens, output_tokens, model)


def _ensure_metrics(state: DesignState) -> RunMetrics:
    if state.metrics is None:
        state.metrics = RunMetrics(
            run_id=state.session_id,
            started_at_ms=int(time.time() * 1000),
        )
    return state.metrics


def instrumented(
    node_name: str,
) -> Callable[[Callable[[DesignState], Awaitable[Any]]], Callable[[DesignState], Awaitable[Any]]]:
    """Decorator: wraps an async pipeline node to capture timing + token usage.

    Emits ``metrics_update`` after the node finishes; the per-node entry is
    appended to ``state.metrics.nodes`` so a final summary can be derived.
    """

    def decorator(func: Callable[[DesignState], Awaitable[Any]]):
        @functools.wraps(func)
        async def wrapper(state: DesignState):
            metrics = _ensure_metrics(state)
            started = int(time.time() * 1000)
            bag = _NodeTokenBag()
            token = _CURRENT_BAG.set(bag)
            status = "ok"
            error: str | None = None
            try:
                result = await func(state)
            except Exception as exc:  # surface, but record first
                status = "error"
                error = repr(exc)
                ended = int(time.time() * 1000)
                _record(node_name, state, metrics, started, ended, bag, status, error)
                raise
            else:
                ended = int(time.time() * 1000)
                _record(node_name, state, metrics, started, ended, bag, status, error)
                return result
            finally:
                _CURRENT_BAG.reset(token)

        return wrapper

    return decorator


def _record(
    node_name: str,
    state: DesignState,
    metrics: RunMetrics,
    started: int,
    ended: int,
    bag: _NodeTokenBag,
    status: str,
    error: str | None,
) -> None:
    feature_id = state.current_feature_id if node_name == "feature_pipeline" else None
    entry = NodeMetric(
        node=node_name,
        feature_id=feature_id,
        started_at_ms=started,
        ended_at_ms=ended,
        duration_ms=max(0, ended - started),
        input_tokens=bag.input,
        output_tokens=bag.output,
        retries=0,  # surfaced from RetryPolicy in a future iteration
        status=status,  # type: ignore[arg-type]
        error=error,
    )
    metrics.nodes.append(entry)
    metrics.total_input_tokens += bag.input
    metrics.total_output_tokens += bag.output
    metrics.ended_at_ms = ended
    metrics.total_cost_usd = sum(
        _cost_for(bag.model or _settings_model(), n.input_tokens, n.output_tokens)
        for n in metrics.nodes
    )
    emit({"type": "metrics_update", "node": entry.model_dump()})


def _settings_model() -> str:
    try:
        return get_settings().sonnet_model
    except Exception:
        return "claude-sonnet-4-6"


def finalize_metrics(state: DesignState) -> None:
    """Compute parallel_speedup + emit the metrics_summary event at end-of-run."""

    if state.metrics is None:
        return
    feature_nodes = [n for n in state.metrics.nodes if n.node == "feature_pipeline"]
    if feature_nodes:
        sum_durations = sum(n.duration_ms for n in feature_nodes)
        # Wall-clock for the parallel block = max(end) - min(start) across feature branches.
        wall = max(n.ended_at_ms for n in feature_nodes) - min(n.started_at_ms for n in feature_nodes)
        wall = max(1, wall)
        state.metrics.parallel_speedup = round(sum_durations / wall, 3)
    state.metrics.ended_at_ms = int(time.time() * 1000)
    emit({"type": "metrics_summary", "metrics": state.metrics.model_dump()})