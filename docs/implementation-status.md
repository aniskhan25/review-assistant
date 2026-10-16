# Current status and verification

The application supports local Fast Lane and Playground reviews targeting LUMI-G. Science and Large Scale support evidence inspection only. Qwen3-4B-Instruct-2507 through MLX is the working local backend; the app defaults to shadow mode and requires explicit final approval. Registry 4.7 uses aggregation version 5; country question 1.2 covers a dated verified subset of EU members and Norway. Saved reviews retain their original policy, registry and extraction.

## Delivered

- PDF text extraction, page-linked evidence, lead-organisation scoping, conflict detection and manual transcription for unresolved extraction.
- Source-backed facts and eligibility checks, bounded local model scoring, deterministic resource checks, reviewer overrides and assessment composition.
- Saved reviews with revisions, provenance, audit history, retention and loopback authentication.
- Browser draft retention between form saves, serialized requests, stale-revision recovery, unsaved-edit approval/export gates, exception navigation and keyboard focus restoration.

Older model adapters, CLI evaluation tools and aggregation paths remain supported. They are required for reproducible comparisons and saved review snapshots, even when the active app uses Qwen. See [review rules](review-rubric.md), [technical checks](narrow-review-checks.md), [deployment](../deploy/README.md) and [evaluation](../evaluation/README.md).

## Verification record — 13 October 2026

| Check | Result and scope |
|---|---|
| Python regression suite | 180 passed, including extraction, eligibility, profiles, aggregation, workflow, API, security and evaluation |
| Frontend regression suite | 14 passed in a Node simulated DOM; not a browser-engine or accessibility certification |
| JavaScript syntax, patch whitespace and local documentation links | Passed |
| Synthetic evaluation smoke | 20 applications processed with manual backend; no model-quality claim |
| Synthetic browser journeys | Draft retention, manual/ready Fast Lane and Playground approval, unsupported Science, conflict recovery, keyboard focus, saved review reopening and 390-pixel layout checked |
| Independent GUI review | Accepted on 13 October; 175 Python tests, 13 frontend tests and eight supplemental probes at that revision. Subsequent country changes are covered by the current regression suite, not that independent verdict |
| Live local app | Qwen backend and registry 4.5/Norway reference confirmed through authenticated configuration endpoint |
| Native assessment download | Export endpoint passes API tests; native browser file completion remains unverified because browser automation did not expose the download event and native control was unavailable |

Run the commands in the root README to reproduce automated checks. Browser journeys used synthetic data and mocked ready-path scores; they do not establish model accuracy. The dated reports under `evaluation/reports/` describe historical experiments, not the current registry's qualification.

## Remaining acceptance gates

- Institutional approval of criteria, templates, thresholds, reference refresh and retention policy.
- Curated historical labels, held-out extraction/retrieval and decision-quality validation, and authorized shadow reviews measuring errors and time savings.
- Target deployment dependency/license review and OS/container egress isolation, including native libraries. The Docker recipe has not been validated on the target.
- Native-browser assessment download confirmation and broader accessibility verification.

Production mode requires an explicitly approved, complete policy; that setting is an administrator attestation, not evidence that these gates passed. Review data, keys, model artifacts, private benchmark inputs and runtime environments remain local and ignored by Git.

## Workload advisory — 16 October 2026

Added a versioned, snapshotted workload reference and three bounded advisory questions, verbatim evidence summaries, opt-in editable final comments, stale-input/reference guards and audit metadata without proposal excerpts. Existing classification rules and required confirmation gates are unchanged. Official hardware, Singularity and AI-environment documentation was checked on 16 October; the initial reference expires on 16 January 2027.

Automated integration verification: 186 Python tests and 15 frontend tests pass. Coverage includes mode-specific prompts, reference expiry, unsupported profiles, model failure, missing summary fields, source boundaries, stale evidence, legacy snapshots, audit privacy, opt-in comments and unchanged approval rules. This is advisory rollout coverage, not reviewer-labelled validation of workload judgments.

