import argparse
import hmac
import json
import os
import secrets
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from app.configuration import load_policy, load_config
from app.decision import build_backend, decide
from app.ingestion import ingest_pdf, MAX_BYTES
from app.review import (prepare_review, new_review, analyze, confirm_decision, confirm_fact, add_evidence,
                        finalize, refresh, text_input)
from app.security import install_network_guard
from app.storage import Store, ConflictError

STATIC = Path(__file__).parent / "static"


def create_server(store, backend, policy, token, reviewer, port=8765):
    request_lock = threading.Lock()

    class ReviewServer(ThreadingHTTPServer):
        last_purge = 0

        def service_actions(self):
            if time.monotonic() - self.last_purge >= 3600:
                store.purge(policy["review_retention_days"], policy["audit_retention_days"])
                self.last_purge = time.monotonic()

    class Handler(BaseHTTPRequestHandler):
        # Access logs otherwise include review identifiers and arbitrary request strings.
        def log_message(self, format, *args):
            pass

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def send(self, status, data, content_type="application/json"):
            body = json.dumps(data, allow_nan=False).encode() if content_type == "application/json" else data
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def check_access(self):
            expected_host = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != expected_host:
                self.send(403, {"error": "Use the literal loopback URL"})
                return False
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + expected_host:
                self.send(403, {"error": "Cross-origin access denied"})
                return False
            if self.path in {"/", "/app.js", "/style.css"} and self.command == "GET":
                return True
            authorization = self.headers.get("Authorization", "")
            if not hmac.compare_digest(authorization.encode(), ("Bearer " + token).encode()):
                self.send(401, {"error": "Reviewer access key required"})
                return False
            return True

        def dispatch(self):
            if not self.check_access():
                return
            try:
                # Idle browser preconnections must not block real requests. Model and
                # review work remain serialized after an HTTP request has arrived.
                with request_lock:
                    store.purge(policy["review_retention_days"], policy["audit_retention_days"])
                    self.route()
            except ConflictError as exc:
                self.send(409, {"error": str(exc)})
            except KeyError:
                self.send(404, {"error": "Record or required field not found"})
            except (ValueError, TypeError) as exc:
                # Only application validation messages reach here; provider errors are suppressed.
                self.send(400, {"error": str(exc) if isinstance(exc, ValueError) else "Invalid request type"})
            except Exception:
                self.send(500, {"error": "Operation failed locally; no proposal content was logged"})

        do_GET = dispatch
        do_POST = dispatch
        do_DELETE = dispatch

        def read_body(self, maximum):
            if self.headers.get("Transfer-Encoding"):
                raise ValueError("Chunked uploads are not supported")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= maximum:
                raise ValueError("Request body is missing or too large")
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("Incomplete request")
            return body

        def route(self):
            path = urlsplit(self.path).path
            if self.command == "GET" and path in {"/", "/app.js", "/style.css"}:
                name, kind = {"/": ("index.html", "text/html; charset=utf-8"),
                              "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                              "/style.css": ("style.css", "text/css; charset=utf-8")}[path]
                return self.send(200, (STATIC / name).read_bytes(), kind)
            if self.command == "GET" and path == "/api/config":
                return self.send(200, {"policy": policy, "backend": backend.name, "reviewer": reviewer,
                                      "questions": load_config("questions.json")})
            if self.command == "GET" and path == "/api/reviews":
                return self.send(200, store.list(reviewer))
            if self.command == "POST" and path == "/api/reviews":
                if self.headers.get("Content-Type") != "application/pdf":
                    raise ValueError("Upload a PDF")
                state = new_review(ingest_pdf(self.read_body(MAX_BYTES)), backend, policy, reviewer)
                store.insert(state)
                return self.send(201, state)
            if self.command == "POST" and path == "/v1/decide":
                payload = json.loads(self.read_body(50_000))
                qid = payload["question_id"]
                question = load_config("questions.json")["questions"][qid]
                if "question" in payload and any(payload["question"].get(key) != question[key]
                                                 for key in ("type", "options", "instructions", "criteria")):
                    raise ValueError("Question must match the versioned registry")
                text = text_input(payload["state"], "evidence state", 20_000)
                evidence = [{"id": "request-evidence", "page": None, "section": "API evidence", "text": text}] if text else []
                return self.send(200, decide(backend, qid, question, evidence, policy))
            parts = path.strip("/").split("/")
            if len(parts) not in {3, 4} or parts[:2] != ["api", "reviews"]:
                return self.send(404, {"error": "Unknown route"})
            review_id = parts[2]
            state = store.get(review_id)
            prepare_review(state)
            if state["reviewer"] != reviewer:
                return self.send(403, {"error": "Review belongs to another reviewer"})
            action = parts[3] if len(parts) == 4 else ""
            if self.command == "GET":
                if not action:
                    return self.send(200, state)
                if action == "audit":
                    return self.send(200, store.audit(review_id))
                if action == "export":
                    if not state["final"]:
                        raise ValueError("Finalize the current revision before export")
                    return self.send(200, state["final"]["text"].encode(), "text/plain; charset=utf-8")
            if self.command == "DELETE" and not action:
                store.delete(review_id)
                return self.send(200, {"deleted": True})
            if self.command != "POST":
                return self.send(404, {"error": "Unknown action"})
            payload = json.loads(self.read_body(50_000))
            revision = payload["revision"]
            if type(revision) is not int or revision != state["revision"]:
                raise ConflictError("Review changed; reload before saving")
            if action == "decision":
                confirm_decision(state, payload["question_id"], payload["answer"], payload["evidence_ids"], payload.get("note", ""))
            elif action == "fact":
                confirm_fact(state, payload["field"], payload.get("value", ""), payload["status"], payload["evidence_ids"], payload.get("note", ""))
            elif action == "evidence":
                add_evidence(state, payload["page"], payload["text"], payload["note"])
            elif action == "resolve-extraction":
                note = text_input(payload["note"], "extraction resolution")
                if not note:
                    raise ValueError("Describe how all extraction failures were checked")
                state["extraction_resolved"] = True
                state["extraction_resolution"] = note
                refresh(state)
            elif action == "analyze":
                analyze(state, backend)
            elif action == "finalize":
                finalize(state, payload["classification"], payload["rationale"], payload.get("acknowledge_findings"),
                         payload.get("rejection_category", "NOT_FEASIBLE"), payload.get("global_comment", ""),
                         payload.get("rejection_details"), payload.get("exception_note", ""))
            else:
                return self.send(404, {"error": "Unknown action"})
            store.save(state, revision, action)
            return self.send(200, state)

    return ReviewServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description="Local technical review assistant")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--reviewer", required=True, help="Reviewer identity; use a dedicated OS account/data directory")
    parser.add_argument("--policy")
    parser.add_argument("--backend", choices=["manual", "jevos", "systemone", "openjev", "masked", "mlx"], default="manual")
    parser.add_argument("--endpoint")
    parser.add_argument("--model-path")
    parser.add_argument("--model-version")
    parser.add_argument("--purge-only", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    install_network_guard()
    policy = load_policy(args.policy)
    store = Store(args.data_dir)
    store.purge(policy["review_retention_days"], policy["audit_retention_days"])
    if args.purge_only:
        return
    try:
        backend = build_backend(args.backend, args.endpoint, args.model_path, args.model_version)
    except Exception:
        parser.error("Requested backend unavailable. Fix its configuration or explicitly choose --backend manual.")
    key_path = Path(args.data_dir) / "reviewer.key"
    if not key_path.exists():
        key_path.write_text(secrets.token_urlsafe(32))
    key_path.chmod(0o600)
    token = key_path.read_text().strip()
    if len(token) < 32:
        raise ValueError("Reviewer key must contain at least 32 characters")
    server = create_server(store, backend, policy, token, args.reviewer, args.port)
    print(f"Open http://127.0.0.1:{server.server_port}; reviewer key: {key_path.resolve()}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
