import json
from pathlib import Path

CONFIG = Path(__file__).parent / "config"


def load_config(name):
    return json.loads((CONFIG / name).read_text())


def load_policy(path=None):
    policy = json.loads(Path(path).read_text()) if path else load_config("policy.json")
    if policy["mode"] not in {"shadow", "production"}:
        raise ValueError("Invalid deployment mode")
    if not 0 <= policy["review_band"] <= policy["high_confidence"] <= 1:
        raise ValueError("Invalid confidence thresholds")
    if not 0 <= policy["minimum_margin"] <= 1:
        raise ValueError("Invalid margin")
    for field in ("gpu_units_per_node", "storage_warning_gb"):
        value = policy[field]
        if value is not None and (type(value) not in (int, float) or not 0 < value < float("inf")):
            raise ValueError(f"Invalid {field}")
    for field in ("review_retention_days", "audit_retention_days"):
        if type(policy[field]) is not int or policy[field] < 1:
            raise ValueError(f"Invalid {field}")
    if policy["mode"] == "production" and (not policy["approved"] or any(
        policy[key] is None for key in ("gpu_units_per_node", "storage_warning_gb")
    )):
        raise ValueError("Production requires approved, complete policy")
    return policy


def review_registry(mode):
    registry = load_config("questions.json")
    registry["profile"] = mode
    registry["workload"] = load_config("workload.json")
    if mode != "PLAYGROUND":
        return registry
    questions = registry["questions"]
    registry["questions"] = {key: value for key, value in questions.items()
                             if key not in {"scaling_strategy_adequate", "official_rocm_builds_available", "fast_lane_validated"}}
    registry["questions"]["software_gpu_capable"]["checks"].pop("compatibility_blocker")
    registry["questions"]["code_previously_installed"]["checks"]["prior_lumi_run"].pop("corroborating_question", None)
    for key, override in load_config("playground.json").items():
        registry["questions"][key].update(override)
    return registry
