"""Launch the verified, already staged Apple Silicon decision backend offline."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def model_fingerprint(root):
    root = Path(root).resolve(strict=True)
    manifest = json.loads((root / "artifact.json").read_text())
    files = manifest["files"]
    if not files or not {"config.json", "model.safetensors", "tokenizer.json", "chat_template.jinja"} <= files.keys():
        raise ValueError("Incomplete model manifest")
    model = (root / "model").resolve(strict=True)
    for name, expected in files.items():
        path = (model / name).resolve(strict=True)
        if not path.is_relative_to(model) or not path.is_file():
            raise ValueError("Invalid model manifest path")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != expected["sha256"] or path.stat().st_size != expected["bytes"]:
            raise ValueError("Model artifact differs from its staged manifest")
    fingerprint = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    if fingerprint != manifest["fingerprint"]:
        raise ValueError("Model manifest fingerprint mismatch")
    return fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--runtime-dir", type=Path, default=Path("models/decision-4b"))
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    try:
        version = model_fingerprint(args.runtime_dir)
    except (OSError, ValueError, KeyError):
        parser.error("Stage and verify the local model first; startup never downloads it.")
    command = [sys.executable, "-m", "app.server", "--reviewer", args.reviewer,
               "--backend", "mlx", "--model-path", str((args.runtime_dir / "model").resolve()),
               "--model-version", version, "--data-dir", args.data_dir, "--port", str(args.port)]
    try:
        raise SystemExit(subprocess.call(command))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
