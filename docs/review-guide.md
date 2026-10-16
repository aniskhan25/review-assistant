# Review workflow and reference

The local assistant prepares evidence-assisted Fast Lane and Playground reviews for LUMI-G. It defaults to shadow mode and requires final human approval. Qwen3-4B through MLX is the working local backend; manual review and alternative adapters are also available. See [setup and startup](../README.md) and [current status](implementation-status.md).

## Review a proposal

For a non-confidential walkthrough, upload `evaluation/datasets/sample.pdf`, a generated synthetic proposal.

1. Upload a PDF. Original bytes are processed in memory and not saved.
2. Resolve highlighted fact gaps. Clear extracted values with matching page evidence are prefilled automatically; missing, malformed and contradictory values remain exceptions. All values stay inspectable and editable.
3. Resolve decision exceptions. High-confidence positive model answers carry forward automatically. Uncertain or conflicting answers, model errors and unmatched eligibility checks need review; clear negative answers can be prefilled for final approval. A changed answer or corrected fact requires a note.
4. Inspect resource calculations and warnings. Explicitly choose acceptance or a rejection category and write a rationale. Acceptance despite blocking guidance also requires an evidence-based exception note.
5. Give one final approval covering the draft, its prefilled facts and answers, then download the assessment. Shadow outputs are visibly marked **not for submission**.

Fact changes and newly added evidence invalidate both automatic answers and decision confirmations; any edit invalidates the final export. Re-running inference also clears confirmations. Reviews survive restarts. Unreadable/scanned pages require reviewer transcription and explicit resolution; automatic OCR is not included.

The review summary links directly to unresolved facts, answers, extraction checks, and the assessment. Saving one form preserves unsaved edits in other forms in this tab's memory. These edits are not saved across a browser reload or lock; navigation warns before discarding them. Save fact, answer, and evidence edits before final approval. Any unsaved edit disables assessment download. After a stale-revision conflict, use **Reload latest and keep my edits**, reconcile the retained input with the updated evidence, and save again. Refreshing the review clears the approval checkbox. Requests are serialized, while **Lock workspace** remains available; locking does not cancel an operation already received by the server.

The extractor supports consolidated EuroHPC forms, including wrapped labels/values, `AI Factory Selection`, organisation VAT/country, storage/transfer questions and the personal-data declaration. Lead organisation fields are kept separate from team-member organisations, even across page breaks. Appended technical assessment forms cannot supply proposal facts or supporting evidence. Framework/backend fields can identify literal names in the listed software; this does not imply compatibility. Explicit missing markers remain unknown. Previous EuroHPC allocation and previous LUMI use are separate facts.

Previous-allocation sections are excluded from current application fields, including access mode and requested resources. The current mode can also be read from the submission's accepted policy paragraph, including paragraphs continuing on the next page; a bare URL or application-ID prefix is insufficient. Partition forms preserve node-hours, per-job GPU counts, simultaneous jobs, storage tiers in TB, storage-hours in TBh, and TB transfers separately. These are never silently converted to total GPU-hours, total concurrency, or GB. Optional partition fields are shown only when present or conflicting. Wrapped software lists are preserved.

Science and Large Scale applications support evidence inspection only. Playground uses its own onboarding profile: a named AMD-capable stack and a concrete trial or exploratory task suffice, without detailed job budgets, measured scaling or exact build verification. A missing current mode also prevents Fast Lane rule execution until verified.

After updating the parser or review policy, restart the service and upload the PDF again to create a newly extracted review. Existing saved reviews preserve their original extraction and confirmations; re-running model suggestions does not re-extract their fields.

## Local models

The review application and local launchers never download weights and include no hosted inference backend. All adapters normalize a full YES/NO/UNKNOWN probability distribution and apply the same confidence/margin policy. Missing evidence bypasses inference. Invalid responses or model failures return UNKNOWN, leaving manual review usable.

**CPU jevos:** stage its reviewed binary and weights separately, start its local server with an explicit model directory and no state cache, then:

```sh
python -m app.server --reviewer your-id --backend jevos \
  --endpoint http://127.0.0.1:8017/v1/systemone \
  --model-version YOUR_STAGED_ARTIFACT_SHA256
```

