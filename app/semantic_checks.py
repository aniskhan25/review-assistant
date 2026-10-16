"""Evidence checks and explicit aggregation for the three submission questions."""

import copy

from app.decision import decide
from app.retrieval import retrieve
from app.source_claims import source_claim, claim_decision, claim_evidence


def assess(state, backend, qid, question, context):
    checks = {}
    for key, specification in question["checks"].items():
        check = dict(question, **specification)
        check.pop("checks", None)
        evidence = retrieve(state["document"]["evidence"], check)
        claim = source_claim(check, claim_evidence(check, state["document"]["evidence"], evidence))
        checks[key] = claim_decision(key, check, claim) if claim else decide(backend, key, check, evidence, state["policy"], context)
        if check.get("corroborating_question") and checks[key]["answer"] in {"YES", "NO"}:
            secondary = dict(check, **check["corroborating_question"])
            secondary.pop("corroborating_question", None)
            corroboration = decide(backend, key + "-corroboration", secondary,
                                   retrieve(state["document"]["evidence"], secondary), state["policy"], context)
            checks[key] = resolve_corroboration(checks[key], corroboration)
        checks[key]["check_title"] = check["title"]
    answer, reason, used = combine(qid, checks, state)
    sources = list(dict.fromkeys(eid for key in used for eid in checks[key]["evidence_ids"]))
    confidence = min((checks[key]["confidence"] for key in used), default=0)
    margin = min((checks[key]["margin"] for key in used), default=0)
    capacity_failure = qid == "workplan_sufficient" and "exceed continuous maximum capacity" in reason
    if capacity_failure:
        from app.readiness import fact_evidence
        sources = list(dict.fromkeys(eid for key in
            ("requested_gpu_hours", "maximum_number_of_gpus", "project_duration_months")
            for eid in fact_evidence(state, state["facts"][key])))
        confidence = margin = 1.
    return {"question_id": qid, "question_version": question["version"],
            "model_answer": answer, "answer": answer, "probabilities": {},
            "confidence": confidence, "margin": margin,
            "band": "high" if answer != "UNKNOWN" and confidence >= state["policy"]["high_confidence"] else "reviewer required",
            "status": "AGGREGATED" if answer != "UNKNOWN" else "CHECKS_UNRESOLVED",
            "model": backend.name, "model_version": backend.version,
            "latency_ms": round(sum(d["latency_ms"] for d in checks.values()), 3),
            "evidence_ids": sources, "reviewer_answer": None, "reviewer_note": "", "confirmed": False,
            "checks": checks, "aggregation_reason": reason,
            "compatibility_unresolved": (state["registry"].get("profile") != "PLAYGROUND" and state["registry"]["version"] in {"4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7"} and qid == "software_gpu_capable"
                                          and checks["compatibility_blocker"]["answer"] == "UNKNOWN"),
            "aggregation_version": {"4.7": "5", "4.6": "5", "4.5": "5", "4.4": "5", "4.3": "4", "4.2": "3", "4.1": "3", "4.0": "2"}.get(state["registry"]["version"], "1")}


def resolve_corroboration(primary, secondary):
    result = copy.deepcopy(primary)
    result["corroboration"] = secondary
    result["latency_ms"] += secondary.get("latency_ms", 0)
    if (primary["status"] == secondary["status"] == "OK"
            and {primary["answer"], secondary["answer"]} == {"YES", "NO"}):
        result.update(answer="UNKNOWN", status="CHECK_DISAGREEMENT", band="reviewer required")
    return result


def combine(qid, checks, state):
    if state["registry"].get("profile") == "PLAYGROUND":
        return combine_playground(qid, checks, state)
    answer, reason, used = _combine(qid, checks, state)
    facts = state["facts"]
    capacity_failure = (qid == "workplan_sufficient"
                        and all(facts[key]["status"] == "PRESENT" for key in ("requested_gpu_hours", "maximum_number_of_gpus", "project_duration_months"))
                        and facts["requested_gpu_hours"]["value"] > facts["maximum_number_of_gpus"]["value"] * 24 * 30 * facts["project_duration_months"]["value"])
    if (not capacity_failure and state["registry"]["version"] == "4.2" and answer == "NO" and qid != "code_previously_installed"
            and any(checks[key].get("confidence", 1) < state["policy"]["high_confidence"] for key in used)):
        return "UNKNOWN", "The negative evidence check is not strong enough for a reliable combined answer; verify its sources.", used
    return answer, reason, used


