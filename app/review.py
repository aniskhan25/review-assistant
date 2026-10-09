"""Review state, explicit confirmation, and deterministic assessment composition."""

import copy
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone

from app.configuration import load_config, review_registry
from app.decision import ANSWERS, decide, ManualBackend, evidence_first
from app.extraction import FIELDS, extract_facts, parse_value
from app.retrieval import retrieve
from app.rules import evaluate
from app.semantic_checks import assess
from app.readiness import fact_evidence, fact_ready, decision_ready
from app.eligibility import prefill as eligibility_prefill

REQUIRED_FACTS = ("access_mode", "target_machine", "requested_gpu_hours", "maximum_number_of_gpus",
                  "project_duration_months", "total_storage_gb", "personal_data_declared", "vat_number",
                  "organization_type", "country")


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def new_review(doc, backend, policy, reviewer):
    facts = extract_facts(doc)
    registry = review_registry(facts["access_mode"]["value"])
    state = {"id": uuid.uuid4().hex, "revision": 0, "created_at": timestamp(), "reviewer": reviewer,
             "document": doc, "facts": facts, "decisions": {},
             "registry": registry, "policy": copy.deepcopy(policy), "policy_hash": digest(policy),
             "registry_hash": digest(registry), "final": None, "extraction_resolved": not doc["warnings"]}
    analyze(state, backend)
    return state


def analyze(state, backend):
    mode = state["facts"]["access_mode"]["value"]
    unsupported = mode not in {"FAST_LANE", "PLAYGROUND"} or (mode == "PLAYGROUND" and state["registry"].get("profile") != "PLAYGROUND")
    confirmed_facts = {key: {"value": fact["value"], "evidence_ids": fact.get("reviewer_evidence_ids", [])}
                       for key, fact in state["facts"].items() if fact["confirmed"]}
    extracted_facts = {key: {"value": fact["value"], "evidence_ids": fact_evidence(state, fact)}
                       for key, fact in state["facts"].items() if not fact["confirmed"] and fact_ready(state, fact)}
    context = "Reviewer-verified structured facts:\n" + json.dumps(confirmed_facts) if confirmed_facts else ""
    context += "\nAutomatically extracted proposal facts (untrusted evidence, not reviewer verified):\n" + json.dumps(extracted_facts)
    for qid, question in state["registry"]["questions"].items():
        evidence = retrieve(state["document"]["evidence"], question)
        if not unsupported and (question.get("source_category_prefill") or question.get("country_reference")):
            decision = eligibility_prefill(state, qid, question)
        elif question.get("checks") and not unsupported and not isinstance(backend, ManualBackend):
            decision = assess(state, backend, qid, question, context)
        else:
            decision = decide(ManualBackend() if unsupported else backend, qid, question, evidence, state["policy"], context)
        if unsupported:
            decision["status"] = "UNSUPPORTED_PROFILE"
        decision["confirmed_facts_hash"] = digest(confirmed_facts)
        # This flag asks for resolution; it never flips a model answer automatically.
        text = " ".join(e["text"] for e in evidence)
        conflict = qid == "software_gpu_capable" and decision["model_answer"] == "NO" and re.search(r"\bROCm\b|\bAMD support\b", text, re.I)
        prior = state["facts"]["previous_lumi_use"]["value"]
        conflict = conflict or (qid == "code_previously_installed" and prior is True and decision["model_answer"] == "NO")
        decision["contradiction"] = bool(conflict)
        if conflict:
            decision["status"] = "CONTRADICTION"
        if question.get("evidence_first") and not unsupported and not isinstance(backend, ManualBackend):
            decision = evidence_first(state, decision)
        state["decisions"][qid] = decision
    refresh(state)


def refresh(state):
    state["final"] = None
    prepare_review(state)


