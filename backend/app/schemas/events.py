from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from .state import AgentName

Panel = Literal["top-left", "top-right", "bottom-left", "bottom-right"]
Severity = Literal["info", "warning", "critical"]


class SessionReady(BaseModel):
    type: Literal["session_ready"] = "session_ready"
    session_id: str


class AgentStart(BaseModel):
    type: Literal["agent_start"] = "agent_start"
    agent: AgentName
    timestamp: float


class AgentReasoning(BaseModel):
    type: Literal["agent_reasoning"] = "agent_reasoning"
    agent: AgentName
    panel: Panel
    delta: str


class AgentComplete(BaseModel):
    type: Literal["agent_complete"] = "agent_complete"
    agent: AgentName
    duration_ms: int


class AssignPinEvent(BaseModel):
    type: Literal["assign_pin"] = "assign_pin"
    pin_number: int
    function: str
    peripheral_instance: str
    label: str
    wire_color: str


class ConfigureClockEvent(BaseModel):
    type: Literal["configure_clock"] = "configure_clock"
    clock_domain: str
    source: str
    freq_hz: int
    divider: float


class SetRegisterEvent(BaseModel):
    type: Literal["set_register"] = "set_register"
    peripheral: str
    register: str
    address: int
    field_name: str
    value: int
    bit_offset: int
    bit_width: int
    human_explanation: str


class AddWireEvent(BaseModel):
    type: Literal["add_wire"] = "add_wire"
    from_component: str
    from_pin: str
    to_component: str
    to_pin: str
    color: str


class ErrataWarningEvent(BaseModel):
    type: Literal["errata_warning"] = "errata_warning"
    errata_id: str
    severity: Severity
    description: str
    workaround: str | None = None


class CodeChunk(BaseModel):
    type: Literal["code_chunk"] = "code_chunk"
    delta: str


class CodeComplete(BaseModel):
    type: Literal["code_complete"] = "code_complete"
    full_code: str


class BuildStart(BaseModel):
    type: Literal["build_start"] = "build_start"


class BuildLog(BaseModel):
    type: Literal["build_log"] = "build_log"
    line: str


class BuildSuccess(BaseModel):
    type: Literal["build_success"] = "build_success"
    uf2_url: str


class BuildFailure(BaseModel):
    type: Literal["build_failure"] = "build_failure"
    error: str
    stderr: str


class SimulateStart(BaseModel):
    type: Literal["simulate_start"] = "simulate_start"


class SimulateOutput(BaseModel):
    type: Literal["simulate_output"] = "simulate_output"
    line: str


class PipelineComplete(BaseModel):
    type: Literal["pipeline_complete"] = "pipeline_complete"
    session_id: str
    duration_ms: int


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str
    recoverable: bool


SSEEvent = Annotated[
    Union[
        SessionReady,
        AgentStart,
        AgentReasoning,
        AgentComplete,
        AssignPinEvent,
        ConfigureClockEvent,
        SetRegisterEvent,
        AddWireEvent,
        ErrataWarningEvent,
        CodeChunk,
        CodeComplete,
        BuildStart,
        BuildLog,
        BuildSuccess,
        BuildFailure,
        SimulateStart,
        SimulateOutput,
        PipelineComplete,
        ErrorEvent,
    ],
    Field(discriminator="type"),
]
