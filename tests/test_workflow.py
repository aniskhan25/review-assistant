import json
import math
import subprocess
import sys
import time

import pytest

from app.configuration import load_policy
from app.decision import ManualBackend, SystemOneBackend, decide, validate_probabilities
from app.extraction import extract_facts, parse_value
from app.ingestion import ingest_pdf, document
from app.retrieval import retrieve
from app.review import (confirm_decision, confirm_fact, add_evidence, finalize, analyze, new_review)
from app.rules import evaluate
from app.storage import Store, ConflictError
from app.evaluation import benchmark, metrics
from tests.helpers import TEXT, review, confirmed, pdf_bytes


def test_real_pdf_to_confirmed_assessment():
    doc = ingest_pdf(pdf_bytes())
    assert doc["pages"][0]["text"].startswith("Project summary")
    state = new_review(doc, ManualBackend(), load_policy(), "test-reviewer")
    assert state["facts"]["requested_gpu_hours"]["value"] == 50000
    assert state["facts"]["vat_number_present"]["value"] is True
    result = finalize(confirmed(state), "ACCEPT", "Feasible independent experiments", True)
    assert "SHADOW DRAFT" in result["text"]
    assert "1.085" in result["text"]
    assert result["citations"] and result["fact_citations"]


@pytest.mark.parametrize("raw", ["-1", "0", "nan", "inf", "1,2", "5 TB", "2 days", "1e20"])
def test_ambiguous_numbers_rejected(raw):
    with pytest.raises(ValueError):
        parse_value("requested_gpu_hours", raw)


def test_extraction_conflict_and_missing_are_not_absence():
    doc = document([{"page": 1, "text": "VAT number: FI123\nRequested GPU hours: 100"},
                    {"page": 2, "text": "Requested GPU hours: 200"}])
    facts = extract_facts(doc)
    assert facts["requested_gpu_hours"]["status"] == "CONFLICT"
    assert facts["maximum_number_of_gpus"]["status"] == "NOT_FOUND"
    assert extract_facts(document([{"page": 1, "text": ""}]))["vat_number_present"]["value"] is None
    assert extract_facts(document([{"page": 1, "text": "VAT number: Not applicable"}]))["vat_number_present"]["value"] is False


def test_numeric_units_and_multiline_fields():
    facts = extract_facts(document([{"page": 1, "text": "Requested GPU hours\n50,000 GPU hours\nMaximum number of GPUs: 64\nProject duration: 2 months"}]))
    assert facts["requested_gpu_hours"]["value"] == 50000
    assert facts["project_duration_months"]["value"] == 2
    with pytest.raises(ValueError):
        parse_value("maximum_number_of_gpus", "1.5")


def test_pdf_failure_and_blank_page():
    with pytest.raises(ValueError, match="PARSE_ERROR"):
        ingest_pdf(b"%PDF-not-real")
    doc = ingest_pdf(pdf_bytes(""))
    assert doc["warnings"]
    assert extract_facts(doc)["vat_number"]["status"] == "PARSE_ERROR"


class FakeBackend:
    name, version = "fixture", "1"

    def __init__(self, probabilities):
        self.probabilities = probabilities

    def decide(self, state, question):
        assert state and question["criteria"]
        return self.probabilities


@pytest.mark.parametrize("p", [{"YES": 1}, {"YES": math.nan, "NO": 0, "UNKNOWN": 0},
                              {"YES": 1, "NO": 1, "UNKNOWN": 0}, {"YES": True, "NO": 0, "UNKNOWN": 0}])
def test_invalid_probabilities_fail_closed(p):
    with pytest.raises(ValueError):
        validate_probabilities(p)
    state = review()
    qid, q = next(iter(state["registry"]["questions"].items()))
    result = decide(FakeBackend(p), qid, q, state["document"]["evidence"], state["policy"])
    assert result["status"] == "MODEL_ERROR" and result["answer"] == "UNKNOWN"


