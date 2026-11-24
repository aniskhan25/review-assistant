# Aitta wording from a minimal assessment

The local Qwen backend still performs the evidence checks. Aitta is an optional online editor for generic assessment comments, global technical comments and the reason for classification. It receives fixed categorical findings and generic sentences composed locally, never proposal content. It cannot change the reviewed answers or classification, and every export still requires final approval.

## Start

With the local Aitta access token already saved in owner-only `data/aitta.token`:

```sh
models/decision-4b/.venv/bin/python -m app.local_mlx --reviewer your-reviewer-id --port 8766 --aitta-drafting
```

For manual review, add `--aitta-drafting` to the normal `app.server` command. The default drafting model is `Qwen/Qwen3.8-27B`; select another Aitta chat model with `--aitta-model vendor/model`.

An `AITTA_API_KEY` environment variable takes precedence over the token file. Keep credentials on the server, outside Git. Obtain a project-bound access token from [Aitta's token page](https://aitta-auth.csc.fi/myToken). Tokens can expire before 90 days if the associated project ends; see the [official guide](https://docs.lumi-supercomputer.eu/laif/inference/aitta/).

On a Mac, to save a token already copied to the clipboard without printing it:

```sh
mkdir -p data
chmod 700 data
umask 077
pbpaste > data/aitta.token
chmod 600 data/aitta.token
```

## Preview and revise wording

1. Resolve fact and decision exceptions and save those edits.
2. Under final assessment, optionally select generic **Scaling results** and **Execution pattern** categories. A supported scaling strategy does not automatically mean measured results are provided; the results category defaults to not assessed.
3. Select **Preview Aitta input**. This is a local operation: no request goes to Aitta. The preview shows the exact request body, including the static editing instructions and model settings.
4. Inspect the preview, then select **Send preview and generate**. Only that approved body is sent. Changing a category requires a fresh preview; stale review revisions and altered preview hashes are rejected.
5. Read and edit the three question comments, global comments and classification reason, then give the normal final approval.

The request contains only an allowlisted assessment: classification, access mode, compatibility, prior installation, workplan, scaling strategy/results, execution pattern, resource justification/capacity, eligibility, tax-identifier presence, initial validation and generic advisory outcomes. It never contains proposal excerpts, names, identifiers, tax-ID values, countries, project titles, software/model names, scientific ideas, datasets, exact figures, previous allocation details, evidence IDs or free-text reviewer notes. Existing draft/final text and manually edited comments are not forwarded. Generic review sentences are rebuilt from a fixed local catalogue; they are not obtained by trying to redact private text.

This is limited sharing rather than offline operation: Aitta receives the chosen assessment categories and uses your access token for authentication. Standard local wording remains available when no external request is desired. Reviews with identical categories send identical bodies regardless of their private content; the wording can vary at the assessment level, without describing or distinguishing their scientific ideas.

Aitta returns text linked to generic assessment fields. Internal proposal citations are attached locally afterward. New numeric details, identifiers, URLs and unsupported assessment references are rejected. These checks do not prove every sentence is accurate: review the wording and any warnings before approval. The saved record retains the privacy mode, model, prompt version, approved-body fingerprint and local provenance.

Changing evidence, facts or reviewed answers makes the draft out of date. Regenerate it, or select **Return to standard wording**. Old excerpt-based Aitta drafts require regeneration; existing finalized exports are preserved. No automatic generation or resend occurs. Failed requests preserve the saved review and unsaved editor text.

Aitta availability depends on model loading and LUMI scheduling, and a draft can take several minutes. A request may time out while the model starts; retry later. The app does not automatically retry or switch models.

## Network behavior

Without `--aitta-drafting`, the app retains its local-only workflow. Only the explicit send action uses verified HTTPS to `aitta-api.csc.fi` and bypasses no other outbound restrictions. There are no proxies, redirects or arbitrary provider URLs. If workstation/VM firewall policy blocks all outbound traffic, allow that Aitta destination for drafting or continue using the local templates.

## Verification

```sh
python -m pytest tests/test_aitta.py -q
node --test tests/frontend.test.cjs
```

Tests cover canary data exclusion, identical requests for equivalent assessments, fixed-category validation, exact-request previews, stale drafts, edited exports, credentials, network isolation and explicit send authorization. Live smoke tests send generic synthetic assessments only.