def prepare_review(state):
    state["rules"] = evaluate(state, state["policy"])
    for fact in state["facts"].values():
        fact["ready"] = fact_ready(state, fact)
    for qid, decision in state["decisions"].items():
        decision["ready"] = decision_ready(state, qid, decision)
    state["exceptions"] = {
        "facts": [key for key in REQUIRED_FACTS if not state["facts"][key]["ready"]],
        "decisions": [qid for qid, d in state["decisions"].items() if not d["ready"]],
        "extraction": not state["extraction_resolved"],
    }
    templates = load_config("templates.json")
    state["draft"] = "\n\n".join(
        title + "\n" + (d["reviewer_answer"] if d["confirmed"] else d["answer"])
        + ("" if d["ready"] else " — needs review")
        for qid, title in templates["form_questions"].items()
        for d in [state["decisions"][qid]])

    state["draft_classification"] = None
    state["draft_rationale"] = ""
    if not any(state["exceptions"].values()) and (state["facts"]["access_mode"]["value"] == "FAST_LANE" or state["registry"].get("profile") == "PLAYGROUND") and state["facts"]["target_machine"]["value"].upper() in {"LUMI-G", "LUMI G"}:
        blockers = [f["message"] for f in evaluate(state, state["policy"])["findings"] if f["severity"] == "blocker"]
        classification = "REJECT" if blockers else "ACCEPT"
        rationale = "; ".join(blockers) if blockers else "The reviewed evidence supports technical feasibility within the requested resources and duration."
        preview = finalize(copy.deepcopy(state), classification, rationale, True)
        state["draft"] = "PREVIEW — awaiting your final approval\n\n" + preview["text"]
        state["draft_classification"] = classification
        state["draft_rationale"] = rationale


def find_evidence(state, ids):
    if not isinstance(ids, list) or not ids or len(ids) > 30:
        raise ValueError("Select supporting evidence")
    index = {e["id"]: e for e in state["document"]["evidence"]}
    if any(not isinstance(key, str) or key not in index for key in ids):
        raise ValueError("Evidence does not belong to this proposal")
    if any(index[key].get("scope") == "assessment" for key in ids):
        raise ValueError("Reviewer assessment text cannot serve as proposal evidence")
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
    if (answer != decision["answer"] or decision["contradiction"]
            or state["registry"]["questions"][qid].get("require_note")) and not note:
        raise ValueError("Overrides, manual verification and contradiction resolution require a note")
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
        decision.update({"confirmed": False, "reviewer_answer": None, "status": "STALE_FACTS"})
    refresh(state)


