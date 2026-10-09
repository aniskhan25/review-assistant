import hashlib
import json

import pytest

from app.local_mlx import model_fingerprint


def stage(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    files = {}
    for name in ("config.json", "model.safetensors", "tokenizer.json", "chat_template.jinja"):
        (model / name).write_bytes(b"fixture")
        files[name] = {"sha256": hashlib.sha256(b"fixture").hexdigest(), "bytes": 7}
    fingerprint = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    manifest = {"files": files, "fingerprint": fingerprint}
    (tmp_path / "artifact.json").write_text(json.dumps(manifest))
    return manifest


def test_verified_artifact_and_modified_weights(tmp_path):
    manifest = stage(tmp_path)
    assert model_fingerprint(tmp_path) == manifest['fingerprint']
    (tmp_path / 'model/model.safetensors').write_bytes(b'altered')
    with pytest.raises(ValueError, match='differs'):
        model_fingerprint(tmp_path)


def test_manifest_cannot_reference_outside_model(tmp_path):
    manifest = stage(tmp_path)
    (tmp_path / 'outside').write_bytes(b'fixture')
    manifest['files']['../outside'] = manifest['files']['config.json']
    (tmp_path / 'artifact.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='manifest path'):
        model_fingerprint(tmp_path)
