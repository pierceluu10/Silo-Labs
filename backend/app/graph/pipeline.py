from __future__ import annotations

import asyncio
import time
import uuid

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import RetryPolicy, Send

from app.agents.clock_configurator import configure_clocks
from app.agents.code_composer import compose_code, is_core_file, split_main_and_cmake
from app.agents.errata_checker import check_errata
from app.agents.peripheral_configurator import configure_peripheral
from app.agents.pinout_resolver import resolve_pinout
from app.agents.requirements_parser import parse_requirements
from app.agents.supervisor import plan_features
from app.agents.wokwi_diagram_generator import generate_diagram
from app.knowledge.graph import (
    DEFAULT_MCU,
    PinAssignment,
    PinConflictError,
    current_mcu,
    get_graph,
    set_target_mcu,
)
from app.mcu import McuProfile, get_profile
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
from app.simulate.runner import stream_simulation

from .event_bus import emit
from .metrics import finalize_metrics, instrumented, reset_aggregator

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
# Placeholders are filled from the target MCU profile.
REASONING_INTRO: dict[AgentName, str] = {
    "supervisor": "→ Decomposing your prompt into independent feature plans for {mcu}.\n",
    "requirements_parser": "→ Parsing your prompt: peripheral, device, one-line spec.\n",
    "pinout_resolver": "→ Picking pins + instance from {mcu} pin mux docs (RAG-grounded).\n",
    "clock_configurator": "→ Clocks: {clock}.\n",
    "peripheral_configurator": "→ Register field plan from retrieved {mcu} specs; the graph injects SVD addresses.\n",
    "errata_checker": "→ Checking {mcu} errata against pins + register plan.\n",
    "wokwi_diagram_generator": "→ Wokwi wiring: {board} ↔ parts (power, bus, GND).\n",
    "code_composer": "→ Generating {sdk} firmware grounded on retrieved {mcu} docs.\n",
}


def _profile() -> McuProfile:
    return get_profile(current_mcu())


def _fill(template: str) -> str:
    profile = _profile()
    return template.format(
        mcu=profile.display_name,
        board=profile.board_name,
        sdk=profile.sdk_label,
        clock=profile.clock_hint.description,
    )


def _agent_start(agent: AgentName) -> float:
    ts = time.time()
    emit({"type": "agent_start", "agent": agent, "timestamp": ts})
    emit(
        {
            "type": "agent_reasoning",
            "agent": agent,
            "panel": AGENT_PANELS[agent],
            "delta": _fill(REASONING_INTRO[agent]),
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
        ("validate-no-uart-debug", "Validating reserved / debug pins are untouched"),
    ],
    "clock_configurator": [
        ("read-topology", "Reading {mcu} clock tree"),
        ("oscillator", "Configuring reference oscillator"),
        ("pll", "Bringing up the system PLL"),
        ("bus-clocks", "Routing CPU / peripheral bus clocks"),
    ],
    "peripheral_configurator": [
        ("read-svd", "Reading SVD for peripheral"),
        ("plan-fields", "Planning register field writes"),
    ],
    "errata_checker": [
        ("cross-ref", "Cross-referencing {mcu} errata"),
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
        ("cmake", "Composing {sdk} build files"),
        ("stream", "Streaming code to editor"),
    ],
}


def _emit_pending(agent: AgentName) -> None:
    for key, label in _ACTIVITY_TEMPLATES.get(agent, []):
        _activity(agent, key, _fill(label), "pending")


def _finalize_pending(agent: AgentName) -> None:
    """Mark any leftover canonical items done at agent_complete time."""
    for key, label in _ACTIVITY_TEMPLATES.get(agent, []):
        _activity(agent, key, _fill(label), "done")


@instrumented("supervisor")
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


@instrumented("requirements")
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


def _feature_send(
    state: DesignState, feature_id: str, plan: RunPlan | None, pin_conflicts: dict[str, str] | None = None
) -> Send:
    return Send(
        "feature_pipeline",
        {
            "session_id": state.session_id,
            "user_prompt": state.user_prompt,
            "target_mcu": state.target_mcu,
            "requirements": state.requirements,
            "current_feature_id": feature_id,
            "run_plan": plan,
            "pin_conflicts": pin_conflicts or {},
        },
    )


def _route_to_feature_pipelines(state: DesignState):
    """Conditional edge: fan out one Send per feature in the plan.

    If the supervisor produced zero features (very simple prompts) we fall back
    to a single Send carrying the parsed requirements as an implicit feature so
    downstream agents always have something to work on.
    """

    plan = state.run_plan
    if plan and plan.features:
        return [_feature_send(state, f.id, plan) for f in plan.features]
    # Synthetic single feature so the join + downstream stages don't see an empty plan.
    if state.requirements is not None:
        synthetic = FeatureSpec(
            id="default",
            peripheral_family=state.requirements.peripheral_type,
            device_name=state.requirements.device_name,
            intent=state.requirements.description,
        )
        return [_feature_send(state, synthetic.id, RunPlan(features=[synthetic]))]
    return []


