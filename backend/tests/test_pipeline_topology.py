"""Topology test: verifies the supervisor + parallel fan-out + retry edges
all land in the compiled LangGraph graph. Pure structural assertions, no LLM
calls.
"""

from __future__ import annotations

import pytest

from app.graph.pipeline import build_pipeline


@pytest.fixture(scope="module")
def graph():
    return build_pipeline().get_graph()


def test_supervisor_is_entry(graph):
    edges = list(graph.edges)
    starts = {e.target for e in edges if e.source == "__start__"}
    assert "supervisor" in starts


def test_all_expected_nodes_present(graph):
    expected = {
        "supervisor",
        "requirements",
        "feature_pipeline",
        "join_features",
        "clocks",
        "errata",
        "render_diagram",
        "code",
        "build",
        "simulate",
    }
    nodes = set(graph.nodes)
    missing = expected - nodes
    assert not missing, f"Missing nodes: {missing}"


def test_parallel_fanout_from_requirements(graph):
    """requirements -> feature_pipeline must be a CONDITIONAL edge (Send fan-out)."""

    edges = [e for e in graph.edges if e.source == "requirements" and e.target == "feature_pipeline"]
    assert edges, "Expected a requirements -> feature_pipeline edge"
    assert any(getattr(e, "conditional", False) for e in edges), (
        "Expected the requirements -> feature_pipeline edge to be conditional (Send fan-out)"
    )


def test_join_after_feature(graph):
    edges = list(graph.edges)
    assert any(e.source == "feature_pipeline" and e.target == "join_features" for e in edges)


def test_retry_edge_build_to_code(graph):
    edges = [e for e in graph.edges if e.source == "build" and e.target == "code"]
    assert edges, "Expected a conditional build -> code retry edge"
    assert any(getattr(e, "conditional", False) for e in edges)


def test_retry_edge_errata_back_to_requirements(graph):
    edges = [e for e in graph.edges if e.source == "errata" and e.target == "requirements"]
    assert edges, "Expected a conditional errata -> requirements retry edge"
    assert any(getattr(e, "conditional", False) for e in edges)


def test_simulate_reaches_end(graph):
    edges = list(graph.edges)
    assert any(e.source == "simulate" and e.target == "__end__" for e in edges)