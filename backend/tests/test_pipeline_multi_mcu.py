"""Full LangGraph run for a non-RP2040 target with a scripted LLM.

Exercises the real graph, schema validators, SVD address resolution, diagram
rendering and build/sim skipping — only the model responses are canned, so a
regression in MCU plumbing (e.g. the target ContextVar not reaching a node)
fails here without an API key.
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
from app.knowledge.graph import current_mcu
from app.mcu import get_profile, profile as profile_module

STM32 = "stm32f103"
STM32_I2C1_CCR = 0x4000541C

_RESPONSES: dict[str, dict[str, Any]] = {
    "RunPlan": {
        "features": [{"id": "i2c-bme280-0", "peripheral_family": "I2C", "device_name": "BME280", "intent": "Read BME280"}],
        "rationale": "one sensor",
    },
    "Requirements": {"peripheral_type": "I2C", "device_name": "BME280", "device_address": "0x76", "description": "Read BME280"},
    "PinAssignmentList": {
        "assignments": [
            {"pin_number": 22, "function": "I2C_SCL", "peripheral_instance": "I2C1", "label": "SCL", "wire_color": "#4a7fd9"},
            {"pin_number": 23, "function": "I2C_SDA", "peripheral_instance": "I2C1", "label": "SDA", "wire_color": "#e6c84a"},
        ]
    },
    "RegisterWriteList": {
        "writes": [
            {"peripheral": "I2C1", "register": "CCR", "field_name": "CCR", "value": 30,
             "bit_offset": 0, "bit_width": 1, "human_explanation": "400 kHz"},
        ]
    },
    "DiagramOutput": {
        "wires": [
            {"from_component": "bluepill", "from_pin": "PB7", "to_component": "bme280", "to_pin": "SDA"},
            {"from_component": "bluepill", "from_pin": "PB6", "to_component": "bme280", "to_pin": "SCL"},
        ]
    },
    "ClockConfigList": {"clocks": get_profile(STM32).clock_hint.rows},
    "MultiFileProject": {
        "files": [
            {"path": "main.c", "content": '#include "stm32f1xx.h"\nint main(void) { for (;;) {} }\n'},
            {"path": "CMakeLists.txt", "content": "project(firmware C ASM)\n"},
        ]
    },
}


class _ScriptedLLM:
    def __init__(self, prompts: list[tuple[str, str]], schema: type | None = None) -> None:
        self.prompts = prompts
        self.schema = schema

    def with_structured_output(self, schema: type) -> _ScriptedLLM:
        return _ScriptedLLM(self.prompts, schema)

    async def ainvoke(self, messages: list) -> Any:
        assert self.schema is not None
        # Every node must see the run's target MCU, or validators resolve against the wrong SVD.
        assert current_mcu() == STM32, f"{self.schema.__name__} ran with target {current_mcu()}"
        self.prompts.append((self.schema.__name__, messages[0].content))
        return self.schema.model_validate(_RESPONSES[self.schema.__name__])


@pytest.fixture
def scripted(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    prompts: list[tuple[str, str]] = []
    grounding_queries: list[tuple[str, str]] = []

    def fake_llm(*_: Any, **__: Any) -> _ScriptedLLM:
        return _ScriptedLLM(prompts)

    def fake_grounding(query: str, mcu: str) -> str:
        grounding_queries.append((mcu, query))
        return f"# Retrieved {mcu.upper()} documentation\n[1] vendor_docs/{mcu}.md § I2C pin mux"

    for module in (supervisor, pinout_resolver, peripheral_configurator, clock_configurator, code_composer):
        monkeypatch.setattr(module, "sonnet", fake_llm)
    monkeypatch.setattr(wokwi_diagram_generator, "haiku", fake_llm)
    monkeypatch.setattr(requirements_parser, "build_parser", lambda: fake_llm().with_structured_output(
        requirements_parser.Requirements))
    monkeypatch.setattr(profile_module, "grounding_context", fake_grounding)
    return {"prompts": prompts, "grounding": grounding_queries}


async def test_stm32_run_end_to_end(scripted: dict[str, Any]) -> None:
    bus = EventBus()
    set_bus(bus)
    state = await run_pipeline("Read a BME280 over I2C", "stm32-e2e", target_mcu=STM32)
    bus.close()
    events = [ev async for ev in bus.aiter()]

    assert state.target_mcu == STM32
    assert [p.pin_name for p in state.pin_assignments] == ["PB6", "PB7"]
    assert state.register_writes[0].address == STM32_I2C1_CCR
    assert {c.clock_domain for c in state.clock_configs} >= {"HSE", "PLL", "SYSCLK"}
    assert state.wokwi_diagram["parts"][0]["type"] == "board-stm32-bluepill"
    assert state.generated_code.startswith('#include "stm32f1xx.h"')
    assert not state.build_success
    assert "build skipped" in state.build_stdout
    assert state.code_retries == 0
    assert state.simulate_log == "[sim] No compiled Blue Pill image — simulation skipped."
    assert state.pipeline_complete

    grounded_agents = {name for name, prompt in scripted["prompts"] if "Retrieved STM32F103 documentation" in prompt}
    print(f"grounded agents: {sorted(grounded_agents)}")
    assert grounded_agents == {"PinAssignmentList", "RegisterWriteList", "ClockConfigList", "MultiFileProject"}
    assert all(mcu == STM32 for mcu, _ in scripted["grounding"])
    for name, prompt in scripted["prompts"]:
        assert "RP2040" not in prompt and "pico-sdk" not in prompt, f"{name} prompt leaks RP2040 context"

    pin_events = [e for e in events if e["type"] == "assign_pin"]
    assert [e["pin_name"] for e in pin_events] == ["PB6", "PB7"]
    reasoning = " ".join(e["delta"] for e in events if e["type"] == "agent_reasoning")
    assert "STM32F103" in reasoning and "RP2040" not in reasoning
