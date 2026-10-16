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


def test_playground_other_category_resolves_to_source_backed_negative():
    from tests.test_playground import playground
    from tests.helpers import TEXT
    from app.review import finalize
    text = TEXT.replace('Fast Lane', 'Playground').replace('Organization type: SME', 'Organization type: Other\nOther: specify the organization type:\nHigher Education Institution / University')
    state = playground(text=text)
    fact = state['facts']['organization_type']
    decision = state['decisions']['organization_eligible']
    assert fact['value'] == 'Higher Education Institution / University' and fact['ready']
    assert fact['source']['method'] == 'specified_other_category'
    assert decision['answer'] == 'NO' and decision['ready'] and not decision['confirmed']
    assert 'organization_eligible' not in state['exceptions']['decisions']
    result = finalize(state, 'REJECT', state['draft_rationale'], True)
    assert 'AI for Science and Collaborative EU projects' in result['rationale']


def test_other_description_excludes_team_and_assessment_across_pages():
    from app.ingestion import document
    from app.extraction import extract_facts
    doc = document([
        {'page': 1, 'text': 'Project Lead and Organisation information\nOrganization type: Other'},
        {'page': 2, 'text': 'Other: specify the organisation type:\nUniversity\nTeam Members #1\nOrganization type: Other\nOther: specify the organization type: SME\nTechnical Assessment - Reviewer\nOther: specify the organization type: Startup'},
    ])
    fact = extract_facts(doc)['organization_type']
    assert fact['value'] == 'University' and fact['status'] == 'PRESENT'
    assert fact['source']['page'] == 2 and len(fact['candidates']) == 1


def test_other_without_detail_and_conflicting_categories_stay_unresolved():
    from app.ingestion import document
    from app.extraction import extract_facts
    assert extract_facts(document([{'page': 1, 'text': 'Organization type: Other'}]))['organization_type']['value'] == 'Other'
    text = 'Organization type: Other\nOther: specify the organization type: University\nOrganization type: SME'
    assert extract_facts(document([{'page': 1, 'text': text}]))['organization_type']['status'] == 'CONFLICT'


def test_playground_reference_overrides_generic_public_sector_rule():
    from tests.test_playground import playground
    from tests.helpers import TEXT
    for category in ('SME', 'Startup', 'University', 'Public sector', 'Other', 'Large enterprise'):
        state = playground(text=TEXT.replace('Fast Lane', 'Playground').replace('Organization type: SME', 'Organization type: '+category))
        d = state['decisions']['organization_eligible']
        expected = 'YES' if category in ('SME', 'Startup') else 'NO' if category in ('University', 'Public sector') else 'UNKNOWN'
        assert d['answer'] == expected
        assert d['ready'] == (expected != 'UNKNOWN')
        q = state['registry']['questions']['organization_eligible']
        q['organization_reference']['expires'] = '2020-01-01'
        assert not decision_ready(state, 'organization_eligible', d)
        assert prefill(state, 'organization_eligible', q)['answer'] == 'UNKNOWN'


def test_horizon_country_prefix_matches_verified_norway_reference():
    from app.ingestion import document
    from app.extraction import extract_facts
    from tests.helpers import TEXT
    for field in ('Country: Horizon 2020: Norway',
                  'Country:\nHorizon 2020: Norway',
                  'Organisation Country - Horizon 2020: Norway',
                  'Country - Horizon 2020: Norway'):
        text = TEXT.replace('Country: Finland', field)
        fact = extract_facts(document([{'page': 1, 'text': text}]))['country']
        assert fact['value'] == 'Norway' and fact['status'] == 'PRESENT'
        assert field in fact['source']['text']
        state = review(text)
        assert state['facts']['country']['ready']
        d = state['decisions']['country_eligible']
        assert d['status'] == 'SOURCE_RULE_MATCH' and d['answer'] == 'YES'
        assert d['reference']['source'] == 'https://lumi-ai-factory.eu/pricing-and-eligibility/'
        assert 'EU member' not in d['reference_reason']


def test_horizon_country_prefix_keeps_conflicts_and_party_boundaries():
    from app.ingestion import document
    from app.extraction import extract_facts
    for extra, expected in (('\nCountry: Norway', 'PRESENT'),
                            ('\nCountry: Sweden', 'CONFLICT'),
                            ('\nTeam Members #1\nCountry: Sweden', 'PRESENT')):
        fact = extract_facts(document([{'page': 1, 'text': 'Country: Horizon 2020: Norway' + extra}]))['country']
        assert fact['status'] == expected
    for value in ('Unknown', 'Not provided'):
        fact = extract_facts(document([{'page': 1, 'text': 'Country: Horizon 2020: '+value}]))['country']
        assert fact['status'] == 'NOT_FOUND' and fact['value'] is None


def test_prefixed_eu_country_can_still_match_existing_reference():
    from tests.helpers import TEXT
    state = review(TEXT.replace('Country: Finland', 'Country: Horizon 2020: Finland'))
    d = state['decisions']['country_eligible']
    assert d['answer'] == 'YES' and d['inference_mode'] == 'source_rule'


def test_norway_reference_applies_to_both_modes_and_preserves_guards():
    from tests.helpers import TEXT
    for mode in ('Fast Lane', 'Playground'):
        state = review(TEXT.replace('Fast Lane', mode).replace('Country: Finland', 'Country: Horizon 2020: Norway'))
        q = state['registry']['questions']['country_eligible']
        assert prefill(state, 'country_eligible', q)['answer'] == 'YES'
        q['country_reference']['expires'] = '2020-01-01'
        assert prefill(state, 'country_eligible', q)['answer'] == 'UNKNOWN'
        q['country_reference']['expires'] = '2099-01-01'
        state['facts']['country']['status'] = 'CONFLICT'
        assert prefill(state, 'country_eligible', q)['answer'] == 'UNKNOWN'


def test_saved_subset_does_not_silently_gain_norway():
    state = configured()
    state['facts']['country']['value'] = 'Norway'
    q = state['registry']['questions']['country_eligible']
    assert prefill(state, 'country_eligible', q)['answer'] == 'UNKNOWN'
