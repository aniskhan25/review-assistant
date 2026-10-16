import pytest
from app.configuration import review_registry
from app.retrieval import retrieve
from app.review import prepare_review, finalize, confirm_decision
from app.readiness import review_reasons
from tests.helpers import review, confirmed, TEXT


def test_readiness_negative_routes_feasible_fast_lane_to_playground():
    state = confirmed(review())
    ids = state['decisions']['workplan_sufficient']['reviewer_evidence_ids']
    confirm_decision(state, 'fast_lane_validated', 'NO', ids, 'No relevant prior testing reported')
    assert state['decisions']['workplan_sufficient']['reviewer_answer'] == 'YES'
    assert state['draft_classification'] == 'REJECT'
    assert 'Playground first' in state['draft_rationale']
    assert 'Try and Buy' not in state['draft_rationale']
    assert "rather than the project's merit" in state['draft_rationale']
    assert not state['exceptions']['decisions']
    assert 'Playground first' in state['draft']
    assert 'Try and Buy' not in state['draft']
    with pytest.raises(ValueError, match='readiness rejections'):
        finalize(state, 'REJECT', state['draft_rationale'], True, rejection_category='OUT_OF_RESOURCES')
    with pytest.raises(ValueError, match='exception'):
        finalize(state, 'ACCEPT', 'Proceed anyway', True)


def test_playground_and_old_registry_do_not_gain_readiness_requirement():
    assert 'fast_lane_validated' not in review_registry('PLAYGROUND')['questions']
    state = confirmed(review())
    del state['registry']['questions']['fast_lane_validated']
    del state['decisions']['fast_lane_validated']
    state['registry']['version']='4.6'
    prepare_review(state)
    assert state['draft_classification']=='ACCEPT'


def test_prior_lumi_no_is_not_a_readiness_failure_when_other_testing_is_confirmed():
    state = confirmed(review())
    assert state['facts']['previous_lumi_use']['value'] is False
    assert state['decisions']['code_previously_installed']['reviewer_answer']=='NO'
    assert state['decisions']['fast_lane_validated']['reviewer_answer']=='YES'
    assert state['draft_classification']=='ACCEPT'


def test_readiness_retrieves_technical_and_historical_evidence_not_team_or_assessments():
    q = review_registry('FAST_LANE')['questions']['fast_lane_validated']
    evidence = [dict(id=str(i), page=1, section=section, scope=scope, text=text) for i, (section,scope,text) in enumerate([
        ('Code details','proposal','We measured training throughput on local AMD MI210 using ROCm.'),
        ('Previous allocations','allocation_history','Try and Buy testing validated this same training workflow.'),
        ('Organization','team','We used LUMI and validated all results.'),
        ('Technical assessment','assessment','LUMI testing succeeded.')])]
    found=retrieve(evidence,q,limit=q['retrieval_limit'])
    assert {e['id'] for e in found}=={'0','1'}


def test_positive_requires_reasoned_review_but_confirmed_answer_clears_messages():
    state=review()
    qid='workplan_sufficient'
    d=state['decisions'][qid]
    d.update(answer='YES',status='AGGREGATED',confidence=.7,margin=.4,contradiction=False)
    reasons=review_reasons(state,qid,d)
    assert any('70%' in r and 'threshold' in r for r in reasons)
    d.update(confirmed=True,reviewer_answer='YES')
    assert review_reasons(state,qid,d)==[]


def test_model_failure_and_ambiguity_cannot_trigger_playground_rejection():
    state=confirmed(review())
    qid='fast_lane_validated'
    for status in ('MODEL_ERROR','CHECK_DISAGREEMENT','LOW_CONFIDENCE'):
        state['decisions'][qid].update(confirmed=False,reviewer_answer=None,answer='UNKNOWN',status=status)
        prepare_review(state)
        assert qid in state['exceptions']['decisions']
        assert state['draft_classification'] is None
