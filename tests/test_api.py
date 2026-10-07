import http.client
import json
import socket
import threading

import pytest

from app.configuration import load_policy
from app.decision import ManualBackend, SystemOneBackend
from app.server import create_server
from app.storage import Store
from tests.helpers import pdf_bytes, confirmed


@pytest.fixture
def service(tmp_path):
    store = Store(tmp_path / "data")
    server = create_server(store, ManualBackend(), load_policy(), "test-secret", "test-reviewer", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(method, path, payload=None, auth=True, headers=None, raw=False):
        body = payload if raw else json.dumps(payload).encode() if payload is not None else None
        all_headers = {"Content-Type": "application/pdf" if raw else "application/json"}
        if auth:
            all_headers["Authorization"] = "Bearer test-secret"
        all_headers.update(headers or {})
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request(method, path, body, all_headers)
        response = connection.getresponse()
        status, data = response.status, response.read()
        is_json = "application/json" in response.getheader("Content-Type", "")
        connection.close()
        return status, json.loads(data) if is_json else data.decode()

    yield request, store
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_auth_origin_host_and_static(service):
    request, _ = service
    assert request("GET", "/api/reviews", auth=False)[0] == 401
    assert request("GET", "/api/reviews", headers={"Origin": "https://evil.example"})[0] == 403
    assert request("GET", "/api/reviews", headers={"Host": "evil.example"})[0] == 403
    assert request("GET", "/", auth=False)[0] == 200
    assert request("GET", "/../../etc/passwd")[0] == 404


def test_idle_browser_connection_does_not_block_requests(tmp_path):
    server = create_server(Store(tmp_path), ManualBackend(), load_policy(), "secret", "reviewer", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    idle = socket.create_connection(("127.0.0.1", server.server_port))
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    try:
        connection.request("GET", "/")
        response = connection.getresponse()
        assert response.status == 200
        response.read()
    finally:
        connection.close()
        idle.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_pdf_confirmation_export_and_revision(service):
    request, store = service
    status, state = request("POST", "/api/reviews", pdf_bytes(), raw=True)
    assert status == 201
    base = "/api/reviews/" + state["id"]
    assert request("GET", base + "/export")[0] == 400
    assert request("POST", base + "/finalize", {"revision": 0, "classification": "ACCEPT", "rationale": "test", "acknowledge_findings": True})[0] == 400
    ids = [ev["id"] for ev in state["document"]["evidence"]]
    status, state = request("POST", base + "/decision", {"revision": 0, "question_id": "software_gpu_capable", "answer": "YES", "evidence_ids": ids, "note": "Verified"})
    assert status == 200 and state["revision"] == 1
    assert request("POST", base + "/analyze", {"revision": 0})[0] == 409
    state = confirmed(store.get(state["id"]))
    store.save(state, 1, "test-confirmed")
    status, state = request("POST", base + "/finalize", {"revision": 2, "classification": "ACCEPT", "rationale": "Verified", "acknowledge_findings": True})
    assert status == 200
    assert "SHADOW DRAFT" in request("GET", base + "/export")[1]
    assert request("GET", base + "/audit")[1][-1]["final_classification"] == "ACCEPT"
    assert request("DELETE", base)[0] == 200
    assert request("GET", base)[0] == 404


def test_decision_endpoint_and_invalid_inputs(service):
    request, _ = service
    status, body = request("POST", "/v1/decide", {"question_id": "software_gpu_capable", "state": "PyTorch ROCm"})
    assert status == 200 and body["answer"] == "UNKNOWN"
    assert request("POST", "/v1/decide", {"question_id": "invented", "state": "x"})[0] == 404
    assert request("POST", "/api/reviews", {"url": "https://evil.example"})[0] == 400
    assert request("POST", "/api/reviews", b"not a pdf", raw=True)[0] == 400


def test_systemone_protocol_and_no_redirect():
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Model(BaseHTTPRequestHandler):
        redirect = False

        def log_message(self, *args):
            pass

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert data["questions"]["review"]["type"] == "choice"
            if self.redirect:
                self.send_response(302)
                self.send_header("Location", "https://example.com")
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"answers": {"review": {"probabilities": {"YES": .9, "NO": .01, "UNKNOWN": .09}}}}).encode())

    server = HTTPServer(("127.0.0.1", 0), Model)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        backend = SystemOneBackend(f"http://127.0.0.1:{server.server_port}/v1/systemone", "jevos", "fixture")
        q = {"type": "choice", "instructions": "Test", "criteria": {"YES": "yes", "NO": "no", "UNKNOWN": "unknown"}}
        assert backend.decide("Evidence", q)["YES"] == .9
        Model.redirect = True
        with pytest.raises(ValueError):
            backend.decide("Evidence", q)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
