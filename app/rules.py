"""Deterministic Fast Lane checks. Model negatives are referrals until confirmed."""


def evaluate(state, policy):
    findings = []
    facts = state["facts"]

    def add(code, severity, message, calculation=None):
        findings.append({"code": code, "severity": severity, "message": message,
                         "calculation": calculation or {}})

    def value(key):
        fact = facts[key]
        return fact["value"] if fact["status"] == "PRESENT" else None

    if value("access_mode") != "FAST_LANE":
        add("unsupported_profile", "attention", "Fast Lane rules were not applied. This access mode needs its own approved review profile.")
        return {"version": policy["version"], "findings": findings, "suggested": "REVIEW_REQUIRED"}
    if value("target_machine") is None or value("target_machine").upper() not in {"LUMI-G", "LUMI G"}:
        add("target_machine", "attention", "Verify that the target is LUMI-G.")
    if not policy["approved"]:
        add("provisional_policy", "attention", "Policy is provisional; outputs are shadow drafts.")
    hours, gpus, months = (value(k) for k in ("requested_gpu_hours", "maximum_number_of_gpus", "project_duration_months"))
    if all(v is not None and v > 0 for v in (hours, gpus, months)):
        minimum = hours / (gpus * 24 * 30)
        calculation = {"requested_gpu_hours": hours, "maximum_number_of_gpus": gpus,
                       "project_duration_months": months, "minimum_months": minimum,
                       "assumption": "30-day months, continuous maximum concurrency; consistent GPU accounting units"}
        add("resource_consumption", "blocker" if minimum > months else "info",
            "Allocation cannot be consumed within the declared duration." if minimum > months else
            "Allocation fits the theoretical maximum capacity; queue availability is not guaranteed.", calculation)
    else:
        add("resource_consumption", "attention", "Resource feasibility needs valid GPU hours, GPU count and duration.")
    threshold = policy["storage_warning_gb"]
    if threshold is None or value("total_storage_gb") is None:
        add("storage", "attention", "Verify storage and configure the approved storage threshold.")
    elif value("total_storage_gb") > threshold:
        add("storage", "warning", "Storage exceeds the configured threshold; review the storage plan.",
            {"storage_gb": value("total_storage_gb"), "threshold_gb": threshold})
    if value("personal_data_declared") is True:
        add("personal_data", "warning", policy["personal_data_wording"])
    elif value("personal_data_declared") is None:
        add("personal_data", "attention", "Verify the personal-data declaration.")
    if facts["vat_number"]["status"] in {"PARSE_ERROR", "NOT_FOUND", "CONFLICT"}:
        add("vat", "attention", "VAT is unverified; parsing failure is not absence.")
    if value("previous_lumi_use") is False:
        add("previous_lumi_use", "warning", "No previous LUMI use is declared; review startup risk.")
    node_units = policy["gpu_units_per_node"]
    if node_units is None:
        add("concurrency_units", "attention", "Configure GPU accounting units per node before interpreting concurrency.")
    elif gpus is not None and gpus > node_units:
        add("multi_node", "info", "Concurrency exceeds one node; distributed execution or independent concurrent jobs may satisfy this requirement.")
    for qid, decision in state["decisions"].items():
        answer = decision["reviewer_answer"] if decision["confirmed"] else decision["answer"]
        if not decision["confirmed"] or answer == "UNKNOWN":
            add(qid, "attention", "Reviewer confirmation required: " + qid)
        elif answer == "NO":
            add(qid, "warning" if qid == "code_previously_installed" else "blocker",
                "Reviewer confirmed NO: " + qid)
        if decision.get("contradiction") and not decision["confirmed"]:
            add("contradiction_" + qid, "attention", "Evidence and recommendation conflict; human resolution required.")
    suggested = "REJECT" if any(f["severity"] == "blocker" for f in findings) else (
        "REVIEW_REQUIRED" if any(f["severity"] == "attention" for f in findings) else "ACCEPT")
    return {"version": policy["version"], "findings": findings, "suggested": suggested}
