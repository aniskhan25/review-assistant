"""Derived guidance regressions using synthetic proposals only."""
import pytest

from app.configuration import load_config, load_policy
from app.decision import decide
from app.review import confirm_decision, confirm_fact, finalize
from app.rules import evaluate
from tests.helpers import TEXT, confirmed, review


def findings(state, code):
    return [f for f in evaluate(state, state["policy"])["findings"] if f["code"] == code]


def test_guidance_policy_is_still_shadow():
    policy = load_policy()
    assert policy["gpu_units_per_node"] == 4
    assert policy["storage_warning_gb"] == 50000
    assert not policy["approved"] and policy["mode"] == "shadow"
    assert all(len(source["sha256"]) == 64 for source in policy["guidance_sources"])


@pytest.mark.parametrize("storage,warn", [(50000, False), (50001, True)])
def test_storage_threshold_warns_without_rejection(storage, warn):
    state = confirmed(review(TEXT.replace("Total storage (GB): 1000", f"Total storage (GB): {storage}")))
    assert bool(findings(state, "storage")) == warn
    result = finalize(state, "ACCEPT", "Storage plan checked", True)
    assert ("LUMI-O" in result["text"]) == warn


@pytest.mark.parametrize("gpus,multinode", [(4, False), (5, True)])
def test_four_full_gpus_per_node(gpus, multinode):
    state = review(TEXT.replace("Maximum number of GPUs: 64", f"Maximum number of GPUs: {gpus}"))
    assert bool(findings(state, "multi_node")) == multinode


def test_rocm_negative_requires_confirmation_and_exception_note():
    state = confirmed(review())
    decision = state["decisions"]["official_rocm_builds_available"]
    decision.update(answer="NO", confirmed=False)
    assert findings(state, "official_rocm_builds_available")[0]["severity"] == "attention"
    confirm_decision(state, "official_rocm_builds_available", "NO", decision["evidence_ids"], "Build unavailable; reviewed porting plan")
    with pytest.raises(ValueError, match="exception"):
        finalize(state, "ACCEPT", "Plausible", True)
    result = finalize(state, "ACCEPT", "Plausible", True, exception_note="Reviewer verified a supported source build and allocated setup time")
    assert "supported source build" in result["text"]
    assert findings(state, "code_previously_installed")[0]["severity"] == "warning"


@pytest.mark.parametrize("qid", ["organization_eligible", "country_eligible"])
def test_eligibility_never_calls_model(qid):
    class ForbiddenBackend:
        name, version = "forbidden", "1"
        def decide(self, *args):
            pytest.fail("Eligibility must be manually verified")
    state = review()
    result = decide(ForbiddenBackend(), qid, state["registry"]["questions"][qid], state["document"]["evidence"], state["policy"])
    assert result["status"] == "MANUAL_REQUIRED"
    assert result["answer"] == "UNKNOWN"


def test_ineligible_organization_uses_not_feasible_category():
    state = confirmed(review(TEXT.replace("Organization type: SME", "Organization type: University")))
    assert findings(state, "organization_eligibility")[0]["severity"] == "blocker"
    with pytest.raises(ValueError, match="not-feasible"):
        finalize(state, "REJECT", "Ineligible organisation", True, "OUT_OF_RESOURCES")
    result = finalize(state, "REJECT", "Ineligible organisation", True)
    assert result["classification_label"] == "Rejected (not feasible)"


def test_missing_vat_is_not_confirmed_absence():
    state = confirmed(review())
    state["facts"]["vat_number"].update(status="NOT_FOUND", confirmed=False)
    assert findings(state, "vat")[0]["severity"] == "attention"
    confirm_fact(state, "vat_number", "", "ABSENT", [state["document"]["evidence"][0]["id"]], "Verified no tax number")
    assert findings(state, "vat")[0]["severity"] == "blocker"


def test_template_sections_and_personal_data_followup():
    state = confirmed(review(TEXT.replace("Personal data declared: No", "Personal data declared: Yes")))
    templates = load_config("templates.json")
    result = finalize(state, "ACCEPT", "Feasible", True, global_comment="Startup allowance checked")
    assert len(templates["form_questions"]) == 3
    assert all(result["text"].count(title) == 1 for title in templates["form_questions"].values())
    assert templates["acceptance"] in result["text"]
    assert templates["personal_data"] in result["text"] and result["follow_up"]
    assert "Startup allowance checked" in result["text"]
    rejected = finalize(state, "REJECT", "Insufficient workplan", True, rejection_details=["workplan"])
    assert templates["personal_data"] not in rejected["text"]
    assert templates["rejection_details"]["workplan"] in rejected["text"]
    assert rejected["text"].endswith(templates["rejection_closing"])
    assert not rejected["follow_up"]


def test_rejection_wording_and_categories():
    state = confirmed(review())
    assert finalize(state, "REJECT", "No allocation available", True, "OUT_OF_RESOURCES")["classification_label"] == "Rejected (out of resources)"
    with pytest.raises(ValueError, match="Capacity"):
        finalize(state, "REJECT", "why", True, rejection_details=["resource_capacity"])
    with pytest.raises(ValueError, match="only available"):
        finalize(state, "ACCEPT", "why", True, rejection_details=["workplan"])
    with pytest.raises(ValueError, match="Invalid rejection"):
        finalize(state, "REJECT", "why", True, rejection_details=["invented"])


def test_missing_previous_use_does_not_force_invented_fact():
    state = confirmed(review(TEXT.replace("Previous LUMI use: No\n", "")))
    assert state["facts"]["previous_lumi_use"]["status"] == "NOT_FOUND"
    assert finalize(state, "ACCEPT", "Installation and startup reviewed", True)