def _combine(qid, checks, state):
    # Saved reviews retain their original registry and aggregation semantics.
    if state["registry"]["version"] not in {"4.0", "4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7"}:
        return combine_legacy(qid, checks, state)

    def is_answer(key, answer):
        return checks[key]["status"] == "OK" and checks[key]["answer"] == answer

    if qid == "software_gpu_capable":
        if is_answer("compatibility_blocker", "YES"):
            return "NO", "A material software compatibility requirement remains unresolved; review the dependency or version requirement.", ["compatibility_blocker"]
        if state["registry"]["version"] in {"4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7"}:
            answer, reason, used = combine_legacy(qid, checks, state)
            if answer == "YES":
                if state["registry"]["version"] in {"4.2", "4.3", "4.4", "4.5", "4.6", "4.7"} and not is_answer("compatibility_blocker", "NO"):
                    return "UNKNOWN", "Resolve the material compatibility check before concluding architecture suitability.", list(checks)
                if is_answer("compatibility_blocker", "NO"):
                    used.append("compatibility_blocker")
                else:
                    reason += " The additional compatibility check is unresolved; reviewer verification is required."
            return answer, reason, used
        if is_answer("amd_path_supported", "NO"):
            return "NO", "The supplied software description does not establish a credible AMD execution path.", ["amd_path_supported"]
        if is_answer("amd_path_supported", "YES") and is_answer("compatibility_blocker", "NO"):
            return "YES", "The named stack has a credible AMD execution path with no documented material compatibility blocker.", list(checks)
        return "UNKNOWN", "Resolve the AMD execution path or material compatibility requirements.", list(checks)
    if qid == "code_previously_installed":
        if is_answer("prior_lumi_run", "YES"):
            if is_answer("custom_install_pending", "YES"):
                return "UNKNOWN", "Prior LUMI use and pending application installation conflict; verify which workflow/version is meant.", list(checks)
            return "YES", "The proposal reports prior LUMI use of this workflow or a substantially equivalent software environment.", ["prior_lumi_run"]
        if is_answer("custom_install_pending", "YES"):
            return "NO", "Application installation or porting on LUMI is still planned; this is a setup risk, not rejection by itself.", ["custom_install_pending"]
        if is_answer("prior_lumi_run", "NO"):
            return "NO", "Prior installation/use on LUMI is not demonstrated in the supplied evidence; this does not establish incompatibility.", ["prior_lumi_run"]
        return "UNKNOWN", "The evidence does not allow the prior installation status to be assessed reliably.", list(checks)
    facts = state["facts"]
    keys = ("requested_gpu_hours", "maximum_number_of_gpus", "project_duration_months")
    if not all(facts[key]["status"] == "PRESENT" for key in keys):
        return "UNKNOWN", "Resource amounts and duration need verification.", list(checks)
    hours, gpus, months = (facts[key]["value"] for key in keys)
    if hours > gpus * 24 * 30 * months:
        return "NO", "Requested GPU-hours exceed continuous maximum capacity within the project duration.", list(checks)
    if checks["execution_fits"]["status"] == "ACCOUNTING_ASSUMPTION_REVIEW":
        return "UNKNOWN", "The budget depends on MFU assumptions and GCD accounting; verify performance measurements and full-MI250X GPU-hour units.", ["execution_fits"]
    for key in ("goals_concrete", "jobs_budgeted", "execution_fits"):
        if is_answer(key, "NO"):
            return "NO", "The workplan has a material evidence gap: " + checks[key].get("check_title", key.replace("_", " ")), [key]
    required = ["goals_concrete", "execution_fits"]
    if state["registry"]["version"] in {"4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7"}:
        required.append("jobs_budgeted")
    if all(is_answer(key, "YES") for key in required):
        return "YES", "Concrete targets, workload sizing and the execution assessment support feasibility; capacity arithmetic fits. Separate startup timing is not required.", required
    return "UNKNOWN", "Concrete targets or a credible execution plan still need clarification.", list(checks)