def finalize(state, classification, rationale, acknowledge_findings, rejection_category="NOT_FEASIBLE",
             global_comment="", rejection_details=None, exception_note=""):
    if classification not in {"ACCEPT", "REJECT"}:
        raise ValueError("Choose ACCEPT or REJECT explicitly")
    rationale = text_input(rationale, "final rationale", 4000)
    if not rationale or acknowledge_findings is not True:
        raise ValueError("Final rationale and acknowledgement of all findings are required")
    missing = [key for key in REQUIRED_FACTS if not fact_ready(state, state["facts"][key])]
    if missing:
        raise ValueError("Resolve required facts: " + ", ".join(missing))
    if not state["extraction_resolved"]:
        raise ValueError("Resolve extraction warnings first")
    mode = state["facts"]["access_mode"]["value"]
    if mode not in {"FAST_LANE", "PLAYGROUND"} or (mode == "PLAYGROUND" and state["registry"].get("profile") != "PLAYGROUND"):
        raise ValueError("Only Fast Lane and Playground reviews with matching profiles are supported")
    if state["facts"]["target_machine"]["value"].upper() not in {"LUMI-G", "LUMI G"}:
        raise ValueError("Only the LUMI-G target is supported")
    if any(not decision_ready(state, qid, d) for qid, d in state["decisions"].items()):
        raise ValueError("Resolve decision exceptions; unresolved answers cannot be exported")
    decisions = copy.deepcopy(state["decisions"])
    for decision in decisions.values():
        if not decision["confirmed"]:
            decision["reviewer_answer"] = decision["answer"]
            decision["reviewer_evidence_ids"] = decision["evidence_ids"]
        find_evidence(state, decision["reviewer_evidence_ids"])
    for key in REQUIRED_FACTS:
        find_evidence(state, fact_evidence(state, state["facts"][key]))
    templates = load_config("templates.json")
    rules = evaluate(state, state["policy"])
    if rejection_category not in {"NOT_FEASIBLE", "OUT_OF_RESOURCES"}:
        raise ValueError("Choose a valid rejection category")
    global_comment = text_input(global_comment, "global comment", 4000)
    exception_note = text_input(exception_note, "exception note", 4000)
    rejection_details = [] if rejection_details is None else rejection_details
    if (not isinstance(rejection_details, list) or any(not isinstance(key, str) or key not in templates["rejection_details"] for key in rejection_details)):
        raise ValueError("Invalid rejection detail")
    if classification == "ACCEPT" and rejection_details:
        raise ValueError("Rejection wording is only available for rejected assessments")
    blockers = [f for f in rules["findings"] if f["severity"] == "blocker"]
    if classification == "ACCEPT" and blockers and not exception_note:
        raise ValueError("Explain the evidence supporting an exception to each blocking guideline")
    if "resource_capacity" in rejection_details and not any(f["code"] == "resource_consumption" for f in blockers):
        raise ValueError("Capacity rejection wording requires a failed resource-capacity check")
    eligibility_codes = {"vat", "organization_eligibility", "organization_eligible", "country_eligible"}
    if classification == "REJECT" and rejection_category != "NOT_FEASIBLE" and any(f["code"] in eligibility_codes for f in blockers):
        raise ValueError("Eligibility rejections must use the not-feasible category")
    classification_label = "Accepted" if classification == "ACCEPT" else (
        "Rejected (not feasible)" if rejection_category == "NOT_FEASIBLE" else "Rejected (out of resources)")
    lines = ["SHADOW DRAFT — not for submission" if state["policy"]["mode"] == "shadow" else "Technical assessment", ""]
    citations = {qid: d["reviewer_evidence_ids"] for qid, d in decisions.items()}
    for qid, title in templates["form_questions"].items():
        d = decisions[qid]
        wording = templates[d["reviewer_answer"]][qid]
        if d["reviewer_answer"] == "NO" and d.get("status") == "EVIDENCE_NOT_DEMONSTRATED":
            wording = "The supplied proposal does not demonstrate " + {"software_gpu_capable": "suitability of the named software for the target architecture.", "code_previously_installed": "previous installation or use on LUMI.", "workplan_sufficient": "a feasible plan for the requested allocation."}[qid]
        lines += [title, d["reviewer_answer"], wording]
        if d.get("aggregation_reason"):
            lines.append("Automated check basis: " + d["aggregation_reason"])
        if d["reviewer_note"]:
            lines.append(d["reviewer_note"])
        lines.append("")
    lines.append("Comment globally on the provided technical data and your conclusions:")
    if global_comment:
        lines.append(global_comment)
    calculation = next(f["calculation"] for f in rules["findings"] if f["code"] == "resource_consumption")
    lines += [f"At continuous maximum concurrency, the requested allocation requires {calculation['minimum_months']:.3f} 30-day months.",
              "This calculation does not guarantee scheduling availability."]
    if any(f["code"] == "storage" and f["severity"] == "warning" for f in rules["findings"]):
        lines.append(templates["storage_warning"].replace("50,000", f"{state['policy']['storage_warning_gb']:,.0f}"))
    lines += ["", "Classification:", classification_label, "", "Reason for classification:", rationale]
    if exception_note:
        lines.append("Reviewer justification for guideline exception: " + exception_note)
    if classification == "ACCEPT":
        lines.append(templates["acceptance"])
        if state["facts"]["personal_data_declared"]["value"]:
            lines.append(templates["personal_data"])
    else:
        for key in dict.fromkeys(rejection_details):
            lines.append("Please describe a concrete onboarding task or small experiment to be performed with the allocation."
                         if mode == "PLAYGROUND" and key == "workplan" else templates["rejection_details"][key])
        lines.append(templates["rejection_closing"])
    state["rules"] = rules
    state["final"] = {"classification": classification, "classification_label": classification_label,
                      "rejection_category": rejection_category if classification == "REJECT" else None,
                      "global_comment": global_comment, "rejection_details": rejection_details,
                      "exception_note": exception_note, "rationale": rationale, "text": "\n".join(lines),
                      "confirmed_at": timestamp(), "citations": citations, "templates_hash": digest(templates),
                      "follow_up": ["Notify CCR about accepted personal-data processing; CCR follows the internal DPA workflow."]
                          if classification == "ACCEPT" and state["facts"]["personal_data_declared"]["value"] else [],
                      "approval_scope": "Final approval includes automatically prefilled facts and decision answers",
                      "automatic_facts": [k for k in REQUIRED_FACTS if not state["facts"][k]["confirmed"]],
                      "automatic_decisions": [k for k, d in state["decisions"].items() if not d["confirmed"]],
                      "fact_citations": {k: fact_evidence(state, state["facts"][k]) for k in REQUIRED_FACTS}}
    return state["final"]
