# Local technical review assistant

A local, evidence-assisted Fast Lane/LUMI-G review application. PDF parsing, lexical retrieval, structured facts, deterministic checks, reviewer confirmations, assessment templates, SQLite audit records and offline evaluation are implemented. The interface works without a model.

**The default is a shadow prototype, not an approved production reviewer.** Sample proposals, an internal guide and a review template have been supplied and used to refine the workflow. Historical reviewer-labelled decisions, policy sign-off, model weights and deployment hardware remain outstanding. The bundled 20 cases are explicitly synthetic. Jevos-v4 is staged and operationally tested on this Mac as the initial model candidate; it has not been qualified for production accuracy.

## Run with the local Jev model

The staged Apple Silicon setup starts both the model and review app with:

```sh
python3 -m app.local_jev --reviewer anisrahm --port 8766 --model-port 8018
```

Open **http://127.0.0.1:8766**, unlock with `data/reviewer.key`, and upload a PDF. The three submission answers are assembled from narrow evidence checks; scaling and official-build checks also run through Jevos-v4; the two eligibility questions remain manual. See [local Jevos setup](deploy/jev-local.md) for artifact hashes, lifecycle and validation limits.

## Manual mode and dependencies

Python 3.11 or later is required. Prepare dependencies in a non-confidential staging environment before deploying offline:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m app.server --reviewer your-reviewer-id
```

Open **http://127.0.0.1:8765**. Paste the key from `data/reviewer.key` into the unlock form. The key is stored only in browser memory. Use a dedicated OS account and data directory per reviewer; this is a single-user service, not a multi-user identity provider.

For a non-confidential walkthrough, upload `evaluation/datasets/sample.pdf`, a generated synthetic proposal.

1. Upload a PDF. Original bytes are processed in memory and not saved.
2. Resolve highlighted fact gaps. Clear extracted values with matching page evidence are prefilled automatically; missing, malformed and contradictory values remain exceptions. All values stay inspectable and editable.
3. Resolve decision exceptions. High-confidence positive model answers carry forward automatically. Negative recommendations, uncertain or conflicting answers, model errors and manual eligibility checks need review. A changed answer or corrected fact requires a note.
4. Inspect resource calculations and warnings. Explicitly choose acceptance or a rejection category and write a rationale. Acceptance despite blocking guidance also requires an evidence-based exception note.
5. Give one final approval covering the draft, its prefilled facts and answers, then download the assessment. Shadow outputs are visibly marked **not for submission**.

Fact changes and newly added evidence invalidate both automatic answers and decision confirmations; any edit invalidates the final export. Re-running inference also clears confirmations. Reviews survive restarts. Unreadable/scanned pages require reviewer transcription and explicit resolution; automatic OCR is not included.

The extractor supports consolidated EuroHPC forms, including wrapped labels/values, `AI Factory Selection`, organisation VAT/country, storage/transfer questions and the personal-data declaration. Lead organisation fields are kept separate from team-member organisations, even across page breaks. Appended technical assessment forms cannot supply proposal facts or supporting evidence. Framework/backend fields can identify literal names in the listed software; this does not imply compatibility. Explicit missing markers remain unknown. Previous EuroHPC allocation and previous LUMI use are separate facts.

Previous-allocation sections are excluded from current application fields, including access mode and requested resources. The current mode can also be read from the submission's accepted policy paragraph, including paragraphs continuing on the next page; a bare URL or application-ID prefix is insufficient. Partition forms preserve node-hours, per-job GPU counts, simultaneous jobs, storage tiers in TB, storage-hours in TBh, and TB transfers separately. These are never silently converted to total GPU-hours, total concurrency, or GB. Optional partition fields are shown only when present or conflicting. Wrapped software lists are preserved.

Science, Large Scale and Playground applications support evidence inspection only. Their detected profiles bypass the Fast Lane model and rule engine, and cannot produce a final Fast Lane assessment. A missing current mode also prevents Fast Lane rule execution until verified.

After updating the parser or review policy, restart the service and upload the PDF again to create a newly extracted review. Existing saved reviews preserve their original extraction and confirmations; re-running model suggestions does not re-extract their fields.

## Local models

The review application and local launcher never download weights and includes no hosted inference backend. All adapters normalize a full YES/NO/UNKNOWN probability distribution and apply the same confidence/margin policy. Missing evidence bypasses inference. Invalid responses or model failures return UNKNOWN, leaving manual review usable.

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

**Masked-logit baseline:** stage a compatible causal model/tokenizer and the optional `masked` dependencies first:

```sh
python -m app.server --reviewer your-id --backend masked \
  --model-path /approved/models/baseline --model-version YOUR_ARTIFACT_SHA256
