"""Supervisor tests with a fake chat model — zero LLM spend."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage

from app.agents import supervisor
from app.schemas.state import RunPlan


class _FakeStructuredLLM:
    """Stands in for ``sonnet(...).with_structured_output(RunPlan)``."""

    def __init__(self, plan: RunPlan) -> None:
        self._plan = plan
        self.calls = 0

    def with_structured_output(self, schema):  # noqa: ARG002
        return self

    async def ainvoke(self, _messages):
        self.calls += 1
        return self._plan


@pytest.mark.asyncio
async def test_plan_features_decomposes_two_devices(monkeypatch):
    """Supervisor returns a plan with multiple features when prompted with 2 devices."""

    canned = RunPlan.model_validate(
        {
            "features": [
                {
                    "id": "i2c-bme280-0",
                    "peripheral_family": "I2C",
                    "device_name": "BME280",
                    "intent": "Read temperature/humidity/pressure over I2C",
                },
                {
                    "id": "i2c-ssd1306-0",
                    "peripheral_family": "I2C",
                    "device_name": "SSD1306",
                    "intent": "Render readings on the OLED",
                    "depends_on": ["i2c-bme280-0"],
                },
            ],
            "rationale": "Sensor + display split into two parallel features.",
        }
    )
    fake = _FakeStructuredLLM(canned)
    monkeypatch.setattr(supervisor, "sonnet", lambda *a, **kw: fake)

    plan = await supervisor.plan_features("BME280 over I2C → SSD1306 OLED")

    assert fake.calls == 1
    assert len(plan.features) == 2
    assert {f.peripheral_family for f in plan.features} == {"I2C"}
    assert plan.features[1].depends_on == ["i2c-bme280-0"]


@pytest.mark.asyncio
async def test_plan_features_dedupes_duplicate_ids(monkeypatch):
    """If the LLM emits two features with the same id, the supervisor renames the second."""

    canned = RunPlan.model_validate(
        {
            "features": [
                {"id": "led-0", "peripheral_family": "GPIO", "device_name": "LED", "intent": "Blink"},
                {"id": "led-0", "peripheral_family": "GPIO", "device_name": "LED", "intent": "Status"},
            ],
            "rationale": "two leds",
        }
    )
    fake = _FakeStructuredLLM(canned)
    monkeypatch.setattr(supervisor, "sonnet", lambda *a, **kw: fake)

    plan = await supervisor.plan_features("two LEDs")
    ids = [f.id for f in plan.features]
    assert ids == ["led-0", "led-0-1"]


def test_run_plan_schema_round_trip():
    """Sanity: RunPlan + FeatureSpec serialize cleanly to JSON for the SSE event."""

    plan = RunPlan.model_validate(
        {
            "features": [{"id": "x", "peripheral_family": "I2C", "device_name": "X", "intent": "y"}],
            "rationale": "r",
        }
    )
    payload = json.dumps([f.model_dump() for f in plan.features])
    assert "X" in payload