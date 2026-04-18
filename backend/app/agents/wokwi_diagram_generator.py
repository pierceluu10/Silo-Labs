from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.knowledge.graph import get_graph
from app.schemas.state import Requirements
from app.schemas.tools import AddWire, AssignPin

from ._common import haiku


class DiagramOutput(BaseModel):
    wires: list[AddWire] = Field(default_factory=list)


SYSTEM = """You are the Wokwi Diagram Generator.

Given the chosen peripheral device and the RP2040 pin assignments, produce a list of wire
connections (AddWire) that map each Pico GP pin to the matching device pin. Also include
power (3V3 -> VCC) and ground (GND -> GND) where needed.

Wire color convention: data=#e6c84a, clock=#4a7fd9, power=#d94a4a, ground=#1a1a1a, aux=#4ad97f.

from_component is always "pico" for RP2040 pins; to_component is the device key
(e.g. "bme280", "ssd1306"). Use Wokwi component pin names from the component spec provided.
"""


def _render_diagram_json(
    device: str,
    wires: list[AddWire],
) -> dict:
    graph = get_graph()
    pico_spec = graph.get_wokwi_component("pico")
    device_spec = graph.get_wokwi_component(device)
    parts = [
        {"type": pico_spec["type"], "id": "pico", "top": 0, "left": 0, "attrs": {}},
    ]
    if device_spec:
        parts.append(
            {
                "type": device_spec["type"],
                "id": device,
                "top": 120,
                "left": 180,
                "attrs": {},
            }
        )
    connections = [[f"{w.from_component}:{w.from_pin}", f"{w.to_component}:{w.to_pin}", w.color.value, []] for w in wires]
    return {"version": 1, "author": "Silo Labs", "editor": "wokwi", "parts": parts, "connections": connections}


async def generate_diagram(
    requirements: Requirements,
    pin_assignments: list[AssignPin],
) -> tuple[list[AddWire], dict]:
    graph = get_graph()
    device_key = requirements.device_name.lower()
    device_spec = graph.get_wokwi_component(device_key)

    pin_summary = [
        {"gp": p.pin_number, "signal": p.label, "function": p.function.value} for p in pin_assignments
    ]
    user = (
        f"Device: {requirements.device_name} (wokwi component key: {device_key})\n"
        f"Device spec: {device_spec}\n"
        f"Pico pin assignments: {pin_summary}\n"
        f"Return the full wire list (signals + power + ground)."
    )

    llm = haiku(max_tokens=768).with_structured_output(DiagramOutput)
    result = await llm.ainvoke([SystemMessage(content=SYSTEM), HumanMessage(content=user)])
    if not isinstance(result, DiagramOutput):
        result = DiagramOutput.model_validate(result)

    wires = list(result.wires)
    diagram = _render_diagram_json(device_key, wires)
    return wires, diagram
