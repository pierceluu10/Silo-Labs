from __future__ import annotations

import asyncio
import time
import uuid

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from app.agents.clock_configurator import configure_clocks
from app.agents.code_composer import compose_code, split_main_and_cmake
from app.agents.errata_checker import check_errata
from app.agents.peripheral_configurator import configure_peripheral
from app.agents.pinout_resolver import resolve_pinout
from app.agents.requirements_parser import parse_requirements
from app.agents.supervisor import plan_features
from app.agents.wokwi_diagram_generator import generate_diagram
from app.build.compiler import build_firmware
from app.schemas.state import (
    AgentName,
    ClockConfigRecord,
    DesignState,
    FeatureOutputs,
    FeatureSpec,
    PinAssignmentRecord,
    RegisterWriteRecord,
    Requirements,
    RunPlan,
    WireConnectionRecord,
)
from app.simulate.runner import run_simulation

from .event_bus import emit

AGENT_PANELS: dict[AgentName, str] = {
    "supervisor": "top-left",
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
    "supervisor": "→ Decomposing your prompt into independent feature plans.\n",
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
    "supervisor": [
        ("read-prompt", "Reading user prompt"),
        ("identify-peripherals", "Identifying peripherals + devices"),
        ("decompose-features", "Decomposing into parallel features"),
        ("publish-plan", "Publishing run plan"),
    ],
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


async def _node_supervisor(state: DesignState) -> DesignState:
    """Decompose the prompt into feature specs the rest of the pipeline branches on."""

    state.active_agent = "supervisor"
    t = _agent_start("supervisor")
    _emit_pending("supervisor")
    plan = await plan_features(state.user_prompt, target_mcu=state.target_mcu)
    state.run_plan = plan
    feature_count = len(plan.features)
    devices = ", ".join(f.device_name for f in plan.features) or "—"
    _activity("supervisor", "read-prompt", "Read user prompt", "done")
    _activity("supervisor", "identify-peripherals", f"Devices: {devices}", "done")
    _activity(
        "supervisor",
        "decompose-features",
        f"Decomposed into {feature_count} feature(s)",
        "done",
    )
    emit(
        {
            "type": "run_plan",
            "features": [f.model_dump() for f in plan.features],
            "rationale": plan.rationale,
        }
    )
    _activity("supervisor", "publish-plan", "Published run plan to UI", "done")
    _agent_complete("supervisor", t)
    return state


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


def _feature_to_requirements(feature: FeatureSpec, base: Requirements | None) -> Requirements:
    """Build a Requirements object scoped to one feature for the per-feature agents."""

    return Requirements(
        peripheral_type=feature.peripheral_family,
        device_name=feature.device_name,
        device_address=base.device_address if base else None,
        baud_rate=base.baud_rate if base else None,
        description=feature.intent,
    )


def _route_to_feature_pipelines(state: DesignState):
    """Conditional edge: fan out one Send per feature in the plan.

    If the supervisor produced zero features (very simple prompts) we fall back
    to a single Send carrying the parsed requirements as an implicit feature so
    downstream agents always have something to work on.
    """

    plan = state.run_plan
    if plan and plan.features:
        return [
            Send(
                "feature_pipeline",
                {
                    "session_id": state.session_id,
                    "user_prompt": state.user_prompt,
                    "target_mcu": state.target_mcu,
                    "requirements": state.requirements,
                    "current_feature_id": f.id,
                    "run_plan": plan,
                },
            )
            for f in plan.features
        ]
    # Synthetic single feature so the join + downstream stages don't see an empty plan.
    if state.requirements is not None:
        synthetic = FeatureSpec(
            id="default",
            peripheral_family=state.requirements.peripheral_type,
            device_name=state.requirements.device_name,
            intent=state.requirements.description,
        )
        return [
            Send(
                "feature_pipeline",
                {
                    "session_id": state.session_id,
                    "user_prompt": state.user_prompt,
                    "target_mcu": state.target_mcu,
                    "requirements": state.requirements,
                    "current_feature_id": synthetic.id,
                    "run_plan": RunPlan(features=[synthetic]),
                },
            )
        ]
    return []


async def _node_feature_pipeline(state: DesignState) -> dict:
    """One feature's pinout -> peripheral -> wiring, run in parallel with sibling Sends.

    Writes results into ``state.feature_outputs[<feature_id>]`` (the merge
    reducer on that field handles concurrent writes).
    """

    feature_id = state.current_feature_id or "default"
    plan = state.run_plan
    feature: FeatureSpec | None = None
    if plan:
        feature = next((f for f in plan.features if f.id == feature_id), None)
    if feature is None and state.requirements is not None:
        feature = FeatureSpec(
            id=feature_id,
            peripheral_family=state.requirements.peripheral_type,
            device_name=state.requirements.device_name,
            intent=state.requirements.description,
        )
    if feature is None:
        # Nothing to do — return an empty FeatureOutputs so the reducer still merges.
        return {"feature_outputs": {feature_id: FeatureOutputs(feature_id=feature_id)}}

    requirements = _feature_to_requirements(feature, state.requirements)

    # ---- Pinout (per feature) -------------------------------------------------
    state.active_agent = "pinout_resolver"
    t_pin = _agent_start("pinout_resolver")
    _emit_pending("pinout_resolver")
    _activity(
        "pinout_resolver",
        "read-datasheet",
        f"[{feature.id}] Reading {feature.device_name} datasheet pinout",
        "done",
    )
    pins_models = await resolve_pinout(requirements)
    pin_records: list[PinAssignmentRecord] = []
    for p in pins_models:
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
            f"pin-{feature.id}-{p.pin_number}",
            f"[{feature.id}] GP{p.pin_number} → {p.peripheral_instance} {p.label}",
            "done",
        )
        pin_records.append(PinAssignmentRecord.model_validate(p.model_dump()))
    inst = pins_models[0].peripheral_instance if pins_models else "—"
    _activity(
        "pinout_resolver",
        f"pick-instance-{feature.id}",
        f"[{feature.id}] Selected instance: {inst}",
        "done",
    )
    _activity(
        "pinout_resolver",
        f"validate-no-uart-debug-{feature.id}",
        f"[{feature.id}] No GP0/GP1 collisions",
        "done",
    )
    _agent_complete("pinout_resolver", t_pin)

    # ---- Peripheral config (per feature) -------------------------------------
    state.active_agent = "peripheral_configurator"
    t_per = _agent_start("peripheral_configurator")
    _emit_pending("peripheral_configurator")
    _activity(
        "peripheral_configurator",
        f"read-svd-{feature.id}",
        f"[{feature.id}] Reading SVD for {feature.peripheral_family}",
        "done",
    )
    writes_models = await configure_peripheral(requirements)
    register_records: list[RegisterWriteRecord] = []
    if not writes_models:
        _activity(
            "peripheral_configurator",
            f"plan-fields-{feature.id}",
            f"[{feature.id}] Using pico-sdk high-level APIs (no direct register writes)",
            "done",
        )
    else:
        _activity(
            "peripheral_configurator",
            f"plan-fields-{feature.id}",
            f"[{feature.id}] Planning {len(writes_models)} register field writes",
            "done",
        )
        for w in writes_models:
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
                f"reg-{feature.id}-{w.peripheral}-{w.register}-{w.field_name}",
                f"[{feature.id}] {w.peripheral}.{w.register}.{w.field_name} = {w.value}",
                "done",
            )
            register_records.append(RegisterWriteRecord.model_validate(w.model_dump()))
    _agent_complete("peripheral_configurator", t_per)

    # ---- Wiring (per feature, wires only — diagram render happens after join) -
    state.active_agent = "wokwi_diagram_generator"
    t_wir = _agent_start("wokwi_diagram_generator")
    _emit_pending("wokwi_diagram_generator")
    _activity(
        "wokwi_diagram_generator",
        f"select-part-{feature.id}",
        f"[{feature.id}] Selecting Wokwi part for {feature.device_name}",
        "done",
    )
    wires_models, _diagram = await generate_diagram(requirements, list(pins_models))
    wire_records: list[WireConnectionRecord] = []
    for w in wires_models:
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
        wire_records.append(WireConnectionRecord.model_validate(w.model_dump()))
    _activity(
        "wokwi_diagram_generator",
        f"wire-signals-{feature.id}",
        f"[{feature.id}] Wired {len(wires_models)} signal lines",
        "done",
    )
    _finalize_pending("wokwi_diagram_generator")
    _agent_complete("wokwi_diagram_generator", t_wir)

    return {
        "feature_outputs": {
            feature.id: FeatureOutputs(
                feature_id=feature.id,
                pin_assignments=pin_records,
                register_writes=register_records,
                wires=wire_records,
            )
        }
    }


