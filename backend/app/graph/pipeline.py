from __future__ import annotations

import uuid

from langgraph.graph import END, StateGraph

from app.agents.clock_configurator import configure_clocks
from app.agents.code_composer import compose_code
from app.agents.errata_checker import check_errata
from app.agents.peripheral_configurator import configure_peripheral
from app.agents.pinout_resolver import resolve_pinout
from app.agents.requirements_parser import parse_requirements
from app.agents.wokwi_diagram_generator import generate_diagram
from app.build.compiler import build_firmware
from app.schemas.state import DesignState


async def _node_requirements(state: DesignState) -> DesignState:
    state.active_agent = "requirements_parser"
    state.requirements = await parse_requirements(state.user_prompt)
    return state


async def _node_pinout(state: DesignState) -> DesignState:
    state.active_agent = "pinout_resolver"
    assert state.requirements is not None
    state.pin_assignments = await resolve_pinout(state.requirements)  # type: ignore[assignment]
    return state


async def _node_clocks(state: DesignState) -> DesignState:
    state.active_agent = "clock_configurator"
    assert state.requirements is not None
    state.clock_configs = await configure_clocks(state.requirements)  # type: ignore[assignment]
    return state


async def _node_peripheral(state: DesignState) -> DesignState:
    state.active_agent = "peripheral_configurator"
    assert state.requirements is not None
    state.register_writes = await configure_peripheral(state.requirements)  # type: ignore[assignment]
    return state


async def _node_errata(state: DesignState) -> DesignState:
    state.active_agent = "errata_checker"
    assert state.requirements is not None
    state.errata_warnings = await check_errata(
        state.requirements, list(state.pin_assignments), list(state.register_writes)
    )
    return state


async def _node_wokwi(state: DesignState) -> DesignState:
    state.active_agent = "wokwi_diagram_generator"
    assert state.requirements is not None
    wires, diagram = await generate_diagram(state.requirements, list(state.pin_assignments))
    state.wires = wires  # type: ignore[assignment]
    state.wokwi_diagram = diagram
    return state


async def _node_code(state: DesignState) -> DesignState:
    state.active_agent = "code_composer"
    assert state.requirements is not None
    main_c, cmake = await compose_code(
        state.requirements,
        list(state.pin_assignments),
        list(state.clock_configs),
        list(state.register_writes),
    )
    state.generated_code = main_c
    state.cmake_content = cmake
    state.active_agent = None
    return state


async def _node_build(state: DesignState) -> DesignState:
    result = await build_firmware(state.generated_code, state.cmake_content)
    state.build_stdout = result.stdout
    state.build_success = result.success
    state.uf2_artifact_path = result.uf2_path
    state.pipeline_complete = True
    return state


def build_pipeline():
    g: StateGraph = StateGraph(DesignState)
    g.add_node("requirements", _node_requirements)
    g.add_node("pinout", _node_pinout)
    g.add_node("clocks", _node_clocks)
    g.add_node("peripheral", _node_peripheral)
    g.add_node("errata", _node_errata)
    g.add_node("wokwi", _node_wokwi)
    g.add_node("code", _node_code)
    g.add_node("build", _node_build)

    g.set_entry_point("requirements")
    g.add_edge("requirements", "pinout")
    g.add_edge("pinout", "clocks")
    g.add_edge("clocks", "peripheral")
    g.add_edge("peripheral", "errata")
    g.add_edge("errata", "wokwi")
    g.add_edge("wokwi", "code")
    g.add_edge("code", "build")
    g.add_edge("build", END)

    return g.compile()


async def run_pipeline(user_prompt: str, session_id: str | None = None) -> DesignState:
    state = DesignState(session_id=session_id or uuid.uuid4().hex, user_prompt=user_prompt)
    pipeline = build_pipeline()
    result = await pipeline.ainvoke(state)
    if isinstance(result, DesignState):
        return result
    return DesignState.model_validate(result)
