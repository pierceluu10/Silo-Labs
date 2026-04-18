from __future__ import annotations

from app.knowledge.graph import get_graph
from app.schemas.state import ErrataWarning, Requirements
from app.schemas.tools import AssignPin, SetRegister


async def check_errata(
    requirements: Requirements,
    pin_assignments: list[AssignPin],
    register_writes: list[SetRegister],
) -> list[ErrataWarning]:
    """Deterministic errata match against hand-authored triggers.

    No LLM call needed — errata triggers are short keyword lists and the match is exact.
    """
    triggers: set[str] = {requirements.peripheral_type.upper()}
    for pin in pin_assignments:
        triggers.add(pin.peripheral_instance.upper())
        triggers.add(pin.function.value.upper())
    for reg in register_writes:
        triggers.add(reg.peripheral.upper())

    graph = get_graph()
    entries = graph.get_errata_by_trigger(triggers)

    warnings: list[ErrataWarning] = []
    for entry in entries:
        warnings.append(
            ErrataWarning(
                errata_id=entry["id"],
                severity=entry.get("severity", "info"),
                description=entry.get("description", ""),
                workaround=entry.get("workaround"),
            )
        )
    return warnings
