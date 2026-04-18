from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .tools import AddWire, AssignPin, ConfigureClock, SetRegister

AgentName = Literal[
    "requirements_parser",
    "pinout_resolver",
    "clock_configurator",
    "peripheral_configurator",
    "errata_checker",
    "wokwi_diagram_generator",
    "code_composer",
]


class Requirements(BaseModel):
    peripheral_type: str
    device_name: str
    device_address: str | None = None
    baud_rate: int | None = None
    description: str


class PinAssignmentRecord(AssignPin):
    pass


class ClockConfigRecord(ConfigureClock):
    pass


class RegisterWriteRecord(SetRegister):
    pass


class WireConnectionRecord(AddWire):
    pass


class ErrataWarning(BaseModel):
    errata_id: str
    severity: Literal["info", "warning", "critical"]
    description: str
    workaround: str | None = None


class DesignState(BaseModel):
    session_id: str
    user_prompt: str
    requirements: Requirements | None = None
    pin_assignments: list[PinAssignmentRecord] = Field(default_factory=list)
    clock_configs: list[ClockConfigRecord] = Field(default_factory=list)
    register_writes: list[RegisterWriteRecord] = Field(default_factory=list)
    wires: list[WireConnectionRecord] = Field(default_factory=list)
    errata_warnings: list[ErrataWarning] = Field(default_factory=list)
    generated_code: str = ""
    cmake_content: str = ""
    wokwi_diagram: dict[str, Any] = Field(default_factory=dict)
    build_stdout: str = ""
    build_success: bool = False
    uf2_artifact_path: str | None = None
    simulate_log: str = ""
    simulate_mode: Literal["fixture", "live"] = "fixture"
    active_agent: AgentName | None = None
    pipeline_complete: bool = False
