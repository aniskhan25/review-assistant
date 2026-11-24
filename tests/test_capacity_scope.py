"""Capacity accounting must distinguish job size from project concurrency."""
from app.capacity import resource_capacity
from app.review import prepare_review
from app.rules import evaluate
from app.semantic_checks import combine
from tests.helpers import review, confirmed, TEXT


def proposal():
    return TEXT.replace('Maximum total concurrent GPUs: 64', 'Maximum number of GPUs: 16').replace(
        'Requested GPU hours: 50000', 'Requested GPU hours: 37000').replace(
        'Project duration (months): 2', 'Project duration (months): 3') + (
        '\nScalability and performance\nSlurm arrays use 1-4 standard-g nodes per training job. '
        'The largest job uses 4 nodes. The project averages 4-5 standard-g nodes over 3 months.')


def test_per_job_limit_does_not_establish_project_capacity():
    state = confirmed(review(proposal()))
    finding = resource_capacity(state)
    assert finding['severity'] == 'attention'
    assert finding['calculation']['maximum_total_concurrent_gpus'] is None
    assert finding['calculation']['required_average_gpus'] > 16
    assert 'maximum_gpu_hours' not in finding['calculation']
    assert state['draft_classification'] == 'ACCEPT'
    assert 'theoretical maximum' not in state['draft_rationale']
    assert 'fit within the theoretical capacity' not in state['draft']
    assert 'Independent jobs may run concurrently' in state['draft']


def test_explicit_total_concurrency_can_still_trigger_capacity_blocker():
    state = confirmed(review(proposal().replace('Maximum number of GPUs: 16', 'Maximum total concurrent GPUs: 16')))
    finding = resource_capacity(state)
    assert finding['severity'] == 'blocker'
    assert finding['calculation']['maximum_gpu_hours'] == 34560
    assert state['draft_classification'] == 'REJECT'
    assert '34,560' in state['draft_rationale']


def test_explicit_per_job_limit_and_job_count_establish_total_upper_bound():
    state = review(proposal() + '\nMaximum # GPUs to be used per job: 16\nNumber of jobs simultaneously: 2')
    finding = resource_capacity(state)
    assert finding['severity'] == 'info'
    assert finding['calculation']['maximum_total_concurrent_gpus'] == 32
    assert finding['calculation']['maximum_gpu_hours'] == 69120
    state['facts']['maximum_simultaneous_jobs']['value'] = 1
    assert resource_capacity(state)['severity'] == 'blocker'


def test_no_job_count_is_inferred_from_slurm_arrays():
    state = review(proposal() + '\nMaximum # GPUs to be used per job: 16')
    assert resource_capacity(state)['severity'] == 'attention'
    assert evaluate(state, state['policy'])['suggested'] != 'REJECT'


def test_workplan_aggregation_does_not_reject_using_per_job_ceiling():
    state = review(proposal())
    checks = {key: {'status': 'OK', 'answer': 'YES'} for key in
              ('goals_concrete', 'jobs_budgeted', 'execution_fits')}
    assert combine('workplan_sufficient', checks, state)[0] == 'YES'
    state['facts']['maximum_number_of_gpus']['source']['text'] = 'Maximum total concurrent GPUs: 16'
    assert combine('workplan_sufficient', checks, state)[0] == 'NO'


def test_unapproved_old_capacity_answer_recombines_cached_checks():
    state = confirmed(review(proposal()))
    d = state['decisions']['workplan_sufficient']
    evidence = d['reviewer_evidence_ids']
    d.update(confirmed=False, reviewer_answer=None, answer='NO', model_answer='NO',
             status='AGGREGATED', aggregation_reason='Requested GPU-hours exceed continuous maximum capacity within the project duration.',
             checks={key: {'status': 'OK', 'answer': 'YES', 'confidence': .96,
                           'margin': .92, 'evidence_ids': evidence} for key in
                     ('goals_concrete', 'jobs_budgeted', 'execution_fits')})
    prepare_review(state)
    assert d['answer'] == 'YES' and d['ready']
    assert d['confidence'] == .96
    assert d['previous_capacity_assessment']['answer'] == 'NO'
    assert state['draft_classification'] == 'ACCEPT'
    assert state['decisions']['code_previously_installed']['confirmed']
    assert '37,000 GPU-hours exceed' not in state['draft']


def test_explicit_reviewer_answer_and_approved_review_are_preserved():
    state = confirmed(review(proposal()))
    d = state['decisions']['workplan_sufficient']
    d['aggregation_reason'] = 'Requested GPU-hours exceed continuous maximum capacity within the project duration.'
    d['reviewer_answer'] = 'NO'
    prepare_review(state)
    assert d['reviewer_answer'] == 'NO' and d['confirmed']
    assert state['draft_classification'] == 'REJECT'
    assert 'previous_capacity_assessment' not in d
