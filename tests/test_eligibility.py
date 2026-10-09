from datetime import date

from app.eligibility import prefill, reference_current
from app.readiness import decision_ready
from tests.helpers import review


def configured():
    state = review()
    state['registry']['questions']['organization_eligible']['source_category_prefill'] = True
    state['registry']['questions']['country_eligible']['country_reference'] = {
        'source': 'https://example.test/eu-members', 'checked': '2026-01-01', 'expires': '2099-01-01',
        'countries': ['Finland', 'Czechia'], 'aliases': {'czech republic': 'czechia'}}
    return state


def test_declared_category_and_member_country_are_prefills():
    state = configured()
    for qid in ('organization_eligible', 'country_eligible'):
        d = prefill(state, qid, state['registry']['questions'][qid])
        assert d['answer'] == 'YES' and d['inference_mode'] == 'source_rule'
        assert d['evidence_ids'] and not d['confirmed']
        assert decision_ready(state, qid, d)


def test_large_enterprise_and_non_member_require_verification():
    state = configured()
    state['facts']['organization_type']['value'] = 'Large enterprise'
    state['facts']['country']['value'] = 'United Kingdom'
    for qid in ('organization_eligible', 'country_eligible'):
        d = prefill(state, qid, state['registry']['questions'][qid])
        assert d['answer'] == 'UNKNOWN' and d['status'] == 'MANUAL_REQUIRED'
        assert not decision_ready(state, qid, d)


def test_reference_expiry_and_missing_source_block_auto_eligibility():
    state = configured()
    q = state['registry']['questions']['country_eligible']
    d = prefill(state, 'country_eligible', q)
    d['reference']['expires'] = '2020-01-01'
    assert not decision_ready(state, 'country_eligible', d)
    assert prefill(state, 'country_eligible', q)['answer'] == 'UNKNOWN'
    state['facts']['organization_type']['status'] = 'CONFLICT'
    assert prefill(state, 'organization_eligible', state['registry']['questions']['organization_eligible'])['answer'] == 'UNKNOWN'


def test_reference_dates_must_be_valid_and_current():
    assert not reference_current({'checked': 'invalid', 'expires': '2099-01-01'})
    assert not reference_current({'checked': '2027-01-01', 'expires': '2099-01-01'}, date(2026,1,1))