def combine_legacy(qid, checks, state):
    def is_answer(key, answer):
        return checks[key]["status"] == "OK" and checks[key]["answer"] == answer

    if qid == "software_gpu_capable":
        if is_answer("cuda_only_required", "YES"):
            return "NO", "A required dependency is explicitly CUDA-only without an AMD alternative.", ["cuda_only_required"]
        if is_answer("amd_path_supported", "NO"):
            return "NO", "The core computation explicitly cannot run on AMD GPUs.", ["amd_path_supported"]
        if all(is_answer(key, "YES") for key in ("dependencies_identified", "amd_path_supported")):
            return "YES", "Core dependencies are identified and an AMD execution path is supported.", ["dependencies_identified", "amd_path_supported"]
        return "UNKNOWN", "Identify the core dependencies and establish their AMD execution path.", list(checks)
    if qid == "code_previously_installed":
        if is_answer("custom_install_pending", "YES"):
            if is_answer("prior_lumi_run", "YES"):
                return "UNKNOWN", "Prior execution and pending installation conflict; verify the exact code version.", list(checks)
            return "NO", "Custom code still needs installation; this is startup risk, not rejection by itself.", ["custom_install_pending"]
        for key in ("prior_lumi_run", "standard_environment_only"):
            if is_answer(key, "YES"):
                return "YES", "The exact code was run on LUMI or needs only an available standard environment.", [key]
        return "UNKNOWN", "Neither prior execution nor a sufficient standard environment is established.", list(checks)
    # Arithmetic is performed in Python, never delegated to the language model.
    facts = state["facts"]
    keys = ("requested_gpu_hours", "maximum_number_of_gpus", "project_duration_months")
    if all(facts[key]["status"] == "PRESENT" for key in keys):
        hours, gpus, months = (facts[key]["value"] for key in keys)
        if hours > gpus * 24 * 30 * months:
            return "NO", "Requested GPU-hours exceed continuous maximum capacity within the project duration.", list(checks)
    else:
        return "UNKNOWN", "Resource amounts and duration need verification.", list(checks)
    for key in checks:
        if is_answer(key, "NO"):
            return "NO", "The workplan fails this evidence check: " + checks[key].get("check_title", key.replace("_", " ")), [key]
    if all(is_answer(key, "YES") for key in checks):
        return "YES", "Goals, job budget, startup allowance and execution strategy support feasibility; capacity arithmetic fits.", list(checks)
    return "UNKNOWN", "Resolve missing evidence about goals, job budgets, startup allowance or achievable targets.", list(checks)


def combine_playground(qid, checks, state):
    if qid == "software_gpu_capable":
        return combine_legacy(qid, checks, state)
    if qid == "code_previously_installed":
        return _combine(qid, checks, state)
    facts = state["facts"]
    keys = ("requested_gpu_hours", "maximum_number_of_gpus", "project_duration_months")
    if not all(facts[key]["status"] == "PRESENT" for key in keys):
        return "UNKNOWN", "Resource amounts and duration need verification.", list(checks)
    hours, gpus, months = (facts[key]["value"] for key in keys)
    if hours > gpus * 24 * 30 * months:
        return "NO", "Requested GPU-hours exceed continuous maximum capacity within the project duration.", list(checks)
    check = checks["onboarding_plan"]
    if check["status"] == "OK" and check["answer"] == "YES":
        return "YES", "A concrete onboarding or exploratory task is described; capacity arithmetic fits. Playground does not require a detailed job budget or measured scaling.", ["onboarding_plan"]
    return "NO" if check["answer"] == "NO" else "UNKNOWN", "The proposal does not demonstrate a concrete onboarding task or small experiment for this allocation.", ["onboarding_plan"]
