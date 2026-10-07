"""Synthetic form structure only; no real proposal data is stored in the repository."""

import pytest

from app.configuration import load_config
from app.extraction import extract_facts
from app.ingestion import document
from app.retrieval import retrieve


def consolidated():
    return document([
        {"page": 1, "text": "ID: EHPC-AIF-2099FL01-0000\nProject summary (abstract):\n"
                             "The objective of this Fast Lane\nproject is to benchmark a synthetic workload."},
        {"page": 2, "text": "Submission details\nProject duration: 6 months\n"
                             "Project Lead and Organisation information\nOrganization details\n"
                             "Organization type: University"},
        {"page": 3, "text": "Organization VAT number: FI00000000\n"
                             "Organization country - Horizon 2020: Finland\n"
                             "Team Members Information\nTeam Members #1\nOrganization details\n"
                             "Organization type: Enterprise\nOrganization VAT number: SE000000000000"},
        {"page": 4, "text": "Organization country - Horizon 2020: Sweden\n"
                             "AI Factory selection\nAI Factory Selection:\nLUMI-G\n"
                             "Code(s) used: PyTorch (ROCm), Example research code\n"
                             "Requested amount of resources (GPU hours): 12000\n"
                             "Maximum number of GPUs: 16\nTotal storage required (GB): 750\n"
                             "Total amount of data to transfer to/from (GB): 125\n"
                             "Indicate if you have had previous EuroHPC JU allocations: No\n"
                             "Code Details and Feasibility\nDescription of the code:\n"
                             "Independent GPU experiments run in PyTorch/ROCm."},
        {"page": 5, "text": "Ethics Self-Assessment\nPrivacy & Data Governance\n"
                             "Does your proposal involve handling of personal\ndata?: No"},
        {"page": 6, "text": "Technical Assessment - Example Reviewer\n"
                             "Technical Assessment Form\nCode(s) assessment\n"
                             "Code(s) used: CUDA-only reviewer placeholder\n"
                             "Previous LUMI use: Yes\nVAT number: Not provided"},
    ])


def test_consolidated_field_labels_and_wrapped_values():
    facts = extract_facts(consolidated())
    expected = {"application_id": "EHPC-AIF-2099FL01-0000", "access_mode": "FAST_LANE",
                "project_duration_months": 6, "target_machine": "LUMI-G",
                "organization_type": "University", "country": "Finland", "vat_number": "FI00000000",
                "requested_gpu_hours": 12000, "maximum_number_of_gpus": 16, "total_storage_gb": 750,
                "total_transfer_gb": 125, "framework_names": "PyTorch", "backend_mentions": "ROCm",
                "previous_eurohpc_allocation": False, "personal_data_declared": False}
    for field, value in expected.items():
        assert facts[field]["value"] == value, field
        assert facts[field]["status"] == "PRESENT", field
        assert facts[field]["source"]["text"]
    assert facts["vat_number"]["source"]["page"] == 3
    assert facts["previous_lumi_use"]["status"] == "NOT_FOUND"
    assert len(facts["vat_number"]["candidates"]) == 1


def test_model_retrieval_excludes_assessment_and_personnel_regions():
    doc = consolidated()
    assert any(e["scope"] == "assessment" for e in doc["evidence"])
    for question in load_config("questions.json")["questions"].values():
        evidence = retrieve(doc["evidence"], question)
        assert evidence
        allowed = {"proposal", "lead"} if question.get("include_lead_evidence") else {"proposal"}
        assert all(e["scope"] in allowed for e in evidence)
        assert all("reviewer placeholder" not in e["text"] for e in evidence)


@pytest.mark.parametrize("next_line", ["Resources", "Requested GPU hours", "Requested GPU hours: 10"])
def test_blank_field_does_not_consume_next_heading(next_line):
    doc = document([{"page": 1, "text": "VAT number:\n" + next_line + "\nOther text"}])
    assert extract_facts(doc)["vat_number"]["status"] == "PARSE_ERROR"


def test_not_provided_is_not_explicit_absence():
    facts = extract_facts(document([{"page": 1, "text": "Organization VAT number: Not provided"}]))
    assert facts["vat_number"]["status"] == "NOT_FOUND"
    assert facts["vat_number_present"]["value"] is None


def test_conflicting_lead_values_remain_conflicts():
    doc = consolidated()
    doc["pages"][2]["text"] = doc["pages"][2]["text"].replace(
        "Organization VAT number: FI00000000", "Organization VAT number: FI00000000\nOrganization VAT number: FI11111111")
    assert extract_facts(doc)["vat_number"]["status"] == "CONFLICT"


def test_no_mode_inference_from_id_or_url_and_no_lumi_use_inference():
    doc = document([{"page": 1, "text": "ID: EHPC-AIF-2099FL01-0000\n"
                     "https://example.invalid/fast-lane\n"
                     "Indicate if you have had previous EuroHPC JU allocations: No"}])
    facts = extract_facts(doc)
    assert facts["access_mode"]["status"] == "NOT_FOUND"
    assert facts["previous_lumi_use"]["status"] == "NOT_FOUND"


def test_software_mentions_are_not_inferred_from_general_narrative():
    doc = document([{"page": 1, "text": "Project summary\nWe compare against papers about CUDA and PyTorch."}])
    facts = extract_facts(doc)
    assert facts["framework_names"]["status"] == "NOT_FOUND"
    assert facts["backend_mentions"]["status"] == "NOT_FOUND"


def test_source_passages_are_available_for_fact_confirmation():
    doc = consolidated()
    facts = extract_facts(doc)
    for fact in facts.values():
        if fact["source"]:
            source = fact["source"]
            assert any(e["page"] == source["page"] and source["text"] in e["text"] for e in doc["evidence"])


def test_reviewer_form_cannot_be_confirmed_as_proposal_evidence():
    from app.review import new_review, confirm_decision
    from app.decision import ManualBackend
    from app.configuration import load_policy
    state = new_review(consolidated(), ManualBackend(), load_policy(), "test-reviewer")
    ids = [e["id"] for e in state["document"]["evidence"] if e["scope"] == "assessment"]
    with pytest.raises(ValueError, match="assessment text"):
        confirm_decision(state, "software_gpu_capable", "YES", ids, "Synthetic test")