```

The baseline loads with `local_files_only=True` and `trust_remote_code=False`, scores single-token A/B/C options, and refuses oversized context. Scores are raw softmax probabilities, not calibrated correctness. OpenJev and masked-model execution are serialized; the small service processes one request at a time. `/v1/decide` handles one registered question per call; a review covers seven top-level decisions, including two manual-only eligibility checks. Registry 4.1 runs nine internal checks behind the three submission answers, plus the scaling and official-build questions (eleven model calls total). See [narrow review checks](docs/narrow-review-checks.md). There is no GPU batching scheduler.

## Configuration and policy

`app/config/questions.json` contains the versioned registry; `templates.json` contains deterministic wording. `policy.json` contains confidence and retention settings. Pass a reviewed policy with `--policy /approved/policy.json`.

The supplied internal guide sets four full MI250X modules per node (two GCDs per module) and a storage warning above 50,000 GB. Storage alone does not trigger rejection. See the [derived review rubric](docs/review-rubric.md) for sources, interpretations and unresolved approval gates. The capacity calculation uses exactly the plan's 24 × 30 hour convention and cannot promise scheduler availability.

Only `FAST_LANE` and `LUMI-G` final assessments are supported. Installation alone is a warning. Independent concurrent jobs are valid scaling. Unconfirmed model negatives are referrals; deterministic impossible capacity can produce a suggested rejection, but **every final classification still needs reviewer confirmation**.

The export follows the template’s three form questions, global comments and classification. Internal checks also cover scaling, official ROCm builds, organisation and country eligibility. Eligibility requires manual verification and a note; the app includes no current country roster. Accepted personal-data projects receive the template’s DPA paragraph and a visible CCR follow-up task. No notifications or enrolments are sent by the app. Previous LUMI use remains optional; installation and startup feasibility must still be reviewed.

Production mode requires `approved: true` and complete thresholds. That configuration gate is an administrator attestation, not evidence that benchmark or organizational approval has occurred. Complete the remaining gates in [implementation status](docs/implementation-status.md) before enabling it.

## Verification and evaluation

```sh
python -m pytest -q
python -m app.evaluation evaluation/datasets/synthetic.jsonl \
  --output evaluation/reports/synthetic-baseline.json
```

Tests cover a real generated PDF through final composition, malformed/ambiguous extraction, confidence and margin handling, contradiction referrals, deterministic rule branches, confirmation gates, API access controls, redirects, optimistic revisions, audit retention and an offline workflow. HTTP integration tests need loopback networking.

Use the same evaluation command with each model's flags and a curated private JSONL dataset. See [dataset format](evaluation/README.md). Metrics include confusion matrices, precision/recall/F1, abstention, conditional high-confidence accuracy, Brier score, ECE, top-5 evidence recall, field accuracy and latency. Review-level semantic risk proxies are explicitly distinguished from actual rejection/acceptance rates. Reports never automatically qualify a model.

## Storage and security

- The service binds only to `127.0.0.1`; authenticated APIs require the private reviewer key. Host and Origin checks resist cross-origin requests and DNS rebinding. Static UI assets contain no external dependencies.
- The browser renders proposal content as text, not HTML. It uses no analytics, remote assets, browser persistence or cloud services.
- The Python runtime blocks external socket connections/DNS and disables Hugging Face telemetry/downloads. Native model libraries and separate processes still require OS/container egress isolation; see [offline deployment](deploy/README.md).
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

The adapters were implemented against the public [jevos wire interface](https://github.com/feder-cr/jev) and [OpenJev-4B inference interface](https://github.com/ejhshen/OpenJev/blob/main/docs/INFERENCE.md). The [lookski/OpenJev implementation](https://github.com/lookski/openjev) is another optional SystemOne-compatible candidate; its hosted backends are not used here. Pin and review upstream source, licenses and model artifacts before staging. Protocol tests use local fixtures; Jevos-v4 has now been tested with real staged weights on Apple Silicon. Other adapters remain unverified with real weights.
