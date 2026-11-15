import json

import pytest

from advisor import CareAdvisor, build_query, parse_llm_json, validate
from pawpal_system import Owner, Pet, Task
from rag import KnowledgeBase


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase.load()


def owner_with(*pets, minutes=120):
    o = Owner("Jordan", minutes)
    for p in pets:
        o.add_pet(p)
    return o


def ids(report, pet=None):
    return {s.source_id for s in report.suggestions if pet in (None, s.pet_name)}


# ---- retrieval
def test_retrieval_filters_by_species_and_age(kb):
    hits = [p.id for p, _ in kb.retrieve("dog puppy", "dog", 0, k=10)]
    assert "dog-puppy" in hits
    assert "dog-senior" not in hits and "cat-litter" not in hits


def test_special_need_drives_retrieval(kb):
    pet = Pet("Tom", "cat", 4, "diabetes")
    top = kb.retrieve(build_query(pet), "cat", 4, k=1)[0][0]
    assert top.id == "med-diabetes"


# ---- RAG changes the output
def test_advice_depends_on_retrieved_guidance(kb):
    a = CareAdvisor(kb, use_llm=False).advise(owner_with(Pet("A", "cat", 3, "diabetes")))
    b = CareAdvisor(kb, use_llm=False).advise(owner_with(Pet("B", "cat", 3)))
    assert "med-diabetes" in ids(a) and "med-diabetes" not in ids(b)
    assert next(s for s in a.suggestions if s.source_id == "med-diabetes").priority == "high"


def test_existing_tasks_are_not_duplicated(kb):
    pet = Pet("Rex", "dog", 4)
    pet.add_task(Task(1, "Walk", "exercise", 30, "high"))
    r = CareAdvisor(kb, use_llm=False).advise(owner_with(pet))
    assert "dog-exercise" not in ids(r)


# ---- guardrails
def test_validate_rejects_uncited_and_bad_values(kb):
    pet = Pet("Rex", "dog", 4)
    allowed = {"dog-feeding": kb.passages[4]}
    good = {"source_id": "dog-feeding", "title": "Feed", "category": "feeding", "duration_minutes": 10,
            "priority": "high", "frequency": "daily", "preferred_time": "07:00", "rationale": "r"}
    assert validate(good, pet, allowed).title == "Feed"
    for bad in ({**good, "source_id": "made-up"}, {**good, "duration_minutes": 9999},
                {**good, "priority": "urgent"}, {**good, "preferred_time": "7am"},
                {**good, "duration_minutes": "abc"}):
        with pytest.raises(ValueError):
            validate(bad, pet, allowed)


def test_parse_llm_json_tolerates_fences():
    assert parse_llm_json('Sure!\n```json\n[{"a": 1}]\n```') == [{"a": 1}]
    with pytest.raises(ValueError):
        parse_llm_json("no json here")


# ---- LLM path with a fake model
def fake_llm_returning(payload):
    return lambda system, prompt: payload if isinstance(payload, str) else json.dumps(payload)


def test_llm_output_is_used_and_validated(kb):
    llm = fake_llm_returning([
        {"source_id": "cat-litter", "title": "Scoop litter", "category": "hygiene", "duration_minutes": 5,
         "priority": "high", "frequency": "daily", "preferred_time": "", "rationale": "Mia's box"},
        {"source_id": "not-retrieved", "title": "Hallucinated", "category": "x", "duration_minutes": 5,
         "priority": "low", "frequency": "daily", "preferred_time": "", "rationale": ""},
    ])
    r = CareAdvisor(kb, llm=llm).advise(owner_with(Pet("Mia", "cat", 3)))
    assert r.mode == "llm"
    assert [s.title for s in r.suggestions] == ["Scoop litter"]


def test_llm_failure_falls_back_to_offline(kb):
    def boom(system, prompt):
        raise RuntimeError("network down")
    r = CareAdvisor(kb, llm=boom).advise(owner_with(Pet("Mia", "cat", 3)))
    assert r.mode == "offline" and r.suggestions and r.warnings


def test_garbage_llm_output_falls_back(kb):
    r = CareAdvisor(kb, llm=fake_llm_returning("I cannot help")).advise(owner_with(Pet("Mia", "cat", 3)))
    assert r.suggestions and r.warnings


# ---- self-check step
def test_check_repairs_time_clash_and_flags_overflow(kb):
    pet = Pet("Rex", "dog", 4)
    pet.add_task(Task(1, "Vet call", "health", 5, "low", "07:00"))
    r = CareAdvisor(kb, use_llm=False).advise(owner_with(pet, minutes=10))
    feed = next(s for s in r.suggestions if s.source_id == "dog-feeding")
    assert feed.preferred_time == "" and feed.notes
    assert any(s.fits is False for s in r.suggestions)


def test_other_species_gets_habitat_guidance(kb):
    r = CareAdvisor(kb, use_llm=False).advise(owner_with(Pet("Bun", "other", 2)))
    assert "other-habitat" in ids(r)


def test_confidence_is_reported_and_bounded(kb):
    r = CareAdvisor(kb, use_llm=False).advise(owner_with(Pet("Tom", "cat", 4, "diabetes")))
    assert r.suggestions and all(0 < s.confidence <= 1 for s in r.suggestions)
    top = next(s for s in r.suggestions if s.source_id == "med-diabetes")
    assert top.confidence == max(s.confidence for s in r.suggestions)


def test_no_pets_gives_no_suggestions(kb):
    r = CareAdvisor(kb, use_llm=False).advise(Owner("J", 60))
    assert r.suggestions == [] and r.warnings == []


@pytest.mark.parametrize("need", ["no known allergies", "not diabetic", "Healthy, no arthritis"])
def test_negated_special_needs_are_not_treated_as_conditions(kb, need):
    r = CareAdvisor(kb, use_llm=False).advise(owner_with(Pet("P", "cat", 4, need)))
    assert not ids(r) & {"med-allergy", "med-diabetes", "med-arthritis"}


def test_affirmed_need_next_to_negated_one_is_kept(kb):
    r = CareAdvisor(kb, use_llm=False).advise(owner_with(Pet("P", "dog", 5, "arthritis, no allergies")))
    assert "med-arthritis" in ids(r) and "med-allergy" not in ids(r)
