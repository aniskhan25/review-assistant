import hashlib
from types import SimpleNamespace

import pytest

from app.local_jev import model_fingerprint, wait_ready


def test_fingerprint_matches_jevos_file_order(tmp_path):
    names = ("model.json", "openvino_model.bin", "openvino_model.xml", "tokenizer.gguf")
    for name in names:
        (tmp_path / name).write_bytes(name.encode())
    expected = hashlib.sha256("".join(f"{hashlib.sha256(name.encode()).hexdigest()}  {name}\n" for name in names).encode()).hexdigest()
    assert model_fingerprint(tmp_path) == expected
    (tmp_path / "openvino_model.bin").write_bytes(b"changed weights")
    assert model_fingerprint(tmp_path) != expected


def test_wait_ready_detects_crashed_process():
    with pytest.raises(RuntimeError, match="stopped"):
        wait_ready(SimpleNamespace(poll=lambda: 1), 1, "expected")


def test_wait_ready_rejects_wrong_model(monkeypatch):
    class Connection:
        def __init__(self, *args, **kwargs): pass
        def request(self, *args): pass
        def getresponse(self):
            return SimpleNamespace(status=200, read=lambda limit: b'{"status":"ready","fingerprint":"wrong"}')
        def close(self): pass
    monkeypatch.setattr("app.local_jev.http.client.HTTPConnection", Connection)
    with pytest.raises(RuntimeError, match="fingerprint"):
        wait_ready(SimpleNamespace(poll=lambda: None), 8017, "expected")


def test_failed_explicit_backend_does_not_fall_back(monkeypatch, tmp_path):
    from app import server
    monkeypatch.setattr("sys.argv", ["review-assistant", "--reviewer", "test", "--data-dir", str(tmp_path), "--backend", "jevos"])
    monkeypatch.setattr(server, "install_network_guard", lambda: None)
    with pytest.raises(SystemExit) as error:
        server.main()
    assert error.value.code == 2