Real local Qwen smoke checks (synthetic data only): an internally consistent 10-hour Playground LoRA pilot was rated plausible on all three dimensions (16.1 s); explicit CUDA-only code requiring 160 GB on one GPU without sharding/offload triggered technical and plan concerns, while resource sizing remained unknown (15.8 s); an unchosen model/dataset/experiment plan returned clarification needs on all dimensions (13.6 s). An initial fixture accidentally combined the pilot with inherited 50,000-hour training boilerplate and mostly abstained; the fixture was corrected without changing prompts or thresholds. These few development examples do not establish accuracy. No real proposal was uploaded, changed or approved during this work. The running service needs a restart to load the Python integration; current browser-engine visual verification is not claimed.

Workload visibility fix: moved the panel above extracted facts, added a direct navigation link, retained stale findings with explicit Out of date labels, and explained missing structured assessments in legacy reviews. Copying stale findings into comments remains disabled. All 17 frontend regressions, JavaScript syntax and whitespace checks pass.

Shadow-preview integration: current workload findings now appear in partial and approval-ready drafts and prefill editable Global technical comments. Stale findings are excluded; saved reviewer comments and explicit removal are preserved. Verified with 187 Python tests and 18 frontend tests.

Applicant-facing wording supersedes automatic workload-comment insertion: diagnostics remain internal; verified findings can be selected into an editable, classification-specific reason with a live email preview. Saved exports are preserved; explicit cleanup removes earlier diagnostic comment lines. Capacity reasons now include figures and assumptions.

Fit controls refined: removed the email preview and email wording from the reason label. Short, highlighted fit toggles now sit under Reason for classification and include/exclude their text without replacing other rationale. Toggle state follows saved reasons and retained drafts; removal remains available after a classification change.

Default fit inclusion: current fit wording matching the suggested classification now appears automatically in the draft reason. Toggles can exclude each paragraph; saved reviewer rationale remains authoritative. Known duplicate capacity and generic build-availability boilerplate is consolidated while underlying blockers and specific findings remain intact. Classification rules are unchanged.

Coherent reason composition supersedes the fit toggles: matching findings form one paragraph with a single clarification request, while capacity constraints remain separate. The final reason stays editable, diagnostics stay internal, and saved approved wording is preserved.


Supported-environment correction — 16 October 2026: registry 4.6 changes the build-availability question to assess a documented supported execution environment, with exact-version/application validation treated separately. Technical retrieval excludes privacy material; no-evidence/uncertain results do not become negative software judgments. Workload abstentions with retrieved evidence no longer produce missing-information paragraphs. The supplied proposal returned YES in a local Qwen check using its technical passages (about 8.1 seconds); no saved review was changed. This focused test is not general accuracy validation.

## Fast Lane readiness and decision-status corrections — 16 October 2026

Registry 4.7 adds a separate Fast Lane prior-validation criterion under the reviewer's explicit policy. A resolved NO becomes a Playground-first readiness blocker, with an applicant-facing explanation distinct from project merit and feasible workplans. Relevant Try and Buy, LUMI or local AMD/ROCm results can independently satisfy it. Playground and saved older registries retain their behavior. Readiness rejections use not-feasible rather than out-of-resources; accepting despite the blocker still requires an exception note.

Confirmed cards show the reviewer answer and no further action required. Unresolved cards explain threshold, conflict, inference or evidence issues; top scores identify their associated answer. Confidence thresholds were not relaxed.

Validation: 201 Python tests and 20 frontend tests pass. Local Qwen tests on six synthetic cases yielded NO for planned-only testing and unrelated experience; YES for local AMD/ROCm, LUMI and Try and Buy results; UNKNOWN for contradictory claims. The initial verbose prompt abstained on some clear cases, so the any-one-route instructions were simplified and all six rerun without changing thresholds. These are development smoke checks, not held-out accuracy validation. No real review was modified or approved.


Readiness question 1.1 correction: completed execution and qualifying hardware must refer to the same test. Preliminary NVIDIA/Intel Gaudi results combined with future ROCm validation no longer count as completed AMD testing. The reported proposal was rescored locally using the application context: Qwen returned NO and the affected draft changed to REJECT with a Playground recommendation. The targeted update retained reviewer confirmations and recorded an audit entry; it did not finalize or submit the review. Nine opt-in local Qwen development regression cases passed, including genuine local AMD, LUMI and Try and Buy runs. Applicant-facing comments recommend Playground without naming Try and Buy, whose eligibility is restricted to Finnish SMEs under the reviewer's clarification.
