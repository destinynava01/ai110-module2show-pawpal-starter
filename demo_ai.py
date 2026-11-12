"""Reproducible demo of the AI care planner (offline drafter, fixed date).

Usage:  python demo_ai.py
Prints example inputs, the AI's outputs and trace, and guardrail results.
"""

from __future__ import annotations

import os
from datetime import date, datetime

os.environ.pop("ANTHROPIC_API_KEY", None)  # force the deterministic offline drafter

from pawpal_ai import CareAssistant, RuleBasedModel, validate_proposals
from pawpal_system import Owner, Task

DAY = date(2030, 1, 7)


def show(assistant: CareAssistant, owner: Owner, pet, goal: str) -> None:
    print(f"INPUT : pet={pet.name} ({pet.species}, age {pet.age}), goal={goal!r}")
    result = assistant.plan(owner, pet, goal, DAY)
    print(f"OUTPUT: model={result.model_name} confidence={result.confidence:.2f} verified={result.verified}")
    for p in result.proposals:
        time = p.scheduled_at.strftime("%I:%M %p").lstrip("0")
        moved = " (moved to avoid conflict)" if p.shifted else ""
        print(f"  {time:>8}  {p.description} - {p.duration_minutes} min, {p.priority} [{p.source_id}]{moved}")
    if not result.proposals:
        print("  (no plan)")
    print("TRACE :")
    for line in result.trace:
        print(f"  - {line}")
    print()


def main() -> None:
    assistant = CareAssistant(model=RuleBasedModel())
    owner = Owner("Jordan")
    mochi = owner.add_pet("Mochi", "dog", 4)
    mochi.add_task(Task("Vet call", datetime(2030, 1, 7, 7, 30), 30))
    luna = owner.add_pet("Luna", "cat", 3)

    print("=== Example 1-3: planning ===\n")
    show(assistant, owner, mochi, "more exercise")
    show(assistant, owner, luna, "feeding")
    show(assistant, owner, mochi, "astrophysics")

    print("=== Guardrail results ===\n")
    good = {"description": "Walk", "time": "08:00", "duration": 20, "frequency": "daily",
            "priority": "high", "source_id": "dog-exercise", "rationale": "x"}
    cases = {
        "valid proposal": good,
        "duration 0": {**good, "duration": 0},
        "start time 03:00": {**good, "time": "03:00"},
        "frequency 'hourly'": {**good, "frequency": "hourly"},
        "invented source_id": {**good, "source_id": "made-up"},
        "empty description": {**good, "description": ""},
        "not an object": "oops",
    }
    for name, item in cases.items():
        valid, rejected = validate_proposals([item], {"dog-exercise"}, DAY)
        print(f"{name:<22} -> {'ACCEPTED' if valid else rejected[0]}")


if __name__ == "__main__":
    main()
