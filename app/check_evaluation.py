"""Run labelled narrow-question cases against the configured local backend."""
import argparse
import json
from pathlib import Path

from app.configuration import load_config, load_policy
from app.decision import build_backend, decide
from app.ingestion import document
from app.retrieval import retrieve
from app.security import install_network_guard


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset")
    parser.add_argument("--output", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model-version", required=True)
    args = parser.parse_args()
    install_network_guard()
    backend = build_backend("jevos", args.endpoint, version=args.model_version)
    registry, policy = load_config("questions.json"), load_policy()
    rows = []
    for line in Path(args.dataset).read_text().splitlines():
        case = json.loads(line)
        parent = registry["questions"][case["question_id"]]
        question = dict(parent, **parent["checks"][case["check_id"]])
        evidence = retrieve(document([{"page": 1, "text": case["text"]}])["evidence"], question)
        result = decide(backend, case["check_id"], question, evidence, policy)
        rows.append({"case_id": case["id"], "gold": case["gold"], **result})
    report = {"dataset_kind": "synthetic development checks", "production_qualified": False,
              "registry_version": registry["version"], "cases": rows,
              "accuracy": sum(r["answer"] == r["gold"] for r in rows) / len(rows),
              "unknown_count": sum(r["answer"] == "UNKNOWN" for r in rows),
              "model_error_count": sum(r["status"] == "MODEL_ERROR" for r in rows)}
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}))


if __name__ == "__main__":
    main()
