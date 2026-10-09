# Review rules derived from the supplied documents

This is an implementation interpretation of the supplied internal guide and `Default.md`, not a newly approved institutional rubric. The guide describes evolving rules of thumb and permits justified technical exceptions. The application remains in shadow mode. Source fingerprints are recorded in `app/config/policy.json`; private source documents and proposals are not copied into this repository.

## Supported scope and source mapping

Fast Lane and Playground applications targeting LUMI-G can produce shadow assessments. Science and Large Scale remain available for extraction and evidence inspection only. Playground uses reviewer-requested onboarding criteria: a named AMD-capable stack and a concrete trial or exploratory task, without detailed job budgets or measured scaling.

| Check | Implemented behaviour | Source |
|---|---|---|
| GPU accounting | GPU-hours and concurrency count full MI250X modules, each containing two GCDs; four modules per node | Guide p.2 |
| Resource consumption | Minimum months = GPU-hours / (concurrent GPUs × 24 × 30); exceeding duration suggests rejection. This assumes continuous maximum concurrency and does not guarantee scheduling | Guide p.2 |
| Parallelism | Above four GPUs, verify that execution can use multiple nodes. Independent concurrent jobs are accepted, consistent with the implementation plan; distributed training is not mandatory | Guide p.2 plus plan interpretation |
| AMD compatibility | Verify the core dependencies have a plausible AMD execution path | Guide pp.2,4 |
| Official builds | Verify official AMD/maintainer ROCm builds, or the exact environment already demonstrated on LUMI. A confirmed negative suggests rejection unless the reviewer records a plausible exception | Guide p.2 |
| Installation | Custom code not explicitly installed or available is NO, even if the framework exists. NO alone is a startup warning | Guide p.4 |
| Workplan | Review achievable goals, job budgets, parallelism, installation, transfer, preprocessing and startup time against resources and calendar duration | Guide pp.2,5 |
| Storage | Above 50,000 GB, warn about LUMI-O or a storage extension; no rejection solely for storage | Guide p.2 |
| Personal data | Flag CCR follow-up. Accepted assessments include the supplied Data Controller/DPA paragraph; the app sends no notification | Guide p.3; Default.md |
| Tax number | Distinguish missing/unreadable evidence from verified absence. Verified absence suggests rejection | Guide p.3 |
| Organisation | Manual verification: startup, SME or public sector; large enterprises require open research including publishing trained models. University/research/nonprofit categories are ineligible | Guide p.3 |
| Country | Mandatory manual verification against the applicable eligible-country list, with a reference or justification in the note. No static roster or model inference | Guide p.3 |
| Classification | Accepted, Rejected (not feasible), or Rejected (out of resources). Eligibility rejection must use not feasible | Guide p.3; Default.md |

Registry 4.3 follows the reviewer's explicit evidence-first policy: missing or insufficient positive technical evidence produces NO (not demonstrated) and a cited explanation. Clear negative answers and evidence-gap negatives are prefilled for one final approval, retaining raw model scores and the distinction between missing support and proven incompatibility. Model failures, unreadable pages, contradictory evidence and missing/conflicting required facts remain exceptions. Eligibility is never inferred by the model. Clear source-backed startup/SME/public-sector declarations and dated EU-country matches can be prefilled; unresolved categories and countries still require verification. Saved older registries keep their original gates.

Every final classification requires explicit approval, evidence and rationale. Acceptance despite remaining blocking findings requires an exception note. The audit records automatic prefills separately from individual confirmations.

Required facts are access mode, target, GPU-hours, maximum GPUs, duration, storage, personal-data declaration, tax number (including verified absence), organisation type and country. Previous LUMI use is optional because an omitted declaration must not be converted into an invented answer. Installation and startup feasibility remain mandatory decisions.

## Output and document precedence

The export uses the three questions from Default.md: architecture suitability, installation, and workplan feasibility. Scaling, official builds and eligibility remain internal checks with recorded evidence. Global comments, resource calculation, applicable storage wording, classification and rationale follow. Acceptance uses the supplied acceptance paragraph and adds the personal-data paragraph when declared. Rejections can include reviewer-selected amendment requests and always end with the Default.md closing.

Default.md and the guide use different rejection closing wording. The implementation uses Default.md as the output template and the guide for review criteria. This is an explicit implementation choice pending institutional validation. The standard wording describes external enrolment and DPA processes; the application does not execute those processes.

## Remaining validation

- Have a reviewer check these derived rules and representative completed drafts against the two documents, including justified exceptions and wording precedence.
- Use authorised historical reviewer-labelled decisions to measure field extraction, evidence retrieval and decision quality. The supplied proposal samples alone do not establish correct classifications.
- Verify current country eligibility through the reviewer’s authorised reference. The application remains offline and does not follow links from the guide.
- Stage and evaluate local model weights before choosing a model or claiming accuracy. Confidence settings remain provisional.
- Implement separate profiles before enabling Science or Large Scale assessment. The guide’s monthly 350,000/500,000 GPU-hour criteria for larger profiles have not been applied to Fast Lane.

Saved reviews retain their original policy and registry. Restart the service and upload a proposal again to review it under this profile. Existing confirmations are not silently migrated. Production approval, retention approval and deployment validation remain separate gates.
