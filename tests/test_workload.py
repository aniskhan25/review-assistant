import copy

from app.decision import ManualBackend
from app.review import analyze, prepare_review, confirm_fact, add_evidence, finalize
from app.workload import assess_workload, reason_options, compose_reason
from tests.helpers import review, TEXT, confirmed


class Scores:
    name, version = 'fixture', '1'

    def __init__(self, answer='YES'):
        self.answer, self.calls = answer, []

    def decide(self, evidence, question):
        self.calls.append((evidence, question))
        return {key: .98 if key == self.answer else .01 for key in ('YES', 'NO', 'UNKNOWN')}


def test_advisory_does_not_change_decisions_or_rejection_gates():
    state = confirmed(review())
    original = copy.deepcopy(state['decisions'])
    for answer, expected in [('YES', 'Plausible'), ('NO', 'Potential material concern'), ('UNKNOWN', 'Needs clarification')]:
        state['workload'] = assess_workload(state, Scores(answer), '')
        prepare_review(state)
        assert {f['finding'] for f in state['workload']['findings']} == {expected}
        assert state['decisions'] == original
        assert state['draft_classification'] == 'ACCEPT'
        result = finalize(state, 'ACCEPT', 'Reviewed evidence', True)
        assert 'Potential material concern' not in result['text']
        comment = ' '.join(o['text'] for o in reason_options(state['workload']))
        result = finalize(state, 'REJECT', 'Reviewer confirmed a material concern', True, global_comment=comment)
        assert comment in result['text']


def test_summary_preserves_evidence_and_excludes_other_parties_and_assessments():
    state = review(TEXT + '\nTeam Members #1\nTraining model SECRET_TEAM\nTechnical Assessment - Reviewer\nTraining model SECRET_REVIEW')
    summary = str(state['workload']['summary'])
    assert 'SECRET_TEAM' not in summary and 'SECRET_REVIEW' not in summary
    assert 'We will run 50 training experiments' in summary
    memory = next(x for x in state['workload']['summary'] if x['label'] == 'Memory / precision')
    assert not memory['passages']
    ids = {ev['id'] for ev in state['document']['evidence']}
    assert all(p['evidence_id'] in ids for x in state['workload']['summary'] for p in x['passages'])


def test_profile_context_reference_grounding_and_expiry():
    for mode in ['Fast Lane', 'Playground']:
        state = review(TEXT.replace('Fast Lane', mode))
        backend = Scores()
        assess_workload(state, backend, '')
        assert len(backend.calls) == 3
        assert ('bounded pilot' if mode == 'Playground' else 'workload sizing evidence') in backend.calls[0][1]['instructions']
        assert '64 GB HBM per GCD' in backend.calls[0][0]
        state['registry']['workload']['references'][0]['expires'] = '2020-01-01'
        backend.calls.clear()
        result = assess_workload(state, backend, '')
        assert not backend.calls
        assert all(f['decision']['status'] == 'REFERENCE_EXPIRED' for f in result['findings'])


def test_edits_invalidate_advisory_and_rerun_refreshes_it():
    state = review()
    fact = state['facts']['requested_gpu_hours']
    ids = state['decisions']['workplan_sufficient']['evidence_ids']
    confirm_fact(state, 'requested_gpu_hours', '40000', 'PRESENT', ids, 'Corrected budget')
    assert state['workload']['stale'] and not state['workload_reason_options']
    analyze(state, ManualBackend())
    assert not state['workload']['stale']
    add_evidence(state, 1, 'Memory per GCD: 40 GB', 'Verified transcription')
    assert state['workload']['stale']


def test_legacy_reviews_do_not_acquire_new_assessment():
    state = review()
    del state['registry']['workload']
    analyze(state, ManualBackend())
    assert state['workload'] is None


def test_model_failure_uncertainty_and_unsupported_mode_are_nonblocking():
    class Failing(Scores):
        def decide(self, evidence, question):
            raise RuntimeError('private detail')
    state = review()
    result = assess_workload(state, Failing(), '')
    assert all(f['decision']['status'] == 'MODEL_ERROR' for f in result['findings'])
    assert 'private detail' not in str(result)
    state['facts']['access_mode']['value'] = 'SCIENCE'
    backend = Scores()
    assert all(f['decision']['status'] == 'UNSUPPORTED_PROFILE' for f in assess_workload(state, backend, '')['findings'])
    assert not backend.calls


def test_diagnostics_stay_internal_and_verified_reason_is_applicant_readable():
    state = confirmed(review())
    state['workload'] = assess_workload(state, Scores('NO'), '')
    prepare_review(state)
    assert state['draft_global_comment'] == ''
    assert 'Needs clarification' not in state['draft']
    assert '[proposal evidence:' not in state['draft']
    options = state['workload_reason_options']
    assert len(options) == 3 and all(o['classification'] == 'REJECT' for o in options)
    reason = ' '.join(o['text'] for o in options)
    final = finalize(state, 'REJECT', reason, True)
    assert reason in final['text'].split('Reason for classification:')[1]
    assert 'ev-' not in final['text']
    assert 'Needs clarification' not in final['text']
    assert not final['global_comment']
    assert state['workload']['findings'][0]['decision']['evidence_ids']
    state['workload']['input_hash'] = 'outdated'
    prepare_review(state)
    assert state['workload_reason_options'] == []


