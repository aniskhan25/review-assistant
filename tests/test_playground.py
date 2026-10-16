"""Synthetic onboarding proposals and evidence-gap policy, without private contents."""
import pytest

from app.configuration import load_policy
from app.ingestion import document
from app.review import new_review, finalize, prepare_review, analyze
from app.decision import ManualBackend
from tests.helpers import TEXT
from tests.test_exception_workflow import PositiveBackend


def playground(backend=None, text=None):
    text = text or TEXT.replace('Fast Lane', 'Playground').replace('VAT number:', 'Company VAT number:')
    return new_review(document([{'page': 1, 'text': text}]), backend or PositiveBackend(), load_policy(), 'test')


def test_simple_playground_can_be_accepted_without_mature_job_budget():
    text = TEXT.replace('Fast Lane', 'Playground').split('Workplan')[0] + 'Workplan\nTry a small PyTorch inference example on LUMI to learn the environment.'
    state = playground(text=text)
    assert state['registry']['profile'] == 'PLAYGROUND'
    assert set(state['decisions']) == {'software_gpu_capable', 'code_previously_installed', 'workplan_sufficient', 'organization_eligible', 'country_eligible'}
    assert set(state['decisions']['workplan_sufficient']['checks']) == {'onboarding_plan'}
    assert not any(state['exceptions'].values())
    assert state['draft_classification'] == 'ACCEPT'
    assert finalize(state, 'ACCEPT', state['draft_rationale'], True)['classification'] == 'ACCEPT'


def test_company_vat_alias_keeps_lead_provenance_and_excludes_team():
    state = playground(text=TEXT.replace('Fast Lane', 'Playground').replace('VAT number:', 'Company VAT number:') + '\nTeam Members #1\nCompany VAT number: DE98765432')
    fact = state['facts']['vat_number']
    assert fact['value'] == 'FI12345678' and fact['ready']
    assert fact['source']['text'] == 'Company VAT number: FI12345678'


class NoSupport:
    name, version = 'fixture', '1'
    def decide(self, text, question):
        return {'YES': .05, 'NO': .05, 'UNKNOWN': .9}


def missing_text():
    return TEXT.replace('Fast Lane', 'Playground').replace('Project summary', 'Submission details').split('Code details')[0]


def test_missing_support_becomes_explained_no_with_one_final_approval():
    state = playground(NoSupport(), missing_text())
    assert not any(state['exceptions'].values())
    assert state['draft_classification'] == 'REJECT'
    for key in ('software_gpu_capable', 'code_previously_installed', 'workplan_sufficient'):
        d = state['decisions'][key]
        assert d['answer'] == 'NO' and d['ready'] and not d['confirmed']
        assert any(c['status'] == 'NO_EVIDENCE_FOUND' for c in d['checks'].values())
    result = finalize(state, 'REJECT', state['draft_rationale'], True, rejection_details=['workplan'])
    assert 'Automated check basis' not in result['text']
    assert 'not independently proven impossible' not in result['text']
    assert 'concrete onboarding task' in result['text']
    assert 'identifies an incompatibility' not in result['text']


@pytest.mark.parametrize('failure', ['model', 'extraction', 'contradiction'])
def test_operational_failure_is_not_missing_evidence(failure):
    class Failing(NoSupport):
        def decide(self, text, question):
            raise ValueError('fixture failure')
    state = playground(Failing() if failure == 'model' else NoSupport())
    if failure == 'extraction':
        state['extraction_resolved'] = False
        analyze(state, NoSupport())
    if failure == 'contradiction':
        state['decisions']['software_gpu_capable']['contradiction'] = True
        prepare_review(state)
    assert state['exceptions']['decisions']
    with pytest.raises(ValueError):
        finalize(state, 'REJECT', 'Not enough evidence', True)


def test_fast_lane_negative_is_prefilled_and_saved_old_registry_is_preserved():
    state = new_review(document([{'page': 1, 'text': TEXT}]), PositiveBackend(), load_policy(), 'test')
    d = state['decisions']['workplan_sufficient']
    d.update(answer='NO', confidence=.95, margin=.9)
    prepare_review(state)
    assert d['ready'] and state['draft_classification'] == 'REJECT'
    state['registry']['version'] = '4.2'
    state['registry']['questions']['workplan_sufficient'].pop('evidence_first')
    prepare_review(state)
    assert not d['ready']


def test_manual_backend_does_not_invent_missing_evidence_answer():
    state = playground(ManualBackend())
    assert state['decisions']['workplan_sufficient']['answer'] == 'UNKNOWN'


def test_empty_retrieval_records_search_scope_without_inventing_model_scores():
    text = TEXT.replace('Fast Lane', 'Playground').replace('Project summary', 'Submission details').split('Code details')[0]
    state = playground(NoSupport(), text)
    d = state['decisions']['workplan_sufficient']
    assert d['answer'] == 'NO' and d['ready']
    assert d['evidence_ids'] and 'searched' in d['evidence_scope']
    assert d['checks']['onboarding_plan']['status'] == 'NO_EVIDENCE_FOUND'


def test_no_plan_omits_capacity_estimate_and_keeps_direct_reasons():
    text = missing_text().replace('Maximum number of GPUs: 64', 'Maximum number of GPUs: 500000')
    state = playground(NoSupport(), text)
    assert not any(state['exceptions'].values())
    assert '0.000' not in state['draft']
    assert '30-day months' not in state['draft']
    assert 'Automated check basis' not in state['draft']
    assert 'NO means' not in state['draft']
    assert 'NO: Is' not in state['draft_rationale']
    assert 'justify the requested GPU allocation' in state['draft']
    assert any(f['code'] == 'resource_consumption' and f['calculation']['minimum_months'] > 0 for f in state['rules']['findings'])


def test_impossible_capacity_still_explains_rejection_without_a_plan():
    text = missing_text().replace('Requested GPU hours: 50000', 'Requested GPU hours: 99999999')
    state = playground(NoSupport(), text)
    assert 'exceed the maximum' in state['draft']
    assert '99,999,999 GPU-hours exceed the theoretical maximum of 92,160 GPU-hours' in state['draft_rationale']
    assert 'cannot be consumed within the declared duration' not in state['draft_rationale']


def test_final_approval_preserves_reviewer_rationale_and_notes():
    state = playground(NoSupport(), missing_text())
    state['decisions']['workplan_sufficient']['reviewer_note'] = 'Only a business objective is supplied.'
    result = finalize(state, 'REJECT', 'Please name the software and describe a trial.', True, global_comment='A revised application is needed.')
    assert result['rationale'] == 'Please name the software and describe a trial.'
    assert 'Only a business objective is supplied.' in result['text']
    assert 'A revised application is needed.' in result['text']


def test_classifier_uncertainty_is_not_missing_evidence():
    state = playground(NoSupport())
    d = state['decisions']['workplan_sufficient']
    assert d['answer'] == 'UNKNOWN' and not d['ready']
    assert d['status'] != 'EVIDENCE_NOT_DEMONSTRATED'
    assert state['decisions']['software_gpu_capable']['answer'] == 'YES'


def test_modest_positive_confidence_is_preserved_for_review():
    class Modest(PositiveBackend):
        def decide(self, text, question):
            if question['title'].startswith('Is a concrete Playground'):
                return {'YES': .7, 'NO': .2, 'UNKNOWN': .1}
            return super().decide(text, question)
    state = playground(Modest())
    d = state['decisions']['workplan_sufficient']
    assert d['answer'] == 'YES' and not d['ready']
    assert d['confidence'] == .7
