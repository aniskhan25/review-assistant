# Local technical review assistant

Review Fast Lane and Playground proposals for LUMI-G using a local Qwen model. Upload a PDF, review the findings, and approve the draft assessment.

## Set up once

Requires an **Apple Silicon Mac** and **Python 3.11+**. Setup downloads dependencies and model weights; the app runs locally afterward.

```sh
git clone https://github.com/aniskhan25/review-assistant.git
cd review-assistant
python3 -m venv models/decision-4b/.venv
models/decision-4b/.venv/bin/python -m pip install -r deploy/mlx-requirements.txt
models/decision-4b/.venv/bin/python tools/stage_mlx_model.py
models/decision-4b/.venv/bin/python -m pip install --no-deps -e .
```

## Start

```sh
models/decision-4b/.venv/bin/python -m app.local_mlx --reviewer your-reviewer-id --port 8766
```

Open **http://127.0.0.1:8766** and unlock with the key in `data/reviewer.key`. Upload your proposal, or try `evaluation/datasets/sample.pdf`. Outputs are shadow drafts requiring your final approval.

Stop with **Ctrl+C**. Use the same start command next time; saved reviews persist.

## Without a model

On any supported Python platform, run manual review:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m app.server --reviewer your-reviewer-id
```

Open **http://127.0.0.1:8765** and unlock with `data/reviewer.key`.

## Details

- [Review workflow, assessment rules and API](docs/review-guide.md)
- [Qwen setup and troubleshooting details](deploy/mlx-local.md)
- [Offline deployment](deploy/README.md) · [Evaluation and tests](evaluation/README.md)
