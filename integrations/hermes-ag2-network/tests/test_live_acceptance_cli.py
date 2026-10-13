"""Real-import controlled CLI receipts; not live ten-step acceptance (#21)."""
import json
import os
from pathlib import Path
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import TypedDict

import pytest


class EndpointState(TypedDict):
    status: int
    body: str
    requests: list[str]


@pytest.fixture
def cli(tmp_path):
    keys = {}
    for profile in ("coding", "architect"):
        keys[profile] = tmp_path / f"{profile}.key"
        keys[profile].write_text(f"{profile}-credential")
        keys[profile].chmod(0o600)
    home = tmp_path / "hermes-home"
    home.mkdir()
    receipt = tmp_path / "evidence" / "receipt.json"

    def run(url, *extra):
        env = {**os.environ, "HERMES_HOME": str(home), "HOME": str(tmp_path),
               "PYTHONPATH": str(Path(__file__).parents[1] / "src")}
        return subprocess.run([
            sys.executable, "-m", "hermes_ag2_network.live_acceptance",
            "--api-url", url, "--coding-api-key-file", str(keys["coding"]),
            "--architect-api-key-file", str(keys["architect"]), "--receipt", str(receipt),
            *extra,
        ], env=env, capture_output=True, text=True, timeout=20)
    return run, receipt, keys, home


@pytest.fixture
def endpoint():
    state: EndpointState = {"status": 200, "body": '{"sessions": [{"title": "private-title"}]}', "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            profile = self.path.split("/")[2]
            state["requests"].append(self.path)
            assert self.headers["Authorization"] == f"Bearer {profile}-credential"
            self.send_response(state["status"])
            self.end_headers()
            self.wfile.write(state["body"].encode())

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize(("status", "body", "action"), [
    (401, "private-body", "credential"),
    (403, "private-body", "permission"),
    (503, "private-body", "Gateway"),
    (200, "private-body", "Sessions JSON"),
    (200, '{"error": "private-body"}', "Sessions JSON"),
])
def test_http_failures_are_actionable_and_sanitized(cli, endpoint, status, body, action):
    run, receipt, _, home = cli
    url, state = endpoint
    state.update(status=status, body=body)
    result = run(url)
    assert result.returncode == 2
    saved = json.loads(receipt.read_text())
    assert json.loads(result.stdout) == saved
    assert saved["ready"] is False
    assert saved["live_scenario_completed"] is False
    assert saved["mutations"] == []
    assert action in " ".join(saved["blockers"])
    for private in ("private-body", "coding-credential", "architect-credential", "Traceback"):
        assert private not in result.stdout + result.stderr + receipt.read_text()
    assert list(home.iterdir()) == []


def test_cli_saves_readiness_without_claiming_live_acceptance(cli, endpoint):
    run, receipt, _, home = cli
    url, state = endpoint
    result = run(url)
    assert result.returncode == 0
    saved = json.loads(receipt.read_text())
    assert json.loads(result.stdout) == saved
    assert saved["ready"] is True
    assert saved["live_scenario_completed"] is False
    assert saved["mutations"] == []
    assert receipt.stat().st_mode & 0o777 == 0o600
    assert state["requests"] == ["/p/coding/api/sessions?limit=1", "/p/architect/api/sessions?limit=1"]
    assert "private-title" not in result.stdout
    assert list(home.iterdir()) == []


@pytest.mark.parametrize("problem", ["missing", "directory", "public", "empty", "multiline", "encoding"])
def test_credential_input_fails_safely_before_http_or_receipt(cli, endpoint, problem):
    run, receipt, keys, _ = cli
    url, state = endpoint
    key = keys["coding"]
    if problem in {"missing", "directory"}:
        key.unlink()
        if problem == "directory":
            key.mkdir()
    elif problem == "public":
        key.chmod(0o644)
    else:
        key.write_bytes({"empty": b"", "multiline": b"secret-one\nsecret-two", "encoding": b"\xff"}[problem])
    result = run(url)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "coding" in result.stderr and "credential" in result.stderr
    assert "--coding-api-key-file" in result.stderr
    assert "Traceback" not in result.stderr and "secret-one" not in result.stderr
    assert state["requests"] == []
    assert not receipt.exists()


def test_existing_receipt_is_preserved_with_actionable_error(cli, endpoint):
    run, receipt, _, _ = cli
    url, _ = endpoint
    receipt.parent.mkdir()
    receipt.write_bytes(b"previous-evidence\n")
    result = run(url)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "already exists" in result.stderr and "new --receipt" in result.stderr
    assert "Traceback" not in result.stderr
    assert receipt.read_bytes() == b"previous-evidence\n"


def test_output_parent_failure_is_safe_and_actionable(cli, endpoint):
    run, receipt, _, _ = cli
    url, _ = endpoint
    receipt.parent.write_text("private-output-parent")
    result = run(url)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "--receipt" in result.stderr and "directory" in result.stderr
    assert "Traceback" not in result.stderr and "private-output-parent" not in result.stderr
    assert receipt.parent.read_text() == "private-output-parent"


@pytest.mark.parametrize("url", ["https://private-token@localhost", "http://remote.invalid", "not-a-url"])
def test_invalid_api_url_is_rejected_without_echoing_input(cli, url):
    run, receipt, _, _ = cli
    result = run(url)
    assert result.returncode == 2
    assert "--api-url" in result.stderr
    assert "Traceback" not in result.stderr and "private-token" not in result.stderr
    assert not receipt.exists()


def test_transport_failure_saves_blocked_receipt(cli):
    import socket

    run, receipt, _, _ = cli
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        result = run(f"http://127.0.0.1:{listener.getsockname()[1]}")
    assert result.returncode == 2
    saved = json.loads(receipt.read_text())
    assert saved == json.loads(result.stdout)
    assert "transport failed" in " ".join(saved["blockers"])
    assert "Gateway listener" in " ".join(saved["blockers"])
    assert saved["ready"] is False and saved["mutations"] == []
    assert "credential" not in result.stdout
