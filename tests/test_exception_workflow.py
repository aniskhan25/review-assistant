import pytest

from app.configuration import load_policy
from app.ingestion import document
from app.review import new_review, confirm_decision, confirm_fact, finalize, add_evidence, prepare_review
from tests.helpers import TEXT


class PositiveBackend:
    name, version = "test-model", "1"
    def decide(self, *args):
        return {"YES": .95, "NO": .02, "UNKNOWN": .03}


def ready_review(text=TEXT):
    state = new_review(document([{"page": 1, "text": text}]), PositiveBackend(), load_policy(), "test")
    ids = [e["id"] for e in state["document"]["evidence"]]
    for qid in ("organization_eligible", "country_eligible"):
        confirm_decision(state, qid, "YES", ids, "Checked the applicable eligibility reference")
    return state


def test_single_final_approval_uses_prefills_without_faking_confirmations():
    state = ready_review()
    assert not state["exceptions"]["facts"] and not state["exceptions"]["decisions"]
    assert "PREVIEW" in state["draft"] and state["final"] is None
    assert not state["facts"]["requested_gpu_hours"]["confirmed"]
    assert not state["decisions"]["workplan_sufficient"]["confirmed"]
    result = finalize(state, "ACCEPT", state["draft_rationale"], True)
    assert len(result["automatic_facts"]) == 10
    assert len(result["automatic_decisions"]) == 5
    assert all(result["fact_citations"].values())
    assert not state["decisions"]["workplan_sufficient"]["confirmed"]


@pytest.mark.parametrize("change", ["missing", "conflict", "warning"])
def test_ambiguous_facts_still_block(change):
    text = TEXT.replace("Country: Finland", "") if change == "missing" else TEXT
    if change == "conflict": text += "\nCountry: Sweden\n"
    state = ready_review(text)
    if change == "warning":
        state["extraction_resolved"] = False
        prepare_review(state)
    assert state["exceptions"]["facts"]
    with pytest.raises(ValueError, match="required facts"):
        finalize(state, "ACCEPT", "why", True)


@pytest.mark.parametrize("change", ["low", "negative", "contradiction", "error"])
def test_model_exceptions_cannot_slip_through_final_gate(change):
    state = ready_review()
    decision = state["decisions"]["workplan_sufficient"]
    if change == "low": decision["confidence"] = .7
    if change == "negative": decision["answer"] = "NO"
    if change == "contradiction": decision["contradiction"] = True
    if change == "error": decision["status"] = "MODEL_ERROR"
    prepare_review(state)
    assert "workplan_sufficient" in state["exceptions"]["decisions"]
    with pytest.raises(ValueError, match="decision exceptions"):
        finalize(state, "ACCEPT", "why", True)


@pytest.mark.parametrize("edit", ["fact", "evidence"])
def test_edits_invalidate_automatic_answers(edit):
    state = ready_review()
    finalize(state, "ACCEPT", "why", True)
    if edit == "fact":
        confirm_fact(state, "total_storage_gb", "2000", "PRESENT", [state["document"]["evidence"][0]["id"]], "Corrected amount")
    else:
        add_evidence(state, 1, "The plan includes extra installation work.", "Checked PDF")
    assert state["final"] is None
    assert len(state["exceptions"]["decisions"]) == 7


def test_extracted_facts_reach_model_without_being_called_verified():
    class Capture(PositiveBackend):
        def decide(self, text, question):
            assert "Automatically extracted proposal facts" in text
            assert '"requested_gpu_hours": {"value": 50000' in text
            assert "Reviewer-verified structured facts" not in text
            return super().decide(text, question)
    new_review(document([{"page": 1, "text": TEXT}]), Capture(), load_policy(), "test")
