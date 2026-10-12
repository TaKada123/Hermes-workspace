"""Operator configuration at the installed CLI / real AG2 / HTTP Runs seam."""
import asyncio
import base64
import json
import os
from pathlib import Path
import subprocess
import sys

import httpx
import pytest

from hermes_ag2_network import Network
from hermes_ag2_network.artifacts import ArtifactStore
from hermes_ag2_network.discovery import enroll_profile
from test_cli import command
from test_http_executor import hermes_api


PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"


def protected(path, value):
    path.write_text(value)
    path.chmod(0o600)
    return str(path)


@pytest.mark.parametrize("images", [True, False])
def test_installed_bridge_content_exchange_and_explicit_image_grant(tmp_path: Path, images):
    approved = tmp_path / "approved"
    approved.mkdir()
    report = approved / "checks.txt"
    report.write_text("3 passed\n")
    image = approved / "pixel.png"
    image.write_bytes(base64.b64decode(PNG))
    config = {
        "artifact_store_root": str(tmp_path / "artifacts"),
        "artifact_project_roots": {"cli-artifacts": [str(approved)]},
        "artifact_image_projects": ["cli-artifacts"] if images else [],
        "artifact_max_bytes": 1024,
    }
    store = ArtifactStore(tmp_path / "artifacts", project_roots={"cli-artifacts": (approved,)}, max_bytes=1024)
    result_ref = store.publish("cli-artifacts", report, kind="check_report", media_type="text/plain")
    output = json.dumps({"network_result": {"text": "Verified checks", "artifact_refs": [result_ref.to_wire()]}})
    keys = protected(tmp_path / "keys", json.dumps({"caller": "a", "architect": "b"}))
    hub_token = protected(tmp_path / "hub-token", "b")
    api_token = protected(tmp_path / "api-token", "fixture-secret")
    tools_token = protected(tmp_path / "tools-token", "fixture-secret-tools")
    config_file = protected(tmp_path / "behavior.json", json.dumps(config))
    home = tmp_path / "home"
    (home / "profiles" / "architect").mkdir(parents=True)
    enroll_profile("architect", home)
    with hermes_api(output=output) as (url, requests):
        with command("hub", "--store", str(tmp_path / "hub"), "--keys-file", keys, "--port", "0") as hub:
            with command("bridge", "--hub-url", hub["url"], "--name", "architect", "--home", str(home),
                         "--project-peer", "cli-artifacts=caller", "--project-peer", "ungranted=caller",
                         "--ledger", str(tmp_path / "architect.sqlite"),
                         "--control-db", str(tmp_path / "network-admission.sqlite"),
                         "--api-url", url, "--api-key-file", api_token, "--hub-key-file", hub_token,
                         "--config-file", config_file, "--tool-api-port", "0", "--tool-api-key-file", tools_token,
                         "--timeout", "5") as bridge:
                async def scenario():
                    async with Network.connect(hub["url"], name="caller", token="a", allowed_peers={"architect"},
                                               ledger_path=tmp_path / "caller.sqlite", artifact_store=store) as caller:
                        channel = await caller.open(peer="architect", project_id="cli-artifacts")
                        async with httpx.AsyncClient(base_url=bridge["tool_api_url"], headers={
                            "Authorization": "Bearer fixture-secret-tools", "X-Hermes-Profile": "architect",
                        }) as http:
                            published = await http.post("/v1/artifacts/publish", json={"channel_id": channel,
                                "path": str(report), "kind": "check_report", "media_type": "text/plain"})
                            assert published.status_code == 200
                            assert published.json()["result"] == result_ref.to_wire()
                            reply = await caller.ask(channel, "Check report", operation_id="report", artifact_refs=(result_ref,), timeout=5)
                            assert reply.text == "Verified checks"
                            assert reply.artifact_refs == (result_ref,)
                            read = await http.post("/v1/artifacts/read", json={"channel_id": channel, "artifact_ref": reply.artifact_refs[0].to_wire()})
                            assert read.status_code == 200 and read.json()["result"]["text"] == "3 passed\n"
                            assert (await caller.history(channel))[-1].artifact_refs == (result_ref,)
                            image_ref = store.publish("cli-artifacts", image, kind="image", media_type="image/png")
                            if images:
                                await caller.ask(channel, "Inspect image", operation_id="image", artifact_refs=(image_ref,), timeout=5)
                            else:
                                from hermes_ag2_network import ExecutionUncertain
                                with pytest.raises(ExecutionUncertain, match="before execution"):
                                    await caller.ask(channel, "Inspect image", operation_id="image", artifact_refs=(image_ref,), timeout=5)
                            other = await caller.open(peer="architect", project_id="ungranted")
                            denied = await http.post("/v1/artifacts/publish", json={"channel_id": other, "path": str(report)})
                            assert denied.status_code == 403
                asyncio.run(scenario())
    runs = [body for path, _, body in requests if path.endswith("/v1/runs")]
    assert len(runs) == (2 if images else 1)
    assert "3 passed\\n" in runs[0]["input"] or "3 passed\n" in runs[0]["input"]
    assert str(approved) not in runs[0]["input"]
    if images:
        content = runs[1]["input"][0]["content"]
        assert content[-1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64," + PNG}}


@pytest.mark.parametrize("bad", ["permissions", "symlink", "unknown", "image_without_root", "roots_string", "bool_limit", "relative_root"])
def test_cli_rejects_unsafe_or_malformed_behavior_config_before_network(tmp_path: Path, bad):
    approved = tmp_path / "approved"
    approved.mkdir()
    config = {"artifact_store_root": str(tmp_path / "artifacts"), "artifact_project_roots": {"p": [str(approved)]}}
    if bad == "unknown":
        config["api_token"] = "do-not-print-secret"
    elif bad == "image_without_root":
        config["artifact_image_projects"] = ["other"]
    elif bad == "roots_string":
        config["artifact_project_roots"]["p"] = str(approved)
    elif bad == "bool_limit":
        config["artifact_max_bytes"] = True
    elif bad == "relative_root":
        config["artifact_store_root"] = "relative"
    config_file = Path(protected(tmp_path / "behavior.json", json.dumps(config)))
    if bad == "permissions":
        config_file.chmod(0o644)
    elif bad == "symlink":
        link = tmp_path / "link.json"
        link.symlink_to(config_file)
        config_file = link
    home = tmp_path / "home"
    (home / "profiles" / "architect").mkdir(parents=True)
    enroll_profile("architect", home)
    result = subprocess.run([sys.executable, "-m", "hermes_ag2_network.cli", "bridge", "--name", "architect",
        "--home", str(home), "--hub-url", "ws://127.0.0.1:1", "--project-peer", "p=caller",
        "--ledger", str(tmp_path / "ledger"), "--control-db", str(tmp_path / "control"),
        "--api-url", "http://127.0.0.1:1", "--config-file", str(config_file)],
        env={**os.environ, "API_SERVER_KEY": "fixture-secret", "AG2_HUB_KEY": "fixture-secret"},
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert any(name + ": command failed" in result.stderr for name in ("ValueError", "PermissionError"))
    assert "fixture-secret" not in result.stdout + result.stderr
    assert "do-not-print-secret" not in result.stdout + result.stderr
    assert not (tmp_path / "ledger").exists()
