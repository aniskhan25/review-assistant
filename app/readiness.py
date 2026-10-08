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
    # Negative recommendations remain exceptions, never automatic rejections.
    return (not question.get("manual_only") and not decision.get("contradiction")
            and decision["status"] == "OK" and decision["answer"] == "YES"
            and decision["confidence"] >= state["policy"]["high_confidence"]
            and decision["margin"] >= state["policy"]["minimum_margin"]
            and bool(decision["evidence_ids"]) and state["extraction_resolved"])
