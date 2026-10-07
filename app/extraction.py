"""Conservative label-based extraction, with explicit missing/error states."""

import re

FIELDS = {
    "application_id": ("text", ["application id", "application number"]),
    "access_mode": ("mode", ["access mode", "access type"]),
    "target_machine": ("text", ["target machine", "target system"]),
    "project_duration_months": ("positive", ["project duration (months)", "project duration months", "project duration"]),
    "organization_type": ("text", ["organization type", "organisation type"]),
    "country": ("text", ["country"]),
    "vat_number": ("text", ["vat number", "vat"]),
    "requested_gpu_hours": ("positive", ["requested amount of resources (gpu hours)", "requested gpu hours", "gpu hours"]),
    "maximum_number_of_gpus": ("integer", ["maximum number of gpus", "maximum gpus"]),
    "total_storage_gb": ("nonnegative", ["total storage (gb)", "total storage gb", "total storage"]),
    "total_transfer_gb": ("nonnegative", ["total transfer (gb)", "total transfer gb", "total transfer"]),
    "listed_codes": ("text", ["code(s) used", "listed codes", "software codes"]),
    "framework_names": ("text", ["framework names", "frameworks"]),
    "backend_mentions": ("text", ["backend", "backends"]),
    "previous_lumi_use": ("boolean", ["previous lumi use", "prior lumi use"]),
    "previous_eurohpc_allocation": ("boolean", ["previous eurohpc allocation"]),
    "personal_data_declared": ("boolean", ["personal data declared", "personal data processing"]),
}


def parse_value(field, raw):
    kind = FIELDS[field][0]
    raw = raw.strip()
    if not raw:
        raise ValueError("Empty value")
    if kind == "boolean":
        if raw.lower() not in {"yes", "no", "true", "false"}:
            raise ValueError("Expected yes or no")
        return raw.lower() in {"yes", "true"}
    if kind in {"positive", "nonnegative", "integer"}:
        units = {"project_duration_months": r"months?", "requested_gpu_hours": r"(?:gpu\s*)?hours?",
                 "maximum_number_of_gpus": r"gpus?", "total_storage_gb": "gb", "total_transfer_gb": "gb"}
        raw = re.sub(r"\s*(?:" + units[field] + r")$", "", raw, flags=re.I).strip()
        if not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?", raw):
            raise ValueError("Expected unambiguous number in the specified units")
        value = float(raw.replace(",", ""))
        if not value < float("inf") or value < 0 or (kind != "nonnegative" and value == 0):
            raise ValueError("Invalid resource value")
        if kind == "integer" and not value.is_integer():
            raise ValueError("GPU count must be integral")
        return int(value) if value.is_integer() else value
    if kind == "mode":
        return raw.upper().replace(" ", "_").replace("-", "_")
    return raw


def extract_facts(doc):
    facts = {}
    for field, (_, aliases) in FIELDS.items():
        label = "|".join(re.escape(alias) for alias in aliases)
        pattern = re.compile(r"^(?:" + label + r")[ \t]*(?::[ \t]*(.*)|\n([^\n]+))$", re.I | re.M)
        matches = []
        for page in doc["pages"]:
            for match in pattern.finditer(page["text"]):
                raw = (match.group(1) if match.group(1) is not None else match.group(2)).strip()
                source = {"page": page["page"], "field": field, "text": match.group(0)}
                try:
                    if field == "vat_number" and raw.lower() in {"none", "n/a", "not applicable", "not provided"}:
                        value, status = None, "ABSENT"
                    else:
                        value, status = parse_value(field, raw), "PRESENT"
                except ValueError:
                    value, status = None, "PARSE_ERROR"
                matches.append({"value": value, "status": status, "source": source})
        if not matches:
            fact = {"value": None, "status": "PARSE_ERROR" if doc["warnings"] else "NOT_FOUND", "source": None}
        elif any(m["value"] != matches[0]["value"] or m["status"] != matches[0]["status"] for m in matches):
            fact = {"value": None, "status": "CONFLICT", "source": None}
        else:
            fact = matches[0].copy()
        fact.update({"candidates": matches, "confirmed": False})
        facts[field] = fact
    facts["vat_number_present"] = {
        "value": True if facts["vat_number"]["status"] == "PRESENT" else
                 False if facts["vat_number"]["status"] == "ABSENT" else None,
        "status": facts["vat_number"]["status"], "source": facts["vat_number"]["source"],
        "confirmed": False, "derived": True,
    }
    return facts
