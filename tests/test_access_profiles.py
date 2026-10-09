"""Synthetic variants of form families; no private proposal contents."""

import pytest

from app.configuration import load_policy, load_config
from app.extraction import extract_facts
from app.ingestion import document
from app.review import new_review
from app.retrieval import retrieve


def policy_text(slug):
    return ("Data Consent\nIn order to submit the proposal, you must accept the terms and conditions "
            "stated in the Access Policy.\nThe documentation can be found at https://\n"
            f"www.eurohpc-ju.europa.eu/{slug}: I accept the terms and conditions stated in the Access Policy")


def test_previous_allocation_mode_does_not_describe_current_application():
    doc = document([
        {"page": 1, "text": "ID: EHPC-AIF-2099FL01-0001\nAI Factory Selection:\nLUMI-G\n"
         "Requested GPU hours: 7200\nIndicate if you have had previous EuroHPC JU allocations: Yes\n"
         "Previous EuroHPC JU allocations #1\nProject ID: EHPC-OLD-0001"},
        {"page": 2, "text": "Access mode: Benchmark Access\nRequested GPU hours: 999\n"
         "Previous EuroHPC JU allocations #2\nAccess mode: Regular Access\n"
         "Code Details and Feasibility\nDescription of the code:\nPyTorch GPU experiments.\n"
         + policy_text("fast-lane-access-ai-factories_en")},
    ])
    facts = extract_facts(doc)
    assert facts["access_mode"]["value"] == "FAST_LANE"
    assert facts["access_mode"]["source"]["method"] == "accepted_submission_policy"
    assert facts["requested_gpu_hours"]["value"] == 7200
    assert facts["application_id"]["value"] == "EHPC-AIF-2099FL01-0001"
    q = load_config("questions.json")["questions"]["workplan_sufficient"]
    assert all(e["scope"] != "allocation_history" for e in retrieve(doc["evidence"], q))


def test_accepted_policy_can_continue_across_page_boundary():
    text = policy_text("fast-lane-access-ai-factories_en")
    first, second = text.split("www.")
    doc = document([{"page": 1, "text": first + "1/2"},
                    {"page": 2, "text": "ID: EHPC-AIF-2099FL01-0002\nwww." + second + "\nTechnical Assessment - Reviewer"}])
    fact = extract_facts(doc)["access_mode"]
    assert fact["value"] == "FAST_LANE"
    assert fact["source"]["page"] == 2
    assert "I accept" in fact["source"]["context"]


@pytest.mark.parametrize("slug,expected", [
    ("fast-lane-access-ai-factories_en", "FAST_LANE"),
    ("playground-access-ai-factories_en", "PLAYGROUND"),
    ("large-scale-access-ai-factories_en", "LARGE_SCALE"),
    ("eurohpc-ju-call-proposals-ai-science-and-collaborative-eu-projects_en", "AI_SCIENCE"),
])
def test_current_policy_mode(slug, expected):
    doc = document([{"page": 1, "text": policy_text(slug)}])
    assert extract_facts(doc)["access_mode"]["value"] == expected


def test_unaccepted_link_does_not_supply_mode():
    doc = document([{"page": 1, "text": policy_text("playground-access-ai-factories_en").replace("I accept", "I do not accept")}])
    assert extract_facts(doc)["access_mode"]["status"] == "NOT_FOUND"


def test_partition_units_and_wrapped_code_list():
    doc = document([{"page": 1, "text": "Partitions\nPartition name:\nLUMI-G\n"
        "Requested amount of resources (node hours): 1200\nCode(s) used: Example scientific pipeline,\n"
        "an additional parser and PyTorch\nJobs\nNumber of jobs simultaneously: 12\n"
        "Maximum # GPUs to be used per job: 16\n# GPUs used per node: 8\n"
        "Storage\nMaximum amount of SCRATCH needed at a time (TB): 3\n"
        "Maximum amount of WORK needed at a time (TB): 7\nTotal amount of data to transfer to/from (TB): 9"}])
    facts = extract_facts(doc)
    assert facts["target_machine"]["value"] == "LUMI-G"
    assert facts["requested_node_hours"]["value"] == 1200
    assert facts["requested_gpu_hours"]["status"] == "NOT_FOUND"
    assert facts["maximum_gpus_per_job"]["value"] == 16
    assert facts["maximum_number_of_gpus"]["status"] == "NOT_FOUND"
    assert facts["scratch_storage_tb"]["value"] == 3
    assert facts["total_storage_gb"]["status"] == "NOT_FOUND"
    assert facts["total_transfer_tb"]["value"] == 9
    assert facts["total_transfer_gb"]["status"] == "NOT_FOUND"
    assert facts["listed_codes"]["value"].endswith("additional parser and PyTorch")
    assert "Jobs" not in facts["listed_codes"]["value"]
    assert facts["framework_names"]["value"] == "PyTorch"


def test_alternate_country_and_principal_investigator_scope():
    doc = document([{"page": 1, "text": "Principal Investigator\nOrganization country: Finland\n"
         "Contact Person and Team Members\nTeam Members #1\nOrganization country: Germany\n"
         "Ethics Self-Assessment\nDoes your proposal involve handling of personal data?: Yes\n"
         + policy_text("playground-access-ai-factories_en")}])
    facts = extract_facts(doc)
    assert facts["country"]["value"] == "Finland"
    assert facts["personal_data_declared"]["value"] is True
    assert facts["access_mode"]["value"] == "PLAYGROUND"


@pytest.mark.parametrize("mode", ["LARGE_SCALE", "AI_SCIENCE"])
def test_unsupported_profile_never_invokes_fast_lane_model_or_rules(mode):
    class ForbiddenBackend:
        name, version = "forbidden", "test"

        def decide(self, state, question):
            pytest.fail("Fast Lane backend must not be called")

    doc = document([{"page": 1, "text": f"Access mode: {mode}\nTarget machine: LUMI-G\n"
                     "Requested GPU hours: 999999\nMaximum number of GPUs: 1\nProject duration: 1\n"
                     "Code details and feasibility\nPyTorch supports ROCm GPU jobs."}])
    state = new_review(doc, ForbiddenBackend(), load_policy(), "synthetic-reviewer")
    assert state["rules"]["suggested"] == "REVIEW_REQUIRED"
    assert [f["code"] for f in state["rules"]["findings"]] == ["unsupported_profile"]
    assert all(d["status"] == "UNSUPPORTED_PROFILE" for d in state["decisions"].values())
