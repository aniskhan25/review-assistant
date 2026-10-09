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


def test_reference_background_is_not_application_proof():
    from app.decision import decide
    class Capture:
        name, version = 'fixture', '1'
        def decide(self, text, question):
            assert 'not proof of application installation or exact-version compatibility' in text
            assert 'https://docs.example.test/framework' in text
            return {'YES': .95, 'NO': .03, 'UNKNOWN': .02}
    state = review()
    q = dict(state['registry']['questions']['software_gpu_capable'])
    q['background_references'] = [{'claim': 'Generic framework support', 'url': 'https://docs.example.test/framework'}]
    result = decide(Capture(), 'software_gpu_capable', q, state['document']['evidence'], state['policy'])
    assert result['status'] == 'OK'
    assert result['evidence_ids'] == [e['id'] for e in state['document']['evidence']]


def test_registry_42_preserves_full_workplan_aggregation():
    state = review()
    state['registry']['version'] = '4.2'
    assert combine('workplan_sufficient', checks(goals_concrete='YES', jobs_budgeted='UNKNOWN', execution_fits='YES'), state)[0] == 'UNKNOWN'


def test_opposite_prior_use_interpretations_remain_unresolved():
    from app.semantic_checks import resolve_corroboration
    primary = dict(status='OK', answer='NO', probabilities={'YES': .01, 'NO': .99, 'UNKNOWN': 0}, latency_ms=5, band='high')
    secondary = dict(status='OK', answer='YES', latency_ms=7)
    result = resolve_corroboration(primary, secondary)
    assert result['answer'] == 'UNKNOWN' and result['status'] == 'CHECK_DISAGREEMENT'
    assert result['probabilities'] == primary['probabilities'] and primary['answer'] == 'NO'


def test_registry_42_does_not_override_with_weak_negative_check():
    state = review();state['registry']['version'] = '4.2'
    c = checks(compatibility_blocker='YES')
    c['compatibility_blocker']['confidence'] = .7
    assert combine('software_gpu_capable', c, state)[0] == 'UNKNOWN'
    state['registry']['version'] = '4.1'
    assert combine('software_gpu_capable', c, state)[0] == 'NO'


def test_deterministic_capacity_failure_is_not_filtered_by_model_confidence():
    state = review();state['registry']['version'] = '4.2'
    state['facts']['requested_gpu_hours']['value'] = 99999999
    c = checks(goals_concrete='YES', jobs_budgeted='YES', execution_fits='YES')
    for check in c.values(): check['confidence'] = .7
    assert combine('workplan_sufficient', c, state)[0] == 'NO'


def test_empty_form_headings_do_not_displace_actual_plan():
    from app.retrieval import retrieve
    evidence = [dict(id=str(i), section='Code details', scope='proposal', text='Code details #1\n4/8\nName and version of the code:') for i in range(8)]
    evidence.append(dict(id='plan', section='Code details', scope='proposal', text='Train 10000 steps with PyTorch.'))
    q = dict(sections=['code'], keywords=['code', 'version'], restrict_sections=True)
    assert [e['id'] for e in retrieve(evidence, q)] == ['plan']


def test_modern_playground_heading_is_technical_evidence():
    from app.ingestion import document
    from app.retrieval import retrieve
    doc = document([{'page': 1, 'text': 'Code details, development and data management\nCode(s) used: PyTorch'}])
    q = dict(sections=['code'], keywords=['PyTorch'], restrict_sections=True)
    assert retrieve(doc['evidence'], q)


def test_explicit_deferred_builds_are_not_contradicted_by_rocm_mention():
    from app.review import new_review
    from app.configuration import load_policy
    from app.ingestion import document
    from tests.helpers import TEXT
    from tests.test_exception_workflow import PositiveBackend
    text = TEXT + '\nCode details #1\nName and version of the code: PyTorch version pinned after training tests.\nWebpage and other references: docs\nCode details #2\nName and version of the code: ROCm version pinned after validation.\nWebpage and other references: docs'
    d = new_review(document([{'page': 1, 'text': text}]), PositiveBackend(), load_policy(), 'test')['decisions']['software_gpu_capable']
    assert d['answer'] == 'NO' and not d['contradiction'] and d['ready']
