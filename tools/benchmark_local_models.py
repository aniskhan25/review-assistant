"""Compare local model candidates with unchanged review rules and historical labels.

Run with the isolated benchmark Python. Private diagnostics stay outside Git.
Kev uses its pinned upstream encoder, MLX backbone and FP32 pointer head.
"""
import argparse
import ctypes
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import statistics
import sys
import threading
import time

from app.configuration import load_policy, load_config
from app.decision import ANSWERS, offline_environment
from app.historical_evaluation import benchmark
from app.security import install_network_guard


class MemorySampler:
    """Sample macOS physical footprint, including Metal, through proc_pid_rusage v2."""
    def __init__(self):
        self.lib = ctypes.CDLL("/usr/lib/libproc.dylib")
        self.lib.proc_pid_rusage.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
        self.lib.proc_pid_rusage.restype = ctypes.c_int
        self.peak = 0
        self.stopped = threading.Event()

    def sample(self):
        # sys/resource.h: UUID[16], seven uint64 fields, then ri_phys_footprint.
        buffer = ctypes.create_string_buffer(160)
        if self.lib.proc_pid_rusage(os.getpid(), 2, ctypes.byref(buffer)) != 0:
            raise OSError("proc_pid_rusage failed")
        footprint = ctypes.c_uint64.from_buffer(buffer, 16 + 7 * 8).value
        self.peak = max(self.peak, footprint)
        return footprint

    def start(self):
        self.sample()
        def poll():
            while not self.stopped.wait(.05):
                self.sample()
        self.thread = threading.Thread(target=poll, daemon=True)
        self.thread.start()

    def stop(self):
        self.stopped.set()
        self.thread.join()
        self.sample()


def kev_record(state, question):
    """Render the same binary option descriptions as the SystemOne adapter."""
    if question.get("binary_evidence"):
        keys = ["NO", "YES"]
        options = ["no: " + question["criteria"]["NO"], "yes: " + question["criteria"]["YES"]]
    else:
        keys = list(ANSWERS)
        options = [key + ": " + question["criteria"][key] for key in keys]
    return {"state": state, "questions": [{"instr": question["instructions"], "options": options, "label": 0}]}, keys


class KevBackend:
    def __init__(self, candidate, root):
        import mlx.core as mx
        import torch
        from mlx_lm.utils import load_model
        from safetensors.torch import load_file
        from transformers import AutoTokenizer
        from kev.mlx_model import MLXDecisionModel, load_base, merge_lora
        from kev.model import pad_id, PointerHead, SPECIAL

        self.name = candidate
        artifact = root / "model"
        self.version = json.loads((root / "artifact.json").read_text())["fingerprint"]
        if candidate == "kev-4b-8bit":
            meta = json.loads((artifact / "kev_config.json").read_text())
            if meta["format"] != "kev" or meta["format_version"] != 1:
                raise ValueError("Unsupported Kev package format")
            if list(meta["delimiters"].values()) != SPECIAL:
                raise ValueError("Kev delimiter mismatch")
            head = load_file(str(artifact / "kev_head.safetensors"))
            lm = load_model(artifact)[0]
        else:
            meta = torch.load(artifact / "head.pt", map_location="cpu", weights_only=True)
            base_root = root.parent / "kev-08b-base"
            base = json.loads((base_root / "artifact.json").read_text())
            if meta["base"] != base["repo"] or meta["base_revision"] != base["revision"]:
                raise ValueError("Base revision does not match checkpoint")
            self.version += ":" + base["fingerprint"]
            head = meta["head"]
            lm = load_base(base_root / "model")
            merge_lora(lm, artifact)
        self.tokenizer = AutoTokenizer.from_pretrained(str(artifact), local_files_only=True, trust_remote_code=False)
        self.model = MLXDecisionModel(lm, pad_id(self.tokenizer), head_dim=meta["head_dim"])
        # Quantized embeddings expose packed columns; infer head input width from
        # its full-precision checkpoint, not the packed embedding tensor shape.
        self.model.head = PointerHead(head["q.weight"].shape[1], dp=meta["head_dim"])
        self.model.head.load_state_dict(head, strict=True)
        self.model.head.temperature = float(meta["temperature"])
        self.model.eval()
        self.prefix_state = self.prefix = None
        mx.set_cache_limit(1 << 30)
        mx.eval(lm.parameters())

    def encode(self, state, question):
        record, keys = kev_record(state, question)
        encoded = self.model.encode(self.tokenizer, record, max_state=8192, max_branch=8192, strict=True)
        return encoded, keys

    def decide(self, state, question):
        encoded, keys = self.encode(state, question)
        if self.prefix_state == state:
            result = self.model.probs_with_prefix(encoded, self.prefix)
        else:
            self.prefix_state = self.prefix = None
            result, self.prefix = self.model.probs_and_prefix(encoded)
            self.prefix_state = state
        scores = dict(zip(keys, result[0].tolist()))
        scores.setdefault("UNKNOWN", 0.0)
        return scores


