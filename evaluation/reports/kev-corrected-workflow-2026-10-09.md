# Kev 0.8B comparison on the corrected workflow

9 October 2026. The app stays on Qwen3-4B-Instruct-2507 in MLX 4-bit format. Kev 0.8B is faster but fails the frozen accuracy and review-requirement gate under the current questions and confidence policy.

## Results

Sixteen development proposals, three historical technical answers each. No confidence thresholds were changed.

| Measure | Qwen 4B, MLX 4-bit | Kev 0.8B, BF16 + decision head |
|---|---:|---:|
| Matching historical answers | 34/48 | 17/48 |
| Incorrect answers | 2 | 5 |
| UNKNOWN answers | 12 | 26 |
| Automatically prefilled answers | 30/48 | 12/48 |
| Answers requiring review | 18 | 36 |
| Incorrect prefills | 1 | 0 |
| Median full review, four matched timing cases | 80.20 s | 10.45 s |
| Sampled process physical footprint peak | 4.51 GB | 3.86 GB |
| MLX allocator peak | 3.12 GB | 2.37 GB |

Kev was **7.7× faster** on the four matched timing cases. Its median across all sixteen proposals was 8.99 seconds; that number is not used for the matched speed ratio. Memory figures overlap and must not be added. They are per-process peaks from the recorded runs, not total Mac memory consumption or a fixed model requirement.

## Per-question results

| Question | Qwen: matching / unknown / prefilled | Kev: matching / unknown / prefilled |
|---|---:|---:|
| Software suitability | 16 / 0 / 16 | 12 / 4 / 12 |
| Prior installation | 7 / 9 / 6 | 0 / 15 / 0 |
| Workplan feasibility | 11 / 3 / 8 | 5 / 7 / 0 |

Kev did not provide an automatically prefilled installation or workplan answer in this sample. Its twelve ready technical answers were software assessments benefiting from the shared source-backed workflow. Its raw model calls did produce both YES and NO answers; the result is not the earlier constant-NO outcome. No inference/model errors were recorded.

## Comparison method

- Registry 4.4 and policy `ai-access-evidence-first-3` were frozen with full hashes, dataset identity, selection conditions and four timing-case IDs before candidate results were inspected. The gate requires no deterioration overall or per question in historical matches, incorrect answers, UNKNOWN answers, readiness or incorrect prefills; speed must also improve.
- Kev ran all sixteen development proposals freshly with the verified pinned BF16 base, merged LoRA adapter and FP32 decision head through the pinned upstream MLX encoder/runtime. The base and adapter manifests were reverified locally.
- Qwen accuracy and readiness use the previously verified exact-input replay under these same corrected criteria. Four preselected proposals were additionally rescored and timed freshly, sequentially after Kev; all twelve fresh submission answers matched the recorded Qwen answers.
- Timing includes source checks, retrieval and complete model-backed review from stored extracted pages. PDF extraction and model loading are excluded. Different conditional corroboration call counts are part of the measured review workflow.
- Both comparisons used the same isolated Python 3.12 / MLX runtime on this MacBook Air M3 with 16 GB unified memory. External Python networking was blocked. Private proposal text and scores stay in ignored local files.

## Limits and decision

These are exposed development proposals with provisional historical labels, not independent production validation. The remaining Qwen workplan disagreements include a review-standard difference already recorded in the evidence-fixes report. Confidence is not necessarily calibrated equally between models; this experiment measures the unchanged current workflow, not the best possible Kev configuration after domain adaptation or calibration.

The historical-answer and readiness comparison excludes eligibility, extracted-fact exceptions and final institutional classification. A faster candidate would have been selected if it preserved quality and review requirements. This candidate did not: historical matches fell from 34 to 17 and required review rose from 18 to 36. The app therefore remains on Qwen; no backend, final-approval rule or confidence threshold was changed.

175 regression tests pass, including guards against hiding per-question regressions or exchanging additional incorrect prefills for speed. The comparison command is documented in `evaluation/README.md`. Detailed reports, requests, manifests and summary are under ignored `evaluation/private/kev-corrected-2026-10-09/`.

## Pinned artifacts

- Qwen artifact fingerprint: `0ada3e291b9fe4c58b30be8ca7a034f4afb59fb7d02b0222f76e3121e123429a`.
- Kev adapter/base fingerprints: `d87256e4d4d28a5a83db6c3fd1f9bf107342dd1dd77d4075cc473d4d7ee12e52:3ccc23b882c6804393214d5d7882851e6d274a245b64c53122cbf77488b3961f`.
- Kev source revision: `5e42a7a03f28134853dd3ff77461457e921e5ec1`.
