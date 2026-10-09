# Review evidence fixes — 9 October 2026

The local assistant now uses question registry 4.4 and policy `ai-access-evidence-first-3`, with the existing Qwen3-4B MLX 4-bit option scorer. No model was promoted or retrained.

## Implemented changes

- Empty form headings and pagination no longer crowd out substantive passages. Technical checks use relevant proposal sections, including the modern Playground code heading and optimization sections.
- Modest positive confidence is preserved as a positive assessment requiring review. Classifier uncertainty is no longer turned into a confident rejection. An empty required evidence search can still yield a cited NO.
- Literal supported framework names and current workload quantities use source-backed checks over the full relevant search scope. These rules do not establish prior installation, exact build compatibility or overall feasibility. Parameter counts alone are not a planned workload.
- Planned porting with named AMD alternatives is separated from unsupported required dependencies. Explicit deferred critical versions still count as an unresolved compatibility requirement.
- A compatibility blocker is not contradicted merely by a ROCm mention. Impossible resource capacity is calculated from cited facts independently of model confidence.
- The UI distinguishes source-backed checks from model scores. Final reviewer approval remains required; numeric confidence thresholds are unchanged.

## Development evaluation

Sixteen development proposals, with three historical submission answers each. The four previously inspected held-out proposals were not rerun or used for these fixes. Historical labels remain provisional pending source/version and criterion curation.

| Submission question | Matching | Disagreeing | Unknown | Automatically prefilled |
|---|---:|---:|---:|---:|
| Software suitability | 16 | 0 | 0 | 16 |
| Prior installation | 7 | 0 | 9 | 6 |
| Workplan feasibility | 11 | 2 | 3 | 8 |
| **Total** | **34/48** | **2/48** | **12/48** | **30/48** |

Eighteen submission answers still require review: twelve UNKNOWN answers and six answers below the automatic approval requirements. Of the thirty prefilled submission answers, twenty-nine match the historical labels. These counts exclude eligibility decisions and fact/extraction exceptions; they are not a count of all app exceptions.

The two remaining workplan disagreements are historical YES answers supported mainly by capacity arithmetic and broad plans. The current evidence criterion additionally requires concrete workload sizing or a bounded experiment plan. One disagreement is prefilled NO; the other has insufficient confidence for automatic prefill. This standard difference needs explicit curation rather than assuming either set of labels is correct. Nine installation answers remain uncertain, principally because prior-use interpretations or installation evidence do not resolve consistently.

## Evaluation method and limits

The first pass used fresh end-to-end local inference for all sixteen development proposals. The compatibility wording was then clarified. The final pass reused 123 model scores only after exact full input SHA-256 matches and freshly scored four changed compatibility inputs. A subsequent exact replay reproduced the final answers and audited readiness without new model inference. Final-pass elapsed times are therefore not end-to-end latency measurements. No claim of a latency improvement or validated production accuracy is made.

The development cases were used for diagnosis and refinement, so this is development selection, not held-out validation. No narrower check labels were invented from the three parent review answers, and no confidence calibration was fitted to unlabelled checks. A private file contains 144 current check/evidence rows for targeted curation, with gold labels left unset.

## Verification and use

171 regression tests passed, including missing-evidence versus uncertainty, preserved modest positive answers, Playground onboarding, technical retrieval, explicit compatibility blockers, source provenance, and capacity calculations. JavaScript syntax and Git whitespace checks passed. The offline app was restarted and the authenticated configuration endpoint verified registry 4.4 and the revised policy.

New uploads use the current extraction and criteria. Saved reviews retain their original registry; upload again for the complete current workflow. Existing approved reviews are not rewritten.

Detailed source text, scored inputs, checkpoints, and curation files are local under ignored `evaluation/private/evidence-fix-2026-10-09/`. They are not committed.
