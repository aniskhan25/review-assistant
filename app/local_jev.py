"""Start the staged Jevos model and review app together, without downloads."""

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time


def model_fingerprint(model_dir):
    names = ("model.json", "openvino_model.bin", "openvino_model.xml", "tokenizer.gguf")
    lines = []
    for name in names:
        with (model_dir / name).open("rb") as stream:
            lines.append(f"{hashlib.file_digest(stream, 'sha256').hexdigest()}  {name}\n")
    return hashlib.sha256("".join(lines).encode()).hexdigest()


def wait_ready(process, port, expected_fingerprint, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Jevos stopped before becoming ready")
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            connection.request("GET", "/health")
            response = connection.getresponse()
            if response.status == 200:
                health = json.loads(response.read(100_001))
                if health.get("fingerprint") != expected_fingerprint:
                    raise RuntimeError("Model fingerprint differs from the staged files")
                if health.get("status") == "ready":
                    return health
        except (OSError, http.client.HTTPException):
            pass
        finally:
            connection.close()
        time.sleep(.5)
    raise RuntimeError("Jevos did not become ready within two minutes")


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--runtime-dir", type=Path, default=Path("models/jevos-v4/jev"))
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model-port", type=int, default=8017)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    runtime = args.runtime_dir.resolve()
    if args.port == args.model_port or not all(0 < port < 65536 for port in (args.port, args.model_port)) or args.threads < 1:
        parser.error("Choose distinct valid ports and at least one thread")
    if not (runtime / "jev").is_file():
        parser.error("Jevos is not staged. See deploy/jev-local.md; no model is downloaded at startup.")
    for port in (args.port, args.model_port):
        try:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", port))
        except OSError:
            parser.error(f"Local port {port} is occupied; stop that service or choose another port.")
    fingerprint = model_fingerprint(runtime / "model")
    environment = dict(os.environ, JEV_API_KEY=secrets.token_urlsafe(32))
    model = app = None
    try:
        model = subprocess.Popen([str(runtime / "jev"), "serve", "--model-dir", str(runtime / "model"),
                                  "--host", "127.0.0.1", "--port", str(args.model_port),
                                  "--threads", str(args.threads), "--state-cache", "0", "--warmup", "0"],
                                 env=environment)
        health = wait_ready(model, args.model_port, fingerprint)
        print(f"Local model ready: {health['model']} · SHA-256 {fingerprint}", flush=True)
        app = subprocess.Popen([sys.executable, "-m", "app.server", "--reviewer", args.reviewer,
                                "--backend", "jevos", "--endpoint", f"http://127.0.0.1:{args.model_port}/v1/systemone",
                                "--model-version", fingerprint, "--port", str(args.port), "--data-dir", args.data_dir],
                               env=environment)
        while app.poll() is None:
            if model.poll() is not None:
                raise RuntimeError("Jevos stopped; stopping the review app")
            time.sleep(.5)
        if app.returncode:
            raise RuntimeError("The review app stopped with an error")
    except KeyboardInterrupt:
        pass
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Local Jev startup failed: {error}", file=sys.stderr)
        raise SystemExit(1)
    finally:
        stop(app)
        stop(model)


if __name__ == "__main__":
    main()
