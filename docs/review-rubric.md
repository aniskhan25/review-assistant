# Review rules derived from the supplied documents

This is an implementation interpretation of the supplied internal guide and `Default.md`, not a newly approved institutional rubric. The guide describes evolving rules of thumb and permits justified technical exceptions. The application remains in shadow mode. Source fingerprints are recorded in `app/config/policy.json`; private source documents and proposals are not copied into this repository.

## Supported scope and source mapping

Fast Lane and Playground applications targeting LUMI-G can produce shadow assessments. Science and Large Scale remain available for extraction and evidence inspection only. Playground uses reviewer-requested onboarding criteria: a named AMD-capable stack and a concrete trial or exploratory task, without detailed job budgets or measured scaling.

| Check | Implemented behaviour | Source |
|---|---|---|
| GPU accounting | GPU-hours and concurrency count full MI250X modules, each containing two GCDs; four modules per node | Guide p.2 |
| Resource consumption | Minimum months = GPU-hours / (concurrent GPUs × 24 × 30); exceeding duration suggests rejection. This assumes continuous maximum concurrency and does not guarantee scheduling | Guide p.2 |
| Parallelism | Above four GPUs, verify that execution can use multiple nodes. Independent concurrent jobs are accepted, consistent with the implemented review interpretation; distributed training is not mandatory | Guide p.2 plus review interpretation |
| AMD compatibility | Verify the core dependencies have a plausible AMD execution path | Guide pp.2,4 |
| Official builds | Verify official AMD/maintainer ROCm builds, or the exact environment already demonstrated on LUMI. A confirmed negative suggests rejection unless the reviewer records a plausible exception | Guide p.2 |
| Installation | Custom code not explicitly installed or available is NO, even if the framework exists. NO alone is a startup warning | Guide p.4 |
| Workplan | Review achievable goals, job budgets, parallelism, installation, transfer, preprocessing and startup time against resources and calendar duration | Guide pp.2,5 |
| Storage | Above 50,000 GB, warn about LUMI-O or a storage extension; no rejection solely for storage | Guide p.2 |
| Personal data | Flag CCR follow-up. Accepted assessments include the supplied Data Controller/DPA paragraph; the app sends no notification | Guide p.3; Default.md |
| Tax number | Distinguish missing/unreadable evidence from verified absence. Verified absence suggests rejection | Guide p.3 |
| Organisation | Fast Lane: startup, SME or public sector; large enterprises need manual verification of open research. Playground: dated call reference permits SMEs/startups; academic/public-sector categories receive NO. Clear categories can be prefilled | Guide p.3 |
| Country | Dated verified subset (EU members and Norway) supports source-backed prefills. Uncovered countries, conflicts and expired references require manual verification with a reference; no model inference | Guide p.3 and country reference in questions.json |
| Classification | Accepted, Rejected (not feasible), or Rejected (out of resources). Eligibility rejection must use not feasible | Guide p.3; Default.md |

The current evidence-first policy permits NO when a required evidence search finds no supporting passage. Model uncertainty is not converted into missing evidence; modest positive scores require review. Clear negative answers can be prefilled for one final approval while retaining raw scores and the distinction between missing support and proven incompatibility. Model failures, unreadable pages, contradictions and missing/conflicting required facts remain exceptions. Eligibility uses sources or reviewer verification. Saved older registries keep their original gates.

Every final classification requires explicit approval, evidence and rationale. Acceptance despite remaining blocking findings requires an exception note. The audit records automatic prefills separately from individual confirmations.

Required facts are access mode, target, GPU-hours, maximum GPUs, duration, storage, personal-data declaration, tax number (including verified absence), organisation type and country. Previous LUMI use is optional because an omitted declaration must not be converted into an invented answer. Installation and startup feasibility remain mandatory decisions.

## Output and document precedence

The export uses the three questions from Default.md: architecture suitability, installation, and workplan feasibility. Scaling, official builds and eligibility remain internal checks with recorded evidence. Global comments, resource calculation, applicable storage wording, classification and rationale follow. Acceptance uses the supplied acceptance paragraph and adds the personal-data paragraph when declared. Rejections can include reviewer-selected amendment requests and always end with the Default.md closing.

Default.md and the guide use different rejection closing wording. The implementation uses Default.md as the output template and the guide for review criteria. This is an explicit implementation choice pending institutional validation. The standard wording describes external enrolment and DPA processes; the application does not execute those processes.

## Remaining validation

- Have a reviewer check these derived rules and representative completed drafts against the two documents, including justified exceptions and wording precedence.
- Use authorised historical reviewer-labelled decisions to measure field extraction, evidence retrieval and decision quality. The supplied proposal samples alone do not establish correct classifications.
- Verify current country eligibility through the reviewer’s authorised reference. The application remains offline and does not follow links from the guide.
- Validate the working Qwen backend against curated held-out labels before claiming production accuracy. Confidence settings remain provisional.
- Implement separate profiles before enabling Science or Large Scale assessment. The guide’s monthly 350,000/500,000 GPU-hour criteria for larger profiles have not been applied to Fast Lane.

Saved reviews retain their original policy and registry. Restart the service and upload a proposal again to review it under this profile. Existing confirmations are not silently migrated. Production approval, retention approval and deployment validation remain separate gates.

## Reviewer-defined Fast Lane readiness policy — 16 October 2026

Registry 4.7 adds a separate prior-validation question for Fast Lane. At least one relevant completed testing route is needed: Try and Buy, successful execution of the proposed or substantially equivalent workflow on LUMI, or local AMD/ROCm test results. A small successful functional test can establish initial validation; full allocation-scale benchmarks and a previous Playground award are not mandatory.

Supported containers, theoretical compatibility, planned onboarding, an allocation award, unrelated team experience and unspecified CSC hardware alone do not establish tested readiness. No previous LUMI use is not disqualifying if another route supplies relevant results. A resolved NO recommends rejection for Fast Lane readiness with an invitation to Playground for porting/validation and a renewed Fast Lane submission. Workplan feasibility and project merit remain separate; Playground itself has no prior-validation prerequisite. Ambiguous/conflicting evidence and model failures require resolution. Reviewer overrides and final approval remain available; accepting against a resolved readiness blocker requires an evidence-based exception note.

Readiness question 1.1 requires the completed run and qualifying platform to belong to the same test claim. Results obtained on NVIDIA or Intel Gaudi cannot be combined with planned ROCm validation to establish a completed AMD test. Future performance tuning does not invalidate a documented successful AMD/ROCm functional run. Saved reviews retain their question snapshots; changing the registry alone does not rescore an existing draft.

Applicant-facing readiness comments recommend Playground and refer to completed LUMI or AMD/ROCm testing without listing Try and Buy as an access option. Per the reviewer's scope clarification, Try and Buy is for Finnish SMEs, so it must not be presented as a generally available route. Documented historical testing through that programme can still be assessed internally; applicants are not required to have used it.

This is the reviewer's explicit routing policy, not a claim that these exact prerequisites are a universally published EuroHPC call rule. New reviews snapshot it; older reviews retain their original criteria.
