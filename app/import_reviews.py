"""Import local work-item reviews as candidate labels, never model evidence."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import re

from app.ingestion import ingest_pdf, form_regions
from app.extraction import extract_facts
from app.configuration import load_config
from app.retrieval import retrieve
from app.ingestion import document

APP_ID = re.compile(r"EHPC-AIF-\d{4}[A-Z]{2}\d{2}-\d+", re.I)
HEADINGS = {
    "software_gpu_capable": "Are the codes to be used in the project suitable for the architecture of the machine chosen?",
    "code_previously_installed": "Is the code installed on the machine chosen?",
    "workplan_sufficient": "Are the targets proposed feasible within the allocation time - Workplan?",
    "global_comment": "Comment globally on the provided technical data and your conclusions:",
    "classification": "Classification:",
    "rationale": "Reason for classification:",
}


def parse_review(description):
    text = description.replace("\\r\\n", "\n").replace("\\n", "\n")
    text = text.replace("\\[", "[").replace("\\]", "]")
    boundaries = []
    for key, heading in HEADINGS.items():
        # Anchor the whole heading, so quoted instructions and rationale prose cannot supply labels.
        pattern = r"(?im)^\s*[*_]*" + re.escape(heading) + r"[*_]*\s*"
        boundaries.extend((m.start(), m.end(), key) for m in re.finditer(pattern, text))
    boundaries.sort()
    sections, issues = {}, []
    for i, (start, end, key) in enumerate(boundaries):
        if key in sections:
            issues.append("duplicate_review_section:" + key)
        sections[key] = text[end:boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)].strip()
    gold, label_sources = {}, {}
    for key in HEADINGS:
        if key not in sections or key in {"global_comment", "rationale"}:
            continue
        content = re.sub(r"\[[\s\S]*?\]", "", sections[key]).strip(" \n\t*_\\")
        pattern = r"^(YES|NO)\b" if key != "classification" else r"^(Accepted|Rejected)\b"
        match = re.match(pattern, content, re.I)
        if match and key == "classification" and re.search(r"\bOR\b|Accepted/rejected", content.splitlines()[0], re.I):
            match = None
        if match:
            gold[key] = {"ACCEPTED": "ACCEPT", "REJECTED": "REJECT"}.get(match[1].upper(), match[1].upper())
            label_sources[key] = content
        else:
            issues.append("missing_explicit_label:" + key)
    for key in ("software_gpu_capable", "code_previously_installed", "workplan_sufficient", "classification"):
        if key not in sections:
            issues.append("missing_review_section:" + key)
    return {"gold": gold, "label_sources": label_sources, "sections": sections, "issues": issues}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(csv_path, pdf_dir, output, exposed=()):
    os.umask(0o077)
    output.mkdir(parents=True, exist_ok=True)
    output.chmod(0o700)
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    files = defaultdict(list)
    for path in sorted(pdf_dir.rglob("*.pdf")):
        match = APP_ID.search(path.name)
        if match:
            files[match[0].upper()].append({"path": str(path.resolve()), "sha256": sha(path.read_bytes())})
    inventory = []
    for number, row in enumerate(rows, 2):
        ids = APP_ID.findall(row["Title"])
        application_id = ids[0].upper() if len(ids) == 1 else None
        parsed = parse_review(row["Description"])
        matches = files.get(application_id, [])
        issues = list(parsed["issues"])
        if not application_id: issues.append("ambiguous_application_id")
        if not matches: issues.append("missing_pdf")
        if len({m["sha256"] for m in matches}) > 1: issues.append("multiple_pdf_versions")
        if row["State"].lower() != "closed": issues.append("review_not_closed")
        inventory.append({"application_id": application_id, "csv_row": number, "work_item_iid": row["IID"],
                          "source_description_sha256": sha(row["Description"].encode()),
                          "state": row["State"], "description": row["Description"].replace("\\n", "\n"),
                          "pdf_candidates": matches, **parsed, "issues": issues})
    counts = Counter(r["application_id"] for r in inventory)
    parent = {r["application_id"]: r["application_id"] for r in inventory if r["application_id"]}
    def root(key):
        while parent[key] != key: key = parent[key]
        return key
    def union(a, b):
        if a in parent and b in parent: parent[max(root(a), root(b))] = min(root(a), root(b))
    iid_to_id = {r["work_item_iid"]: r["application_id"] for r in inventory}
    # Group explicit work-item/application cross-references and same applicant filenames.
    applicants = defaultdict(set)
    for record in inventory:
        app_id = record["application_id"]
        if not app_id: continue
        if counts[app_id] > 1: record["issues"].append("multiple_review_rows")
        references = APP_ID.findall(record["description"])
        references += [iid_to_id[iid] for iid in re.findall(r"(?<!\w)#(\d+)\b", record["description"]) if iid in iid_to_id]
        for reference in references:
            if reference: union(app_id, reference.upper())
        unresolved = [iid for iid in re.findall(r"(?<!\w)#(\d+)\b", record["description"]) if iid not in iid_to_id]
        record["unresolved_work_item_references"] = unresolved
        for item in record["pdf_candidates"]:
            suffix = Path(item["path"]).stem.split("_", 1)
            if len(suffix) == 2:
                applicant = re.sub(r"\s*\(\d+\)$", "", suffix[1].split("_")[0]).casefold()
                applicants[applicant].add(app_id)
    for ids in applicants.values():
        for app_id in ids: union(min(ids), app_id)
    exposed_roots = {root(key) for key in exposed if key in parent}
    # Deterministic provisional split; group review is required before treating it as sealed test data.
    candidates, other_profiles = [], []
    for record in inventory:
        app_id = record["application_id"]
        if not app_id: continue
        record["group_id"] = root(app_id)
        record["profile_from_id"] = re.search(r"\d{4}([A-Z]{2})", app_id)[1]
        record["split"] = "development" if root(app_id) in exposed_roots or record["unresolved_work_item_references"] else ("heldout" if int(sha(root(app_id).encode())[:8], 16) % 5 == 0 else "development")
        if record["issues"]: continue
        selected = record["pdf_candidates"][0]
        try:
            doc = ingest_pdf(Path(selected["path"]).read_bytes())
        except ValueError:
            record["issues"].append("pdf_extraction_failed")
            continue
        if doc["warnings"]:
            record["issues"].append("pdf_extraction_warnings")
            continue
        # Strip appended assessment regions before producing any benchmark input.
        by_page = defaultdict(list)
        for region in form_regions(doc["pages"]):
            if region["scope"] != "assessment": by_page[region["page"]].append(region["text"])
        pages = [{"page": n, "text": "\n".join(parts)} for n, parts in sorted(by_page.items())]
        facts = extract_facts(doc)
        record["detected_access_mode"] = facts["access_mode"]["value"]
        record["detected_target"] = facts["target_machine"]["value"]
        proposal_ids = APP_ID.findall(pages[0]["text"][:2000]) if pages else []
        if app_id not in [i.upper() for i in proposal_ids]:
            record["issues"].append("pdf_identity_not_verified")
            continue
        item = {"application_id": app_id, "group_id": record["group_id"], "split": record["split"],
                "synthetic": False, "label_status": "imported_explicit_review_labels_pending_curation",
                "pages": pages, "gold": record["gold"], "gold_facts": {}, "evidence": {},
                "review_reference": {"csv_row": record["csv_row"], "work_item_iid": record["work_item_iid"],
                                     "label_sources": record["label_sources"], "rationale": record["sections"].get("rationale", "")},
                "source_pdf": selected, "narrow_gold": {}, "group_review_required": True}
        if record["profile_from_id"] == "FL" and record["detected_access_mode"] == "FAST_LANE" and record["detected_target"] in {"LUMI-G", "LUMI G"}:
            candidates.append(item)
        else:
            other_profiles.append(item)
    for name, values in (("gold-candidates.jsonl", candidates), ("other-profiles.jsonl", other_profiles)):
        (output / name).write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values))
    registry = load_config("questions.json")
    curation = []
    for item in candidates:
        if item["split"] != "development":
            continue
        doc = document(item["pages"])
        for qid, question in registry["questions"].items():
            for check_id, specification in question.get("checks", {}).items():
                check = dict(question, **specification)
                curation.append({"application_id": item["application_id"], "question_id": qid,
                                 "check_id": check_id, "title": check["title"], "criteria": check["criteria"],
                                 "gold": None, "decisive_evidence_ids": [], "external_knowledge": None,
                                 "review_answer_for_context_only": item["gold"][qid],
                                 "review_explanation_for_labelling_only": item["review_reference"]["label_sources"][qid],
                                 "candidate_proposal_evidence": retrieve(doc["evidence"], check)})
    (output / "development-check-curation.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in curation))
    (output / "inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")
    summary = {"csv_rows": len(rows), "pdf_files": sum(map(len, files.values())), "pdf_application_ids": len(files),
               "explicit_complete_reviews": sum(len(r["gold"]) == 4 and not any(i.startswith('duplicate') for i in r['issues']) for r in inventory),
               "fast_lane_candidates": len(candidates), "other_profile_candidates": len(other_profiles),
               "excluded_rows": sum(bool(r["issues"]) for r in inventory),
               "issues": dict(Counter(i for r in inventory for i in r["issues"])),
               "splits": dict(Counter(r["split"] for r in candidates)),
               "development_narrow_checks_to_label": len(curation),
               "classifications": dict(Counter(r["gold"]["classification"] for r in candidates)),
               "unmatched_pdf_ids": sorted(set(files) - set(parent)),
               "source_csv_sha256": sha(csv_path.read_bytes()), "production_qualified": False}
    (output / "import-settings.json").write_text(json.dumps({"csv_path": str(csv_path.resolve()), "pdf_directory": str(pdf_dir.resolve()), "previously_exposed_application_ids": list(exposed)}, indent=2) + "\n")
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["# Historical review import", "", "Candidate labels only. Sources are unchanged; all data here is private and Git-ignored.", "", "```json", json.dumps(summary, indent=2), "```", "", "## Rows requiring resolution", "", "| Application | CSV row | Issue |", "|---|---:|---|"]
    lines += [f"| {r['application_id']} | {r['csv_row']} | {', '.join(r['issues'])} |" for r in inventory if r["issues"]]
    lines += ["", "## Curation still needed", "", "- Resolve distinct PDF revisions against the reviewed version; no latest-file guessing was used.", "- Confirm related project groups before sealing the provisional held-out split. Known previously inspected examples are development-only.", "- Verify imported answers against source descriptions. A closed work item or template option is not a gold answer.", "- Label narrow checks and decisive proposal passages separately. Broad answers and acceptance cannot be copied into every narrow check.", "- Record external software/hardware knowledge separately from proposal evidence.", "- Other access modes are stored separately and must not be evaluated using Fast Lane rules.", "- No model was run and no held-out scores were used to tune prompts during this import."]
    (output / "import-report.md").write_text("\n".join(lines) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("pdf_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exposed", nargs="*", default=[])
    args = parser.parse_args()
    print(json.dumps(build(args.csv, args.pdf_dir, args.output, args.exposed), indent=2))


if __name__ == "__main__":
    main()
