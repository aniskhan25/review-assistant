"""Automatic prefill is distinct from an individual reviewer confirmation."""


def fact_evidence(state, fact):
    if fact.get("confirmed"):
        return fact.get("reviewer_evidence_ids", [])
    source = fact.get("source")
    if not source or fact["status"] != "PRESENT" or not state["extraction_resolved"]:
        return []
    return [e["id"] for e in state["document"]["evidence"]
            if e.get("scope") not in {"assessment", "team", "allocation_history"}
            and e["page"] == source["page"] and source["text"] in e["text"]]


def fact_ready(state, fact):
    return bool(fact_evidence(state, fact)) and fact["status"] in {"PRESENT", "ABSENT"}


def decision_ready(state, qid, decision):
    if decision.get("confirmed"):
        return decision.get("reviewer_answer") in {"YES", "NO"}
    question = state["registry"]["questions"][qid]
    source_rule = decision.get("inference_mode") == "source_rule" and decision["status"] == "SOURCE_RULE_MATCH"
    if source_rule and (qid == "country_eligible" or question.get("organization_reference")):
        from app.eligibility import reference_current
        if not reference_current(decision.get("reference", {})):
            return False
    # Lack of prior installation is a setup warning, not a rejection. Clear
    # negative installation answers can be included in the single final approval.
    evidence_first = question.get("evidence_first", False)
    if (evidence_first and decision["status"] == "EVIDENCE_NOT_DEMONSTRATED"
            and decision["answer"] == "NO" and not decision.get("contradiction")):
        return bool(decision["evidence_ids"]) and state["extraction_resolved"]
    resolved_answer = decision["answer"] == "YES" or ((evidence_first or source_rule) and decision["answer"] == "NO") or (qid == "code_previously_installed" and decision["answer"] == "NO")
    return ((not question.get("manual_only") or source_rule) and not decision.get("contradiction") and not decision.get("compatibility_unresolved")
            and decision["status"] in {"OK", "AGGREGATED", "SOURCE_RULE_MATCH"} and resolved_answer
            and decision["confidence"] >= state["policy"]["high_confidence"]
            and decision["margin"] >= state["policy"]["minimum_margin"]
            and bool(decision["evidence_ids"]) and state["extraction_resolved"])