class RecordedBackend:
    def __init__(self, backend):
        self.backend = backend
        self.name, self.version = backend.name, backend.version
        self.calls = []

    def decide(self, state, question):
        start = time.perf_counter()
        scores = self.backend.decide(state, question)
        self.calls.append({"state": state, "question": question, "probabilities": scores,
                           "mode": "binary_evidence" if question.get("binary_evidence") else "choice",
                           "seconds": time.perf_counter() - start,
                           "input_sha256": hashlib.sha256(json.dumps([state, question], sort_keys=True).encode()).hexdigest()})
        return scores


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=["baseline", "kev-08b", "kev-4b-8bit"], required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--split", choices=["development", "heldout"], required=True)
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--source", type=Path, default=Path("models/kev-benchmark/source"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(".cases.jsonl").exists():
        parser.error("Choose a new output path")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.source.resolve()))
    install_network_guard()
    offline_environment()
    import mlx.core as mx
    mx.reset_peak_memory()
    sampler = MemorySampler()
    sampler.start()
    started = time.perf_counter()
    if args.candidate == "baseline":
        from app.mlx_backend import MLXBackend
        root = Path("models/decision-4b")
        backend = MLXBackend(root / "model", json.loads((root / "artifact.json").read_text())["fingerprint"])
        mx.eval(backend.model.parameters())
    else:
        backend = KevBackend(args.candidate, Path("models") / args.candidate)
    loading = {"seconds": time.perf_counter() - started, "mlx_peak_bytes": mx.get_peak_memory(),
               "sampled_physical_footprint_peak_bytes": sampler.peak}
    print("Loaded", args.candidate, "in", round(loading["seconds"], 2), "seconds", flush=True)
    mx.reset_peak_memory()
    sampler.peak = sampler.sample()
    wrapped = RecordedBackend(backend)
    records = [json.loads(line) for line in args.dataset.read_text().splitlines() if line.strip()]
    if args.ids:
        records = [r for r in records if r["application_id"] in args.ids]
        if set(args.ids) != {r["application_id"] for r in records}:
            raise ValueError("Requested application missing")
    def save_case(case):
        with args.output.with_suffix(".cases.jsonl").open("a") as stream:
            stream.write(json.dumps(case) + "\n")
        print(case["application_id"], case["elapsed_seconds"], "seconds", flush=True)
    result = benchmark(records, wrapped, load_policy(), args.split, save_case)
    # Replay exactly the first five observed requests twice. Distinguish cache
    # misses from repeated-state hits; baseline has no cross-call state cache.
    replay = []
    for call in wrapped.calls[:5]:
        if isinstance(backend, KevBackend):
            backend.prefix_state = backend.prefix = None
        timings, scores = [], []
        for _ in range(2):
            start = time.perf_counter()
            scores.append(backend.decide(call["state"], call["question"]))
            timings.append(time.perf_counter() - start)
        replay.append({"input_sha256": call["input_sha256"], "new_state_seconds": timings[0],
                       "repeated_state_seconds": timings[1], "probabilities": scores})
    sampler.stop()
    result.update(candidate=args.candidate, loading=loading,
                  inference_memory={"mlx_peak_bytes": mx.get_peak_memory(),
                      "sampled_physical_footprint_peak_bytes": sampler.peak, "sampling_interval_seconds": .05},
                  model_calls=len(wrapped.calls),
                  median_review_seconds=statistics.median(r["elapsed_seconds"] for r in result["cases"]),
                  registry_version=load_config("questions.json")["version"],
                  policy_sha256=hashlib.sha256(json.dumps(load_policy(), sort_keys=True).encode()).hexdigest(),
                  dataset_sha256=hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
                  kev_source_revision=(args.source / "revision.txt").read_text().strip(),
                  device=mx.device_info(),
                  runtime={p: importlib.metadata.version(p) for p in ["mlx", "mlx-lm", "transformers", "torch"]},
                  request_replays=replay,
                  requests=wrapped.calls)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ["candidate", "applications", "per_question", "median_review_seconds", "loading", "inference_memory", "model_calls"]}), flush=True)


if __name__ == "__main__":
    main()
