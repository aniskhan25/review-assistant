"""Review state, explicit confirmation, and deterministic assessment composition."""

import copy
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone

from app.configuration import load_config
from app.decision import ANSWERS, decide
from app.extraction import FIELDS, extract_facts, parse_value
from app.retrieval import retrieve
from app.rules import evaluate

REQUIRED_FACTS = ("access_mode", "target_machine", "requested_gpu_hours", "maximum_number_of_gpus",
                  "project_duration_months", "total_storage_gb", "personal_data_declared", "vat_number", "previous_lumi_use")


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def new_review(doc, backend, policy, reviewer):
    registry = load_config("questions.json")
    state = {"id": uuid.uuid4().hex, "revision": 0, "created_at": timestamp(), "reviewer": reviewer,
             "document": doc, "facts": extract_facts(doc), "decisions": {},
             "registry": registry, "policy": copy.deepcopy(policy), "policy_hash": digest(policy),
             "registry_hash": digest(registry), "final": None, "extraction_resolved": not doc["warnings"]}
    analyze(state, backend)
    return state


def analyze(state, backend):
    confirmed_facts = {key: {"value": fact["value"], "evidence_ids": fact.get("reviewer_evidence_ids", [])}
                       for key, fact in state["facts"].items() if fact["confirmed"]}
    context = "Reviewer-verified structured facts:\n" + json.dumps(confirmed_facts) if confirmed_facts else ""
    for qid, question in state["registry"]["questions"].items():
        evidence = retrieve(state["document"]["evidence"], question)
        decision = decide(backend, qid, question, evidence, state["policy"], context)
        decision["confirmed_facts_hash"] = digest(confirmed_facts)
        # This flag asks for resolution; it never flips a model answer automatically.
        text = " ".join(e["text"] for e in evidence)
        conflict = qid == "software_gpu_capable" and decision["model_answer"] == "NO" and re.search(r"\bROCm\b|\bAMD support\b", text, re.I)
        prior = state["facts"]["previous_lumi_use"]["value"]
        conflict = conflict or (qid == "code_previously_installed" and prior is True and decision["model_answer"] == "NO")
        decision["contradiction"] = bool(conflict)
        if conflict:
            decision["status"] = "CONTRADICTION"
        state["decisions"][qid] = decision
    refresh(state)


def refresh(state):
    state["rules"] = evaluate(state, state["policy"])
    state["final"] = None


def find_evidence(state, ids):
    if not isinstance(ids, list) or not ids or len(ids) > 30:
        raise ValueError("Select supporting evidence")
    index = {e["id"]: e for e in state["document"]["evidence"]}
    if any(not isinstance(key, str) or key not in index for key in ids):
        raise ValueError("Evidence does not belong to this proposal")
    return [index[key] for key in dict.fromkeys(ids)]


def text_input(value, name, limit=2000):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f"Invalid {name}")
    return value.strip()


def confirm_decision(state, qid, answer, evidence_ids, note):
    if qid not in state["decisions"] or answer not in ANSWERS:
        raise ValueError("Invalid question or answer")
    note = text_input(note, "reviewer note")
    evidence = find_evidence(state, evidence_ids)
    decision = state["decisions"][qid]
    if (answer != decision["answer"] or decision["contradiction"]) and not note:
        raise ValueError("Overrides and contradiction resolution require a note")
    decision.update({"reviewer_answer": answer, "confirmed": answer != "UNKNOWN",
                     "reviewer_note": note, "reviewer_evidence_ids": [e["id"] for e in evidence],
                     "confirmed_at": timestamp()})
    refresh(state)


def confirm_fact(state, field, raw, status, evidence_ids, note):
    if field not in FIELDS or status not in {"PRESENT", "ABSENT"}:
        raise ValueError("Invalid fact or status")
    note = text_input(note, "reviewer note")
    evidence = find_evidence(state, evidence_ids)
    if status == "ABSENT":
        if field != "vat_number" or not note:
            raise ValueError("Only VAT may be explicitly absent; provide a verification note")
        value = None
    else:
        value = parse_value(field, text_input(raw, "fact value", 1000))
    fact = state["facts"][field]
    changed = value != fact["value"] or status != fact["status"]
    if changed and not note:
        raise ValueError("Fact corrections require a note")
    fact.update({"value": value, "status": status, "confirmed": True,
                 "reviewer_note": note, "reviewer_evidence_ids": [e["id"] for e in evidence],
                 "confirmed_at": timestamp()})
    if field == "vat_number":
        state["facts"]["vat_number_present"].update({"value": status == "PRESENT", "status": status,
                                                  "confirmed": True, "reviewer_evidence_ids": evidence_ids})
    if changed:
        for decision in state["decisions"].values():
            decision.update({"confirmed": False, "reviewer_answer": None, "status": "STALE_FACTS",
                             "band": "reviewer required"})
    refresh(state)


