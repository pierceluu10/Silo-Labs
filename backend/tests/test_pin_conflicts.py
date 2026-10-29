"""Cross-feature pin conflicts are caught at join_features and only the
conflicting feature is re-dispatched. Real graph, scripted LLM (no API key).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.agents import (
    clock_configurator,
    code_composer,
    peripheral_configurator,
    pinout_resolver,
    requirements_parser,
    supervisor,
    wokwi_diagram_generator,
)
from app.graph.event_bus import EventBus, set_bus
from app.graph.pipeline import run_pipeline
from app.knowledge.graph import PinConflictError
from app.mcu import profile as profile_module

from .test_pipeline_multi_mcu import _RESPONSES, STM32

I2C_PINS = [
    {"pin_number": 22, "function": "I2C_SCL", "peripheral_instance": "I2C1", "label": "SCL", "wire_color": "#4a7fd9"},
    {"pin_number": 23, "function": "I2C_SDA", "peripheral_instance": "I2C1", "label": "SDA", "wire_color": "#e6c84a"},
]
# Collides with the I2C feature's SCL on pin 22.
UART_CLASHING_PINS = [
    {"pin_number": 22, "function": "UART_TX", "peripheral_instance": "USART1", "label": "TX", "wire_color": "#e6c84a"},
    {"pin_number": 10, "function": "UART_RX", "peripheral_instance": "USART1", "label": "RX", "wire_color": "#4ad97f"},
]
UART_FIXED_PINS = [
    {"pin_number": 9, "function": "UART_TX", "peripheral_instance": "USART1", "label": "TX", "wire_color": "#e6c84a"},
    {"pin_number": 10, "function": "UART_RX", "peripheral_instance": "USART1", "label": "RX", "wire_color": "#4ad97f"},
]
TWO_FEATURE_PLAN = {
    "features": [
        {"id": "i2c-bme280-0", "peripheral_family": "I2C", "device_name": "BME280", "intent": "Read BME280"},
        {"id": "uart-gps-1", "peripheral_family": "UART", "device_name": "GPS", "intent": "Read GPS over UART"},
    ],
    "rationale": "two devices",
}


class _PinScriptedLLM:
    def __init__(self, calls: list[str], uart_fixes: bool, schema: type | None = None) -> None:
        self.calls = calls
        self.uart_fixes = uart_fixes
        self.schema = schema

    def with_structured_output(self, schema: type) -> _PinScriptedLLM:
        return _PinScriptedLLM(self.calls, self.uart_fixes, schema)

    async def ainvoke(self, messages: list) -> Any:
        assert self.schema is not None
        name = self.schema.__name__
        if name == "RunPlan":
            return self.schema.model_validate(TWO_FEATURE_PLAN)
        if name != "PinAssignmentList":
            return self.schema.model_validate(_RESPONSES[name])
        prompt = messages[-1].content
        retried = "conflicted with another feature" in prompt
        self.calls.append(f"{'GPS' if 'GPS' in prompt else 'BME280'}{' (retry)' if retried else ''}")
        if "GPS" not in prompt:
            return self.schema.model_validate({"assignments": I2C_PINS})
        pins = UART_FIXED_PINS if retried and self.uart_fixes else UART_CLASHING_PINS
        return self.schema.model_validate({"assignments": pins})


def _script(monkeypatch: pytest.MonkeyPatch, uart_fixes: bool) -> list[str]:
    calls: list[str] = []

    def fake_llm(*_: Any, **__: Any) -> _PinScriptedLLM:
        return _PinScriptedLLM(calls, uart_fixes)

    for module in (supervisor, pinout_resolver, peripheral_configurator, clock_configurator, code_composer):
        monkeypatch.setattr(module, "sonnet", fake_llm)
    monkeypatch.setattr(wokwi_diagram_generator, "haiku", fake_llm)
    monkeypatch.setattr(requirements_parser, "build_parser", lambda: fake_llm().with_structured_output(
        requirements_parser.Requirements))
    monkeypatch.setattr(profile_module, "grounding_context", lambda query, mcu: "")
    return calls


async def test_conflicting_feature_is_rerun_with_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _script(monkeypatch, uart_fixes=True)
    set_bus(EventBus())
    state = await run_pipeline("BME280 over I2C and a GPS over UART", "pin-conflict-fixed", target_mcu=STM32)

    print(f"pinout calls: {calls}")
    # Only the GPS feature is re-dispatched; BME280 keeps its pins.
    assert sorted(calls) == ["BME280", "GPS", "GPS (retry)"]
    assert state.pin_conflict_retries == 1
    assert state.pin_conflicts == {}
    pins = sorted(p.pin_number for p in state.pin_assignments)
    assert pins == [9, 10, 22, 23]
    assert state.pipeline_complete


async def test_conflict_surviving_retry_fails_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _script(monkeypatch, uart_fixes=False)
    set_bus(EventBus())
    with pytest.raises(PinConflictError, match="22"):
        await run_pipeline("BME280 over I2C and a GPS over UART", "pin-conflict-stuck", target_mcu=STM32)
    print(f"pinout calls: {calls}")
    assert calls.count("GPS (retry)") == 1
