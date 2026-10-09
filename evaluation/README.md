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

## Import historical work-item reviews

`python -m app.import_reviews REVIEWS.csv PROPOSAL_DIRECTORY --output evaluation/private/RUN --exposed PREVIOUSLY_INSPECTED_APPLICATION_IDS...` matches explicit application IDs, imports only explicit YES/NO and classification answers, and flags blank templates, missing files and distinct PDF revisions. Identical file copies are deduplicated by SHA-256; distinct revisions are never selected by filename date or guesswork. Appended assessment regions are removed from benchmark inputs.

The private output contains an inventory, source fingerprints, candidate Fast Lane labels, separately retained other profiles, an issue report, and unlabelled narrow-check curation rows for development proposals. Review descriptions remain separate from proposal pages. Overall acceptance never becomes an inferred YES for every technical check. Groups use explicit cross-references and applicant filename matches; split assignments are provisional until related-project checks are complete. Pass all previously inspected/tuned examples via `--exposed` to keep their groups in development. Do not use Git for the generated source data.

For registries 3.0, 4.1 and 4.2, use the actual aggregation benchmark rather than the legacy broad-question runner:

```sh
python -m app.historical_evaluation evaluation/private/RUN/gold-candidates.jsonl \
  --split development --endpoint http://127.0.0.1:8018/v1/systemone \
  --model-version MODEL_FINGERPRINT --output evaluation/private/RUN/baseline.json
```

Supply the model service's authentication through `JEV_API_KEY`, never a command argument. The normal launcher owns an ephemeral key; a separately launched local model with a controlled key is suitable for CLI evaluation. This runner compares the three aggregated submission answers with historical labels, records abstentions and incorrect non-abstaining answers, and refuses cross-split related groups. It does not claim to evaluate final institutional classifications, which may depend on eligibility, exceptions and external verification. Review labels/rationales never enter the model input. Keep the held-out split untouched while tuning on development records.

Each completed proposal is saved to a sibling `.cases.jsonl` file with timing, individual check results and aggregation reasons. The aggregate JSON is written only after completion. Choose a fresh output name for every run; existing results are never overwritten. These diagnostic files contain private proposal evidence and must remain in `evaluation/private/`.

The local MLX runner accepts `--backend mlx --model-path /absolute/staged/model --model-version FINGERPRINT` instead of an endpoint. Run it in the prepared MLX environment. Development comparisons can reuse actual scores only after verifying identical wire questions, context construction, retrieval configuration and evidence IDs; disclose replay and deterministic source guards separately from fresh end-to-end inference. Never present development selection as held-out validation.
