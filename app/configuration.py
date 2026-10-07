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
