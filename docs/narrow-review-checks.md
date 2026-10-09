# Narrow checks behind the submission form

Registry 4.2 preserves the three submission questions and their output wording. Nine evidence checks support these answers; scaling and official-build availability remain separate, and eligibility can use clear source-backed category and EU-member rules. Up to twelve model calls are used, including a prior-use consistency check; literal source claims can bypass some calls.

| Submission answer | Internal checks | Combination |
|---|---|---|
| Architecture suitability | Named dependencies; AMD execution path; CUDA-only requirement; material compatibility blocker | A positive material blocker or the original architecture failure checks yields NO. The retained dependency and AMD-path checks support the draft YES; an unresolved additional compatibility check still requires reviewer verification. A resolved compatibility check contributes to the combined confidence. Otherwise UNKNOWN. Repeated explicit deferral of critical component version pinning is a source-backed blocker; routine porting does not by itself. Unresolved compatibility remains UNKNOWN. Weak negative checks cannot override into a reliable combined NO. |
| Code installed | Prior LUMI use of the workflow/equivalent environment; future installation or porting | Prior use supports YES. Pending installation or a finding that prior use is not demonstrated supports NO. Conflicting prior-use and pending-installation statements, or opposite answers under corroborating prior-use interpretations, remain UNKNOWN. Extensions in an already validated environment are distinguished from first installation. NO is a setup risk, not rejection by itself. |
| Workplan feasibility | Concrete targets; meaningful workload sizing; credible execution plan | Impossible capacity or a material negative check yields NO. Concrete targets, meaningful sizing and a positive execution assessment support YES without requiring a separate startup timetable. Unresolved sizing remains UNKNOWN. Otherwise UNKNOWN. |

These are proposed review interpretations derived from development reviews, not independently approved policy. They classify supplied evidence rather than independently verifying package compatibility. NO for missing installation evidence means “not demonstrated,” not “incompatible.” UNKNOWN is reserved for evidence that cannot support a reliable assessment; it is not automatically interchangeable with a negative finding.

Jevos and the local MLX scorer evaluate eight evidence checks through binary YES/NO scoring (`noul` for Jevos, masked option logits for MLX). Its score is mapped to YES and NO; UNKNOWN is produced by the existing confidence/margin policy or absent evidence, not by inventing a third model probability. The AMD-path check uses three options and cited generic framework references; these references do not verify exact application versions or installation. Other adapters retain their own scoring interfaces. Saved registry 3.0 reviews retain their original choice-scoring behavior.

The technical checks with section restrictions constrain retrieval to their relevant proposal sections, preventing ethics/privacy boilerplate from displacing technical evidence. Previous-allocation evidence is allowed only for the prior-use check. Retrieved text and structured facts remain untrusted evidence; historical review answers never enter inference.

The interface shows each internal result, score, status and source IDs, together with the aggregation reason. Combined scores are the minimum supporting scores, not calibrated probabilities of correctness. Confidence and margin thresholds are unchanged. Clear high-confidence installation NO answers are setup-warning prefills. Other negative recommendations, contradictions, low-confidence results and accounting assumptions still require review. Reviewers resolve the submission answer without confirming every internal check. Final output and audit records retain the reasoning and aggregation version.

## Validation

Run the deterministic aggregation, retrieval and workflow tests with `python3 -m pytest -q`. Historical evaluation uses the actual aggregation pipeline:

```sh
python3 -m app.historical_evaluation evaluation/private/RUN/gold-candidates.jsonl \
  --endpoint http://127.0.0.1:8019/v1/systemone --split development \
  --model-version MODEL_FINGERPRINT --output evaluation/private/RUN/revised.json
```

Use a local service with `JEV_API_KEY` in its environment. Do not put secrets in command arguments or proposal data in Git. Keep held-out proposals untouched during development. See [evaluation documentation](../evaluation/README.md).

`evaluation/datasets/narrow-checks.jsonl` contains synthetic examples with proposed labels for registry 4.2. These are not human-labelled historical checks or model quality evidence. The earlier registry 3.0 synthetic result (8/12) does not apply to these revised examples. The historical registry 3.0 baseline matched 6/48 submission answers, gave one incorrect answer and abstained on 41, motivating the revised criteria. Baseline and revised reports remain private.

New uploads receive registry 4.2 and aggregation version 3. Saved reviews retain their original registry and aggregation semantics, including the stricter registry 3.0 rules; rerunning does not silently migrate them. Upload a proposal again to use the revised checks. The app remains in shadow mode with final human approval.

The final development comparison reused unchanged model questions, probability outputs and retrieved evidence from the baseline and native-scoring runs. Registry 4.1 aggregation produced 19 matching answers, four incorrect answers and 25 abstentions across 48 submission answers, compared with 6/1/41 for registry 3.0. Final aggregation was checked by deterministic replay, not a fresh full 16-case run. Architecture retained its baseline draft results; installation matched 9/16 with three disagreements; workplan matched 4/16 with no non-abstaining disagreements. No submission answer met all automatic-readiness criteria. These development results improve draft coverage, not autonomous review reliability.

The local 4B scorer and revised source checks resolved more development answers. Across 48 submission answers, the final replay matched 32, disagreed on 3, and returned UNKNOWN on 13, compared with 19/4/25 for the previous Jevos workflow. Eight revised check scores were measured afresh on all sixteen development proposals; unchanged scores and a corroborating prior-use interpretation were verified against the real MLX baseline. Final aggregation also applied deterministic source-claim guards. This is not a fresh full candidate run or held-out validation, and it does not evaluate final classification. A separate live PDF smoke run verifies application integration.
