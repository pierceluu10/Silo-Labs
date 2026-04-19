from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .tools import AddWire, AssignPin, ConfigureClock, SetRegister

AgentName = Literal[
    "supervisor",
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


class FeatureSpec(BaseModel):
    """A single peripheral/device the supervisor decomposed the prompt into.

    Each feature runs an independent pinout/peripheral/wiring sub-graph in
    parallel. Code composition merges them into one multi-file project.
    """

    id: str = Field(description="Stable id like 'i2c-bme280-0' so the UI can key on it.")
    peripheral_family: str = Field(description="I2C, SPI, UART, PWM, ADC, GPIO, ...")
    device_name: str = Field(description="Datasheet name of the device, e.g. 'BME280'.")
    intent: str = Field(description="One-line description of what this feature should do.")
    depends_on: list[str] = Field(default_factory=list)


class RunPlan(BaseModel):
    features: list[FeatureSpec] = Field(default_factory=list)
    rationale: str = Field(default="", description="Supervisor's short explanation of the plan.")


class FeatureOutputs(BaseModel):
    """Per-feature outputs collected before the global join."""

    feature_id: str
    pin_assignments: list["PinAssignmentRecord"] = Field(default_factory=list)
    register_writes: list["RegisterWriteRecord"] = Field(default_factory=list)
    wires: list["WireConnectionRecord"] = Field(default_factory=list)


class GeneratedFile(BaseModel):
    path: str = Field(description="Path relative to project root, e.g. 'main.c' or 'drivers/ws2812.pio'.")
    content: str
    language: str | None = Field(default=None, description="Hint for syntax highlighting.")


class NodeMetric(BaseModel):
    """One entry per pipeline node execution."""

    node: str
    feature_id: str | None = None
    started_at_ms: int
    ended_at_ms: int
    duration_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    retries: int = 0
    status: Literal["ok", "retry", "error"] = "ok"
    error: str | None = None


class RunMetrics(BaseModel):
    run_id: str
    started_at_ms: int = 0
    ended_at_ms: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    parallel_speedup: float = 1.0
    nodes: list[NodeMetric] = Field(default_factory=list)


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
    target_mcu: str = Field(default="rp2040", description="Key into McuProfile registry.")
    run_plan: RunPlan | None = None
    requirements: Requirements | None = None
    feature_outputs: dict[str, FeatureOutputs] = Field(default_factory=dict)
    pin_assignments: list[PinAssignmentRecord] = Field(default_factory=list)
    clock_configs: list[ClockConfigRecord] = Field(default_factory=list)
    register_writes: list[RegisterWriteRecord] = Field(default_factory=list)
    wires: list[WireConnectionRecord] = Field(default_factory=list)
    errata_warnings: list[ErrataWarning] = Field(default_factory=list)
    generated_code: str = ""
    cmake_content: str = ""
    generated_files: list[GeneratedFile] = Field(default_factory=list)
    wokwi_diagram: dict[str, Any] = Field(default_factory=dict)
    build_stdout: str = ""
    build_success: bool = False
    uf2_artifact_path: str | None = None
    elf_artifact_path: str | None = None
    simulate_log: str = ""
    simulate_mode: Literal["fixture", "live"] = "fixture"
    active_agent: AgentName | None = None
    pipeline_complete: bool = False
    # Retry budgets — incremented by conditional edges so we don't loop forever.
    code_retries: int = 0
    errata_retries: int = 0
    last_build_error_hint: str | None = None
    last_errata_hint: str | None = None
    metrics: RunMetrics | None = None


# Resolve forward refs that pointed at types declared later in the file.
FeatureOutputs.model_rebuild()
