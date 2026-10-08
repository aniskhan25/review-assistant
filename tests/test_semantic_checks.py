from app.semantic_checks import combine
from tests.helpers import review


def checks(**answers):
    return {key: {"status": "OK", "answer": value} for key, value in answers.items()}


def test_cuda_only_failure_wins_over_positive_checks():
    result = combine("software_gpu_capable", checks(dependencies_identified="YES", amd_path_supported="YES", cuda_only_required="YES"), review())
    assert result[0] == "NO" and result[2] == ["cuda_only_required"]


def test_missing_amd_evidence_is_not_incompatibility():
    assert combine("software_gpu_capable", checks(dependencies_identified="YES", amd_path_supported="UNKNOWN", cuda_only_required="UNKNOWN"), review())[0] == "UNKNOWN"


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
    answer = combine("workplan_sufficient", checks(goals_concrete="YES", jobs_budgeted="YES", startup_accounted="UNKNOWN", execution_fits="YES"), review())
    assert answer[0] == "UNKNOWN"


def test_explicit_infeasible_execution_overrides_other_positive_checks():
    answer = combine("workplan_sufficient", checks(goals_concrete="YES", jobs_budgeted="YES", startup_accounted="YES", execution_fits="NO"), review())
    assert answer[0] == "NO"
