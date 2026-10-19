from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.knowledge.graph import get_graph
from app.schemas.state import Requirements
from app.schemas.tools import AddWire, AssignPin

from ._common import haiku, target_profile


class DiagramOutput(BaseModel):
    wires: list[AddWire] = Field(default_factory=list)


SYSTEM = """You are the Wokwi Diagram Generator.

Given the chosen peripheral device and the MCU board's pin assignments, produce a list of wire
connections (AddWire) that map each board pin to the matching device pin. Also include
power (3V3 -> VCC) and ground (GND -> GND) where needed.

Wire color convention: data=#e6c84a, clock=#4a7fd9, power=#d94a4a, ground=#1a1a1a, aux=#4ad97f.

from_component is always the board id given below; to_component is the device key
(e.g. "bme280", "ssd1306"). Use Wokwi pin names from the board and device specs provided.
"""


def _normalize_pin_for_part(spec: dict | None, pin: str) -> str:
    """Map common LLM-emitted pin aliases to valid Wokwi pin names.

    Boards like the Pico and ESP32 DevKit expose numbered ground pads
    (GND.1..GND.n) — a bare "GND" is rejected by wokwi-cli with
    `[invalid-pin] Invalid pin "GND"`. Map it (and VCC) when the part needs it.
    """
    pins = spec.get("pins", []) if spec else []
    if pin == "GND" and "GND" not in pins and "GND.1" in pins:
        return "GND.1"
    if pin == "VCC" and "VCC" not in pins and "3V3" in pins:
        return "3V3"
    return pin


def _render_diagram_json(
    board: str,
    device: str,
    wires: list[AddWire],
) -> dict:
    graph = get_graph()
    specs = {board: graph.get_wokwi_component(board), device: graph.get_wokwi_component(device)}
    device_spec = specs[device]
    parts = [
        {"type": specs[board]["type"], "id": board, "top": 0, "left": 0, "attrs": {}},
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
    connections = [
        [
            f"{w.from_component}:{_normalize_pin_for_part(specs.get(w.from_component), w.from_pin)}",
            f"{w.to_component}:{_normalize_pin_for_part(specs.get(w.to_component), w.to_pin)}",
            w.color.value,
            [],
        ]
        for w in wires
    ]
    return {"version": 1, "author": "Silo Labs", "editor": "wokwi", "parts": parts, "connections": connections}


async def generate_diagram(
    requirements: Requirements,
    pin_assignments: list[AssignPin],
) -> tuple[list[AddWire], dict]:
    graph = get_graph()
    profile = target_profile()
    board = profile.board_part
    device_key = requirements.device_name.lower()
    device_spec = graph.get_wokwi_component(device_key)

    pin_summary = [
        {"pin": p.pin_name, "signal": p.label, "function": p.function.value} for p in pin_assignments
    ]
    user = (
        f"Board: {profile.board_name} (board id: {board})\n"
        f"Board spec: {graph.get_wokwi_component(board)}\n"
        f"Device: {requirements.device_name} (wokwi component key: {device_key})\n"
        f"Device spec: {device_spec}\n"
        f"Board pin assignments: {pin_summary}\n"
        f"Return the full wire list (signals + power + ground)."
    )

    llm = haiku(max_tokens=768).with_structured_output(DiagramOutput)
    result = await llm.ainvoke([SystemMessage(content=SYSTEM), HumanMessage(content=user)])
    if not isinstance(result, DiagramOutput):
        result = DiagramOutput.model_validate(result)

    wires = list(result.wires)
    diagram = _render_diagram_json(board, device_key, wires)
    return wires, diagram
