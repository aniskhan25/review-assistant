"""Adapter bounds and offline loading, without requiring MLX or downloaded weights."""
import sys
import types

import pytest

from app.decision import build_backend


class Tokenizer:
    def encode(self, letter, **kwargs):
        return [ord(letter)]

    def apply_chat_template(self, messages, **kwargs):
        return list(range(8193))


def fake_runtime(monkeypatch, tokenizer=None):
    calls = []
    def load(path, **kwargs):
        calls.append((path, kwargs))
        return lambda x: pytest.fail("Oversized evidence reached the model"), tokenizer or Tokenizer()
    monkeypatch.setitem(sys.modules, "mlx", types.ModuleType("mlx"))
    monkeypatch.setitem(sys.modules, "mlx.core", types.ModuleType("mlx.core"))
    monkeypatch.setitem(sys.modules, "mlx_lm", types.SimpleNamespace(load=load))
    monkeypatch.setitem(sys.modules, "mlx_lm.models", types.ModuleType("mlx_lm.models"))
    monkeypatch.setitem(sys.modules, "mlx_lm.models.cache", types.SimpleNamespace(make_prompt_cache=lambda model: []))
    return calls


def test_load_is_local_and_context_is_not_truncated(tmp_path, monkeypatch):
    calls = fake_runtime(monkeypatch)
    backend = build_backend("mlx", model_path=tmp_path, version="test-artifact")
    assert calls == [(str(tmp_path), {"tokenizer_config": {"local_files_only": True, "trust_remote_code": False},
                                      "trust_remote_code": False})]
    assert __import__('os').environ['HF_HUB_OFFLINE'] == '1'
    question = {"instructions": "Check the evidence", "criteria": dict.fromkeys(("YES", "NO", "UNKNOWN"), "criteria")}
    with pytest.raises(ValueError, match="no silent truncation"):
        backend.decide("untrusted evidence", question)


def test_labels_must_be_single_distinct_tokens(tmp_path, monkeypatch):
    tokenizer = Tokenizer()
    tokenizer.encode = lambda *args, **kwargs: [1, 2]
    fake_runtime(monkeypatch, tokenizer)
    with pytest.raises(ValueError, match="single-token"):
        build_backend("mlx", model_path=tmp_path, version="test-artifact")


def test_missing_artifact_is_not_a_download(tmp_path, monkeypatch):
    calls = fake_runtime(monkeypatch)
    with pytest.raises(FileNotFoundError):
        build_backend("mlx", model_path=tmp_path / "missing", version="test-artifact")
    assert not calls


def test_binary_score_preserves_policy_abstention(tmp_path, monkeypatch):
    from app.decision import decide
    from app.configuration import load_policy
    calls = fake_runtime(monkeypatch)
    backend = build_backend('mlx', model_path=tmp_path, version='test-artifact')
    prompts = []
    backend.tokenizer.apply_chat_template = lambda messages, **kw: prompts.append(messages) or [1, 2, 3]

    class Array:
        def __getitem__(self, key):
            return self
        def astype(self, dtype):
            return self
        def tolist(self):
            return [.55, .45]

    backend.mx = types.SimpleNamespace(array=lambda x: x, float32='float32',
                                      eval=lambda x: None, clear_cache=lambda: None,
                                      softmax=lambda x: Array())
    backend.model = lambda tokens, **kw: Array()
    q = {'version': 'test', 'instructions': 'Is prior use documented?', 'binary_evidence': True,
         'criteria': {'YES': 'Prior use reported', 'NO': 'Not reported', 'UNKNOWN': 'Conflicting'}}
    result = decide(backend, 'prior', q, [{'id': 'ev', 'page': 1, 'section': 'Code', 'text': 'Example'}], load_policy())
    assert result['probabilities'] == {'YES': .55, 'NO': .45, 'UNKNOWN': 0}
    assert result['answer'] == 'UNKNOWN'
    assert result['status'] == 'LOW_CONFIDENCE'
    assert result['inference_mode'] == 'binary_evidence'
    assert 'C: UNKNOWN' not in prompts[0][1]['content']
