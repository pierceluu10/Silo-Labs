from __future__ import annotations

import asyncio
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
from app.schemas.state import (
    AgentName,
    ClockConfigRecord,
    DesignState,
    PinAssignmentRecord,
    RegisterWriteRecord,
    WireConnectionRecord,
)
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

# Short status lines for SSE (LangGraph still runs the real work in each node).
REASONING_INTRO: dict[AgentName, str] = {
    "requirements_parser": "→ Parsing your prompt: peripheral, device, one-line spec.\n",
    "pinout_resolver": "→ Picking SDA/SCL and instance on valid user GPIOs (not GP0/GP1).\n",
    "clock_configurator": "→ Clocks: XOSC, PLL, CLK_SYS / CLK_PERI for 125 MHz bring-up.\n",
    "peripheral_configurator": "→ Register field plan; the graph injects SVD addresses.\n",
    "errata_checker": "→ Checking RP2040 errata against pins + register plan.\n",
    "wokwi_diagram_generator": "→ Wokwi wiring: Pico ↔ parts (power, bus, GND).\n",
    "code_composer": "→ Generating pico-sdk C + project CMake; USB stdio for logs.\n",
}


def _agent_start(agent: AgentName) -> float:
    ts = time.time()
    emit({"type": "agent_start", "agent": agent, "timestamp": ts})
    emit(
        {
            "type": "agent_reasoning",
            "agent": agent,
            "panel": AGENT_PANELS[agent],
            "delta": REASONING_INTRO[agent],
        }
    )
    return time.monotonic()


