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


def review_reasons(state, qid, decision):
    """Explain existing gates without changing confidence or approval policy."""
    if decision_ready(state, qid, decision):
        return []
    reasons = []
    statuses = {
        'MODEL_ERROR': 'Model inference failed; check the evidence and record an answer.',
        'STALE_FACTS': 'Facts or evidence changed; rerun suggestions or verify the answer.',
        'NO_EVIDENCE_FOUND': 'No relevant supporting passage was retrieved.',
        'MANUAL_REQUIRED': 'This check requires reviewer verification.',
        'UNSUPPORTED_PROFILE': 'This access profile is not supported for this check.',
        'CHECK_DISAGREEMENT': 'Supporting interpretations disagree.',
        'ACCOUNTING_ASSUMPTION_REVIEW': 'GPU accounting assumptions need verification.',
    }
    if decision['status'] in statuses:
        reasons.append(statuses[decision['status']])
    if not state['extraction_resolved']:
        reasons.append('Document extraction is not resolved.')
    if decision.get('contradiction'):
        reasons.append('The evidence and suggested answer conflict.')
    if decision.get('compatibility_unresolved'):
        reasons.append('A material compatibility check remains unresolved.')
    if decision['answer'] == 'UNKNOWN':
        reasons.append('The model did not establish YES or NO; this does not prove incompatibility.')
    policy = state['policy']
    if decision.get('confidence', 0) < policy['high_confidence']:
        reasons.append(f"The supporting score ({decision.get('confidence', 0):.0%}) is below the automatic-prefill threshold ({policy['high_confidence']:.0%}).")
    if decision.get('margin', 0) < policy['minimum_margin']:
        reasons.append('The score difference between answers is below the automatic-prefill threshold.')
    weak = [d.get('check_title', key) for key, d in decision.get('checks', {}).items()
            if d.get('status') != 'OK' or d.get('answer') == 'UNKNOWN'
            or d.get('confidence', 0) < policy['high_confidence'] or d.get('margin', 0) < policy['minimum_margin']]
    if weak:
        reasons.append('Inspect supporting checks: ' + '; '.join(weak) + '.')
    return reasons or ['Verify the evidence and applicable reference before confirming this answer.']