**OpenJev-4B:** install the reviewed `ejhshen/OpenJev` runtime in its own prepared environment and supply an absolute, existing artifact directory:

```sh
python -m app.server --reviewer your-id --backend openjev \
  --model-path /approved/models/openjev-4b --model-version YOUR_ARTIFACT_SHA256
```

Alternatively, run it in a separately isolated local process and use `--backend systemone --endpoint http://127.0.0.1:8080/v1/systemone`. Literal IPv4 loopback is required; proxies, remote hosts and HTTP redirects are not supported. `JEV_API_KEY` supplies local server authentication when enabled. The model service must itself be isolated; a local address does not prove that a separately installed service stays offline.

**Apple Silicon option scorer:** the staged 4-bit Qwen3 model can use the Mac GPU through MLX. It follows Jev-style option scoring and is not Jevos or the fine-tuned OpenJev model. See [local MLX setup](../deploy/mlx-local.md) for the pinned artifact, isolated runtime and offline launcher.

**Masked-logit baseline:** stage a compatible causal model/tokenizer and the optional `masked` dependencies first:

```sh
python -m app.server --reviewer your-id --backend masked \
  --model-path /approved/models/baseline --model-version YOUR_ARTIFACT_SHA256
```

The baseline loads with `local_files_only=True` and `trust_remote_code=False`, scores single-token A/B/C options, and refuses oversized context. Scores are raw softmax probabilities, not calibrated correctness. OpenJev and masked-model execution are serialized; the small service processes one request at a time. `/v1/decide` handles one registered question per call; a Fast Lane review covers eight top-level decisions, including two eligibility checks resolved from source-backed rules where possible. The current registry retains nine Fast Lane internal checks behind the three submission answers, plus scaling/build questions and a prior-use consistency check (up to twelve model calls; literal source claims can bypass calls). See [narrow review checks](narrow-review-checks.md). There is no GPU batching scheduler.

## Configuration and policy

`app/config/questions.json` contains the versioned registry; `templates.json` contains deterministic wording. `policy.json` contains confidence and retention settings. Pass a reviewed policy with `--policy /approved/policy.json`.

The supplied internal guide sets four full MI250X modules per node (two GCDs per module) and a storage warning above 50,000 GB. Storage alone does not trigger rejection. See the [derived review rubric](review-rubric.md) for sources, interpretations and unresolved approval gates. The capacity calculation uses exactly the plan's 24 × 30 hour convention and cannot promise scheduler availability.

Final assessments support `FAST_LANE` and `PLAYGROUND` on `LUMI-G`. Installation alone is a warning. Independent concurrent jobs are valid scaling. Clear high-confidence negative installation answers are prefilled as setup warnings. New uploads use an evidence-first policy: an empty required evidence search can produce NO (not demonstrated). Model uncertainty is not converted into missing evidence; modest positive scores remain positive but require review. Negative answers can be prefilled for final approval; installation NO remains only a setup warning. Raw model scores are preserved. Extraction failures, model errors, contradictory evidence, missing required facts and unresolved legal eligibility still need resolution. Deterministic impossible capacity can suggest rejection, but **every final classification still needs reviewer confirmation**.

The export follows the template’s three form questions, global comments and classification. Internal checks also cover scaling, official ROCm builds, organisation and country eligibility. Clear declared startup/SME/public-sector categories and countries in the verified subset (EU members and Norway) can be prefilled using the guide and a dated reference subset. Large-enterprise conditions, other countries and uncertain declarations still need manual verification and a note. The country reference expires on 2027-10-13; it does not cover all affiliated countries. Accepted personal-data projects receive the template’s DPA paragraph and a visible CCR follow-up task. No notifications or enrolments are sent by the app. Previous LUMI use remains optional; installation and startup feasibility must still be reviewed.

Production mode requires `approved: true` and complete thresholds. That configuration gate is an administrator attestation, not evidence that benchmark or organizational approval has occurred. Complete the remaining gates in [implementation status](implementation-status.md) before enabling it.

## Verification and evaluation

```sh
python -m pytest -q
node --test tests/frontend.test.cjs
python -m app.evaluation evaluation/datasets/synthetic.jsonl \
  --output evaluation/reports/synthetic-smoke.json
```

