# Review rules derived from the supplied documents

This is an implementation interpretation of the supplied internal guide and `Default.md`, not a newly approved institutional rubric. The guide describes evolving rules of thumb and permits justified technical exceptions. The application remains in shadow mode. Source fingerprints are recorded in `app/config/policy.json`; private source documents and proposals are not copied into this repository.

## Supported scope and source mapping

Fast Lane and Playground applications targeting LUMI-G can produce shadow assessments. Science and Large Scale remain available for extraction and evidence inspection only. Playground uses reviewer-requested onboarding criteria: a named AMD-capable stack and a concrete trial or exploratory task, without detailed job budgets or measured scaling.

| Check | Implemented behaviour | Source |
|---|---|---|
| GPU accounting | GPU-hours and concurrency count full MI250X modules, each containing two GCDs; four modules per node | Guide p.2 |
| Resource consumption | Minimum months = GPU-hours / (total concurrent GPUs across all jobs × 24 × 30); exceeding duration suggests rejection only when a project-wide concurrency bound is explicit. This assumes continuous maximum concurrency and does not guarantee scheduling | Guide p.2 |
| Parallelism | Above four GPUs, verify that execution can use multiple nodes. Independent concurrent jobs are accepted, consistent with the implemented review interpretation; distributed training is not mandatory | Guide p.2 plus review interpretation |
| AMD compatibility | Verify the core dependencies have a plausible AMD execution path | Guide pp.2,4 |
| Official builds | Verify official AMD/maintainer ROCm builds, or the exact environment already demonstrated on LUMI. A confirmed negative suggests rejection unless the reviewer records a plausible exception | Guide p.2 |
| Installation | Custom code not explicitly installed or available is NO, even if the framework exists. NO alone is a startup warning | Guide p.4 |
| Workplan | Review achievable goals, job budgets, parallelism, installation, transfer, preprocessing and startup time against resources and calendar duration | Guide pp.2,5 |
| Storage | Above 50,000 GB, warn about LUMI-O or a storage extension; no rejection solely for storage | Guide p.2 |
| Personal data | Flag CCR follow-up. Accepted assessments include the supplied Data Controller/DPA paragraph; the app sends no notification | Guide p.3; Default.md |
| Tax number | Distinguish missing/unreadable evidence from verified absence. Verified absence suggests rejection | Guide p.3 |
| Organisation | Fast Lane: startup, SME or public sector; large enterprises need manual verification of open research. Playground: dated call reference permits SMEs/startups; academic/public-sector categories receive NO. Clear categories can be prefilled | Guide p.3 |
| Country | Dated verified LUMI AI Factory list (including the United Kingdom) supports source-backed prefills. Uncovered countries, conflicts and expired references require manual verification with a reference; no model inference | Guide p.3 and country reference in questions.json |
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


## Country reference update — 19 October 2026

Country question 1.3 snapshots all 38 countries explicitly listed on [LUMI AI Factory pricing and eligibility](https://lumi-ai-factory.eu/pricing-and-eligibility/), including the United Kingdom. The computing-services section connects the list to EuroHPC JU Industrial Innovation access, including Playground and Fast Lane. The reference was checked on 2026-10-19 and expires on 2027-10-19. UK, U.K., GB and GBR resolve to United Kingdom; Turkey resolves to Türkiye. Countries outside the published list still need verification rather than automatic rejection. Consortium membership is not a requirement for EuroHPC JU access. Organisation and project eligibility remain separate. Older saved reviews retain their original reference snapshot.

Prior-installation question 4.5 clarifies that documented prior use of the proposed core stack on LUMI counts even when a new project proposes new datasets, model experiments or tuning. Prior allocation awards and generic environment availability alone do not establish that the application was used. Independent corroboration and genuine disagreement handling remain enabled.


## Project concurrency correction — 19 October 2026

A generic “Maximum number of GPUs” field and the largest job size do not establish a project-wide limit. Independent jobs, hyperparameter sweeps, inference batches and data-parallel experiments can overlap. A hard capacity check needs either an explicit total-concurrent-GPU field (for example “Maximum total concurrent GPUs”) or both explicit maximum GPUs per job and maximum simultaneous jobs. The latter product is an upper bound, not promised utilization. Unknown concurrency produces an attention finding and a clarification comment, without automatic rejection or a claim that capacity is proven to fit. Workload sizing remains a separate assessment. Workplan question 4.5 and workload reference 1.1 reflect this distinction. Unapproved, unconfirmed workplan answers produced solely by the obsolete capacity override are recombined from their cached evidence checks; their old assessment is retained as provenance. Confirmed reviewer answers and finalized exports are preserved.

Prior-installation question 4.6 requires an explicit completed LUMI installation/test/execution claim. A proposed evaluation build, planned ROCm stack, local prototype, institutional system, documentation link or future compatibility test cannot establish prior LUMI use. Playground retains the independent corroboration check, just as Fast Lane does; unresolved corroboration cannot support an automatic positive answer. Installation NO remains a setup warning for Playground, which is intended to support initial testing.


## Continuations and self-employed businesses — 23 November 2026

Workplan question 4.6 treats a current model-training-to-convergence objective, benchmark evaluation and usable demonstrator as concrete technical work; a separate Workplan heading or detailed timetable is not mandatory. Prior executed allocations can provide a sizing baseline when the proposal explicitly connects the same code or architecture to the new work. They remain historical evidence: quantities do not automatically become new experiment counts, and an award alone is not completed testing. Prior-use question 4.7 and readiness question 1.2 reserve retrieval space for previous-allocation passages rather than allowing generic software text to crowd them out. Model reasoning must keep CUDA-predecessor performance distinct from AMD/LUMI measurements.

The organisation-category rule now covers an explicitly declared sole proprietor or self-employed business with source-backed VAT/tax-ID evidence in either supported access mode. This is the reviewer's declared eligibility handling, informed by the [EU enterprise definition](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32003H0361), which includes self-employed economic activity. The app does not independently validate registration, tax IDs or SME financial thresholds. A future startup or individual applicant alone is insufficient. Both category and tax-ID passages are retained as decision evidence; missing IDs and expired references prevent automatic matching.
