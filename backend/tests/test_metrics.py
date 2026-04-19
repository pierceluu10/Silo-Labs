"""Metrics module tests: instrumented decorator + cost calculation + speedup."""

from __future__ import annotations

import asyncio

import pytest

from app.graph import metrics as metrics_mod
from app.graph.event_bus import EventBus, set_bus
from app.schemas.state import DesignState


@pytest.mark.asyncio
async def test_instrumented_records_node():
    bus = EventBus()
    set_bus(bus)
    state = DesignState(session_id="s-test", user_prompt="p")

    @metrics_mod.instrumented("noop")
    async def noop(s):
        await asyncio.sleep(0.001)
        return s

    out = await noop(state)
    assert out is state
    assert state.metrics is not None
    assert len(state.metrics.nodes) == 1
    n = state.metrics.nodes[0]
    assert n.node == "noop"
    assert n.status == "ok"
    assert n.duration_ms >= 0


@pytest.mark.asyncio
async def test_instrumented_records_token_usage():
    bus = EventBus()
    set_bus(bus)
    state = DesignState(session_id="s-tokens", user_prompt="p")

    @metrics_mod.instrumented("with-tokens")
    async def with_tokens(s):
        metrics_mod.record_llm_usage(input_tokens=1000, output_tokens=500, model="claude-sonnet-4-6")
        return s

    await with_tokens(state)
    assert state.metrics is not None
    n = state.metrics.nodes[0]
    assert n.input_tokens == 1000
    assert n.output_tokens == 500
    # Sonnet cost: 1000/1000 * 0.003 + 500/1000 * 0.015 = 0.003 + 0.0075 = 0.0105
    assert state.metrics.total_cost_usd == pytest.approx(0.0105, rel=1e-3)


@pytest.mark.asyncio
async def test_finalize_metrics_computes_parallel_speedup():
    bus = EventBus()
    set_bus(bus)
    state = DesignState(session_id="s-speed", user_prompt="p")

    @metrics_mod.instrumented("feature_pipeline")
    async def feat(s):
        # Each "feature" sleeps 25 ms; if there are 3 features running in
        # parallel the wall-clock should be ~25 ms not 75 ms => speedup ~3x.
        await asyncio.sleep(0.025)
        return s

    # Simulate three concurrent fan-out branches by gathering them.
    await asyncio.gather(feat(state), feat(state), feat(state))

    metrics_mod.finalize_metrics(state)
    assert state.metrics is not None
    assert state.metrics.parallel_speedup > 1.5  # genuine parallelism observed
    assert len([n for n in state.metrics.nodes if n.node == "feature_pipeline"]) == 3