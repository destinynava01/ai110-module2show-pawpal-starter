"""AI care planner for PawPal+.

Pipeline (agentic, with guardrails):
    1. RETRIEVE  - look up care guidelines in a local knowledge base (RAG).
    2. DRAFT     - a model turns ONLY the retrieved guidelines into task proposals.
                   Uses Claude when ANTHROPIC_API_KEY is set, otherwise a
                   deterministic rule-based drafter so the app runs offline.
    3. VALIDATE  - guardrails reject malformed, out-of-range, or ungrounded
                   proposals (e.g. citing a guideline that was never retrieved).
    4. CHECK     - the plan is checked against the owner's real schedule for
                   duplicates and overlapping times.
    5. REPAIR    - conflicting proposals are shifted and re-checked, up to a
                   bounded number of rounds, then verified with Scheduler.

Every step is logged to ``pawpal_ai.log`` and recorded in ``PlanResult.trace``.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Protocol

from pawpal_system import Owner, Pet, Scheduler, Task

KNOWLEDGE_PATH = Path(__file__).parent / "knowledge" / "pet_care.json"
LOG_PATH = Path(__file__).parent / "pawpal_ai.log"

VALID_FREQUENCIES = {"once", "daily", "weekly"}
VALID_PRIORITIES = {"low", "medium", "high"}
MAX_DURATION_MINUTES = 240
MAX_REPAIR_ROUNDS = 5
SHIFT_MINUTES = 15
LATEST_START = 22 * 60  # no task may start after 10:00 PM
EARLIEST_START = 5 * 60  # nor before 5:00 AM

logger = logging.getLogger("pawpal.ai")


def configure_logging(path: Path = LOG_PATH) -> None:
    """Send pawpal.ai logs to a file (idempotent)."""
    if any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        return
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# --------------------------------------------------------------------------
# 1. Retrieval (RAG)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Document:
    id: str
    species: tuple[str, ...]
    stages: tuple[str, ...]
    title: str
    text: str
    tags: tuple[str, ...]
    tasks: tuple[dict, ...]


def load_knowledge(path: Path = KNOWLEDGE_PATH) -> list[Document]:
    """Load the guideline knowledge base; raise a clear error if unusable."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return [
            Document(
                id=d["id"],
                species=tuple(d["species"]),
                stages=tuple(d["stages"]),
                title=d["title"],
                text=d["text"],
                tags=tuple(d["tags"]),
                tasks=tuple(d["tasks"]),
            )
            for d in raw
        ]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.error("Could not load knowledge base %s: %s", path, exc)
        raise RuntimeError(f"Knowledge base unavailable: {exc}") from exc


def life_stage(pet: Pet) -> str:
    """Map a pet's age to a coarse life stage used to filter guidelines."""
    if pet.age is None:
        return "adult"
    if pet.age < 1:
        return "young"
    if pet.age >= 8:
        return "senior"
    return "adult"


def _tokens(text: str) -> set[str]:
    stop = {"the", "a", "an", "and", "to", "for", "of", "my", "is", "on", "in", "with", "i", "want"}
    words = {w for w in re.findall(r"[a-z]+", text.lower()) if w not in stop}
    # Cheap stemming so "walks"/"walking" match "walk".
    return {re.sub(r"(ing|es|s)$", "", w) if len(w) > 4 else w.rstrip("s") for w in words}


class Retriever:
    """Keyword-overlap retriever over the guideline knowledge base."""

    def __init__(self, documents: list[Document]):
        self.documents = documents

    def retrieve(
        self, goal: str, species: str, stage: str, k: int = 4
    ) -> list[tuple[Document, float]]:
        """Return up to k (document, score) pairs relevant to the goal.

        Documents must match the pet's species and life stage. If the goal has
        keywords, a document needs at least one keyword hit to be returned, so
        irrelevant requests retrieve nothing instead of unrelated advice.
        """
        goal_tokens = _tokens(goal)
        scored: list[tuple[Document, float]] = []
        for doc in self.documents:
            if species not in doc.species or stage not in doc.stages:
                continue
            tag_tokens = {t for tag in doc.tags for t in _tokens(tag)}
            text_tokens = _tokens(doc.title + " " + doc.text)
            score = 2.0 * len(goal_tokens & tag_tokens) + 0.5 * len(goal_tokens & text_tokens)
            if goal_tokens and score == 0:
                continue
            if not goal_tokens:
                score = 1.0
            scored.append((doc, score))
        scored.sort(key=lambda pair: (-pair[1], pair[0].id))
        return scored[:k]