Tests cover a real generated PDF through final composition, malformed/ambiguous extraction, confidence and margin handling, contradiction referrals, deterministic rule branches, confirmation gates, API access controls, redirects, optimistic revisions, audit retention and an offline workflow. HTTP integration tests need loopback networking.

Use the same evaluation command with each model's flags and a curated private JSONL dataset. See [dataset format](../evaluation/README.md). Metrics include confusion matrices, precision/recall/F1, abstention, conditional high-confidence accuracy, Brier score, ECE, top-5 evidence recall, field accuracy and latency. Review-level semantic risk proxies are explicitly distinguished from actual rejection/acceptance rates. Reports never automatically qualify a model.

## Storage and security

- The service binds only to `127.0.0.1`; authenticated APIs require the private reviewer key. Host and Origin checks resist cross-origin requests and DNS rebinding. Static UI assets contain no external dependencies.
- The browser renders proposal content as text, not HTML. It uses no analytics, remote assets, browser persistence or cloud services.
- The Python runtime blocks external socket connections/DNS and disables Hugging Face telemetry/downloads. Native model libraries and separate processes still require OS/container egress isolation; see [offline deployment](../deploy/README.md).
- SQLite and key files are private (`0600`), in a `0700` directory. Full-disk encryption, account access and backups are deployment responsibilities. There is no application-level encryption.
- Original PDF retention is zero. Parsed text, facts, decisions and their override notes share a configurable review retention (default 30 days). Protected audit metadata and override reasons have independent retention (default 90 days). Defaults are provisional. Fine-grained separate retention for each review component is not implemented because those components form one reproducible state.
- Cleanup runs at startup, on requests and hourly while serving. Run `--purge-only` through an approved scheduler when the app is normally stopped. Deleting a review removes its audit records too. SQLite secure deletion is enabled; SSD snapshots/backups require separate retention controls.
- Operational request/exception logs contain no proposal content. Audit files are sensitive review data, not public telemetry. Private benchmark data belongs in ignored `evaluation/private/`, with its own approved retention process.

## API

All API requests use `Authorization: Bearer <reviewer key>`. Mutation JSON includes the current `revision`; stale updates return 409. See `app/server.py` for payloads.

| Route | Purpose |
|---|---|
| `POST /api/reviews` | Raw `application/pdf` upload |
| `GET /api/reviews` | Reviewer-owned saved reviews |
| `GET /api/reviews/{id}` | Canonical review state and provenance |
| `POST /api/reviews/{id}/fact` | Confirm/correct a fact with evidence IDs |
| `POST /api/reviews/{id}/decision` | Confirm/override a semantic answer |
| `POST /api/reviews/{id}/evidence` | Add page-referenced manual transcription |
| `POST /api/reviews/{id}/resolve-extraction` | Record manual extraction verification |
| `POST /api/reviews/{id}/analyze` | Re-run suggestions and clear confirmations |
| `POST /api/reviews/{id}/finalize` | Explicit classification, rationale, findings acknowledgement |
| `GET /api/reviews/{id}/export` | Current confirmed plain-text assessment |
| `GET /api/reviews/{id}/audit` | Protected audit history |
| `DELETE /api/reviews/{id}` | Delete state and audit |
| `POST /v1/decide` | `{ "question_id": "software_gpu_capable", "state": "evidence..." }` |

## Adapter references

