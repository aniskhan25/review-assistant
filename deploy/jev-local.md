# Local Jevos on Apple Silicon

Jevos-v4 is an optional CPU backend, separate from the working Qwen/MLX setup. It runs locally after staging and scores bounded technical questions; extraction, resource arithmetic, source-backed eligibility and assessment composition remain deterministic. Current profiles, readiness rules and verification limits are described in the [root README](../README.md).

## Start

From the project root, using Python 3.11 or later with the project dependencies installed:

```sh
python3 -m app.local_jev --reviewer your-reviewer-id --port 8766 --model-port 8018
```

Open `http://127.0.0.1:8766` and unlock with `data/reviewer.key`. Stop any app already using port 8766 before launching this alternative. The defaults are 8765 for the app and 8017 for the model if both ports are free. The launcher refuses occupied ports rather than stopping an existing service.

Keep the launch terminal open. Ctrl-C stops both children. The launcher waits for model readiness, compares the model server's fingerprint with the local files, creates an ephemeral authentication key for the model service, and disables model state caching. If the model dies, it stops the app. An explicitly requested backend that cannot initialize no longer silently switches to manual mode. Request-time inference errors remain visible as MODEL_ERROR/UNKNOWN.

The launcher performs no downloads. It uses four CPU threads by default (`--threads` changes this). Native runtime isolation is still a deployment responsibility; the review app's Python network guard is not an OS sandbox for Jevos.

## Staged artifacts

The following public upstream release assets were downloaded into the ignored `models/jevos-v4/downloads/` directory and verified against the GitHub release asset SHA-256 digests:

| Asset | SHA-256 |
|---|---|
| `jev-macos-arm64.tar.gz` | `741dae47575de66568ba5f53693f5a183dd5694f937ee901f9bcb539a868fcfc` |
| `jevos-v4-openvino-int8.zip` | `b86c2b55aa97d4f89af5660251a1c943ff9ed52712568bfb4ad44fa734aaeb8c` |

Source: [feder-cr/jev release jevos-v4](https://github.com/feder-cr/jev/releases/tag/jevos-v4). The runtime archive is extracted under `models/jevos-v4/`; the model archive is extracted under `models/jevos-v4/jev/`, creating its `model/` subdirectory. No installation outside the project is needed. The release manifest is stored beside the runtime. Weights and runtime binaries are not committed to Git.

Runtime licenses and third-party notices ship inside the extracted `jev/` folder. Source and runtime notices were inspected; this is not an institutional dependency/license approval.

The model-file fingerprint, calculated using upstream's sorted file convention, is:

```text
6afd085ed8676530c4e4f0dfd0e532b5903f6445742979b342c30ea3b3b2af53
```

Each review records this fingerprint. To stage another installation, download the two pinned assets from the linked release, verify the digests above, and preserve the same extraction layout. Re-evaluate changed model artifacts rather than substituting them silently.

## Verification and limits

Real inference has been exercised on this Mac, not just against protocol fixtures. The HTTP adapter includes Jevos's mandatory `model: jev-latest` field. Registry 3.0 uses the [narrow-check workflow](../docs/narrow-review-checks.md); low confidence remains UNKNOWN. The following measurements describe the earlier five-call profile. The initial synthetic smoke review returned usable installation and scaling answers while abstaining on the other three technical questions. The synthetic PDF took 20.6 seconds end to end. A supplied Fast Lane PDF took 54.7 seconds and completed all five model calls without errors: scaling returned YES and four technical answers remained UNKNOWN. Its review is saved locally; private smoke results are in the ignored `evaluation/private/jevos-local-smoke.json`. These results show substantial abstention, so further domain evaluation is needed for useful automation coverage. This is operational verification, not an accuracy benchmark.

Use the authenticated app on 8766 for model-assisted reviews. Existing saved manual reviews need **Re-run suggestions** (which clears prior decision confirmations), or upload again for fresh extraction and policy. The model does not generate prose or chain-of-thought; it returns option probabilities. Evidence passages and the source-guided rules support review of its recommendations.

The old synthetic evaluation corpus covers four questions under earlier workplan criteria. It needs new reviewer-checked labels, including official-build availability, before it can establish the quality of this seven-question profile. No accuracy claim or production qualification follows from a successful upload. Keep shadow mode enabled while validating representative reviewer-labelled cases.
