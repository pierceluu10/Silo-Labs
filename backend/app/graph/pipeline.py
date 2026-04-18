from __future__ import annotations

import time
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
from app.schemas.state import AgentName, DesignState
from app.simulate.runner import run_simulation

from .event_bus import emit

AGENT_PANELS: dict[AgentName, str] = {
    "requirements_parser": "top-left",
    "pinout_resolver": "top-left",
    "clock_configurator": "top-right",
    "peripheral_configurator": "bottom-right",
    "errata_checker": "bottom-left",
    "wokwi_diagram_generator": "bottom-left",
    "code_composer": "bottom-right",
}


def _agent_start(agent: AgentName) -> float:
    emit({"type": "agent_start", "agent": agent, "timestamp": time.time()})
    return time.monotonic()


def _agent_complete(agent: AgentName, started: float) -> None:
    emit(
        {
            "type": "agent_complete",
            "agent": agent,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    )


async def _node_requirements(state: DesignState) -> DesignState:
    state.active_agent = "requirements_parser"
    t = _agent_start("requirements_parser")
    state.requirements = await parse_requirements(state.user_prompt)
    _agent_complete("requirements_parser", t)
    return state


async def _node_pinout(state: DesignState) -> DesignState:
    state.active_agent = "pinout_resolver"
    t = _agent_start("pinout_resolver")
    assert state.requirements is not None
    pins = await resolve_pinout(state.requirements)
    for p in pins:
        emit(
            {
                "type": "assign_pin",
                "pin_number": p.pin_number,
                "function": p.function.value,
                "peripheral_instance": p.peripheral_instance,
                "label": p.label,
                "wire_color": p.wire_color,
            }
        )
    state.pin_assignments = pins  # type: ignore[assignment]
    _agent_complete("pinout_resolver", t)
    return state


async def _node_clocks(state: DesignState) -> DesignState:
    state.active_agent = "clock_configurator"
    t = _agent_start("clock_configurator")
    assert state.requirements is not None
    clocks = await configure_clocks(state.requirements)
    for c in clocks:
        emit(
            {
                "type": "configure_clock",
                "clock_domain": c.clock_domain.value,
                "source": c.source.value,
                "freq_hz": c.freq_hz,
                "divider": c.divider,
            }
        )
    state.clock_configs = clocks  # type: ignore[assignment]
    _agent_complete("clock_configurator", t)
    return state


async def _node_peripheral(state: DesignState) -> DesignState:
    state.active_agent = "peripheral_configurator"
    t = _agent_start("peripheral_configurator")
    assert state.requirements is not None
    writes = await configure_peripheral(state.requirements)
    for w in writes:
        emit(
            {
                "type": "set_register",
                "peripheral": w.peripheral,
                "register": w.register,
                "address": w.address,
                "field_name": w.field_name,
                "value": w.value,
                "bit_offset": w.bit_offset,
                "bit_width": w.bit_width,
                "human_explanation": w.human_explanation,
            }
        )
    state.register_writes = writes  # type: ignore[assignment]
    _agent_complete("peripheral_configurator", t)
    return state


async def _node_errata(state: DesignState) -> DesignState:
    state.active_agent = "errata_checker"
    t = _agent_start("errata_checker")
    assert state.requirements is not None
    warnings = await check_errata(
        state.requirements, list(state.pin_assignments), list(state.register_writes)
    )
    for w in warnings:
        emit(
            {
                "type": "errata_warning",
                "errata_id": w.errata_id,
                "severity": w.severity,
                "description": w.description,
                "workaround": w.workaround,
            }
        )
    state.errata_warnings = warnings
    _agent_complete("errata_checker", t)
    return state


async def _node_wokwi(state: DesignState) -> DesignState:
    state.active_agent = "wokwi_diagram_generator"
    t = _agent_start("wokwi_diagram_generator")
    assert state.requirements is not None
    wires, diagram = await generate_diagram(state.requirements, list(state.pin_assignments))
    for w in wires:
        emit(
            {
                "type": "add_wire",
                "from_component": w.from_component,
                "from_pin": w.from_pin,
                "to_component": w.to_component,
                "to_pin": w.to_pin,
                "color": w.color.value,
            }
        )
    state.wires = wires  # type: ignore[assignment]
    state.wokwi_diagram = diagram
    _agent_complete("wokwi_diagram_generator", t)
    return state


async def _node_code(state: DesignState) -> DesignState:
    state.active_agent = "code_composer"
    t = _agent_start("code_composer")
    assert state.requirements is not None
    main_c, cmake = await compose_code(
        state.requirements,
        list(state.pin_assignments),
        list(state.clock_configs),
        list(state.register_writes),
    )
    state.generated_code = main_c
    state.cmake_content = cmake
    emit({"type": "code_chunk", "delta": main_c})
    emit({"type": "code_complete", "full_code": main_c})
    state.active_agent = None
    _agent_complete("code_composer", t)
    return state


async def _node_build(state: DesignState) -> DesignState:
    emit({"type": "build_start"})
    result = await build_firmware(state.generated_code, state.cmake_content)
    for line in result.stdout.splitlines():
        emit({"type": "build_log", "line": line})
    state.build_stdout = result.stdout
    state.build_success = result.success
    state.uf2_artifact_path = result.uf2_path
    if result.success and result.uf2_path:
        emit({"type": "build_success", "uf2_url": f"/api/artifacts/{state.session_id}/firmware.uf2"})
    else:
        emit({"type": "build_failure", "error": "build failed", "stderr": result.stdout[-2000:]})
    return state


async def _node_simulate(state: DesignState) -> DesignState:
    emit({"type": "simulate_start"})
    sim = await run_simulation(state.uf2_artifact_path, state.wokwi_diagram)
    for line in sim.log.splitlines():
        emit({"type": "simulate_output", "line": line})
    state.simulate_log = sim.log
    state.simulate_mode = sim.mode  # type: ignore[assignment]
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
    g.add_node("simulate", _node_simulate)

    g.set_entry_point("requirements")
    g.add_edge("requirements", "pinout")
    g.add_edge("pinout", "clocks")
    g.add_edge("clocks", "peripheral")
    g.add_edge("peripheral", "errata")
    g.add_edge("errata", "wokwi")
    g.add_edge("wokwi", "code")
    g.add_edge("code", "build")
    g.add_edge("build", "simulate")
    g.add_edge("simulate", END)

    return g.compile()


async def run_pipeline(user_prompt: str, session_id: str | None = None) -> DesignState:
    state = DesignState(session_id=session_id or uuid.uuid4().hex, user_prompt=user_prompt)
    pipeline = build_pipeline()
    result = await pipeline.ainvoke(state)
    if isinstance(result, DesignState):
        return result
    return DesignState.model_validate(result)
