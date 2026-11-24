"""Continuation history is context, never an invented current workload."""
from app.configuration import review_registry
from app.retrieval import retrieve
from app.source_claims import source_claim


def passage(eid, section, text, scope='proposal'):
    return dict(id=eid, page=1, section=section, text=text, scope=scope)


def test_prior_allocations_remain_visible_in_readiness_and_sizing():
    r = review_registry('FAST_LANE')['questions']
    history = passage('history', 'Previous allocations',
                      'Previous allocation used 50000 GPU hours: three training runs with 10000 GPU hours each.',
                      'allocation_history')
    evidence = [passage(str(i), 'Code details',
                        'LUMI ROCm GPU training models tested validated porting training results.') for i in range(12)] + [history]
    for q in [r['fast_lane_validated'], r['code_previously_installed']['checks']['prior_lumi_run'],
              r['workplan_sufficient']['checks']['jobs_budgeted']]:
        found = retrieve(evidence, q, limit=q['retrieval_limit'])
        assert any(e['id'] == 'history' for e in found)
        assert len(found) <= q['retrieval_limit']
        assert any(e['scope'] == 'proposal' for e in found)


def test_history_is_not_a_literal_current_quantity_or_current_goal():
    r = review_registry('FAST_LANE')['questions']['workplan_sufficient']['checks']
    history = passage('history', 'Previous allocations',
                      'We trained three models and processed 40 billion tokens.', 'allocation_history')
    assert source_claim(r['jobs_budgeted'], [history]) is None
    assert retrieve([history], r['goals_concrete']) == []


def test_reserved_history_does_not_admit_assessments_or_team_claims():
    q = review_registry('FAST_LANE')['questions']['fast_lane_validated']
    evidence = [passage('assessment', 'Previous allocations', 'LUMI prior tests passed.', 'assessment'),
                passage('team', 'Previous allocations', 'LUMI prior tests passed.', 'team'),
                passage('current', 'Code details', 'The current application targets LUMI ROCm.')]
    assert [e['id'] for e in retrieve(evidence, q)] == ['current']
