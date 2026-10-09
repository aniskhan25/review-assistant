from app.semantic_checks import combine, combine_legacy
from tests.helpers import review


def checks(**answers):
    return {key: {"status": "OK", "answer": value} for key, value in answers.items()}


def test_cuda_only_failure_wins_over_positive_checks():
    result = combine_legacy("software_gpu_capable", checks(dependencies_identified="YES", amd_path_supported="YES", cuda_only_required="YES"), review())
    assert result[0] == "NO" and result[2] == ["cuda_only_required"]


def test_missing_amd_evidence_is_not_incompatibility():
    assert combine_legacy("software_gpu_capable", checks(dependencies_identified="YES", amd_path_supported="UNKNOWN", cuda_only_required="UNKNOWN"), review())[0] == "UNKNOWN"


def test_pending_installation_and_conflicting_prior_execution():
    for prior, expected in [("UNKNOWN", "NO"), ("YES", "UNKNOWN")]:
        answer = combine("code_previously_installed", checks(prior_lumi_run=prior, standard_environment_only="NO", custom_install_pending="YES"), review())
        assert answer[0] == expected


def test_capacity_overrides_positive_workplan_checks():
    state = review()
    state["facts"]["requested_gpu_hours"]["value"] = 99999999
    answer = combine("workplan_sufficient", checks(goals_concrete="YES", jobs_budgeted="YES", startup_accounted="YES", execution_fits="YES"), state)
    assert answer[0] == "NO" and "capacity" in answer[1]


def test_one_missing_workplan_component_prevents_positive_answer():
    answer = combine_legacy("workplan_sufficient", checks(goals_concrete="YES", jobs_budgeted="YES", startup_accounted="UNKNOWN", execution_fits="YES"), review())
    assert answer[0] == "UNKNOWN"


def test_explicit_infeasible_execution_overrides_other_positive_checks():
    answer = combine("workplan_sufficient", checks(goals_concrete="YES", jobs_budgeted="YES", startup_accounted="YES", execution_fits="NO"), review())
    assert answer[0] == "NO"


def test_unproven_installation_is_no_not_incompatibility():
    answer = combine("code_previously_installed", checks(prior_lumi_run="NO", custom_install_pending="UNKNOWN"), review())
    assert answer[0] == "NO" and "does not establish incompatibility" in answer[1]


def test_material_version_requirement_overrides_plausible_amd_path():
    answer = combine("software_gpu_capable", checks(amd_path_supported="YES", compatibility_blocker="YES"), review())
    assert answer[0] == "NO"


def test_unresolved_compatibility_does_not_become_positive():
    from app.readiness import decision_ready
    state = review()
    decision = dict(confirmed=False, compatibility_unresolved=True, status='AGGREGATED', answer='YES', confidence=.99, margin=.98, evidence_ids=['ev-1'])
    assert not decision_ready(state, 'software_gpu_capable', decision)


def test_plausible_workplan_does_not_require_separate_startup_timetable():
    assert combine("workplan_sufficient", checks(goals_concrete="YES", jobs_budgeted="YES", execution_fits="YES"), review())[0] == "YES"


def test_unresolved_workload_sizing_needs_review():
    assert combine("workplan_sufficient", checks(goals_concrete="YES", jobs_budgeted="UNKNOWN", execution_fits="YES"), review())[0] == "UNKNOWN"


def test_insufficient_sizing_overrides_positive_execution_assessment():
    assert combine("workplan_sufficient", checks(goals_concrete="YES", jobs_budgeted="NO", execution_fits="YES"), review())[0] == "NO"


def test_old_registry_keeps_old_installation_semantics():
    state = review()
    state['registry']['version'] = '3.0'
    assert combine("code_previously_installed", checks(prior_lumi_run="NO", standard_environment_only="UNKNOWN", custom_install_pending="UNKNOWN"), state)[0] == "UNKNOWN"


def test_technical_retrieval_excludes_ethics_sections():
    from app.retrieval import retrieve
    evidence = [dict(id='ethics', section='Privacy & Data Governance', scope='proposal', text='goals target experiment'),
                dict(id='summary', section='Project summary (abstract)', scope='proposal', text='concrete goals')]
    question = dict(sections=['summary'], keywords=['goals'], restrict_sections=True)
    assert [e['id'] for e in retrieve(evidence, question)] == ['summary']


def test_synthetic_checks_use_current_registry_ids():
    import json
    from pathlib import Path
    registry = review()['registry']
    for line in Path('evaluation/datasets/narrow-checks.jsonl').read_text().splitlines():
        case = json.loads(line)
        assert case['check_id'] in registry['questions'][case['question_id']]['checks']


def test_binary_evidence_still_abstains_at_low_confidence():
    from app.decision import decide
    class BinaryBackend:
        name, version = 'jevos', 'fixture'
        def decide(self, text, question):
            return {'YES': .51, 'NO': .49, 'UNKNOWN': 0.0}
    state = review()
    q = state['registry']['questions']['workplan_sufficient']
    q = dict(q, **q['checks']['goals_concrete'])
    result = decide(BinaryBackend(), 'goals_concrete', q, state['document']['evidence'], state['policy'])
    assert result['inference_mode'] == 'binary_evidence'
    assert result['answer'] == 'UNKNOWN' and result['status'] == 'LOW_CONFIDENCE'
    assert result['probabilities']['UNKNOWN'] == 0


def test_architecture_confidence_includes_resolved_compatibility_check():
    state = review()
    answer, _, used = combine('software_gpu_capable', checks(dependencies_identified='YES', amd_path_supported='YES', cuda_only_required='UNKNOWN', compatibility_blocker='NO'), state)
    assert answer == 'YES' and 'compatibility_blocker' in used