The adapters were implemented against the public [jevos wire interface](https://github.com/feder-cr/jev) and [OpenJev-4B inference interface](https://github.com/ejhshen/OpenJev/blob/main/docs/INFERENCE.md). The [lookski/OpenJev implementation](https://github.com/lookski/openjev) is another optional SystemOne-compatible candidate; its hosted backends are not used here. Pin and review upstream source, licenses and model artifacts before staging. Protocol tests use local fixtures; Jevos-v4 has now been tested with real staged weights on Apple Silicon. The MLX option scorer has been evaluated with real local weights on sixteen development proposals; reports distinguish it from Jevos. Other adapters remain unverified with real weights.

Country extraction removes the form prefix `Horizon 2020:` from declared country values while preserving the original passage as evidence. This is a parsing correction, not an eligibility decision. The automatic country reference covers EU members and Norway, verified against [LUMI AI Factory eligibility](https://lumi-ai-factory.eu/pricing-and-eligibility/). Countries outside this subset still require reviewer verification against the applicable list. Eligibility cards explain this reference check separately from model inference. Saved reviews retain their original extraction and country-reference snapshot. Reupload to use the updated extractor and registry 4.5, or record a manual country decision with its reference in an existing review.

## AI workload assessment

New reviews include an advisory workload panel alongside the existing decision checks. It shows verbatim proposal excerpts for the task/method, model scale, data, memory/precision, experiments/runtime and intended outputs; missing matches remain explicitly unidentified. These excerpts are a navigation aid, not verified structured facts or inferred memory/runtime estimates.

Three additional bounded model calls assess technical fit, resource fit and plan credibility. Fast Lane expects a sizing rationale and executable plan; Playground accepts a bounded learning experiment. Findings distinguish plausible plans, potential material concerns and clarification needs. Model failures or unavailable references are shown separately. This adds inference time and does not change the existing automatic recommendation, exception count or approval gates.

The panel uses dated official LUMI hardware, container and AI-environment references from `app/config/workload.json`, snapshotted with each new review. The reference is general guidance, not a complete service catalogue or certification of an application's versions. The app stays offline; maintainers must verify and update references when they expire.

Workload evidence IDs, diagnostic labels and model uncertainty stay in the reviewer panel. Diagnostic labels and evidence IDs are never copied into applicant-facing wording. Plain-language fit findings matching the suggested classification are included in the draft Reason for classification by default, subject to your final review. The **Reason for classification** is the standalone explanation sent to the applicant by email; global technical comments are visible in the portal. The app combines applicable fit findings into one paragraph with a single clarification request, keeping numerical capacity constraints separate. There are no fit toggles; correct or remove any inaccurate wording directly in the editable reason before approval. Acceptance wording requires ACCEPT; concern wording requires REJECT. No uncertain finding automatically changes classification. The app prepares classification text only; email generation belongs to the EuroHPC JU portal. Replace generic wording with the specific confirmed problem when needed.

Saved approved wording is preserved. For reviews containing diagnostics copied by earlier versions, **Remove previous internal workload text from comments** removes those generated lines from the editable field while retaining other comments. Review and approve again to change the saved export. Capacity-related draft rejection reasons include the resource figures, assumptions and requested correction.

The AI workload assessment appears above extracted facts and has a direct navigation link. Fact/evidence changes invalidate the advisory findings; previous findings remain visible with an Out of date label, and rerunning suggestions refreshes them. If you already copied findings into comments, revise that text after any evidence change. Existing reviews retain their original registry and will not silently acquire the new assessment: restart the service and reupload to use it. The workload configuration has its own version (1.0); technical aggregation remains unchanged.


Registry 4.6 separates a documented supported LUMI-G software environment from complete application/version validation. Explicit LUMI-supported PyTorch/ROCm containers with a credible ROCm path can support YES; a generic framework name alone cannot. Routine package installation and onboarding are not proof of incompatibility. The check retrieves technical sections and preserves UNKNOWN when evidence is unresolved. Workload classifier uncertainty remains internal and is not automatically described as missing information in classification reasons; an empty evidence search is handled separately. Saved reviews keep their original question; reupload after restarting to use the revised check.

Registry 4.7 adds a Fast Lane readiness check under the [reviewer-defined routing policy](review-rubric.md): relevant completed Try and Buy testing, LUMI execution or local AMD/ROCm results can each establish initial validation. A supported container or a feasible workplan alone does not establish this readiness. A resolved negative directs the applicant to Playground for initial porting/testing and explains that distinction in the classification reason. Playground has no such prerequisite. Restart and reupload to apply the new criteria; rerunning an older saved review preserves its snapshot.

Decision cards now display the confirmed reviewer answer without the obsolete "reviewer required" label. Unconfirmed answers explain the applicable uncertainty, conflict, missing evidence or score threshold. Positive suggestions still use the existing confidence policy; thresholds have not been relaxed. Model scores identify which answer they support, including UNKNOWN.