@instrumented("feature_pipeline")
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
    pins_models = await resolve_pinout(requirements, state.pin_conflicts.get(feature.id))
    pin_records: list[PinAssignmentRecord] = []
    for p in pins_models:
        emit(
            {
                "type": "assign_pin",
                "pin_number": p.pin_number,
                "pin_name": p.pin_name,
                "function": p.function.value,
                "peripheral_instance": p.peripheral_instance,
                "label": p.label,
                "wire_color": p.wire_color,
            }
        )
        _activity(
            "pinout_resolver",
            f"pin-{feature.id}-{p.pin_number}",
            f"[{feature.id}] {p.pin_name} → {p.peripheral_instance} {p.label}",
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
        f"[{feature.id}] Pins checked against {_profile().display_name} pin rules",
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
            f"[{feature.id}] Using {_profile().sdk_label} driver APIs (no direct register writes)",
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


def _find_pin_conflicts(feature_outputs: dict[str, FeatureOutputs]) -> dict[str, str]:
    """Map each feature whose pins collide with an earlier feature (or itself) to a retry hint.

    Features are checked in sorted id order, so the first feature to claim a pin keeps it.
    """

    graph = get_graph()
    claimed: list[PinAssignment] = []
    conflicts: dict[str, str] = {}
    for fid in sorted(feature_outputs):
        mine = [PinAssignment(p.pin_number, p.function.value) for p in feature_outputs[fid].pin_assignments]
        try:
            graph.check_pin_conflicts([*claimed, *mine])
        except PinConflictError as err:
            taken = ", ".join(str(n) for n in sorted({a.pin_number for a in claimed}))
            conflicts[fid] = f"{err}. Pins already claimed by other features: {taken or 'none'}. Choose different pins."
            continue
        claimed.extend(mine)
    return conflicts


@instrumented("join_features")
async def _node_join_features(state: DesignState) -> DesignState:
    """Check cross-feature pin conflicts, then aggregate feature_outputs into the top-level design fields.

    Runs once after every Send branch from ``_route_to_feature_pipelines``
    has completed (LangGraph naturally fans in here). Conflicting features are
    re-dispatched once by ``_route_after_join``; a conflict that survives the
    retry fails the run rather than emitting firmware with a double-assigned pin.
    """

    conflicts = _find_pin_conflicts(state.feature_outputs)
    if conflicts and state.pin_conflict_retries >= _MAX_PIN_CONFLICT_RETRIES:
        raise PinConflictError("; ".join(conflicts.values()))
    state.pin_conflicts = conflicts
    if conflicts:
        # Counted here, not in the router: LangGraph drops state changes made inside routers.
        state.pin_conflict_retries += 1
        for fid, hint in conflicts.items():
            _activity(
                "pinout_resolver",
                f"pin-conflict-{fid}",
                f"[{fid}] Pin conflict, re-resolving: {hint[:70]}",
                "active",
            )
        return state

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


@instrumented("clocks")
async def _node_clocks(state: DesignState) -> DesignState:
    state.active_agent = "clock_configurator"
    t = _agent_start("clock_configurator")
    _emit_pending("clock_configurator")
    assert state.requirements is not None
    _activity("clock_configurator", "read-topology", _fill("Reading {mcu} clock tree"), "done")
    clocks = await configure_clocks(state.requirements)
    for c in clocks:
        emit(
            {
                "type": "configure_clock",
                "clock_domain": c.clock_domain,
                "source": c.source,
                "freq_hz": c.freq_hz,
                "divider": c.divider,
            }
        )
        _activity(
            "clock_configurator",
            f"clk-{c.clock_domain}",
            f"{c.clock_domain} ← {c.source} @ {c.freq_hz / 1_000_000:g} MHz",
            "done",
        )
    _finalize_pending("clock_configurator")
    state.clock_configs = [ClockConfigRecord.model_validate(c.model_dump()) for c in clocks]
    _agent_complete("clock_configurator", t)
    return state


@instrumented("errata")
async def _node_errata(state: DesignState) -> DesignState:
    state.active_agent = "errata_checker"
    t = _agent_start("errata_checker")
    _emit_pending("errata_checker")
    assert state.requirements is not None
    _activity("errata_checker", "cross-ref", _fill("Cross-referencing {mcu} errata"), "done")
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


@instrumented("code")
async def _node_code(state: DesignState) -> DesignState:
    state.active_agent = "code_composer"
    t = _agent_start("code_composer")
    _emit_pending("code_composer")
    assert state.requirements is not None
    _activity("code_composer", "includes", "Drafting includes + pin macros", "done")

    # Combined retry hint: build failure + critical errata workaround.
    hint_chunks: list[str] = []
    if state.last_errata_hint:
        hint_chunks.append("Critical errata workarounds:\n" + state.last_errata_hint)
    if state.last_build_error_hint:
        hint_chunks.append("Previous build stderr:\n" + state.last_build_error_hint)
    combined_hint = "\n\n".join(hint_chunks) if hint_chunks else None
    files = await compose_code(
        state.requirements,
        list(state.pin_assignments),
        list(state.clock_configs),
        list(state.register_writes),
        target_mcu=state.target_mcu,
        build_error_hint=combined_hint,
    )
    state.generated_files = files
    main_c, cmake = split_main_and_cmake(files)
    state.generated_code = main_c
    state.cmake_content = cmake

    extra_files = [f.path for f in files if not is_core_file(f.path)]
    _activity("code_composer", "init", f"Wrote {state.requirements.device_name} init sequence", "done")
    _activity("code_composer", "loop", "Wrote main loop with printf cadence", "done")
    _activity(
        "code_composer",
        "cmake",
        f"Composed build files + {len(extra_files)} extra file(s)" if extra_files else "Composed build files",
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


@instrumented("build")
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
    profile = _profile()
    if profile.build_firmware is None:
        message = (
            f"No {profile.sdk_label} toolchain in this deployment — "
            f"{len(files)} source file(s) emitted for {profile.display_name}, build skipped."
        )
        # A missing toolchain is a deployment limit, not a firmware error — log it, don't fail the run.
        emit({"type": "build_log", "line": message})
        state.build_stdout = message
        state.build_success = False
        return state
    result = await profile.build_firmware(files)
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


@instrumented("simulate")
async def _node_simulate(state: DesignState) -> DesignState:
    emit({"type": "simulate_start"})
    lines: list[str] = []
    profile = _profile()
    if profile.build_firmware is None:
        # Fixture captures are RP2040 runs; replaying them for an uncompiled design would lie.
        lines.append(f"[sim] No compiled {profile.board_name} image — simulation skipped.")
        emit({"type": "simulate_output", "line": lines[0]})
    else:
        async for line in stream_simulation(state.uf2_artifact_path, state.wokwi_diagram):
            lines.append(line)
            emit({"type": "simulate_output", "line": line})
    state.simulate_log = "\n".join(lines)
    state.simulate_mode = "fixture"
    state.pipeline_complete = True
    finalize_metrics(state)
    return state


_MAX_CODE_RETRIES = 1
_MAX_ERRATA_RETRIES = 1
_MAX_PIN_CONFLICT_RETRIES = 1


def _route_after_join(state: DesignState):
    """Conditional edge after join: re-dispatch only the conflicting features, else continue."""

    if not state.pin_conflicts:
        return "clocks"
    return [_feature_send(state, fid, state.run_plan, {fid: hint}) for fid, hint in state.pin_conflicts.items()]


def _route_after_build(state: DesignState):
    """Conditional edge after build: success -> simulate, failure -> retry code (max 1)."""

    if state.build_success or _profile().build_firmware is None:
        return "simulate"
    if state.code_retries < _MAX_CODE_RETRIES:
        # bump the retry counter so the next failure goes to simulate (giving up)
        state.code_retries += 1
        emit(
            {
                "type": "agent_activity",
                "agent": "code_composer",
                "key": "build-retry",
                "label": (
                    f"Build failed — re-composing with stderr context "
                    f"(retry {state.code_retries}/{_MAX_CODE_RETRIES})"
                ),
                "status": "active",
            }
        )
        return "code"
    return "simulate"


def _route_after_errata(state: DesignState):
    """Conditional edge after errata: critical warning -> rerun feature pipelines (max 1)."""

    critical = [w for w in state.errata_warnings if w.severity == "critical"]
    if critical and state.errata_retries < _MAX_ERRATA_RETRIES:
        state.errata_retries += 1
        # Stash a hint that the next code_composer pass should respect the
        # workaround; the per-feature peripheral re-run uses fresh prompts but
        # the hint flows through to code_composer via state.last_errata_hint.
        state.last_errata_hint = "; ".join(
            f"{w.errata_id}: {w.workaround or w.description}" for w in critical
        )[:1500]
        emit(
            {
                "type": "agent_activity",
                "agent": "errata_checker",
                "key": "rerun",
                "label": (
                    f"Critical errata — re-running feature pipelines with workaround context "
                    f"(retry {state.errata_retries}/{_MAX_ERRATA_RETRIES})"
                ),
                "status": "active",
            }
        )
        # Reset the per-feature outputs so the rerun doesn't double-merge.
        state.feature_outputs = {}
        return "feature_pipeline_rerun"
    return "render_diagram"


@instrumented("render_diagram")
async def _node_render_diagram(state: DesignState) -> DesignState:
    """Render the merged Wokwi diagram.json from all per-feature wires.

    The per-feature pipeline nodes only emit wire records (and per-feature
    `add_wire` SSE events). Building the actual diagram JSON is global because
    Wokwi expects exactly one diagram per project.
    """

    if not state.wires or state.requirements is None:
        return state
    from app.agents.wokwi_diagram_generator import _render_diagram_json
    device_key = state.requirements.device_name.lower()
    diagram = _render_diagram_json(_profile().board_part, device_key, list(state.wires))
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


# Retry policy applied to every LLM-bearing node. Two attempts with a short
# backoff catches transient rate-limits / structured-output decode hiccups
# without hammering Anthropic on real failures.
_LLM_RETRY = RetryPolicy(max_attempts=2, initial_interval=1.0, backoff_factor=2.0)


# A process-wide checkpointer keyed by session_id. MemorySaver is enough for
# dev (lost on restart); SqliteSaver is a one-line swap for production
# (`langgraph-checkpoint-sqlite` dep + connect string).
_CHECKPOINTER = MemorySaver()


def build_pipeline():
    g: StateGraph = StateGraph(DesignState)
    # LLM-bearing nodes get the retry policy; deterministic nodes don't need it.
    g.add_node("supervisor", _node_supervisor, retry_policy=_LLM_RETRY)
    g.add_node("requirements", _node_requirements, retry_policy=_LLM_RETRY)
    g.add_node("feature_pipeline", _node_feature_pipeline, retry_policy=_LLM_RETRY)
    g.add_node("join_features", _node_join_features)
    g.add_node("clocks", _node_clocks, retry_policy=_LLM_RETRY)
    g.add_node("errata", _node_errata, retry_policy=_LLM_RETRY)
    g.add_node("render_diagram", _node_render_diagram)
    g.add_node("code", _node_code, retry_policy=_LLM_RETRY)
    g.add_node("build", _node_build)
    g.add_node("simulate", _node_simulate)

    g.set_entry_point("supervisor")
    g.add_edge("supervisor", "requirements")
    # Fan out: one Send per feature -> feature_pipeline (parallel branches).
    g.add_conditional_edges("requirements", _route_to_feature_pipelines, ["feature_pipeline"])
    g.add_edge("feature_pipeline", "join_features")
    # Pin conflict at the join -> re-run just the conflicting features (max 1).
    g.add_conditional_edges("join_features", _route_after_join, ["feature_pipeline", "clocks"])
    g.add_edge("clocks", "errata")
    # Errata may route back to a fresh fan-out if any warning is `critical`.
    g.add_conditional_edges(
        "errata",
        _route_after_errata,
        {
            "render_diagram": "render_diagram",
            # Re-fan-out via the same Send routing helper as the original branch.
            "feature_pipeline_rerun": "requirements",
        },
    )
    g.add_edge("render_diagram", "code")
    g.add_edge("code", "build")
    # Build failure -> retry code with stderr hint (max 1).
    g.add_conditional_edges(
        "build",
        _route_after_build,
        {"simulate": "simulate", "code": "code"},
    )
    g.add_edge("simulate", END)

    return g.compile(checkpointer=_CHECKPOINTER)


def _runner_config(session_id: str) -> dict:
    """LangGraph thread config — the checkpointer keys snapshots by thread_id."""

    return {"configurable": {"thread_id": session_id}}


async def run_pipeline(
    user_prompt: str, session_id: str | None = None, target_mcu: str = DEFAULT_MCU
) -> DesignState:
    sid = session_id or uuid.uuid4().hex
    get_profile(target_mcu)  # fail fast on unknown MCUs
    # Every node (and the schema validators they trigger) inherits this context.
    set_target_mcu(target_mcu)
    # Fresh metrics for this session — old aggregator entries (e.g. from a
    # prior crashed run with the same id) are wiped so we don't double-count.
    reset_aggregator(sid)
    state = DesignState(session_id=sid, user_prompt=user_prompt, target_mcu=target_mcu)
    pipeline = build_pipeline()
    result = await pipeline.ainvoke(state, _runner_config(sid))
    if isinstance(result, DesignState):
        return result
    return DesignState.model_validate(result)


async def resume_pipeline(session_id: str) -> DesignState | None:
    """Resume a previously-checkpointed run. Returns None if no checkpoint exists."""

    pipeline = build_pipeline()
    snapshot = pipeline.get_state(_runner_config(session_id))
    if snapshot is None or not snapshot.values:
        return None
    set_target_mcu(snapshot.values.get("target_mcu", DEFAULT_MCU))
    # Passing None as the input tells LangGraph to continue from the saved state.
    result = await pipeline.ainvoke(None, _runner_config(session_id))
    if isinstance(result, DesignState):
        return result
    return DesignState.model_validate(result)