async def _node_join_features(state: DesignState) -> DesignState:
    """Aggregate all feature_outputs back into the top-level design fields.

    Runs once after every Send branch from ``_route_to_feature_pipelines``
    has completed (LangGraph naturally fans in here).
    """

    pin_assignments: list[PinAssignmentRecord] = []
    register_writes: list[RegisterWriteRecord] = []
    wires: list[WireConnectionRecord] = []
    for fid in sorted(state.feature_outputs):
        fo = state.feature_outputs[fid]
        pin_assignments.extend(fo.pin_assignments)
        register_writes.extend(fo.register_writes)
        wires.extend(fo.wires)
    state.pin_assignments = pin_assignments
    state.register_writes = register_writes
    state.wires = wires
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


async def _node_code(state: DesignState) -> DesignState:
    state.active_agent = "code_composer"
    t = _agent_start("code_composer")
    _emit_pending("code_composer")
    assert state.requirements is not None
    _activity("code_composer", "includes", "Drafting includes + pin macros", "done")

    files = await compose_code(
        state.requirements,
        list(state.pin_assignments),
        list(state.clock_configs),
        list(state.register_writes),
        target_mcu=state.target_mcu,
        build_error_hint=state.last_build_error_hint,
    )
    state.generated_files = files
    main_c, cmake = split_main_and_cmake(files)
    state.generated_code = main_c
    state.cmake_content = cmake

    extra_files = [f.path for f in files if f.path not in {"main.c", "CMakeLists.txt"}]
    _activity("code_composer", "init", f"Wrote {state.requirements.device_name} init sequence", "done")
    _activity("code_composer", "loop", "Wrote main loop with printf cadence", "done")
    _activity(
        "code_composer",
        "cmake",
        f"Composed CMakeLists + {len(extra_files)} extra file(s)" if extra_files else "Composed CMakeLists target",
        "done",
    )
    emit(
        {
            "type": "generated_files",
            "files": [f.model_dump() for f in files],
        }
    )

    _activity("code_composer", "stream", "Streaming code to editor…", "active")
    # Typewriter-style stream of main.c so the central editor fills progressively.
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
    files = state.generated_files or [
        # Legacy fallback if some path skipped multi-file generation.
        # GeneratedFile import lives inline to avoid cycles with state.
    ]
    if not files:
        from app.schemas.state import GeneratedFile

        files = [
            GeneratedFile(path="main.c", content=state.generated_code),
            GeneratedFile(path="CMakeLists.txt", content=state.cmake_content),
        ]
    result = await build_firmware(files)
    for line in result.stdout.splitlines():
        emit({"type": "build_log", "line": line})
    state.build_stdout = result.stdout
    state.build_success = result.success
    state.uf2_artifact_path = result.uf2_path
    state.elf_artifact_path = result.elf_path
    if result.success and result.uf2_path:
        # Successful build clears any prior retry hint so a future failure routes fresh.
        state.last_build_error_hint = None
        emit({"type": "build_success", "uf2_url": f"/api/artifacts/{state.session_id}/firmware.uf2"})
    else:
        # Stash the tail of stderr so the conditional retry edge can hand it to code_composer.
        state.last_build_error_hint = result.stdout[-1500:]
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


