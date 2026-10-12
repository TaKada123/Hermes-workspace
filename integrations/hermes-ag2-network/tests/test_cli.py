"""Installed separate-process hub/bridge observed through agent_network."""
import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
import select
import subprocess
import sys

import pytest
from ag2.network import ProtocolError

from hermes_ag2_network import Network
from test_http_executor import hermes_api


@contextmanager
def command(*arguments):
    process = subprocess.Popen([sys.executable, "-m", "hermes_ag2_network.cli", *arguments],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert process.stdout is not None and process.stderr is not None
    try:
        ready, _, _ = select.select([process.stdout], [], [], 10)
        if not ready:
            raise AssertionError("CLI service did not report readiness")
        line = process.stdout.readline()
        assert line, process.stderr.read() if process.poll() is not None else "CLI exited without readiness"
        yield json.loads(line)
    finally:
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, (process.returncode, stderr)
        assert "fixture-secret" not in stdout + stderr


def test_separate_hub_and_profile_bridge_cli(tmp_path: Path):
    keys = tmp_path / "hub-keys.json"
    keys.write_text(json.dumps({"caller": "a", "architect": "b"}))
    keys.chmod(0o600)
    hub_token = tmp_path / "hub-token"
    hub_token.write_text("b")
    hub_token.chmod(0o600)
    api_token = tmp_path / "api-token"
    api_token.write_text("fixture-secret")
    api_token.chmod(0o600)
    with hermes_api() as (url, _):
        with command("hub", "--store", str(tmp_path / "hub"), "--keys-file", str(keys), "--port", "0") as hub:
            with command("bridge", "--hub-url", hub["url"], "--name", "architect",
                         "--project-peer", "cli-tracer=caller", "--max-hops", "1",
                         "--max-turns", "1", "--max-pending", "1", "--timeout", "5",
                         "--control-db", str(tmp_path / "network-admission.sqlite"),
                         "--ledger", str(tmp_path / "architect.sqlite"), "--api-url", url,
                         "--api-key-file", str(api_token), "--hub-key-file", str(hub_token)) as bridge:
                assert bridge == {"ready": "bridge", "profile": "architect"}

                async def scenario():
                    async with Network.connect(hub["url"], name="caller", token="a", allowed_peers={"architect"},
                                               ledger_path=tmp_path / "caller.sqlite") as caller:
                        channel = await caller.open(peer="architect", project_id="cli-tracer")
                        reply = await caller.ask(channel, "Only this new message.", operation_id="cli-01", timeout=5)
                        assert reply.text == "HTTP runtime replied."
                        assert len(await caller.history(channel)) == 2
                        with pytest.raises(ProtocolError, match="invite_rejected"):
                            await caller.open(peer="architect", project_id="not-granted")
                asyncio.run(scenario())
