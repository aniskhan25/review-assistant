# Implementation status and acceptance gates

The supplied [implementation plan](implementation-plan.md) is copied for traceability, with trailing whitespace normalized. This repository implements a usable shadow workflow from an initially empty directory. It does not claim completion of data collection, policy approval, a real model bake-off or live deployment.

| Phase | Implemented | External requirements / remaining work |
|---|---|---|
| 0 — Baseline | Canonical state, provisional four-question registry and rules, synthetic fixtures | Existing application/source, internal policy, hardware definition and 30–50 historical reviews were not supplied; current behavior cannot be reproduced or frozen |
| 1 — Evidence | Embedded PDF text, page boundaries, sections, deterministic fields, conflict handling, BM25/top-5, reviewer evidence UI | Validate field aliases against real forms; measure ≥95% retrieval recall and ≥99% extraction on historical records; layout/OCR adapters remain optional follow-up |
| 2 — Bake-off | jevos/SystemOne, OpenJev-4B and masked-logit adapters; offline evaluation and synthetic manual baseline | Stage real weights/runtimes; review licenses; measure actual accuracy, calibration, wording sensitivity, evidence sensitivity, memory and latency; no winner selected |
| 3 — Integration | YES/NO/UNKNOWN, thresholds/margin, provenance, contradiction flags, human overrides and stale confirmation invalidation | Per-question calibration and historical contradiction testing |
| 4 — Rules | Capacity formula, storage warning, prior-use/startup risk, personal-data flag, software/workplan/scaling checks | Approve actual rule policy and GPU accounting units; regression against historical classifications |
| 5 — Composition | Confirmed templated assessments, rationale, evidence references, support configuration | Approve operational wording and contact information |
| 6 — Security | Local-only service, authentication, egress guard, no downloads/telemetry, cleanup, offline build recipe | Validate deployed OS/container isolation and native libraries, dependency/license sign-off, approved retention; multi-user RBAC and independently retained review components are not included |
| 7 — Shadow | Visible shadow mode and audit/override capture | Run 20–50 authorized live reviews; measure time savings and errors |
| 8 — Production | Explicit approved-policy switch, mandatory human final gate retained | Promote only after all institutional acceptance criteria pass |

No tests or synthetic metrics substitute for the external requirements. Production review quality targets remain unmeasured. The in-process Python service is intentionally small and suited to one local reviewer; resource-constrained container isolation is appropriate for untrusted PDF parsing and model execution.

The default rule profile is illustrative, based on the plan. Unset thresholds always produce reviewer-attention findings. Unsupported access modes and non-LUMI-G final exports are rejected. General CHOICE/SCORE questions, Playground/Large Scale profiles, tiered model routing, training, and automatic OCR are outside the delivered four-question workflow.

Decisions retain their registry version, model identity, raw probabilities, effective suggestion, evidence IDs, confirmed-facts hash and reviewer answer. Reviews snapshot policy and registry, including hashes; changing administrator configuration does not silently rewrite existing records. Final output records its template hash. Existing reviews should be re-created under a newly approved policy when policy migration is required.

Verification on the development workstation: 43 automated tests passed, a distributable wheel built successfully, and the browser workflow completed synthetic upload, nine required fact confirmations, four decision confirmations, final composition and persistence after reload. The authenticated export endpoint passed integration tests. The in-app browser did not report a file-download event for the Blob download, so native browser download completion remains unverified. Docker builds and real model execution were not run because a staged container environment and weights were not supplied.
