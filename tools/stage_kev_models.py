"""Download pinned public Kev artifacts; never reads proposal data."""
import hashlib
import json
import os
from pathlib import Path
import ssl
import urllib.request

import certifi
from huggingface_hub import snapshot_download

ARTIFACTS = {
    "kev-4b-8bit": ("aselea/Kev-4B-MLX-Serve-8bit", "2fd4aab21005e4e88e065b964a03e9bf69195bfd"),
    "kev-08b": ("jaredpalmer/kev-0.8b", "bf75a6a8848ea6960ff2ed108d9ed44c2941174f"),
    "kev-08b-base": ("Qwen/Qwen3.5-0.8B-Base", "dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68"),
}
SOURCE_REVISION = "5e42a7a03f28134853dd3ff77461457e921e5ec1"
SOURCE_FILES = {
    "kev/model.py": "2ff3b2e67c048e3bc5a0d1a32aafe50804ed315a5564fce06bb4b95697c5271c",
    "kev/mlx_model.py": "49c4a3de3952429e8a4b3945c33b0697a1cd84c41c945709ce6619af2c15842c",
    "kev/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "LICENSE": "6b08bb37982c233aa12bcbdf19106da12f3f4fcf800773ea42e28ebeddd34fb8",
}


def main():
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    source = Path("models/kev-benchmark/source")
    for name, expected in SOURCE_FILES.items():
        url = f"https://raw.githubusercontent.com/jaredpalmer/kev/{SOURCE_REVISION}/{name}"
        with urllib.request.urlopen(url, context=ssl.create_default_context(cafile=certifi.where()), timeout=60) as response:
            content = response.read()
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("Source hash mismatch: " + name)
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    (source / "revision.txt").write_text(SOURCE_REVISION + "\n")
    for name, (repo, revision) in ARTIFACTS.items():
        root = Path("models") / name
        url = f"https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true"
        with urllib.request.urlopen(url, context=ssl.create_default_context(cafile=certifi.where()), timeout=60) as response:
            metadata = json.load(response)
        if metadata["sha"] != revision:
            raise ValueError("Revision mismatch")
        path = Path(snapshot_download(repo, revision=revision, local_dir=root / "model",
                    allow_patterns=["*.json", "*.safetensors", "head.pt", "*.txt", "*.jinja", "README.md", "LICENSE"],
                    max_workers=2))
        files = {}
        for item in metadata["siblings"]:
            artifact = path / item["rfilename"]
            if not artifact.is_file():
                continue
            with artifact.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if item.get("lfs") and digest != item["lfs"]["sha256"]:
                raise ValueError("Hash mismatch: " + item["rfilename"])
            files[item["rfilename"]] = {"sha256": digest, "bytes": artifact.stat().st_size}
        manifest = {"repo": repo, "revision": revision, "files": files,
                    "fingerprint": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}
        (root / "artifact.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(name, manifest["fingerprint"], flush=True)


if __name__ == "__main__":
    main()