@pytest.mark.parametrize("probabilities,answer", [({"YES": .6, "NO": .3, "UNKNOWN": .1}, "UNKNOWN"),
                                               ({"YES": .85, "NO": .1, "UNKNOWN": .05}, "YES"),
                                               ({"YES": .7, "NO": .2, "UNKNOWN": .1}, "YES")])
def test_confidence_policy(probabilities, answer):
    state = review()
    qid, q = next(iter(state["registry"]["questions"].items()))
    result = decide(FakeBackend(probabilities), qid, q, state["document"]["evidence"], state["policy"])
    assert result["answer"] == answer


def test_margin_and_no_evidence():
    state = review()
    qid, q = next(iter(state["registry"]["questions"].items()))
    policy = dict(state["policy"], minimum_margin=.8)
    backend = FakeBackend({"YES": .7, "NO": .2, "UNKNOWN": .1})
    assert decide(backend, qid, q, state["document"]["evidence"], policy)["answer"] == "UNKNOWN"
    assert decide(backend, qid, q, [], policy)["status"] == "NO_EVIDENCE_FOUND"


def test_retrieval_and_contradiction_no_auto_reject():
    state = review()
    analyze(state, FakeBackend({"YES": .01, "NO": .98, "UNKNOWN": .01}))
    assert state["decisions"]["software_gpu_capable"]["contradiction"]
    assert state["rules"]["suggested"] != "REJECT"
    q = state["registry"]["questions"]["software_gpu_capable"]
    assert any("ROCm" in e["text"] for e in retrieve(state["document"]["evidence"], q))


def test_resource_formula_boundary_and_invalid_inputs():
    state = review()
    for hours, severity in [(64 * 24 * 30 * 2, "info"), (64 * 24 * 30 * 2 + 1, "blocker")]:
        state["facts"]["requested_gpu_hours"]["value"] = hours
        rules = evaluate(state, state["policy"])
        assert next(f for f in rules["findings"] if f["code"] == "resource_consumption")["severity"] == severity
    state["facts"]["maximum_number_of_gpus"]["value"] = 0
    assert next(f for f in evaluate(state, state["policy"])["findings"] if f["code"] == "resource_consumption")["severity"] == "attention"


def test_storage_personal_data_installation_and_concurrency():
    state = confirmed(review())
    policy = dict(state["policy"], approved=True, gpu_units_per_node=8, storage_warning_gb=500)
    state["facts"]["personal_data_declared"]["value"] = True
    rules = evaluate(state, policy)
    assert rules["suggested"] == "ACCEPT"
    assert {f["code"] for f in rules["findings"]} >= {"storage", "personal_data", "multi_node", "code_previously_installed"}
    state["decisions"]["software_gpu_capable"]["reviewer_answer"] = "NO"
    assert evaluate(state, policy)["suggested"] == "REJECT"


def test_final_confirmation_and_edit_invalidation():
    state = review()
    with pytest.raises(ValueError):
        finalize(state, "ACCEPT", "why", True)
    confirmed(state)
    finalize(state, "ACCEPT", "why", True)
    ids = [state["document"]["evidence"][0]["id"]]
    confirm_fact(state, "requested_gpu_hours", "60000", "PRESENT", ids, "Correction verified")
    assert state["final"] is None and not any(d["confirmed"] for d in state["decisions"].values())
    with pytest.raises(ValueError):
        finalize(state, "ACCEPT", "why", True)


def test_unknown_invalid_evidence_and_override_notes():
    state = review()
    qid = "software_gpu_capable"
    ids = [state["document"]["evidence"][0]["id"]]
    with pytest.raises(ValueError):
        confirm_decision(state, qid, "YES", ids, "")
    with pytest.raises(ValueError):
        confirm_decision(state, qid, "YES", ["foreign-evidence"], "why")
    confirmed(state)
    confirm_decision(state, qid, "UNKNOWN", ids, "Not resolved")
    with pytest.raises(ValueError):
        finalize(state, "ACCEPT", "why", True)