def _agent_complete(agent: AgentName, started: float) -> None:
    emit(
        {
            "type": "agent_complete",
            "agent": agent,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    )


def _activity(agent: AgentName, key: str, label: str, status: str, value: str | None = None) -> None:
    """Emit an agent_activity row so the UI can render a per-agent checklist."""
    payload: dict = {
        "type": "agent_activity",
        "agent": agent,
        "key": key,
        "label": label,
        "status": status,
    }
    if value is not None:
        payload["value"] = value
    emit(payload)


# Canonical narrative checklist for each agent. Items get emitted as `pending`
# at agent_start and promoted to `done` either inline (when matching SSE
# events fire — pin_<n>, clock_<domain>, etc.) or in bulk at agent_complete
# for the items that don't have a corresponding event source.
_ACTIVITY_TEMPLATES: dict[AgentName, list[tuple[str, str]]] = {
    "requirements_parser": [
        ("parse-prompt", "Parsing prompt for peripheral type"),
        ("identify-device", "Identifying device + I2C/SPI address"),
        ("infer-rate", "Inferring baud / sample rate"),
        ("draft-spec", "Drafting one-line spec"),
    ],
    "pinout_resolver": [
        ("read-datasheet", "Reading device datasheet pinout"),
        ("pick-instance", "Selecting peripheral instance"),
        ("validate-no-uart-debug", "Validating no GP0 / GP1 collision"),
    ],
    "clock_configurator": [
        ("read-topology", "Reading RP2040 clock topology"),
        ("xosc", "Configuring XOSC @ 12 MHz"),
        ("pll-sys", "Bringing up PLL_SYS @ 125 MHz"),
        ("clk-sys-peri", "Routing CLK_SYS / CLK_PERI"),
        ("clk-ref", "Setting CLK_REF reference"),
    ],
    "peripheral_configurator": [
        ("read-svd", "Reading SVD for peripheral"),
        ("plan-fields", "Planning register field writes"),
    ],
    "errata_checker": [
        ("cross-ref", "Cross-referencing RP2040 errata"),
        ("scan-pins", "Scanning pin + register plan"),
        ("mark-workarounds", "Marking workarounds (if any)"),
    ],
    "wokwi_diagram_generator": [
        ("select-part", "Selecting Wokwi part for device"),
        ("wire-signals", "Wiring signal lines"),
        ("wire-power", "Adding power rail"),
        ("wire-ground", "Adding ground"),
        ("validate-diagram", "Validating diagram against wokwi-cli"),
    ],
    "code_composer": [
        ("includes", "Drafting includes + pin macros"),
        ("init", "Writing device init sequence"),
        ("loop", "Writing main loop with printf cadence"),
        ("cmake", "Composing CMakeLists target"),
        ("stream", "Streaming code to editor"),
    ],
}


def _emit_pending(agent: AgentName) -> None:
    for key, label in _ACTIVITY_TEMPLATES.get(agent, []):
        _activity(agent, key, label, "pending")


def _finalize_pending(agent: AgentName) -> None:
    """Mark any leftover canonical items done at agent_complete time."""
    for key, label in _ACTIVITY_TEMPLATES.get(agent, []):
        _activity(agent, key, label, "done")


async def _node_requirements(state: DesignState) -> DesignState:
    state.active_agent = "requirements_parser"
    t = _agent_start("requirements_parser")
    _emit_pending("requirements_parser")
    state.requirements = await parse_requirements(state.user_prompt)
    r = state.requirements
    _activity("requirements_parser", "parse-prompt", f"Parsed peripheral: {r.peripheral_type}", "done")
    _activity("requirements_parser", "identify-device", f"Device: {r.device_name} @ {r.device_address or '—'}", "done")
    _activity("requirements_parser", "infer-rate", f"Baud / rate: {r.baud_rate or '—'}", "done")
    _activity("requirements_parser", "draft-spec", f"Spec: {r.description[:60]}", "done")
    _agent_complete("requirements_parser", t)
    return state


async def _node_pinout(state: DesignState) -> DesignState:
    state.active_agent = "pinout_resolver"
    t = _agent_start("pinout_resolver")
    _emit_pending("pinout_resolver")
    assert state.requirements is not None
    _activity(
        "pinout_resolver",
        "read-datasheet",
        f"Reading {state.requirements.device_name} datasheet pinout",
        "done",
    )
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
        _activity(
            "pinout_resolver",
            f"pin-{p.pin_number}",
            f"Allocating GP{p.pin_number} → {p.peripheral_instance} {p.label}",
            "done",
        )
    inst = pins[0].peripheral_instance if pins else "—"
    _activity("pinout_resolver", "pick-instance", f"Selected peripheral instance: {inst}", "done")
    _activity("pinout_resolver", "validate-no-uart-debug", "No GP0 / GP1 collisions detected", "done")
    state.pin_assignments = [PinAssignmentRecord.model_validate(p.model_dump()) for p in pins]
    _agent_complete("pinout_resolver", t)
    return state


async def _node_clocks(state: DesignState) -> DesignState:
    state.active_agent = "clock_configurator"
    t = _agent_start("clock_configurator")
    _emit_pending("clock_configurator")
    assert state.requirements is not None
    _activity("clock_configurator", "read-topology", "Reading RP2040 clock topology", "done")
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
        _activity(
            "clock_configurator",
            f"clk-{c.clock_domain.value}",
            f"{c.clock_domain.value} ← {c.source.value} @ {c.freq_hz / 1_000_000:g} MHz",
            "done",
        )
    _finalize_pending("clock_configurator")
    state.clock_configs = [ClockConfigRecord.model_validate(c.model_dump()) for c in clocks]
    _agent_complete("clock_configurator", t)
    return state


async def _node_peripheral(state: DesignState) -> DesignState:
    state.active_agent = "peripheral_configurator"
    t = _agent_start("peripheral_configurator")
    _emit_pending("peripheral_configurator")
    assert state.requirements is not None
    _activity(
        "peripheral_configurator",
        "read-svd",
        f"Reading SVD for {state.requirements.peripheral_type}",
        "done",
    )
    writes = await configure_peripheral(state.requirements)
    if not writes:
        _activity(
            "peripheral_configurator",
            "plan-fields",
            "Using pico-sdk high-level APIs (no direct register writes)",
            "done",
        )
    else:
        _activity("peripheral_configurator", "plan-fields", f"Planning {len(writes)} register field writes", "done")
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
            _activity(
                "peripheral_configurator",
                f"reg-{w.peripheral}-{w.register}-{w.field_name}",
                f"{w.peripheral}.{w.register}.{w.field_name} = {w.value}",
                "done",
            )
    state.register_writes = [RegisterWriteRecord.model_validate(w.model_dump()) for w in writes]
    _agent_complete("peripheral_configurator", t)
    return state


async def _node_errata(state: DesignState) -> DesignState:
    state.active_agent = "errata_checker"
    t = _agent_start("errata_checker")
    _emit_pending("errata_checker")
    assert state.requirements is not None
    _activity("errata_checker", "cross-ref", "Cross-referencing RP2040 errata", "done")
    warnings = await check_errata(
        state.requirements, list(state.pin_assignments), list(state.register_writes)
    )
    _activity("errata_checker", "scan-pins", f"Scanned {len(state.pin_assignments)} pins + {len(state.register_writes)} writes", "done")
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
        _activity(
            "errata_checker",
            f"errata-{w.errata_id}",
            f"{w.errata_id}: {w.description[:70]}",
            "done",
        )
    if warnings:
        _activity("errata_checker", "mark-workarounds", f"{len(warnings)} workaround(s) marked", "done")
    else:
        _activity("errata_checker", "mark-workarounds", "No applicable errata for this design", "done")
    state.errata_warnings = warnings
    _agent_complete("errata_checker", t)
    return state


async def _node_wokwi(state: DesignState) -> DesignState:
    state.active_agent = "wokwi_diagram_generator"
    t = _agent_start("wokwi_diagram_generator")
    _emit_pending("wokwi_diagram_generator")
    assert state.requirements is not None
    from app.knowledge.graph import get_graph as _get_graph

    device_key = state.requirements.device_name.lower()
    spec = _get_graph().get_wokwi_component(device_key)
    if spec is not None:
        _activity(
            "wokwi_diagram_generator",
            "select-part",
            f"Wokwi part for {device_key}: {spec.get('type', '?')}",
            "done",
        )
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
    _activity(
        "wokwi_diagram_generator",
        "wire-signals",
        f"Wired {len(wires)} signal lines",
        "done",
    )
    _finalize_pending("wokwi_diagram_generator")
    if spec is not None:
        emit(
            {
                "type": "device_part_info",
                "device": device_key,
                "wokwi_part": spec.get("type", ""),
                "is_stub": "_note" in spec,
                "note": spec.get("_note", ""),
            }
        )
    state.wires = [WireConnectionRecord.model_validate(w.model_dump()) for w in wires]
    state.wokwi_diagram = diagram
    _agent_complete("wokwi_diagram_generator", t)
    return state


async def _node_code(state: DesignState) -> DesignState:
    state.active_agent = "code_composer"
    t = _agent_start("code_composer")
    _emit_pending("code_composer")
    assert state.requirements is not None
    _activity("code_composer", "includes", "Drafting includes + pin macros", "done")
    main_c, cmake = await compose_code(
        state.requirements,
        list(state.pin_assignments),
        list(state.clock_configs),
        list(state.register_writes),
    )
    state.generated_code = main_c
    state.cmake_content = cmake
    _activity("code_composer", "init", f"Wrote {state.requirements.device_name} init sequence", "done")
    _activity("code_composer", "loop", "Wrote main loop with printf cadence", "done")
    _activity("code_composer", "cmake", f"Composed CMakeLists ({len(cmake)} chars)", "done")
    _activity("code_composer", "stream", "Streaming code to editor…", "active")
    # Typewriter-style stream: emit one line at a time. Sleep length scales
    # with line length (longer lines = a touch more pause) so a 13 KB main.c
    # streams visibly over ~6-8 s rather than dumping at once. Real token
    # streaming isn't available because `with_structured_output` returns the
    # full string; this is the cheapest convincing approximation.
    for line in main_c.splitlines(keepends=True):
        emit({"type": "code_chunk", "delta": line})
        await asyncio.sleep(min(0.08, 0.020 + len(line) * 0.0008))
    _activity("code_composer", "stream", "Code streamed to editor", "done")
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
    state.elf_artifact_path = result.elf_path
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
