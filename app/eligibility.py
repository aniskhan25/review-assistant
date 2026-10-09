"""Source-backed eligibility prefills under the supplied guide, without model guesses."""
from datetime import date
import hashlib
import json

from app.decision import ManualBackend, decide
from app.readiness import fact_evidence, fact_ready
from app.retrieval import retrieve

CATEGORIES = {'startup', 'start-up', 'sme', 'small and medium enterprise (sme)',
              'public sector', 'public-sector institution', 'public sector institution'}


def reference_current(reference, today=None):
    today = today or date.today()
    try:
        return date.fromisoformat(reference['checked']) <= today <= date.fromisoformat(reference['expires'])
    except (ValueError, KeyError, TypeError):
        return False


def prefill(state, qid, question):
    evidence = retrieve(state['document']['evidence'], question)
    decision = decide(ManualBackend(), qid, question, evidence, state['policy'])
    facts = state['facts']
    if facts['access_mode']['value'] not in {'FAST_LANE', 'PLAYGROUND'} or str(facts['target_machine']['value']).upper() not in {'LUMI-G', 'LUMI G'}:
        return decision
    field = 'organization_type' if qid == 'organization_eligible' else 'country'
    fact = facts[field]
    if not fact_ready(state, fact) or not isinstance(fact['value'], str):
        return decision
    value = fact['value'].strip().casefold()
    answer = 'YES'
    if qid == 'organization_eligible':
        playground = question.get('organization_reference')
        if playground:
            if facts['access_mode']['value'] != 'PLAYGROUND' or not reference_current(playground):
                return decision
            if value in playground['eligible_categories']:
                reason = f"The proposal declares {fact['value']}, an eligible category for Playground access."
            elif value in playground['ineligible_categories']:
                answer = 'NO'
                reason = f"The proposal declares {fact['value']}. Playground targets industrial SMEs and startups; academic and public-sector applicants should use AI for Science and Collaborative EU projects."
            else:
                return decision
            reference = playground
        elif not question.get('source_category_prefill') or value not in CATEGORIES:
            return decision
        else:
            reference = {'source': state['policy']['rule_sources']['organization_eligible'],
                         'guidance': state['policy']['guidance_sources']}
            reason = f"The proposal declares {fact['value']}, which meets the supplied guide's organisation-category rule."
    else:
        reference = question.get('country_reference', {})
        if not reference_current(reference):
            return decision
        value = reference.get('aliases', {}).get(value, value)
        if value not in {country.casefold() for country in reference.get('countries', [])}:
            # This subset covers EU members only; affiliated countries need verification.
            return decision
        reason = f"The proposal's declared country, {fact['value']}, is an EU member in the dated reference list; the supplied guide permits EU countries."
    version = hashlib.sha256(json.dumps(reference, sort_keys=True).encode()).hexdigest()
    decision.update(answer=answer, model_answer=answer, probabilities={}, confidence=1., margin=1.,
                    status='SOURCE_RULE_MATCH', band='source-backed prefill', model='source-guidance-rule',
                    model_version=version, inference_mode='source_rule', evidence_ids=fact_evidence(state, fact),
                    reference=reference, reference_reason=reason)
    return decision