def add_evidence(state, page, text, note):
    text = text_input(text, "evidence", 5000)
    note = text_input(note, "transcription note")
    if type(page) is not int or not any(p["page"] == page for p in state["document"]["pages"]):
        raise ValueError("Invalid proposal page")
    if not text or not note:
        raise ValueError("Manual evidence needs text and a source/transcription note")
    evidence = state["document"]["evidence"]
    evidence.append({"id": "manual-" + uuid.uuid4().hex[:12], "page": page,
                     "section": "Reviewer transcription", "text": text, "note": note,
                     "added_by": state["reviewer"]})
    for decision in state["decisions"].values():
        decision.update({"confirmed": False, "reviewer_answer": None})
    refresh(state)


def finalize(state, classification, rationale, acknowledge_findings):
    if classification not in {"ACCEPT", "REJECT"}:
        raise ValueError("Choose ACCEPT or REJECT explicitly")
    rationale = text_input(rationale, "final rationale", 4000)
    if not rationale or acknowledge_findings is not True:
        raise ValueError("Final rationale and acknowledgement of all findings are required")
    missing = [key for key in REQUIRED_FACTS if not state["facts"][key]["confirmed"]]
    if missing:
        raise ValueError("Confirm required facts: " + ", ".join(missing))
    if not state["extraction_resolved"]:
        raise ValueError("Resolve extraction warnings first")
    if state["facts"]["access_mode"]["value"] != "FAST_LANE":
        raise ValueError("Only Fast Lane reviews are supported")
    if state["facts"]["target_machine"]["value"].upper() not in {"LUMI-G", "LUMI G"}:
        raise ValueError("Only the LUMI-G target is supported")
    if any(not d["confirmed"] or d["reviewer_answer"] == "UNKNOWN" for d in state["decisions"].values()):
        raise ValueError("Confirm every decision; unresolved answers cannot be exported")
    for decision in state["decisions"].values():
        find_evidence(state, decision["reviewer_evidence_ids"])
    templates = load_config("templates.json")
    rules = evaluate(state, state["policy"])
    lines = ["SHADOW DRAFT — not for submission" if state["policy"]["mode"] == "shadow" else "Technical assessment",
             f"Reviewer classification: {classification}", f"Reviewer: {state['reviewer']}",
             f"Proposal: {state['document']['document_id']}", ""]
    citations = {}
    for qid, d in state["decisions"].items():
        evidence = find_evidence(state, d["reviewer_evidence_ids"])
        refs = ", ".join(f"{e['id']} (p. {e['page']})" for e in evidence)
        lines += [state["registry"]["questions"][qid]["title"],
                  templates[d["reviewer_answer"]][qid] + f" [Evidence: {refs}]", ""]
        if d["reviewer_note"]:
            lines += ["Reviewer note: " + d["reviewer_note"], ""]
        citations[qid] = d["reviewer_evidence_ids"]
    calculation = next(f["calculation"] for f in rules["findings"] if f["code"] == "resource_consumption")
    lines += [f"At continuous maximum concurrency, the requested allocation requires {calculation['minimum_months']:.3f} 30-day months.",
              "This calculation does not guarantee scheduling availability."]
    for finding in rules["findings"]:
        if finding["severity"] in {"warning", "blocker", "attention"}:
            lines.append(f"{finding['severity'].upper()}: {finding['message']}")
    lines += ["", "Reviewer classification rationale: " + rationale]
    if state["policy"]["support_contact"]:
        lines += ["Support: " + state["policy"]["support_contact"]]
    state["rules"] = rules
    state["final"] = {"classification": classification, "rationale": rationale, "text": "\n".join(lines),
                      "confirmed_at": timestamp(), "citations": citations, "templates_hash": digest(templates),
                      "fact_citations": {k: state["facts"][k]["reviewer_evidence_ids"] for k in REQUIRED_FACTS}}
    return state["final"]
