"""Opt-in real user-manager acceptance, isolated from installed/live Hermes services.

Run with --ag2-systemd-acceptance. Temporary runtime unit names/config/state only.
The packaged policies and sandbox are retained; paths, ports and names are isolated.
"""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid

import httpx
import pytest

from hermes_ag2_network import Network
from hermes_ag2_network.discovery import enroll_profile
from test_http_executor import hermes_api
from test_cli import command
from queue import Queue
import threading


def test_bridge_exits_on_hub_eof_without_runtime_work(tmp_path: Path):
    home = tmp_path / "home"
    (home / "profiles" / "architect").mkdir(parents=True)
    enroll_profile("architect", home)
    keys = tmp_path / "keys.json"
    keys.write_text(json.dumps({"architect": "b", "caller": "a"}), encoding="utf-8")
    keys.chmod(0o600)
    token = tmp_path / "hub.key"
    token.write_text("b", encoding="utf-8")
    token.chmod(0o600)
    api_key = tmp_path / "api.key"
    api_key.write_text("fixture-secret", encoding="utf-8")
    api_key.chmod(0o600)
    process = None
    with hermes_api() as (url, posts):
        try:
            with command("hub", "--store", str(tmp_path / "hub"), "--keys-file", str(keys), "--port", "0") as hub:
                process = subprocess.Popen([sys.executable, "-m", "hermes_ag2_network.cli", "bridge",
                    "--hub-url", hub["url"], "--name", "architect", "--home", str(home),
                    "--allow-peer", "caller", "--ledger", str(tmp_path / "bridge.sqlite"),
                    "--control-db", str(tmp_path / "control.sqlite"), "--api-url", url,
                    "--hub-key-file", str(token), "--api-key-file", str(api_key)],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stream = process.stdout
                assert stream is not None
                ready = Queue()
                reader = threading.Thread(target=lambda: ready.put(stream.readline()), daemon=True)
                reader.start()
                assert json.loads(ready.get(timeout=10)) == {"ready": "bridge", "profile": "architect"}
                reader.join(timeout=1)
            stdout, stderr = process.communicate(timeout=10)
            assert process.returncode == 1
            assert "ConnectionError" in stderr
            assert "fixture-secret" not in stdout + stderr
            assert posts == []
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                process.communicate(timeout=10)

SYSTEMD = Path(__file__).parents[1] / "systemd"


def systemctl(*args, check=True):
    return subprocess.run(["systemctl", "--user", *args], check=check, capture_output=True,
                          text=True, timeout=20)


def properties(unit):
    result = systemctl("show", unit, "--property=MainPID,ActiveState,NRestarts,UnitFileState,LoadState")
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def wait_for(predicate, *, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.1)
    raise AssertionError("systemd acceptance condition did not become true within deadline")


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_real_systemd_process_restart_hub_reconnect_and_disable(tmp_path: Path, request, monkeypatch):
    if not request.config.getoption("--ag2-systemd-acceptance"):
        pytest.skip("explicit opt-in required for isolated user-manager acceptance")
    runtime_override = request.config.getoption("--ag2-systemd-runtime-dir")
    if runtime_override:
        runtime_path = Path(runtime_override)
        assert runtime_path.stat().st_uid == os.getuid() and (runtime_path / "bus").exists()
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_path))
        monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=" + str(runtime_path / "bus"))
    if systemctl("show-environment", check=False).returncode:
        pytest.skip("systemd user manager unavailable")
    executable = Path(sys.prefix) / "bin" / "hermes-ag2-network"
    assert executable.is_file(), "requires a PM-built installed standalone distribution"
    runtime = Path(os.environ["XDG_RUNTIME_DIR"]) / "systemd" / "user"
    runtime.mkdir(parents=True, exist_ok=True)
    identity = "ag2-acceptance-" + uuid.uuid4().hex
    hub_name = identity + "-hub.service"
    template_name = identity + "-bridge@.service"
    bridge_name = identity + "-bridge@architect.service"
    state = tmp_path / "state"
    config = tmp_path / "config"
    state.mkdir(mode=0o700)
    (config / "bridges").mkdir(parents=True, mode=0o700)
    home = tmp_path / "hermes-home"
    (home / "profiles" / "architect").mkdir(parents=True)
    enroll_profile("architect", home)
    hub_port, api_port = port(), port()
    hub_url = f"ws://127.0.0.1:{hub_port}"
    units = [runtime / hub_name, runtime / template_name]
    receipt = {"units": [hub_name, bridge_name], "controlled_http": True, "live_llm": False}

    def protected(path, value):
        path.write_text(value, encoding="utf-8")
        path.chmod(0o600)

    protected(config / "identity-keys.json", json.dumps({"caller": "caller-fixture", "architect": "architect-fixture"}))
    for suffix, secret in (("hub", "architect-fixture"), ("api", "fixture-secret"), ("tools", "tools-fixture")):
        protected(config / "bridges" / f"architect-{suffix}.key", secret)

    def isolate(source):
        return (source.replace("%h/.local/share/hermes-ag2-network/bin/hermes-ag2-network", str(executable))
                .replace("%h/.local/state/hermes-ag2-network", str(state))
                .replace("%h/.config/hermes-ag2-network", str(config))
                .replace("hermes-ag2-hub.service", hub_name)
                .replace("--port 8765", f"--port {hub_port}")
                .replace("[Service]", f"[Service]\nEnvironment=HERMES_HOME={home}"))

    headers = {"Authorization": "Bearer tools-fixture", "X-Hermes-Profile": "architect"}
    def bridge_ready():
        try:
            response = httpx.get(f"http://127.0.0.1:{api_port}/v1/peers", headers=headers, timeout=1)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    with hermes_api() as (url, posts):
        protected(config / "bridges" / "architect.env",
                  f"HUB_URL={hub_url}\nAPI_URL={url}\nPROJECT_PEER=lifecycle=caller\nTOOL_API_PORT={api_port}\n")
        for target, source in zip(units, ("hermes-ag2-hub.service", "hermes-ag2-bridge@.service"), strict=True):
            assert not target.exists()
            target.write_text(isolate((SYSTEMD / source).read_text(encoding="utf-8")), encoding="utf-8")
        try:
            systemctl("daemon-reload")
            systemctl("enable", "--runtime", "--now", hub_name, bridge_name)
            wait_for(bridge_ready)
            initial = {"hub": properties(hub_name), "bridge": properties(bridge_name)}
            assert initial["bridge"]["UnitFileState"] == "enabled-runtime"

            async def exchange(operation):
                async with Network.connect(hub_url, name="caller", token="caller-fixture", allowed_peers={"architect"},
                                           ledger_path=state / "caller.sqlite", control_path=state / "network-admission.sqlite") as caller:
                    channel = await caller.open(peer="architect", project_id="lifecycle")
                    reply = await caller.ask(channel, "read-only fixture input", operation_id=operation, timeout=10)
                    assert reply.text == "HTTP runtime replied."
                    return channel, reply.session_id, reply.run_id

            first = asyncio.run(exchange("before-outage"))
            # Real process crash: systemd, not a Python context manager, performs restart.
            systemctl("kill", "--signal=SIGKILL", "--kill-whom=main", bridge_name)
            wait_for(lambda: properties(bridge_name)["MainPID"] not in {"0", initial["bridge"]["MainPID"]})
            wait_for(bridge_ready)
            after_bridge = properties(bridge_name)
            replay = asyncio.run(exchange("before-outage"))
            assert replay == first
            assert len([p for p in posts if p[0].endswith("/v1/runs")]) == 1

            systemctl("kill", "--signal=SIGKILL", "--kill-whom=main", hub_name)
            wait_for(lambda: properties(hub_name)["MainPID"] not in {"0", initial["hub"]["MainPID"]})
            wait_for(lambda: properties(bridge_name)["MainPID"] not in {"0", after_bridge["MainPID"]})
            wait_for(bridge_ready)
            second = asyncio.run(exchange("after-hub-outage"))
            assert second[0] == first[0]
            origins = [p[2]["id"] for p in posts if p[0].endswith("/api/sessions")]
            assert set(origins) == {first[1]}
            assert second[1] == "rotated-" + first[1]
            assert second[2] != first[2]
            assert len([p for p in posts if p[0].endswith("/v1/runs")]) == 2
            receipt.update(initial=initial, after_bridge_crash=after_bridge,
                           after_hub_crash={"hub": properties(hub_name), "bridge": properties(bridge_name)},
                           channel_id=first[0], session_origin_id=first[1], run_posts=2, replay_no_post=True)
            systemctl("disable", "--runtime", "--now", bridge_name, hub_name)
            stopped = {"hub": properties(hub_name), "bridge": properties(bridge_name)}
            # Observe beyond the packaged three-second restart interval.
            time.sleep(4)
            for unit, prior in ((hub_name, stopped["hub"]), (bridge_name, stopped["bridge"])):
                current = properties(unit)
                assert current["ActiveState"] == "inactive" and current["MainPID"] == "0"
                assert current["NRestarts"] == prior["NRestarts"]
                assert systemctl("is-enabled", unit, check=False).returncode != 0
            assert len([p for p in posts if p[0].endswith("/v1/runs")]) == 2
            receipt["disabled_readback"] = stopped
        finally:
            systemctl("disable", "--runtime", "--now", bridge_name, hub_name, check=False)
            for unit in (bridge_name, hub_name):
                assert properties(unit)["MainPID"] == "0"
            for target in units:
                target.unlink(missing_ok=True)
            systemctl("daemon-reload")
            systemctl("reset-failed", bridge_name, hub_name, check=False)
            for unit in (bridge_name, hub_name):
                assert properties(unit)["LoadState"] == "not-found"
            receipt["cleanup_readback"] = "units not-found; main PIDs zero; runtime enablement removed"
            receipt_path = request.config.getoption("--ag2-systemd-receipt")
            target = Path(receipt_path) if receipt_path else tmp_path / "lifecycle-receipt.json"
            target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
            print("SYSTEMD_RECEIPT=" + json.dumps(receipt))
