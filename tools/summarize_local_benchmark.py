"""Summarize the three completed private held-out reports without proposal text."""
import argparse
from collections import Counter
import json
from pathlib import Path
import statistics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    names = ["baseline", "kev-08b", "kev-4b-8bit"]
    reports = {name: json.loads((args.directory / (name + "-heldout.json")).read_text()) for name in names}
    baseline = reports["baseline"]
    for report in reports.values():
        if (report["dataset_sha256"], report["policy_sha256"], report["registry_version"],
            [c["application_id"] for c in report["cases"]]) != (
            baseline["dataset_sha256"], baseline["policy_sha256"], baseline["registry_version"],
            [c["application_id"] for c in baseline["cases"]]):
            raise ValueError("Unmatched evaluation inputs")
    rows = []
    base_inputs = {r["input_sha256"] for r in baseline["requests"]}
    for name, report in reports.items():
        answers = [a for case in report["cases"] for a in case["answers"].values()]
        rows.append({"candidate": name, "correct": sum(a["gold"] == a["predicted"] for a in answers),
                     "total": len(answers), "unknown": sum(a["predicted"] == "UNKNOWN" for a in answers),
                     "wrong": sum(a["predicted"] not in (a["gold"], "UNKNOWN") for a in answers),
                     "model_errors": sum(c["model_errors"] for c in report["cases"]),
                     "median_review_seconds": report["median_review_seconds"],
                     "loading": report["loading"], "inference_memory": report["inference_memory"],
                     "model_calls": report["model_calls"],
                     "shared_unique_inputs_with_baseline": len(base_inputs & {r["input_sha256"] for r in report["requests"]}),
                     "median_new_state_seconds": statistics.median(r["new_state_seconds"] for r in report["request_replays"]),
                     "median_repeated_state_seconds": statistics.median(r["repeated_state_seconds"] for r in report["request_replays"]),
                     "max_cache_probability_delta": max(abs(r["probabilities"][0][k] - r["probabilities"][1][k])
                            for r in report["request_replays"] for k in r["probabilities"][0])})
    base = rows[0]
    for row in rows:
        row["passes_frozen_comparison_gate"] = (row["correct"] >= base["correct"] and row["wrong"] <= base["wrong"]
            and row["unknown"] <= base["unknown"] and row["model_errors"] <= base["model_errors"]
            and row["median_review_seconds"] < base["median_review_seconds"])
    gold = [a["gold"] for c in baseline["cases"] for a in c["answers"].values()]
    summary = {"applications": baseline["applications"], "split": "heldout", "rows": rows,
               "constant_no_correct": sum(answer == "NO" for answer in gold),
               "per_question_majority_correct_descriptive_only": sum(max(Counter(c["answers"][q]["gold"]
                    for c in baseline["cases"]).values()) for q in baseline["per_question"]),
               "production_qualified": False, "classification_evaluated": False,
               "limits": "Small provisional historical sample; unchanged confidence thresholds; page extraction excluded; conditional corroboration can change call counts."}
    output = args.directory / "summary.json"
    if output.exists():
        raise ValueError("Summary already exists")
    output.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
