# Narrow checks behind the submission form

Registry version 3.0 preserves the three submission questions and their output wording. With a model configured, the app runs ten smaller evidence checks and combines them with explicit rules. Scaling and official-build availability remain separate checks; the two eligibility questions remain manual. There are twelve model calls per supported review instead of five, so inference can take longer.

| Submission answer | Internal checks | Combination |
|---|---|---|
| Architecture suitability | Named core dependencies; proposed AMD/ROCm execution path; explicitly required CUDA-only dependency | Explicit CUDA-only requirement or inability to run on AMD yields a negative recommendation. Identified dependencies plus an AMD path support YES. Otherwise UNKNOWN. Official-build availability remains a separate required check. |
| Code installed | Exact application previously installed/run on LUMI; only a sufficient standard environment needed; custom installation pending | Pending installation yields NO unless it conflicts with prior execution, which yields UNKNOWN. Prior exact execution or a sufficient standard environment supports YES. Otherwise UNKNOWN. NO alone is a startup warning. |
| Workplan feasibility | Concrete outputs; quantitative job sizing; startup allowance; execution requirements versus targets | Python first checks GPU-hours against concurrency and duration. Impossible capacity yields NO. An explicit failure in any workplan check yields a negative recommendation. All four positive checks plus fitting arithmetic support YES. Missing evidence remains UNKNOWN. |

These checks classify what the proposal supports; they do not independently verify package compatibility or country eligibility. Naming a framework alone is insufficient evidence of full application compatibility or installation.

The interface displays each internal answer, score, status and evidence IDs under its submission question, plus the rule used to combine them. The combined answer has no invented probability distribution: the displayed score is the minimum among checks supporting that conclusion, not a calibrated probability. Contradictions, negative recommendations and insufficient confidence remain exceptions. Reviewers can resolve the submission answer without separately confirming every internal check. Final output includes the automated check basis and any reviewer explanation. Audit records retain internal results and aggregation version.

## Validation

Run the deterministic aggregation and workflow tests with `python3 -m pytest -q`.

`evaluation/datasets/narrow-checks.jsonl` contains twelve **synthetic development examples with proposed labels**, not historical reviewer decisions. The cases test explicit evidence and missing information, not end-to-end review accuracy. Run against an authenticated local model endpoint with `JEV_API_KEY` set in the environment:

```sh
python3 -m app.check_evaluation evaluation/datasets/narrow-checks.jsonl \
  --endpoint http://127.0.0.1:8018/v1/systemone \
  --model-version YOUR_MODEL_FINGERPRINT \
  --output evaluation/reports/narrow-jevos.json
```

The launcher creates an ephemeral model key for its own children; use a separately started model with a key you control for this CLI benchmark. Never place keys in command arguments or commit private proposal evidence.

On the installed Jevos-v4 model, the initial twelve-case run matched 8/12 proposed labels. Four clear positive examples returned UNKNOWN (dependency identification, concrete goals, job sizing and startup allowance). One correctly unknown case also abstained. All seven non-abstaining answers matched the proposed labels, with no model errors. This small development set is insufficient to claim model quality or calibration. Thresholds have not been lowered to improve the score.

The previous broad-question benchmark remains a legacy comparison and does not evaluate the new aggregation pipeline. Next, have a reviewer check the proposed labels, add private representative examples for each check, and reserve separate held-out proposals before comparing models or tuning prompts further.

New uploads receive registry 3.0. Saved reviews retain their original question registry; rerunning an old review does not silently migrate its criteria. Upload again to use the new checks. The application remains in shadow mode with final human approval.

A supplied Fast Lane proposal completed the new twelve-call workflow in 116.8 seconds. Internal checks identified an AMD path, concrete goals and a plausible execution plan, while dependency identification, job sizing and startup timing remained unresolved. The three submission answers remained UNKNOWN; scaling was still the only automatically ready top-level decision. This run improved diagnostic detail, not the number of resolved decisions. The private result is stored under ignored `evaluation/private/narrow-workflow-smoke.json`.
