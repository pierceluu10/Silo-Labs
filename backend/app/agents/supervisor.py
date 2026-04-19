"""Supervisor / planner agent.

The supervisor reads the user's prompt and decomposes it into 1+ "features",
each describing one peripheral the firmware needs to bring up. Downstream the
pipeline fans out (LangGraph ``Send``) so each feature's pinout / peripheral
config / wiring runs in parallel; the code composer then merges them into a
single multi-file project.

Cost/latency: this runs once per session and uses Sonnet with a small
``max_tokens=512``. Average prompt: ~250 tokens of system + ~50 tokens user.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.mcu import get_profile
from app.schemas.state import FeatureSpec, RunPlan

from ._common import sonnet


SYSTEM = """You are the Silo Labs Supervisor.

Given a user request for embedded firmware, decompose it into independent
"features" the rest of the pipeline can build in parallel. Each feature is
ONE peripheral driving ONE device (e.g. an I2C BME280 sensor, a UART log
output, a PWM servo, a pushbutton input).

Rules:
- Pick the smallest set of features that fully covers the prompt (1-4 typical, 6 max).
- One device per feature. If the prompt mentions multiple devices, emit one feature each.
- ``peripheral_family`` MUST be one of the families the target MCU supports (provided below).
- ``device_name`` is the canonical chip / part name (e.g. "BME280", "MPU6050", "SSD1306").
  For pure GPIO outputs, use the actuator name (e.g. "LED", "Pushbutton", "Servo").
- ``intent`` is a one-line plain-English summary of what this feature does.
- ``id`` is a stable kebab-case identifier — typically ``"<family>-<device>-<n>"``.
- Use ``depends_on`` only when one feature literally needs another's data
  (e.g. "display readings on OLED" depends on the sensor feature). Default empty.

Return ALSO a short ``rationale`` (one sentence) explaining the decomposition,
which the UI shows users.

Output STRICT structured JSON. No markdown, no commentary outside the schema.
"""


async def plan_features(user_prompt: str, target_mcu: str = "rp2040") -> RunPlan:
    profile = get_profile(target_mcu)
    sys_msg = (
        SYSTEM
        + f"\n\n# Target MCU: {profile.display_name} ({profile.name})\n"
        + f"Supported peripheral families: {', '.join(profile.supported_peripheral_families)}\n"
        + f"Pin convention: {profile.valid_pin_label}\n"
    )
    llm = sonnet(max_tokens=768).with_structured_output(RunPlan)
    result = await llm.ainvoke(
        [
            SystemMessage(content=sys_msg),
            HumanMessage(content=f"User request: {user_prompt}\n\nDecompose into features."),
        ]
    )
    if not isinstance(result, RunPlan):
        result = RunPlan.model_validate(result)
    # Defensive: ensure feature ids are unique even if the LLM duplicates.
    seen: set[str] = set()
    fixed: list[FeatureSpec] = []
    for f in result.features:
        fid = f.id or f"{f.peripheral_family.lower()}-{f.device_name.lower()}-0"
        n = 0
        candidate = fid
        while candidate in seen:
            n += 1
            candidate = f"{fid}-{n}"
        seen.add(candidate)
        fixed.append(f.model_copy(update={"id": candidate}))
    return result.model_copy(update={"features": fixed})