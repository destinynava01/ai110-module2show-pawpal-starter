"""Reliability harness for the AI care planner.

Runs fixed scenarios through CareAssistant and reports pass/fail on:
  * consistency  - identical inputs give identical plans
  * grounding    - every proposal cites a retrieved guideline
  * safety       - self-check passes (no schedule conflicts)
  * relevance    - a plan includes the expected kind of task for the goal

Usage:  python eval_ai.py          (exits non-zero if any check fails)
"""

from __future__ import annotations

import sys
from datetime import date, datetime

from pawpal_ai import CareAssistant
from pawpal_system import Owner, Task

DAY = date(2030, 1, 7)

# (species, age, goal, keyword expected in at least one task description, or None for "no plan")
SCENARIOS = [
    ("dog", 4, "more exercise", "walk"),
    ("dog", 0, "puppy training", "training"),
    ("dog", 10, "medication", "medic"),
    ("cat", 3, "feeding", "breakfast"),
    ("cat", 3, "litter", "litter"),
    ("other", 2, "clean cage", "enclosure"),
    ("dog", 4, "astrophysics", None),
]


def run() -> int:
    assistant = CareAssistant()
    failures = 0
    confidences = []
    print(f"Model: {assistant.model.name}\n")
    print("| Scenario | Goal | Consistent | Grounded | Safe | Relevant | Confidence | Result |")
    print("|---|---|---|---|---|---|---|---|")
    for species, age, goal, keyword in SCENARIOS:
        def build():
            owner = Owner("Eval")
            pet = owner.add_pet("Pet", species, age)
            pet.add_task(Task("Existing", datetime(2030, 1, 7, 7, 30), 30))
            return owner, pet

        owner, pet = build()
        first = assistant.plan(owner, pet, goal, DAY)
        owner2, pet2 = build()
        second = assistant.plan(owner2, pet2, goal, DAY)

        checks = {
            "consistent": [(p.description, p.scheduled_at) for p in first.proposals]
            == [(p.description, p.scheduled_at) for p in second.proposals],
            "grounded": all(p.source_id in {d.id for d in first.sources} for p in first.proposals),
            "safe": first.verified or not first.proposals,
            "relevant": (
                not first.proposals
                if keyword is None
                else any(keyword in p.description.lower() for p in first.proposals)
            ),
        }
        ok = all(checks.values())
        failures += not ok
        if first.proposals:
            confidences.append(first.confidence)
        cells = " | ".join("pass" if v else "FAIL" for v in checks.values())
        print(f"| {species}/{age} | {goal} | {cells} | {first.confidence:.2f} | {'PASS' if ok else 'FAIL'} |")
    avg = sum(confidences) / len(confidences) if confidences else 0.0
    print(
        f"\n{len(SCENARIOS) - failures}/{len(SCENARIOS)} scenarios passed. "
        f"Mean confidence on scenarios with a plan: {avg:.2f}."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
