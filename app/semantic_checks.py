"""Evidence checks and explicit aggregation for the three submission questions."""

from app.decision import decide
from app.retrieval import retrieve


def assess(state, backend, qid, question, context):
    checks = {}
    for key, specification in question["checks"].items():
        check = dict(question, **specification)
        check.pop("checks", None)
        checks[key] = decide(backend, key, check, retrieve(state["document"]["evidence"], check), state["policy"], context)
        checks[key]["check_title"] = check["title"]
    answer, reason, used = combine(qid, checks, state)
    sources = list(dict.fromkeys(eid for key in used for eid in checks[key]["evidence_ids"]))
    confidence = min((checks[key]["confidence"] for key in used), default=0)
    margin = min((checks[key]["margin"] for key in used), default=0)
    return {"question_id": qid, "question_version": question["version"],
            "model_answer": answer, "answer": answer, "probabilities": {},
            "confidence": confidence, "margin": margin,
            "band": "high" if answer != "UNKNOWN" and confidence >= state["policy"]["high_confidence"] else "reviewer required",
            "status": "AGGREGATED" if answer != "UNKNOWN" else "CHECKS_UNRESOLVED",
            "model": backend.name, "model_version": backend.version,
            "latency_ms": round(sum(d["latency_ms"] for d in checks.values()), 3),
            "evidence_ids": sources, "reviewer_answer": None, "reviewer_note": "", "confirmed": False,
            "checks": checks, "aggregation_reason": reason, "aggregation_version": "1"}


def combine(qid, checks, state):
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