# --------------------------------------------------------------------------
# 2. Drafting models
# --------------------------------------------------------------------------
class DraftModel(Protocol):
    name: str

    def draft(self, pet: Pet, goal: str, docs: list[Document]) -> list[dict]: ...


class RuleBasedModel:
    """Offline drafter: converts retrieved guideline tasks into proposals."""

    name = "rule-based"

    def draft(self, pet: Pet, goal: str, docs: list[Document]) -> list[dict]:
        proposals = []
        for doc in docs:
            reason = doc.text.split(". ")[0].rstrip(".") + "."
            for task in doc.tasks:
                proposals.append({**task, "source_id": doc.id, "rationale": reason})
        return proposals


class ClaudeModel:
    """Drafts proposals with Claude, constrained to the retrieved guidelines."""

    def __init__(self, model: str | None = None):
        import anthropic  # imported lazily so the dependency stays optional

        self.client = anthropic.Anthropic()
        self.model = model or os.environ.get("PAWPAL_MODEL", "claude-sonnet-5-5")
        self.name = f"claude ({self.model})"

    def draft(self, pet: Pet, goal: str, docs: list[Document]) -> list[dict]:
        context = "\n".join(f"[{d.id}] {d.title}: {d.text}" for d in docs)
        prompt = (
            f"Pet: {pet.name}, a {pet.age if pet.age is not None else 'adult'}-year-old {pet.species}.\n"
            f"Owner goal: {goal or 'a healthy daily care routine'}\n\n"
            f"Care guidelines (your ONLY source of facts):\n{context}\n\n"
            "Propose daily care tasks grounded in these guidelines. Reply with ONLY a JSON "
            'array. Each item: {"description": str, "time": "HH:MM" (24h), "duration": int '
            'minutes, "frequency": "once"|"daily"|"weekly", "priority": "low"|"medium"|"high", '
            '"source_id": one of the bracketed ids above, "rationale": one sentence}.'
        )
        message = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system="You are a careful pet-care planning assistant. Never invent guidelines.",
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            raise ValueError("Model reply did not contain a JSON array.")
        return json.loads(match.group(0))


