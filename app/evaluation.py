"""Offline JSONL bake-off. Synthetic results never qualify a production model."""

import argparse
import json
import platform
import resource
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from app.configuration import load_config, load_policy
from app.decision import ANSWERS, build_backend, decide
from app.extraction import extract_facts
from app.ingestion import document
from app.retrieval import retrieve
from app.security import install_network_guard


def metrics(rows, high_confidence=0.85):
    n = len(rows)
    if not n:
        return {"count": 0}
    high = [r for r in rows if r["confidence"] >= high_confidence and r["answer"] != "UNKNOWN"]
    yes = [r for r in rows if r["gold"] == "YES"]
    no = [r for r in rows if r["gold"] == "NO"]
    confusion = {gold: {pred: sum(r["gold"] == gold and r["answer"] == pred for r in rows)
                        for pred in ANSWERS} for gold in ANSWERS}
    per_label = {}
    for label in ANSWERS:
        tp = confusion[label][label]
        predicted = sum(confusion[g][label] for g in ANSWERS)
        actual = sum(confusion[label].values())
        precision = tp / predicted if predicted else None
        recall = tp / actual if actual else None
        f1 = 2 * tp / (predicted + actual) if predicted + actual else None
        per_label[label] = {"precision": precision, "recall": recall, "f1": f1}
    # ECE uses raw model answer, since abstention is a subsequent operational policy.
    ece = 0
    for index in range(10):
        bucket = [r for r in rows if min(int(r["confidence"] * 10), 9) == index]
        if bucket:
            accuracy = sum(r["model_answer"] == r["gold"] for r in bucket) / len(bucket)
            ece += len(bucket) / n * abs(accuracy - statistics.mean(r["confidence"] for r in bucket))
    return {"count": n, "accuracy": sum(r["answer"] == r["gold"] for r in rows) / n,
            "confusion_matrix": confusion, "per_label": per_label,
            "unknown_rate": sum(r["answer"] == "UNKNOWN" for r in rows) / n,
            "incorrect_unknown_rate": sum(r["answer"] == "UNKNOWN" and r["gold"] != "UNKNOWN" for r in rows) / n,
            "correct_escalation_rate": sum(r["answer"] == r["gold"] == "UNKNOWN" for r in rows) / n,
            "high_confidence_count": len(high),
            "high_confidence_accuracy": sum(r["answer"] == r["gold"] for r in high) / len(high) if high else None,
            "false_negative_rate": sum(r["answer"] == "NO" for r in yes) / len(yes) if yes else None,
            "false_positive_rate": sum(r["answer"] == "YES" for r in no) / len(no) if no else None,
            "brier_score": statistics.mean(sum((r["probabilities"][a] - (r["gold"] == a)) ** 2 for a in ANSWERS) for r in rows),
            "expected_calibration_error": ece,
            "latency_median_ms": statistics.median(r["latency_ms"] for r in rows),
            "latency_p95_ms": sorted(r["latency_ms"] for r in rows)[min(n - 1, int(.95 * n))],
            "model_error_count": sum(r["status"] == "MODEL_ERROR" for r in rows)}


def benchmark(records, backend, policy, split="heldout"):
    registry = load_config("questions.json")
    seen, groups = set(), {}
    rows, retrieval_hits, extraction_hits, review_results = [], [], [], []
    selected = []
    for record in records:
        if record["application_id"] in seen:
            raise ValueError("Duplicate application IDs in dataset")
        seen.add(record["application_id"])
        group = record.get("group_id", record["application_id"])
        if group in groups and groups[group] != record["split"]:
            raise ValueError("Group leaks across evaluation splits")
        groups[group] = record["split"]
        if record["split"] == split:
            selected.append(record)
    if not selected:
        raise ValueError("No records in requested split")
    for record in selected:
        doc = document(record["pages"])
        facts = extract_facts(doc)
        for field, expected in record.get("gold_facts", {}).items():
            extraction_hits.append(facts[field]["value"] == expected)
        answers = {}
        for qid, gold in record["gold"].items():
            if qid == "classification":
                continue
            if qid not in registry["questions"] or gold not in ANSWERS:
                raise ValueError("Unknown question/label in evaluation dataset")
            question = registry["questions"][qid]
            evidence = retrieve(doc["evidence"], question)
            expected = record.get("evidence", {}).get(qid, [])
            if expected:
                retrieval_hits.append(all(any(e["page"] == target["page"] and target["text"] in e["text"] for e in evidence) for target in expected))
            result = decide(backend, qid, question, evidence, policy)
            rows.append({**result, "gold": gold, "application_id": record["application_id"]})
            answers[qid] = result["answer"]
        # Risk proxy only: suggestions cannot become actual submitted classifications.
        material = [answers.get(qid, "UNKNOWN") for qid in ("software_gpu_capable", "workplan_sufficient", "scaling_strategy_adequate")]
        suggestion = "REJECT" if "NO" in material else "REVIEW_REQUIRED" if "UNKNOWN" in material else "ACCEPT"
        if "classification" in record["gold"]:
            review_results.append((record["gold"]["classification"], suggestion))
    by_question = defaultdict(list)
    for row in rows:
        by_question[row["question_id"]].append(row)
    accepts = [pred for gold, pred in review_results if gold == "ACCEPT"]
    rejects = [pred for gold, pred in review_results if gold == "REJECT"]
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {"backend": backend.name, "model_version": backend.version, "split": split,
            "dataset_kind": "synthetic" if any(r.get("synthetic") for r in selected) else "historical-unverified",
            "applications": len(selected), "production_qualified": False,
            "qualification_note": "Requires approved policy, curated historical labels, held-out validation and shadow deployment.",
            "overall": metrics(rows, policy["high_confidence"]),
            "per_question": {qid: metrics(items, policy["high_confidence"]) for qid, items in by_question.items()},
            "evidence_questions_evaluated": len(retrieval_hits), "fields_evaluated": len(extraction_hits),
            "evidence_top5_recall": statistics.mean(retrieval_hits) if retrieval_hits else None,
            "field_accuracy": statistics.mean(extraction_hits) if extraction_hits else None,
            "semantic_rejection_proxy_false_rejection_rate": sum(p == "REJECT" for p in accepts) / len(accepts) if accepts else None,
            "semantic_acceptance_proxy_false_acceptance_rate": sum(p == "ACCEPT" for p in rejects) / len(rejects) if rejects else None,
            "peak_runner_rss_bytes": rss if platform.system() == "Darwin" else rss * 1024,
            "resource_note": "Runner RSS excludes separate model servers and GPU memory; measure those externally.",
            "status_counts": dict(Counter(r["status"] for r in rows))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset")
    parser.add_argument("--output", required=True)
    parser.add_argument("--split", choices=["development", "validation", "heldout"], default="heldout")
    parser.add_argument("--backend", choices=["manual", "jevos", "systemone", "openjev", "masked"], default="manual")
    parser.add_argument("--endpoint")
    parser.add_argument("--model-path")
    parser.add_argument("--model-version")
    parser.add_argument("--policy")
    args = parser.parse_args()
    install_network_guard()
    records = [json.loads(line) for line in Path(args.dataset).read_text().splitlines() if line.strip()]
    backend = build_backend(args.backend, args.endpoint, args.model_path, args.model_version)
    report = benchmark(records, backend, load_policy(args.policy), args.split)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(f"Evaluated {report['applications']} applications; report written locally.")


if __name__ == "__main__":
    main()
