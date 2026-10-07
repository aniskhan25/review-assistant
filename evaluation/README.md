# Offline evaluation

`datasets/synthetic.jsonl` contains 20 synthetic scenarios for pipeline smoke tests. They include explicit ROCm, CUDA-only, prior installation, missing fields, ambiguous values, independent job arrays, distributed execution and prompt-injection text. They are not historical reviews or a representative model-selection dataset. All belong to a synthetic `heldout` partition only so the default runner can exercise the full corpus.

Curate a private JSONL file with one record per reviewed proposal:

```json
{"application_id":"internal-001","group_id":"project-001","split":"heldout","synthetic":false,"pages":[{"page":1,"text":"Proposal text..."}],"gold":{"software_gpu_capable":"YES","code_previously_installed":"NO","workplan_sufficient":"YES","scaling_strategy_adequate":"YES","classification":"ACCEPT"},"gold_facts":{"requested_gpu_hours":50000},"evidence":{"software_gpu_capable":[{"page":1,"text":"Exact decisive excerpt"}]}}
```

Use `development`, `validation`, and `heldout` splits. Related variants must share `group_id` and stay in the same split. The loader rejects duplicate application IDs and cross-split group leakage. Gold labels must use canonical registry IDs (map legacy `code_installed` to `code_previously_installed` during curation). Confidence thresholds must be tuned outside the final held-out set.

The retrieval metric counts a question as a hit only if **every** annotated decisive excerpt appears in its top five passages. Missing gold evidence/fields yield null metrics, never synthetic perfect scores. Label excerpts that fit within the 900-character chunk size; inspect long-paragraph boundary failures during curation.

Run each staged candidate against the same split, for example:

```sh
python -m app.evaluation evaluation/private/gold.jsonl --backend jevos \
  --model-version reviewed-artifact-fingerprint --output evaluation/reports/jevos.json
python -m app.evaluation evaluation/private/gold.jsonl --backend openjev \
  --model-path /approved/models/openjev --model-version reviewed-artifact-fingerprint \
  --output evaluation/reports/openjev.json
python -m app.evaluation evaluation/private/gold.jsonl --backend masked \
  --model-path /approved/models/baseline --model-version reviewed-artifact-fingerprint \
  --output evaluation/reports/masked.json
```

Reports are aggregate-only. Per-question false negatives are not automatically false rejections (installation is an example). Semantic classification proxies ignore deterministic feasibility and require separate interpretation; actual review-level rejection/acceptance rates must be measured against the approved rule profile and human outcomes during shadow operation. Measure server-process/GPU memory separately: runner RSS cannot capture it. Compare annotated wording/evidence variants as separate records, then analyze differences before model selection.

Proposed promotion gates: top-5 evidence recall ≥95%, high-confidence accuracy ≥95%, false-rejection recommendations <1%, structured extraction ≥99%, acceptable interactive latency and no external traffic during a full review. The report keeps `production_qualified: false`; administrators must review all gates explicitly.