def default_model() -> DraftModel:
    """Use Claude if configured and importable, else the offline drafter."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return ClaudeModel()
        except Exception as exc:  # noqa: BLE001 - any setup failure falls back
            logger.warning("Claude unavailable (%s); using rule-based model.", exc)
    return RuleBasedModel()


# --------------------------------------------------------------------------
# 3. Guardrails
# --------------------------------------------------------------------------
@dataclass
class Proposal:
    description: str
    scheduled_at: datetime
    duration_minutes: int
    frequency: str
    priority: str
    source_id: str
    rationale: str
    shifted: bool = False

    @property
    def start_minute(self) -> int:
        return self.scheduled_at.hour * 60 + self.scheduled_at.minute

    @property
    def end_minute(self) -> int:
        return self.start_minute + self.duration_minutes


def validate_proposals(
    raw: object, allowed_sources: set[str], day: date
) -> tuple[list[Proposal], list[str]]:
    """Return (valid proposals, rejection reasons). Never raises on bad input."""
    if not isinstance(raw, list):
        return [], ["Model output was not a list."]
    valid: list[Proposal] = []
    rejected: list[str] = []
    for index, item in enumerate(raw):
        label = f"item {index + 1}"
        try:
            if not isinstance(item, dict):
                raise ValueError("not an object")
            description = str(item["description"]).strip()
            if not description or len(description) > 80:
                raise ValueError("description empty or too long")
            hour, minute = (int(p) for p in str(item["time"]).split(":"))
            start = hour * 60 + minute
            if not EARLIEST_START <= start <= LATEST_START:
                raise ValueError("start time outside 05:00-22:00")
            duration = int(item["duration"])
            if not 1 <= duration <= MAX_DURATION_MINUTES:
                raise ValueError("duration out of range")
            if item["frequency"] not in VALID_FREQUENCIES:
                raise ValueError("bad frequency")
            if item["priority"] not in VALID_PRIORITIES:
                raise ValueError("bad priority")
            if item.get("source_id") not in allowed_sources:
                raise ValueError("not grounded in a retrieved guideline")
            valid.append(
                Proposal(
                    description=description,
                    scheduled_at=datetime(day.year, day.month, day.day, hour, minute),
                    duration_minutes=duration,
                    frequency=item["frequency"],
                    priority=item["priority"],
                    source_id=item["source_id"],
                    rationale=str(item.get("rationale", "")).strip(),
                )
            )
        except (KeyError, ValueError, TypeError) as exc:
            rejected.append(f"Rejected {label}: {exc}")
    return valid, rejected


# --------------------------------------------------------------------------
# 4-5. Check and repair against the real schedule
# --------------------------------------------------------------------------
def _busy_intervals(owner: Owner, day: date) -> list[tuple[int, int, str]]:
    intervals = []
    for pet in owner.pets:
        for task in pet.tasks:
            if task.is_due_on(day) and not task.is_completed_on(day):
                start = task.scheduled_at.hour * 60 + task.scheduled_at.minute
                intervals.append((start, start + task.duration_minutes, task.description))
    return intervals


def _overlaps(start: int, end: int, busy: list[tuple[int, int, str]]) -> bool:
    return any(start < b_end and b_start < end for b_start, b_end, _ in busy)


def _repair(
    proposals: list[Proposal], owner: Owner, pet: Pet, day: date, trace: list[str]
) -> list[Proposal]:
    """Drop duplicates, then shift overlapping proposals to the next free slot."""
    existing = {
        (t.description.casefold(), t.scheduled_at.hour, t.scheduled_at.minute)
        for t in pet.tasks
        if t.is_due_on(day)
    }
    kept: list[Proposal] = []
    for p in proposals:
        key = (p.description.casefold(), p.scheduled_at.hour, p.scheduled_at.minute)
        if key in existing:
            trace.append(f"Skipped '{p.description}' - already scheduled for {pet.name}.")
        else:
            kept.append(p)

    # Higher priority proposals claim their preferred slot first.
    order = {"high": 0, "medium": 1, "low": 2}
    kept.sort(key=lambda p: (order[p.priority], p.start_minute))
    busy = _busy_intervals(owner, day)
    placed: list[Proposal] = []
    for p in kept:
        for round_no in range(MAX_REPAIR_ROUNDS + 1):
            if not _overlaps(p.start_minute, p.end_minute, busy):
                break
            if round_no == MAX_REPAIR_ROUNDS:
                break
            p.scheduled_at += timedelta(minutes=SHIFT_MINUTES)
            p.shifted = True
        if _overlaps(p.start_minute, p.end_minute, busy) or p.start_minute > LATEST_START:
            trace.append(f"Dropped '{p.description}' - no free slot within {MAX_REPAIR_ROUNDS} shifts.")
            continue
        if p.shifted:
            trace.append(
                f"Moved '{p.description}' to {p.scheduled_at.strftime('%I:%M %p').lstrip('0')} to avoid a conflict."
            )
        busy.append((p.start_minute, p.end_minute, p.description))
        placed.append(p)
    return sorted(placed, key=lambda p: p.start_minute)


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------
@dataclass
class PlanResult:
    proposals: list[Proposal] = field(default_factory=list)
    sources: list[Document] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)
    model_name: str = ""
    verified: bool = False
    confidence: float = 0.0  # 0-1; see compute_confidence()


def compute_confidence(
    top_score: float, goal: str, drafted: int, valid: int, kept: int, verified: bool
) -> float:
    """Heuristic 0-1 confidence in a plan (not a probability).

    Average of three signals, zeroed if the self-check failed:
      * retrieval strength - how well the best guideline matches the goal
        (a tag hit for every goal keyword = 1.0; no goal = neutral 0.5)
      * validation rate    - share of drafted tasks that passed the guardrails
      * placement rate     - share of valid tasks placed without being dropped
    """
    if not verified or drafted == 0 or valid == 0:
        return 0.0
    goal_size = len(_tokens(goal))
    retrieval = 0.5 if goal_size == 0 else min(1.0, top_score / (2.0 * goal_size))
    return round((retrieval + valid / drafted + kept / valid) / 3, 2)


class CareAssistant:
    """Retrieval-grounded, self-checking care planner."""

    def __init__(
        self,
        model: DraftModel | None = None,
        documents: list[Document] | None = None,
    ):
        configure_logging()
        self.model = model if model is not None else default_model()
        self.retriever = Retriever(documents if documents is not None else load_knowledge())

    def plan(self, owner: Owner, pet: Pet, goal: str = "", day: date | None = None) -> PlanResult:
        day = day or date.today()
        result = PlanResult(model_name=self.model.name)
        trace = result.trace

        goal = (goal or "").strip()[:300]
        hits = self.retriever.retrieve(goal, pet.species, life_stage(pet))
        result.sources = [doc for doc, _ in hits]
        trace.append(
            f"Retrieved {len(hits)} guideline(s) for {pet.species}/{life_stage(pet)}: "
            + (", ".join(d.id for d, _ in hits) or "none")
        )
        logger.info("plan pet=%s goal=%r retrieved=%s", pet.name, goal, [d.id for d, _ in hits])
        if not hits:
            trace.append("No relevant guidelines found; no plan generated (guardrail).")
            return result

        try:
            raw = self.model.draft(pet, goal, result.sources)
        except Exception as exc:  # noqa: BLE001 - never let a model failure crash the app
            logger.warning("Model %s failed: %s; falling back", self.model.name, exc)
            trace.append(f"Model '{self.model.name}' failed ({type(exc).__name__}); used rule-based fallback.")
            fallback = RuleBasedModel()
            result.model_name = fallback.name
            raw = fallback.draft(pet, goal, result.sources)

        drafted = len(raw) if isinstance(raw, list) else 0
        proposals, rejected = validate_proposals(raw, {d.id for d in result.sources}, day)
        for reason in rejected:
            logger.warning("guardrail: %s", reason)
        trace.extend(rejected)
        trace.append(f"Validated {len(proposals)} of {drafted} drafted task(s).")

        valid_count = len(proposals)
        result.proposals = _repair(proposals, owner, pet, day, trace)

        # Final self-check: simulate adding the plan and run the real Scheduler.
        sandbox = copy.deepcopy(owner)
        sandbox_pet = next(p for p in sandbox.pets if p.name == pet.name)
        for p in result.proposals:
            sandbox_pet.add_task(to_task(p))
        remaining = Scheduler().detect_conflicts(sandbox, day)
        result.verified = not remaining
        trace.append(
            "Self-check passed: no schedule conflicts."
            if result.verified
            else f"Self-check found {len(remaining)} remaining conflict(s)."
        )
        result.confidence = compute_confidence(
            hits[0][1], goal, drafted, valid_count, len(result.proposals), result.verified
        )
        trace.append(f"Confidence: {result.confidence:.2f}")
        logger.info(
            "plan done pet=%s proposals=%d verified=%s confidence=%.2f",
            pet.name, len(result.proposals), result.verified, result.confidence,
        )
        return result


def to_task(proposal: Proposal) -> Task:
    return Task(
        description=proposal.description,
        scheduled_at=proposal.scheduled_at,
        duration_minutes=proposal.duration_minutes,
        frequency=proposal.frequency,  # type: ignore[arg-type]
        priority=proposal.priority,  # type: ignore[arg-type]
    )


def apply_plan(pet: Pet, proposals: list[Proposal]) -> int:
    """Add accepted proposals to the pet's schedule; return how many were added."""
    for proposal in proposals:
        pet.add_task(to_task(proposal))
    logger.info("applied %d proposal(s) to %s", len(proposals), pet.name)
    return len(proposals)
