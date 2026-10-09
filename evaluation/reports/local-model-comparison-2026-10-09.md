# Local model comparison — 2026-10-09

Measured on Apple M3 with 16 GB unified memory. Four held-out Fast Lane proposals, with three historical submission answers per proposal. Imported labels remain provisional. No institutional classification or Playground accuracy was evaluated.

## Results

| Model | Median review | Historical-answer agreement | Unresolved | MLX inference peak | Sampled process footprint peak | Loading |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3-4B, MLX 4-bit | 114.8 s | 5/12 | 1 | 3.01 GB | 4.31 GB | 8.7 s |
| Kev-0.8B, BF16 | 15.5 s | 6/12 | 0 | 2.34 GB | 4.01 GB | 9.1 s |
| Kev-4B, MLX 8-bit | 124.4 s | 6/12 | 0 | 5.59 GB | 7.15 GB | 10.5 s |

Both Kev candidates produced NO for all 12 final submission answers. An always-NO rule also agrees with 6/12 labels. The apparent one-answer improvement over Qwen replaces its single unresolved answer with NO; the six incorrect non-abstaining answers remain. This is not evidence of improved semantic review quality. All runs completed without model errors.

Kev-0.8B passes the frozen relative comparison gate: fewer unresolved answers, no additional incorrect answers, and lower median latency. It is about 7.4 times faster here. That relative gate does not establish adequate absolute accuracy. Kev-4B 8-bit is about 8.4% slower than Qwen and uses more memory. Neither candidate is promoted; the running application remains unchanged.

## Request timing and comparability

| Model | Median new state | Median repeated state | Actual review model calls | Shared unique inputs with Qwen |
|---|---:|---:|---:|---:|
| Qwen3-4B, MLX 4-bit | 9.348 s | 9.018 s | 48 | 48 |
| Kev-0.8B, BF16 | 1.321 s | 0.220 s | 44 | 44 |
| Kev-4B, MLX 8-bit | 11.424 s | 1.490 s | 46 | 46 |

Request timing uses each candidate's first five observed requests; these are not necessarily identical sets because corroboration is conditional on model answers. Every Kev review request has an identical evidence/question input hash in the baseline trace. Qwen has no cross-call state cache; Kev caches only the most recent evidence state. New/repeated request probabilities matched exactly on the sampled requests. Complete-review timing is the main comparison metric.

## Method and limits

- All timed candidates used the same isolated Python 3.12 environment, MLX 0.32.3, MLX-LM 0.32.0, Transformers 5.19.0 and tokenizers 0.23.3. The installed app uses Python 3.14 and tokenizers 0.23.2; its weights and MLX versions are the same. Runtime dependencies are pinned in `deploy/kev-benchmark-requirements.txt`.
- Candidates ran sequentially in the order Qwen, Kev-0.8B, Kev-4B. The app remained running but idle. This was one pass per proposal, with background load and thermal conditions uncontrolled.
- Review timing starts from stored extracted proposal pages and includes extraction of structured facts, retrieval, model checks, deterministic source guards, aggregation and draft preparation. PDF-to-text extraction, UI traffic and loading are excluded.
- Memory figures are process-specific: MLX allocator peak and macOS physical footprint sampled every 50 ms. They overlap and must not be summed. Inference peaks include timing replays. Loading peaks are separate.
- Model weights, upstream code, dataset and policy were frozen and fingerprinted. Proposal text, historical labels and detailed traces stay in ignored private files. Model inference uses the offline network guard.
- Confidence thresholds were unchanged. No thresholds or prompts were tuned on held-out cases. Historical labels are pending source/version curation and do not label each narrow evidence check. Four related-group-separated cases cannot establish production accuracy.

## Next step

Use the 16 development proposals to curate evidence and narrow-check labels, check why demonstrated positive evidence becomes NO, and calibrate the model/policy on development data. Confirm any resulting improvement on fresh held-out proposals. The four cases read here must not be reused as an untouched final confirmation set. Add reviewed Playground examples before claiming accuracy for that profile.

Detailed private reports and frozen protocol: `evaluation/private/kev-comparison-2026-10-09/`. Benchmark and application tests: 159 passed.
