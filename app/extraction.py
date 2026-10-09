"""Conservative label-based extraction, with explicit missing/error states."""

import re

from app.ingestion import form_regions

FIELDS = {
    "application_id": ("text", ["application id", "application number", "id"]),
    "access_mode": ("mode", ["access mode", "access type"]),
    "target_machine": ("text", ["target machine", "target system", "ai factory selection", "partition name"]),
    "project_duration_months": ("positive", ["project duration (months)", "project duration months", "project duration"]),
    "organization_type": ("text", ["organization type", "organisation type"]),
    "country": ("text", ["country", "organization country", "organisation country", "organization country - horizon 2020", "organisation country - horizon 2020"]),
    "vat_number": ("text", ["vat number", "vat", "organization vat number", "organisation vat number", "company vat number", "company tax number"]),
    "requested_gpu_hours": ("positive", ["requested amount of resources (gpu hours)", "requested gpu hours", "gpu hours"]),
    "maximum_number_of_gpus": ("integer", ["maximum number of gpus", "maximum gpus"]),
    "total_storage_gb": ("nonnegative", ["total storage (gb)", "total storage gb", "total storage", "total storage required (gb)"]),
    "total_transfer_gb": ("nonnegative", ["total transfer (gb)", "total transfer gb", "total transfer", "total amount of data to transfer to/from (gb)"]),
    "listed_codes": ("text", ["code(s) used", "listed codes", "software codes"]),
    "framework_names": ("text", ["framework names", "frameworks"]),
    "backend_mentions": ("text", ["backend", "backends"]),
    "previous_lumi_use": ("boolean", ["previous lumi use", "prior lumi use"]),
    "previous_eurohpc_allocation": ("boolean", ["previous eurohpc allocation", "indicate if you have had previous eurohpc ju allocations"]),
    "personal_data_declared": ("boolean", ["personal data declared", "personal data processing", "does your proposal involve handling of personal data?"]),
    "requested_node_hours": ("positive", ["requested amount of resources (node hours)"]),
    "maximum_gpus_per_job": ("integer", ["maximum # gpus to be used per job"]),
    "gpus_per_node": ("integer", ["# gpus used per node"]),
    "maximum_simultaneous_jobs": ("integer", ["number of jobs simultaneously", "maximum number of jobs running simultaneously on the gpu partition"]),
    "scratch_storage_tb": ("nonnegative", ["maximum amount of scratch needed at a time (tb)"]),
    "work_storage_tb": ("nonnegative", ["maximum amount of work needed at a time (tb)"]),
    "home_storage_tb": ("nonnegative", ["maximum amount of home needed at a time (tb)"]),
    "archive_storage_tb": ("nonnegative", ["maximum amount of archive needed at a time (tb)"]),
    "requested_storage_tbh": ("nonnegative", ["requested amount of storage hours (tbh)"]),
    "total_transfer_tb": ("nonnegative", ["total amount of data to transfer to/from (tb)"]),
}

PARTITION_FIELDS = {"requested_node_hours", "maximum_gpus_per_job", "gpus_per_node", "maximum_simultaneous_jobs",
                    "scratch_storage_tb", "work_storage_tb", "home_storage_tb", "archive_storage_tb",
                    "requested_storage_tbh", "total_transfer_tb"}
POLICY_MODES = {
    "fast-lane-access-ai-factories_en": "FAST_LANE",
    "large-scale-access-ai-factories_en": "LARGE_SCALE",
    "playground-access-ai-factories_en": "PLAYGROUND",
    "eurohpc-ju-call-proposals-ai-science-and-collaborative-eu-projects_en": "AI_SCIENCE",
}

ORGANIZATION_FIELDS = {"organization_type", "country", "vat_number"}
MISSING_MARKERS = {"not provided", "not specified", "unknown"}
FIELD_BOUNDARIES = {alias for _, aliases in FIELDS.values() for alias in aliases} | {
    "project summary", "project details", "resources", "workplan", "work plan",
    "code details and feasibility", "scalability and performance", "organization details",
    "organisation details", "submission details", "ethics self-assessment",
}


def field_matches(text, aliases, multiline=False):
    # Whitespace may wrap inside long labels; values can follow a colon on the next line.
    labels = "|".join(r"\s+".join(re.escape(word) for word in alias.split())
                      for alias in sorted(aliases, key=len, reverse=True))
    pattern = re.compile(r"^(?:" + labels + r")[ \t]*(?::[ \t]*([^\n]*)|(?=$))", re.I | re.M)
    for match in pattern.finditer(text):
        raw = (match.group(1) or "").strip()
        end = match.end()
        if not raw:
            following = re.match(r"\n[ \t]*([^\n]+)", text[end:])
            if following:
                candidate = following.group(1).strip()
                # Do not consume a subsequent label or repeated section heading as a value.
                if (":" not in candidate and candidate.lower() not in FIELD_BOUNDARIES
                        and not re.fullmatch(r"\d+/\d+", candidate)):
                    raw = candidate
                    end += following.end()
        if not raw and match.group(1) is None:
            continue  # A bare heading is not a blank form field.
        if multiline and raw:
            for line in text[end:].splitlines()[1:]:
                if (not line.strip() or ":" in line or line.strip().lower() in FIELD_BOUNDARIES
                        or line.strip().lower() in {"jobs", "checkpoints", "cores/nodes", "memory", "instructions"}
                        or re.fullmatch(r"\d+/\d+", line.strip())):
                    break
                raw += " " + line.strip()
                end += 1 + len(line)
        yield raw, text[match.start():end]