async def _node_render_diagram(state: DesignState) -> DesignState:
    """Render the merged Wokwi diagram.json from all per-feature wires.

    The per-feature pipeline nodes only emit wire records (and per-feature
    `add_wire` SSE events). Building the actual diagram JSON is global because
    Wokwi expects exactly one diagram per project.
    """

    if not state.wires or state.requirements is None:
        return state
    from app.agents.wokwi_diagram_generator import _render_diagram_json
    from app.knowledge.graph import get_graph

    device_key = state.requirements.device_name.lower()
    diagram = _render_diagram_json(device_key, [w for w in state.wires])
    state.wokwi_diagram = diagram
    spec = get_graph().get_wokwi_component(device_key)
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
    return state


def build_pipeline():
    g: StateGraph = StateGraph(DesignState)
    g.add_node("supervisor", _node_supervisor)
    g.add_node("requirements", _node_requirements)
    g.add_node("feature_pipeline", _node_feature_pipeline)
    g.add_node("join_features", _node_join_features)
    g.add_node("clocks", _node_clocks)
    g.add_node("errata", _node_errata)
    g.add_node("render_diagram", _node_render_diagram)
    g.add_node("code", _node_code)
    g.add_node("build", _node_build)
    g.add_node("simulate", _node_simulate)

    g.set_entry_point("supervisor")
    g.add_edge("supervisor", "requirements")
    # Fan out: one Send per feature -> feature_pipeline (parallel branches).
    g.add_conditional_edges("requirements", _route_to_feature_pipelines, ["feature_pipeline"])
    g.add_edge("feature_pipeline", "join_features")
    g.add_edge("join_features", "clocks")
    g.add_edge("clocks", "errata")
    g.add_edge("errata", "render_diagram")
    g.add_edge("render_diagram", "code")
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
