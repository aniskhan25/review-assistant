# Local Apple Silicon option scorer

This adapter uses Qwen3-4B-Instruct-2507 in MLX 4-bit format. It uses Jev-style
single-token A/B/C option scoring; it is **not Jevos, proprietary Jev, or the
fine-tuned OpenJev decision-head model**. It generates no review prose and exposes
raw uncalibrated option scores. Binary evidence checks score YES/NO; UNKNOWN
remains a confidence/margin abstention. Choice checks also score UNKNOWN explicitly.
Numeric thresholds are unchanged. Registry 4.4 filters empty form headings and confines technical retrieval to relevant sections. Named supported frameworks, literal workload quantities and repeated version deferrals can be resolved from cited source claims. A modest positive score stays positive but requires review; classifier uncertainty is not converted into missing evidence. A genuinely empty required evidence search can yield NO. MFU/GCD accounting assumptions and conflicting prior-use interpretations remain exceptions. Source-backed scores indicate a rule match, not calibrated model accuracy.

The public artifact is [mlx-community/Qwen3-4B-Instruct-2507-4bit](https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit),
pinned to `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b`, Apache-2.0.
The runtime is [MLX-LM](https://github.com/ml-explore/mlx-lm). Weight downloads
are separate from application startup and contain no proposal data.

## Prepare once

On this Mac, the isolated environment and verified artifact are already under
ignored `models/decision-4b/`. To reproduce staging on a suitable Apple Silicon Mac:

```sh
python3 -m venv models/decision-4b/.venv
models/decision-4b/.venv/bin/python -m pip install -r deploy/mlx-requirements.txt
HF_HUB_DISABLE_XET=1 models/decision-4b/.venv/bin/python tools/stage_mlx_model.py
models/decision-4b/.venv/bin/python -m pip install --no-deps -e .
```

The explicit staging script downloads only weights, tokenizer/configuration data
and notices from the pinned revision, verifies weight SHA-256 against Hub metadata,
and writes a full local manifest. TLS uses the certifi certificate bundle; verification
is never disabled. The runtime does not execute model-supplied Python code.

## Start offline

Stop the previous service on the same port, then:

```sh
models/decision-4b/.venv/bin/python -m app.local_mlx --reviewer anisrahm --port 8766
```

The launcher hashes every manifest file again before starting. It records the
artifact fingerprint in review provenance. The app loads only an existing local
directory, disables Hub downloads/telemetry, and blocks external Python networking.
It retains loopback authentication and serializes inference. It refuses contexts
above 8,192 tokens rather than dropping evidence. Native-library egress isolation
remains an OS deployment responsibility, as with the other local backends.

Saved reviews retain their original registry; upload again for current extraction,
or re-run suggestions to use the selected model with the saved review's criteria.
Re-running clears previous model-answer confirmations. Clear high-confidence installation
NO answers can be prefilled as setup warnings; clear negative technical answers can also be prefilled. Uncertain answers require
review. Clear organisation categories and EU-member countries can be prefilled from source-backed rules; uncertain and uncovered eligibility conditions remain manual. Final approval remains explicit.
