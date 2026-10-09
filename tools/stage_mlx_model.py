"""Explicit model staging, separate from the offline app; sends no private data."""
import hashlib
import json
import os
from pathlib import Path
import ssl
import urllib.request

import certifi

REPO = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
REVISION = "50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b"


def main():
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    from huggingface_hub import snapshot_download
    root = Path("models/decision-4b")
    root.mkdir(parents=True, exist_ok=True)
    url = f"https://huggingface.co/api/models/{REPO}/revision/{REVISION}?blobs=true"
    with urllib.request.urlopen(url, timeout=30,
                                context=ssl.create_default_context(cafile=certifi.where())) as response:
        metadata = json.load(response)
    if metadata["sha"] != REVISION:
        raise ValueError("Pinned revision mismatch")
    path = Path(snapshot_download(
        repo_id=REPO, revision=REVISION, local_dir=root / "model", cache_dir=root / "cache",
        allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model", "*.jinja", "README.md", "LICENSE"],
        max_workers=2))
    files = {}
    for item in metadata["siblings"]:
        name = item["rfilename"]
        artifact = path / name
        if not artifact.is_file():
            continue
        with artifact.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if item.get("lfs") and digest != item["lfs"]["sha256"]:
            raise ValueError("Downloaded model hash mismatch: " + name)
        files[name] = {"sha256": digest, "bytes": artifact.stat().st_size}
    fingerprint = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    manifest = {"repo": REPO, "revision": REVISION, "files": files,
                "fingerprint": fingerprint, "license": "apache-2.0"}
    (root / "artifact.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Verified local model:", fingerprint, flush=True)


if __name__ == "__main__":
    main()
