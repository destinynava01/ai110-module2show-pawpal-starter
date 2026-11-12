from datetime import date, datetime

import pytest

from pawpal_ai import (
    CareAssistant,
    RuleBasedModel,
    Retriever,
    apply_plan,
    life_stage,
    load_knowledge,
    validate_proposals,
)
from pawpal_system import Owner, Pet, Scheduler, Task

DAY = date(2030, 1, 7)


@pytest.fixture
def docs():
    return load_knowledge()


def make_owner(species="dog", age=4):
    owner = Owner(name="Sam")
    pet = owner.add_pet("Rex", species, age)
    return owner, pet


def test_retriever_matches_species_and_goal(docs):
    hits = Retriever(docs).retrieve("more exercise and walks", "dog", "adult")
    assert hits and hits[0][0].id == "dog-exercise"
    assert all("dog" in d.species for d, _ in hits)


def test_retriever_returns_nothing_for_irrelevant_goal(docs):
    assert Retriever(docs).retrieve("quantum physics homework", "dog", "adult") == []


def test_life_stage_boundaries():
    assert life_stage(Pet("a", "dog", 0)) == "young"
    assert life_stage(Pet("a", "dog", 7)) == "adult"
    assert life_stage(Pet("a", "dog", 8)) == "senior"


def test_retrieval_changes_output(docs):
    owner, pet = make_owner("dog")
    assistant = CareAssistant(model=RuleBasedModel(), documents=docs)
    walks = assistant.plan(owner, pet, "walks", DAY)
    teeth = assistant.plan(owner, pet, "dental teeth", DAY)
    assert {p.description for p in walks.proposals} != {p.description for p in teeth.proposals}
    assert all(p.source_id in {d.id for d in walks.sources} for p in walks.proposals)


def test_guardrails_reject_bad_and_ungrounded_proposals():
    good = {"description": "Walk", "time": "08:00", "duration": 20, "frequency": "daily",
            "priority": "high", "source_id": "dog-exercise", "rationale": "x"}
    bad = [
        {**good, "duration": 0},
        {**good, "time": "03:00"},
        {**good, "frequency": "hourly"},
        {**good, "source_id": "made-up"},
        {**good, "description": ""},
        "not a dict",
    ]
    valid, rejected = validate_proposals([good, *bad], {"dog-exercise"}, DAY)
    assert len(valid) == 1
    assert len(rejected) == len(bad)


def test_guardrails_handle_non_list_output():
    valid, rejected = validate_proposals("garbage", set(), DAY)
    assert valid == [] and rejected


def test_plan_avoids_conflicts_with_existing_schedule(docs):
    owner, pet = make_owner("dog")
    pet.add_task(Task("Vet call", datetime(2030, 1, 7, 7, 30), 30))
    result = CareAssistant(model=RuleBasedModel(), documents=docs).plan(owner, pet, "walks", DAY)
    assert result.verified
    walk = next(p for p in result.proposals if p.description == "Morning walk")
    assert walk.shifted and walk.start_minute >= 8 * 60


def test_plan_skips_duplicates(docs):
    owner, pet = make_owner("dog")
    pet.add_task(Task("Morning walk", datetime(2030, 1, 7, 7, 30), 30, "daily"))
    result = CareAssistant(model=RuleBasedModel(), documents=docs).plan(owner, pet, "walks", DAY)
    assert "Morning walk" not in [p.description for p in result.proposals]


def test_bad_model_falls_back_safely(docs):
    class Broken:
        name = "broken"

        def draft(self, pet, goal, docs):
            raise TimeoutError("boom")

    owner, pet = make_owner("cat")
    result = CareAssistant(model=Broken(), documents=docs).plan(owner, pet, "feeding", DAY)
    assert result.proposals and result.model_name == "rule-based"


def test_hallucinating_model_is_filtered(docs):
    class Hallucinator:
        name = "liar"

        def draft(self, pet, goal, docs):
            return [{"description": "Feed gold", "time": "09:00", "duration": 5,
                     "frequency": "daily", "priority": "high",
                     "source_id": "invented", "rationale": "trust me"}]

    owner, pet = make_owner("dog")
    result = CareAssistant(model=Hallucinator(), documents=docs).plan(owner, pet, "walks", DAY)
    assert result.proposals == []


def test_apply_plan_adds_tasks_without_conflicts(docs):
    owner, pet = make_owner("cat")
    result = CareAssistant(model=RuleBasedModel(), documents=docs).plan(owner, pet, "", DAY)
    assert apply_plan(pet, result.proposals) == len(result.proposals) > 0
    assert Scheduler().detect_conflicts(owner, DAY) == []


def test_no_guidelines_means_no_plan(docs):
    owner, pet = make_owner("dog")
    result = CareAssistant(model=RuleBasedModel(), documents=docs).plan(owner, pet, "astrophysics", DAY)
    assert result.proposals == [] and result.sources == []


def test_confidence_is_scored_and_reflects_quality(docs):
    owner, pet = make_owner("dog")
    assistant = CareAssistant(model=RuleBasedModel(), documents=docs)
    strong = assistant.plan(owner, pet, "walks", DAY)
    none = assistant.plan(owner, pet, "astrophysics", DAY)
    assert 0.5 < strong.confidence <= 1.0
    assert none.confidence == 0.0


def test_confidence_zero_when_model_output_all_rejected(docs):
    class Junk:
        name = "junk"

        def draft(self, pet, goal, docs):
            return [{"description": "x"}]

    owner, pet = make_owner("dog")
    result = CareAssistant(model=Junk(), documents=docs).plan(owner, pet, "walks", DAY)
    assert result.confidence == 0.0
