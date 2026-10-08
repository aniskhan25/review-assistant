"""Evaluate actual review aggregation against imported historical answers."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

from app.configuration import load_policy
from app.decision import build_backend
from app.ingestion import document
from app.review import new_review
from app.security import install_network_guard

QUESTIONS = ("software_gpu_capable", "code_previously_installed", "workplan_sufficient")


def benchmark(records, backend, policy, split="development", on_case=None):
    seen, groups = set(), {}
    for record in records:
        if record["application_id"] in seen:
            raise ValueError("Duplicate application IDs")
        seen.add(record["application_id"])
        group = record["group_id"]
        if group in groups and groups[group] != record["split"]:
            raise ValueError("Related proposals cross dataset splits")
        groups[group] = record["split"]
    selected = [r for r in records if r["split"] == split]
    if not selected:
        raise ValueError("No cases in selected split")
    results = []
    for record in selected:
        started = time.monotonic()
        if any(record["gold"].get(q) not in {"YES", "NO"} for q in QUESTIONS):
            raise ValueError("Missing explicit gold submission answer")
        # Only proposal pages enter inference. Review prose and labels stay outside.
        state = new_review(document(record["pages"]), backend, policy, "offline-benchmark")
        if state["facts"]["access_mode"]["value"] != "FAST_LANE":
            raise ValueError("Historical aggregation evaluation only supports Fast Lane")
        results.append({"application_id": record["application_id"],
                        "elapsed_seconds": round(time.monotonic() - started, 2),
                        "answers": {q: {"gold": record["gold"][q], "predicted": state["decisions"][q]["answer"],
                                        "status": state["decisions"][q]["status"],
                                        "confidence": state["decisions"][q].get("confidence"),
                                        "aggregation_reason": state["decisions"][q].get("aggregation_reason"),
                                        "checks": state["decisions"][q].get("checks", {})} for q in QUESTIONS},
                        "model_errors": sum(c["status"] == "MODEL_ERROR" for d in state["decisions"].values()
                                            for c in d.get("checks", {"direct": d}).values())})
        if on_case:
            on_case(results[-1])
    metrics = {}
    for q in QUESTIONS:
        rows = [r["answers"][q] for r in results]
        metrics[q] = {"count": len(rows), "accuracy": sum(r["gold"] == r["predicted"] for r in rows)/len(rows),
                      "abstentions": sum(r["predicted"] == "UNKNOWN" for r in rows),
                      "wrong_non_abstaining": sum(r["predicted"] != "UNKNOWN" and r["predicted"] != r["gold"] for r in rows),
                      "gold_counts": dict(Counter(r["gold"] for r in rows))}
    return {"split": split, "applications": len(results), "backend": backend.name,
            "model_version": backend.version, "production_qualified": False,
            "label_status": "imported historical labels pending source and version curation",
            "classification_evaluated": False, "per_question": metrics, "cases": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--split", choices=["development", "heldout"], default="development")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    install_network_guard()
    records = [json.loads(line) for line in args.dataset.read_text().splitlines() if line.strip()]
    checkpoint = args.output.with_suffix(".cases.jsonl")
    if args.output.exists() or checkpoint.exists():
        parser.error("Choose a new output path to preserve previous benchmark results")
    total = sum(record["split"] == args.split for record in records)
    completed = 0

    def save_case(case):
        nonlocal completed
        with checkpoint.open("a") as stream:
            stream.write(json.dumps(case) + "\n")
        completed += 1
        print(f"Completed {completed}/{total}: {case['application_id']} ({case['elapsed_seconds']}s)", flush=True)

    result = benchmark(records, build_backend("jevos", args.endpoint, version=args.model_version), load_policy(), args.split, save_case)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}))


if __name__ == "__main__":
    main()
