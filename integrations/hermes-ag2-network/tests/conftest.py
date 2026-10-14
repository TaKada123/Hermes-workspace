"""Explicit owning-runtime interpreter for real core memory fixtures."""
import sys
import os
from pathlib import Path
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import TypedDict

import pytest


def pytest_addoption(parser):
    parser.addoption("--ag2-systemd-acceptance", action="store_true", default=False,
                     help="opt in to isolated temporary real systemd user-service acceptance")
    parser.addoption("--ag2-systemd-runtime-dir", default=None,
                     help="explicit owning user runtime dir when canonical runner sanitizes D-Bus env")
    parser.addoption("--ag2-systemd-receipt", default=None,
                     help="approved output path for the sanitized systemd acceptance receipt")
    parser.addoption("--hermes-core-python", default=sys.executable,
                     help="Hermes core test interpreter for the production memory/config fixture")


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
