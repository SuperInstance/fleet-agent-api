"""Tests for agent_api.py — the main HTTP server every agent runs."""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
import signal

import pytest

# ---------------------------------------------------------------------------
# Helper: start agent_api.py as a subprocess with controlled env vars, yield
# its base URL, then tear it down.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def agent_server():
    """Start agent_api.py on a random high port in a subprocess."""
    port = 18901  # unlikely to conflict
    env = {
        **os.environ,
        "FLEET_TOKEN": "test-secret-token",
        "AGENT_NAME": "TestAgent",
        "AGENT_ROLE": "tester",
        "AGENT_VERSION": "1.0.0",
        "AGENT_API_PORT": str(port),
        "AGENT_CAPABILITIES": "testing,mocking",
        "KEEPER_URL": "",  # no keeper
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    proc = subprocess.Popen(
        [sys.executable, os.path.join(os.path.dirname(__file__), "..", "agent_api.py")],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    base = f"http://localhost:{port}"
    # Wait for server to be ready
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{base}/health", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    else:
        proc.kill()
        out, err = proc.communicate()
        pytest.fail(f"Server did not start.\nstdout: {out.decode()}\nstderr: {err.decode()}")
    yield base
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


# ---------- Auth helper ----------

def _auth_headers(token="test-secret-token"):
    return {"Authorization": f"Bearer {token}"}


def _get(path, base, headers=None):
    req = urllib.request.Request(f"{base}{path}", headers=headers or {})
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _post(path, base, body, headers=None):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{base}{path}",
        data=data,
        headers={**({"Content-Type": "application/json"}), **(headers or {})},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ===================== GET /health =====================

class TestHealthEndpoint:
    def test_health_returns_ok(self, agent_server):
        code, data = _get("/health", agent_server)
        assert code == 200
        assert data["status"] == "ok"
        assert data["agent"] == "TestAgent"

    def test_health_no_auth_required(self, agent_server):
        code, data = _get("/health", agent_server, headers={"Authorization": "Bearer wrong"})
        assert code == 200


# ===================== GET /whoami =====================

class TestWhoamiEndpoint:
    def test_whoami_returns_identity(self, agent_server):
        code, data = _get("/whoami", agent_server)
        assert code == 200
        assert data["name"] == "TestAgent"
        assert data["role"] == "tester"
        assert data["version"] == "1.0.0"

    def test_whoami_has_capabilities(self, agent_server):
        code, data = _get("/whoami", agent_server)
        assert "capabilities" in data
        assert "testing" in data["capabilities"]
        assert "mocking" in data["capabilities"]

    def test_whoami_has_uptime(self, agent_server):
        code, data = _get("/whoami", agent_server)
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0

    def test_whoami_has_timestamp(self, agent_server):
        code, data = _get("/whoami", agent_server)
        assert "timestamp" in data
        assert "T" in data["timestamp"]  # ISO format

    def test_whoami_has_port(self, agent_server):
        code, data = _get("/whoami", agent_server)
        assert data["port"] == 18901


# ===================== GET /status =====================

class TestStatusEndpoint:
    def test_status_returns_ok_health(self, agent_server):
        code, data = _get("/status", agent_server)
        assert code == 200
        assert data["health"] == "ok"

    def test_status_has_load(self, agent_server):
        code, data = _get("/status", agent_server)
        assert "load" in data
        assert len(data["load"]) == 3

    def test_status_has_uptime(self, agent_server):
        code, data = _get("/status", agent_server)
        assert "uptime_seconds" in data

    def test_status_has_messages_count(self, agent_server):
        code, data = _get("/status", agent_server)
        assert "messages_received" in data


# ===================== POST /message =====================

class TestMessageEndpoint:
    def test_message_without_auth_returns_401(self, agent_server):
        code, data = _post("/message", agent_server, {"from": "A", "body": "hi"})
        assert code == 401
        assert "Unauthorized" in data.get("error", "")

    def test_message_wrong_token_returns_401(self, agent_server):
        code, data = _post(
            "/message", agent_server,
            {"from": "A", "body": "hi"},
            headers=_auth_headers("wrong-token"),
        )
        assert code == 401

    def test_message_invalid_json_returns_400(self, agent_server):
        req = urllib.request.Request(
            f"{agent_server}/message",
            data=b"not-json",
            headers={"Content-Type": "application/json", **_auth_headers()},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=5)
        assert exc_info.value.code == 400

    def test_message_info_type_gets_reply(self, agent_server):
        code, data = _post(
            "/message", agent_server,
            {"from": "Oracle1", "type": "info", "body": "Hello there"},
            headers=_auth_headers(),
        )
        assert code == 200
        assert data["received"] is True
        assert "Received" in data["reply"]

    def test_message_question_type_auto_reply(self, agent_server):
        code, data = _post(
            "/message", agent_server,
            {"from": "JetsonClaw1", "type": "question", "body": "What is the meaning of life?"},
            headers=_auth_headers(),
        )
        assert code == 200
        assert "question" in data["reply"].lower() or "think" in data["reply"].lower()

    def test_message_alert_type_auto_reply(self, agent_server):
        code, data = _post(
            "/message", agent_server,
            {"from": "Babel", "type": "alert", "body": "GPU temperature critical!"},
            headers=_auth_headers(),
        )
        assert code == 200
        assert "Alert" in data["reply"] or "acknowledged" in data["reply"].lower()

    def test_message_missing_type_defaults_to_info(self, agent_server):
        code, data = _post(
            "/message", agent_server,
            {"from": "Navigator", "body": "Just a note"},
            headers=_auth_headers(),
        )
        assert code == 200
        assert data["received"] is True

    def test_message_increments_status_count(self, agent_server):
        _, before = _get("/status", agent_server)
        count_before = before["messages_received"]
        _post(
            "/message", agent_server,
            {"from": "Guinan", "type": "info", "body": "Testing counts"},
            headers=_auth_headers(),
        )
        _, after = _get("/status", agent_server)
        assert after["messages_received"] == count_before + 1


# ===================== GET /bottles =====================

class TestBottlesEndpoint:
    def test_bottles_without_auth_returns_401(self, agent_server):
        code, data = _get("/bottles", agent_server)
        assert code == 401

    def test_bottles_with_auth_returns_list(self, agent_server):
        code, data = _get("/bottles", agent_server, headers=_auth_headers())
        assert code == 200
        assert "for_me" in data
        assert "count" in data


# ===================== GET /fleet =====================

class TestFleetEndpoint:
    def test_fleet_without_auth_returns_401(self, agent_server):
        code, data = _get("/fleet", agent_server)
        assert code == 401

    def test_fleet_with_auth_returns_agents(self, agent_server):
        code, data = _get("/fleet", agent_server, headers=_auth_headers())
        assert code == 200
        assert "agents" in data
        # At minimum, the agent itself
        assert len(data["agents"]) >= 1
        # Self should be listed
        names = [a["name"] for a in data["agents"]]
        assert "TestAgent" in names


# ===================== POST /register =====================

class TestRegisterEndpoint:
    def test_register_without_auth_returns_401(self, agent_server):
        code, data = _post("/register", agent_server, {"name": "X", "api": "http://x"})
        assert code == 401

    def test_register_with_auth_succeeds(self, agent_server):
        code, data = _post(
            "/register", agent_server,
            {"name": "NewAgent", "api": "http://newagent:8901"},
            headers=_auth_headers(),
        )
        assert code == 200
        assert data["registered"] is True
        assert data["by"] == "TestAgent"


# ===================== 404 / unknown =====================

class TestUnknownEndpoints:
    def test_unknown_get_returns_404(self, agent_server):
        code, data = _get("/nonexistent", agent_server)
        assert code == 404
        assert "error" in data

    def test_unknown_post_returns_404(self, agent_server):
        code, data = _post("/nonexistent", agent_server, {})
        assert code == 404


# ===================== OPTIONS / CORS =====================

class TestCorsOptions:
    def test_options_returns_200(self, agent_server):
        req = urllib.request.Request(f"{agent_server}/any-path", method="OPTIONS")
        resp = urllib.request.urlopen(req, timeout=5)
        assert resp.status == 200
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"

    def test_options_allows_post(self, agent_server):
        req = urllib.request.Request(f"{agent_server}/any-path", method="OPTIONS")
        resp = urllib.request.urlopen(req, timeout=5)
        methods = resp.headers.get("Access-Control-Allow-Methods", "")
        assert "POST" in methods

    def test_options_allows_authorization_header(self, agent_server):
        req = urllib.request.Request(f"{agent_server}/any-path", method="OPTIONS")
        resp = urllib.request.urlopen(req, timeout=5)
        headers = resp.headers.get("Access-Control-Allow-Headers", "")
        assert "Authorization" in headers


# ===================== Query string handling =====================

class TestQueryStringHandling:
    def test_whoami_ignores_query_string(self, agent_server):
        code, data = _get("/whoami?v=2", agent_server)
        assert code == 200
        assert data["name"] == "TestAgent"