def test_manual_evidence_and_unsupported_profile():
    state = confirmed(review())
    add_evidence(state, 1, "Corrected transcription", "Read original PDF")
    assert not any(d["confirmed"] for d in state["decisions"].values())
    with pytest.raises(ValueError):
        add_evidence(state, 9, "Text", "Note")
    state = confirmed(review())
    state["facts"]["access_mode"]["value"] = "PLAYGROUND"
    with pytest.raises(ValueError, match="Only Fast Lane"):
        finalize(state, "ACCEPT", "why", True)


def test_storage_revisions_audit_and_retention(tmp_path):
    store = Store(tmp_path / "private")
    state = review()
    store.insert(state)
    store.save(state, 0, "confirmed")
    with pytest.raises(ConflictError):
        store.save(state, 0, "stale")
    assert "PyTorch" not in json.dumps(store.audit(state["id"]))
    result = store.purge(30, 90, now=time.time() + 31 * 86400)
    assert result["reviews"] == 1 and result["audit_records"] == 0
    assert store.audit(state["id"])
    store.purge(30, 90, now=time.time() + 91 * 86400)
    assert not store.audit(state["id"])


@pytest.mark.parametrize("endpoint", ["https://example.com/v1/systemone", "http://localhost:80/v1/systemone", "http://127.0.0.1.evil/v1/systemone", "http://user@127.0.0.1/v1/systemone", "http://127.0.0.1/v1/systemone?url=evil"])
def test_remote_endpoints_rejected(endpoint):
    with pytest.raises(ValueError):
        SystemOneBackend(endpoint, "test", "version")


def test_network_guard_and_offline_workflow():
    script = '''
import socket
from app.security import install_network_guard
from tests.helpers import confirmed, review
from app.review import finalize
install_network_guard()
try:
    socket.create_connection(("8.8.8.8", 443))
except PermissionError:
    pass
else:
    raise AssertionError("Egress permitted")
finalize(confirmed(review()), "ACCEPT", "Confirmed offline", True)
'''
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, timeout=20)


def test_dataset_split_leakage_and_metrics():
    rows = [{"application_id": "a", "group_id": "g", "split": "heldout"},
            {"application_id": "b", "group_id": "g", "split": "development"}]
    with pytest.raises(ValueError, match="leaks"):
        benchmark(rows, ManualBackend(), load_policy())
    assert metrics([]) == {"count": 0}


def test_synthetic_regression_corpus():
    from pathlib import Path
    records = [json.loads(line) for line in Path("evaluation/datasets/synthetic.jsonl").read_text().splitlines()]
    report = benchmark(records, ManualBackend(), load_policy())
    assert report["applications"] == 20
    assert report["field_accuracy"] == 1
    assert report["evidence_top5_recall"] == 1
    assert report["dataset_kind"] == "synthetic" and not report["production_qualified"]


def test_confirmed_fact_context_is_passed_to_model():
    state = confirmed(review())

    class CaptureBackend(FakeBackend):
        def decide(self, text, question):
            assert '"requested_gpu_hours": {"value": 50000' in text
            return super().decide(text, question)

    analyze(state, CaptureBackend({"YES": .9, "NO": .05, "UNKNOWN": .05}))
    assert all(d["status"] == "OK" for d in state["decisions"].values())


def test_production_configuration_gate(tmp_path):
    policy = load_policy()
    policy["mode"] = "production"
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy))
    with pytest.raises(ValueError, match="Production requires"):
        load_policy(path)


def test_non_lumi_target_and_extraction_gap_block_export():
    state = confirmed(review())
    state["extraction_resolved"] = False
    with pytest.raises(ValueError, match="extraction"):
        finalize(state, "ACCEPT", "why", True)
    state["extraction_resolved"] = True
    state["facts"]["target_machine"]["value"] = "OTHER"
    with pytest.raises(ValueError, match="LUMI-G"):
        finalize(state, "ACCEPT", "why", True)