def test_positive_findings_offer_acceptance_wording_and_failures_offer_none():
    state = review()
    positive = reason_options(assess_workload(state, Scores('YES'), ''))
    assert all(o['classification'] == 'ACCEPT' for o in positive)
    assert all('Please' not in o['text'] for o in positive)
    assert reason_options(state['workload']) == []  # Manual backend unavailable


def test_capacity_reason_in_email_contains_numbers_and_assumptions():
    state = confirmed(review(TEXT.replace('50000', '12000').replace('Maximum number of GPUs: 64', 'Maximum number of GPUs: 8')))
    prepare_review(state)
    assert state['draft_classification'] == 'REJECT'
    assert '12,000 GPU-hours' in state['draft_rationale']
    assert '11,520 GPU-hours' in state['draft_rationale']
    assert '30-day months' in state['draft_rationale']
    assert 'Please revise' in state['draft_rationale']


def test_matching_findings_default_into_reason_without_duplicate_blocker_wording():
    state = confirmed(review(TEXT.replace('50000', '12000').replace('Maximum number of GPUs: 64', 'Maximum number of GPUs: 8')))
    for key in ('workplan_sufficient', 'official_rocm_builds_available'):
        state['decisions'][key]['reviewer_answer'] = 'NO'
    state['workload'] = assess_workload(state, Scores('NO'), '')
    prepare_review(state)
    reason = state['draft_rationale']
    assert state['draft_classification'] == 'REJECT'
    assert compose_reason(state['workload_reason_options'], 'REJECT') in reason
    assert reason.count('Please explain') == 1
    assert reason.count('12,000') == 1
    assert 'cannot be consumed' not in reason
    assert reason.count('AMD/ROCm builds') == 1
    assert '[proposal evidence:' not in reason
    assert reason in state['draft']
    assert state['draft_global_comment'] == ''
    assert any(f['code'] == 'official_rocm_builds_available' and f['severity'] == 'blocker' for f in state['rules']['findings'])
    state['workload']['input_hash'] = 'stale'
    prepare_review(state)
    assert not any(o['text'] in state['draft_rationale'] for o in reason_options(assess_workload(state, Scores('NO'), '')))
    assert 'suitable AMD/ROCm builds' in state['draft_rationale']


def test_acceptance_includes_only_positive_fit_findings_and_preserves_saved_reason():
    state = confirmed(review())
    state['workload'] = assess_workload(state, Scores('YES'), '')
    prepare_review(state)
    assert compose_reason(state['workload_reason_options'], 'ACCEPT') in state['draft_rationale']
    finalize(state, 'ACCEPT', 'My reviewed reason with the fit wording excluded.', True)
    prepare_review(state)
    assert state['final']['rationale'] == 'My reviewed reason with the fit wording excluded.'
    state['workload'] = assess_workload(state, Scores('NO'), '')
    prepare_review(state)
    assert state['draft_classification'] == 'ACCEPT'
    assert not any(o['text'] in state['draft_rationale'] for o in state['workload_reason_options'])


def test_coherent_reason_covers_each_subset_without_repeated_requests():
    from itertools import combinations
    state = review()
    options = reason_options(assess_workload(state, Scores('NO'), ''))
    for count in (1, 2, 3):
        for subset in combinations(options, count):
            text = compose_reason(subset, 'REJECT')
            assert text.count('Please') == 1 and '\n' not in text
            assert ('AMD/ROCm' in text) == any(o['id'] == 'technical_fit' for o in subset)
            assert ('expected runtimes' in text) == any(o['id'] == 'resource_fit' for o in subset)
            assert ('success criteria' in text) == any(o['id'] == 'plan_credibility' for o in subset)
            assert 'ev-' not in text and 'Needs clarification' not in text
    assert compose_reason(options, 'ACCEPT') == ''
    assert compose_reason([], 'REJECT') == ''


def test_model_uncertainty_does_not_become_missing_information_in_reason():
    state = confirmed(review())
    for answer in ('UNKNOWN',):
        state['workload'] = assess_workload(state, Scores(answer), '')
        prepare_review(state)
        assert all(f['finding'] == 'Needs clarification' for f in state['workload']['findings'])
        assert state['workload_reason_options'] == []
        assert 'Further detail is needed' not in state['draft_rationale']
    finding = state['workload']['findings'][0]
    finding['decision']['status'] = 'NO_EVIDENCE_FOUND'
    assert len(reason_options(state['workload'])) == 1
