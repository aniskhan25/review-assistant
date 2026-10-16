# Technical checks behind the submission form

Registry 4.5 preserves three submission answers: software suitability, prior installation and workplan feasibility. Fast Lane uses nine supporting evidence checks plus separate scaling/build questions and a prior-use consistency check. Source-backed literal claims can bypass model calls. Playground uses simpler onboarding criteria and omits separate scaling/build verification and the material compatibility blocker.

| Submission answer | Evidence and combination |
|---|---|
| Software suitability | Named dependencies and a plausible AMD path support YES. An explicit CUDA-only requirement or material unsupported dependency can yield NO. Planned porting with named AMD alternatives is distinct from an unsupported dependency; unresolved compatibility remains an exception. |
| Prior installation | Prior LUMI execution of the workflow or equivalent environment supports YES. Pending first installation or no demonstrated prior use supports NO, which is a setup warning. Conflicting prior-use interpretations remain unresolved. |
| Workplan feasibility | Fast Lane checks concrete goals, meaningful workload sizing and a credible execution plan. Playground requires a concrete onboarding trial. Impossible capacity can yield NO using cited resource facts independently of model confidence. |

Jevos and MLX score binary evidence questions with YES/NO options; the AMD-path check uses three options and cited generic framework references. These references do not verify application versions or installation. Raw option scores are uncalibrated. Combined confidence is the minimum supporting confidence, not a probability that the complete review is correct.

Retrieval restricts technical checks to relevant proposal sections. Previous-allocation evidence is permitted for prior-use checks; historical reviewer answers never enter inference. Proposal text and extracted facts remain untrusted evidence.

An empty required evidence search can produce a cited NO (not demonstrated). Classifier uncertainty is not treated as absent evidence: modest positive scores stay positive but require review. Model failures, conflicting interpretations, unresolved extraction, accounting assumptions and missing required facts remain exceptions. Clear negative technical answers can be prefilled for the single final approval; prior installation NO alone does not reject a proposal.

Organisation and country eligibility use source-backed rules or reviewer verification, never model guesses. Playground's dated organisation reference permits SMEs/startups and identifies academic/public-sector applicants for the AI for Science route. The country reference covers EU members and Norway; uncovered countries, expired references and conflicts require verification. See [review rubric](review-rubric.md).

The interface exposes individual check results, evidence and combination reasons. Reviews snapshot their registry, including legacy aggregation behavior; rerunning suggestions does not migrate it. Reupload for current extraction and criteria.

## Validation

Run `python -m pytest -q` for extraction, aggregation and workflow regressions. The [evaluation guide](../evaluation/README.md) documents synthetic checks, private historical evaluation and model comparisons. `evaluation/datasets/narrow-checks.jsonl` contains synthetic proposed labels originating with registry 4.2; it is not a held-out quality benchmark. Dated development reports record the policy used and must not be read as validation of later registries.