def candidate(field, raw, page, source_text, method="form_field"):
    source = {"page": page, "field": field, "text": source_text, "method": method}
    try:
        if raw.lower() in MISSING_MARKERS:
            value, status = None, "NOT_FOUND"
        elif field == "vat_number" and raw.lower() in {"none", "n/a", "not applicable"}:
            value, status = None, "ABSENT"
        else:
            value, status = parse_value(field, raw), "PRESENT"
    except ValueError:
        value, status = None, "PARSE_ERROR"
    return {"value": value, "status": status, "source": source}


def supplemental_matches(field, regions):
    if field == "access_mode":
        # Use an explicit self-description, not the application ID or a policy URL.
        pattern = re.compile(r"\b(?:this|our|the proposed)\s+(Fast\s+Lane|Playground|Large\s+Scale)\s+project\b", re.I)
        for region in regions:
            for match in pattern.finditer(region["text"]):
                yield candidate(field, " ".join(match.group(1).split()), region["page"], match.group(0), "explicit_project_description")
        # A current submission's accepted policy is different from a bare URL or a
        # previous allocation. Keep the provenance and still require confirmation.
        policy = re.compile(r"In order to submit the proposal,[\s\S]{0,1400}?I accept[^\n]*(?:\nReference)?", re.I)
        # Consent paragraphs can continue on the following page, before the
        # appended reviewer form begins. Locate the URL's original page for citation.
        combined = "\n".join(region["text"] for region in regions)
        offsets, offset = [], 0
        for region in regions:
            offsets.append((offset, offset + len(region["text"]), region["page"]))
            offset += len(region["text"]) + 1
        for match in policy.finditer(combined):
            for slug, mode in POLICY_MODES.items():
                link = re.search(r"(?:www\.)?eurohpc-ju\.europa\.eu/\s*" + re.escape(slug) + r"\b", match.group(0), re.I)
                if link:
                    position = match.start() + link.start()
                    page = next(page for start, end, page in offsets if start <= position < end)
                    result = candidate(field, mode, page, link.group(0), "accepted_submission_policy")
                    result["source"]["context"] = match.group(0)
                    yield result
    if field in {"framework_names", "backend_mentions"}:
        names = (r"PyTorch|TensorFlow|JAX" if field == "framework_names" else r"ROCm|CUDA|HIP|OpenCL")
        for region in regions:
            for raw, source in field_matches(region["text"], FIELDS["listed_codes"][1], multiline=True):
                mentions = list(dict.fromkeys(m.group(0) for m in re.finditer(r"\b(?:" + names + r")\b", raw, re.I)))
                if mentions:
                    yield candidate(field, ", ".join(mentions), region["page"], source, "listed_software_mentions")


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
                 "maximum_number_of_gpus": r"gpus?", "total_storage_gb": "gb", "total_transfer_gb": "gb",
                 "requested_node_hours": r"(?:node\s*)?hours?", "maximum_gpus_per_job": "gpus?",
                 "gpus_per_node": "gpus?", "maximum_simultaneous_jobs": "jobs?",
                 "scratch_storage_tb": "tb", "work_storage_tb": "tb", "home_storage_tb": "tb",
                 "archive_storage_tb": "tb", "requested_storage_tbh": "tbh", "total_transfer_tb": "tb"}
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
        normalized = re.sub(r"[\s-]+", "_", raw.upper())
        return {"AIF_FAST_LANE_ACCESS": "FAST_LANE", "FAST_LANE_ACCESS": "FAST_LANE",
                "PLAYGROUND_ACCESS": "PLAYGROUND", "LARGE_SCALE_ACCESS": "LARGE_SCALE"}.get(normalized, normalized)
    return raw


def extract_facts(doc):
    facts = {}
    regions = [region for region in form_regions(doc["pages"]) if region["scope"] not in {"assessment", "allocation_history"}]
    for field, (_, aliases) in FIELDS.items():
        matches = []
        for region in regions:
            if field in ORGANIZATION_FIELDS and region["scope"] == "team":
                continue
            for raw, source_text in field_matches(region["text"], aliases, multiline=field == "listed_codes"):
                matches.append(candidate(field, raw, region["page"], source_text))
        if not matches:
            matches = list(supplemental_matches(field, [r for r in regions if r["scope"] == "proposal"]))
        if not matches:
            fact = {"value": None, "status": "PARSE_ERROR" if doc["warnings"] else "NOT_FOUND", "source": None}
        elif any(m["value"] != matches[0]["value"] or m["status"] != matches[0]["status"] for m in matches):
            fact = {"value": None, "status": "CONFLICT", "source": None}
        else:
            fact = matches[0].copy()
        fact.update({"candidates": matches, "confirmed": False})
        if field in PARTITION_FIELDS:
            fact["optional_resource_field"] = True
        facts[field] = fact
    facts["vat_number_present"] = {
        "value": True if facts["vat_number"]["status"] == "PRESENT" else
                 False if facts["vat_number"]["status"] == "ABSENT" else None,
        "status": facts["vat_number"]["status"], "source": facts["vat_number"]["source"],
        "confirmed": False, "derived": True,
    }
    return facts
