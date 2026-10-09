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

## Compare Qwen and Kev on Apple Silicon

`tools/stage_kev_models.py` downloads pinned public artifacts and verifies their SHA-256 hashes. It reads no private proposal data. Stage models while online, then run inference with the network guard enabled. Keep the benchmark environment separate from the application. The benchmark imports the pinned upstream Kev encoder, MLX backbone and FP32 pointer head from `models/kev-benchmark/source`; record the upstream commit in `revision.txt`. The 0.8B checkpoint uses its pinned BF16 base and merges its adapter. The 4B package uses an already merged 8-bit trunk and its saved head and temperature.

The recorded runtime uses Python 3.12 and `deploy/kev-benchmark-requirements.txt`. Upstream Kev source is pinned to `5e42a7a03f28134853dd3ff77461457e921e5ec1`. Run `python -m tools.stage_kev_models` in the environment to stage weights and hash-verified source modules with their Apache license. All candidates use this same runtime for the comparison; the application's environment remains separate.

```sh
models/kev-benchmark/.venv/bin/python -m tools.benchmark_local_models \
  --candidate baseline --dataset evaluation/private/RUN/gold-candidates.jsonl \
  --split heldout --output evaluation/private/COMPARISON/baseline.json
```

Repeat sequentially with `--candidate kev-08b` and `--candidate kev-4b-8bit`. Freeze candidates, dataset, policy, registry and selection criteria before reading the held-out results. Use a development smoke case to catch integration failures. Do not tune confidence thresholds on held-out proposals.

Each report records full review latency from stored extracted pages, loading time, MLX allocator peak, and separately sampled macOS physical footprint (50 ms interval). These memory figures overlap and must not be added together. PDF extraction is excluded. The first five observed model requests are replayed twice to distinguish a new state from a repeated state. Qwen has no cross-call prefix cache. Kev retains only the last state's prefix, so cache benefits depend on the application's retrieved evidence. Per-request input hashes allow shared calls to be checked across models; conditional corroboration can change call counts.

Reports and request traces contain private proposal evidence and remain ignored by Git. Historical labels are provisional; three submission answers are evaluated, not the final institutional classification. A small held-out sample cannot establish production accuracy. The benchmark never changes the running app's backend or approval policy.

## Compare the corrected workflow

For the corrected-workflow development comparison, freeze the dataset, complete registry and policy hashes, candidate identities, baseline report/readiness hashes, development IDs, timing IDs and selection conditions before inspecting candidate results. The accuracy gate also checks each submission question independently: more correct answers elsewhere cannot hide a workplan regression. Lower latency alone does not compensate for more incorrect answers, incorrect prefills or review requirements. Keep the numeric confidence policy unchanged while comparing models.

The current private experiment is `evaluation/private/kev-corrected-2026-10-09/`. It contains a frozen manifest, a fresh sixteen-proposal Kev run and a fresh Qwen timing run on four preselected matching cases. Full Qwen development accuracy/readiness comes from the previously verified exact-input replay; fresh timing answers must reproduce those recorded answers. The comparison validates matching criteria, policy, data and case IDs, and records per-question readiness separately from UNKNOWN counts. Eligibility and fact/extraction exceptions are outside these technical-answer counts.

```sh
models/kev-benchmark/.venv/bin/python -m tools.compare_corrected_models \
  evaluation/private/kev-corrected-2026-10-09
```

The summary refuses to overwrite an existing result. Development selection remains separate from production qualification and fresh held-out validation. This experiment does not tune either model to the exposed evaluation labels.
