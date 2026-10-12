"""Executable hub, profile bridge and real-runtime tracer smoke commands."""
import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import stat

from .executor import HermesHTTPExecutor
from .hub import network_hub
from .network import Network
from .tool_api import ToolAPI
from .types import NetworkLimits


PROBE_TEXT = "AG2-HERMES-TRACER"
PROBE_PROMPT = (
    "This is an authorized read-only transport smoke test. Use your terminal tool "
    "to compute the SHA256 of the UTF-8 string AG2-HERMES-TRACER with Python hashlib. "
    "Do not edit files, settings, secrets or memory. Reply with AG2-HERMES-TRACER "
    "followed by the hexadecimal digest and no other text."
)


def protected_file(path: str) -> str:
    file = Path(path)
    metadata = file.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ValueError("credential file must be owner-only (0600) and owned by this user")
    return file.read_text(encoding="utf-8-sig").strip()


def token(args, prefix: str) -> str:
    path = getattr(args, prefix + "_key_file")
    env = getattr(args, prefix + "_key_env")
    value = protected_file(path) if path else os.environ.get(env, "")
    # Protected file accepts a raw token or a dotenv API_SERVER_KEY assignment.
    field = getattr(args, prefix + "_key_field", None)
    if path and field:
        pairs = [line.split("=", 1) for line in value.splitlines() if "=" in line and not line.lstrip().startswith("#")]
        value = next((v.strip().strip("\"'") for k, v in pairs if k.strip() == field), "")
    if not value or "\n" in value:
        raise ValueError("credential unavailable or invalid; provide a protected file or secret environment variable")
    return value


async def until_stopped():
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await stop.wait()


async def serve_hub(args):
    keys = json.loads(protected_file(args.keys_file))
    async with network_hub(Path(args.store), keys, port=args.port) as hub:
        print(json.dumps({"ready": "hub", "url": hub.url}), flush=True)
        await until_stopped()


def project_peer_grants(values: list[str]) -> dict[str, set[str]]:
    grants: dict[str, set[str]] = {}
    for value in values:
        project_id, separator, peer = value.partition("=")
        if not separator or not project_id.strip() or not peer.strip():
            raise ValueError("project peer grant must use PROJECT=PEER")
        grants.setdefault(project_id.strip(), set()).add(peer.strip())
    return grants


async def serve_bridge(args):
    limits = NetworkLimits(
        max_hops=args.max_hops, max_turns=args.max_turns, max_pending=args.max_pending,
        request_timeout=args.timeout, max_active=args.max_active,
    )
    project_peers = project_peer_grants(args.project_peer)
    if not args.allow_peer and not project_peers:
        raise ValueError("at least one --allow-peer or --project-peer grant is required")
    async with HermesHTTPExecutor(args.api_url, profile=args.name, token=token(args, "api"), deadline=args.timeout) as executor:
        async with Network.connect(args.hub_url, name=args.name, token=token(args, "hub"),
            allowed_peers=set(args.allow_peer), executor=executor, ledger_path=Path(args.ledger),
            project_peers=project_peers, limits=limits, control_path=Path(args.control_db)) as network:
            if args.tool_api_port is None:
                if args.tool_api_key_file:
                    raise ValueError("--tool-api-key-file requires --tool-api-port")
                print(json.dumps({"ready": "bridge", "profile": args.name}), flush=True)
                await until_stopped()
            else:
                if not args.tool_api_key_file:
                    raise ValueError("--tool-api-port requires an owner-only --tool-api-key-file")
                async with ToolAPI(network, protected_file(args.tool_api_key_file), port=args.tool_api_port) as tool_api:
                    print(json.dumps({"ready": "bridge", "profile": args.name,
                                      "tool_api_url": tool_api.url}), flush=True)
                    await until_stopped()


async def smoke(args):
    """No controlled executor: POST a real authenticated Hermes run via AG2."""
    caller_name = "tracer-caller"
    if args.profile == caller_name:
        raise ValueError("profile conflicts with smoke caller")
    operation_id = args.operation_id
    keys = {caller_name: secrets.token_urlsafe(32), args.profile: secrets.token_urlsafe(32)}
    root = Path(args.store)
    async with HermesHTTPExecutor(args.api_url, profile=args.profile, token=token(args, "api"), deadline=args.timeout) as executor:
        async with network_hub(root / "hub", keys) as hub:
            async with Network.connect(hub.url, name=args.profile, token=keys[args.profile],
                allowed_peers={caller_name}, executor=executor, ledger_path=root / "profile.sqlite"):
                async with Network.connect(hub.url, name=caller_name, token=keys[caller_name],
                    allowed_peers={args.profile}, ledger_path=root / "caller.sqlite") as caller:
                    channel = await caller.open(peer=args.profile, project_id="live-tracer")
                    reply = await caller.ask(channel, PROBE_PROMPT, operation_id=operation_id, timeout=args.timeout + 10)
                    expected = hashlib.sha256(PROBE_TEXT.encode()).hexdigest()
                    if PROBE_TEXT not in reply.text or expected not in reply.text:
                        raise RuntimeError("live reply did not contain the verified read-only probe result")
                    history = await caller.history(channel)
                    if [m.kind for m in history] != ["request", "reply"]:
                        raise RuntimeError("native WAL does not contain exactly one request and one reply")
                    # Read back the exact real run; never invent runtime metadata.
                    response = await executor.http.get(f"v1/runs/{reply.run_id}")
                    response.raise_for_status()
                    run = response.json()
                    messages_response = await executor.http.get(f"api/sessions/{reply.session_id}/messages", params={"limit": 100})
                    messages_response.raise_for_status()
                    messages = messages_response.json().get("data", [])
                    tool_messages = sum(m.get("role") == "tool" for m in messages)
                    if tool_messages == 0:
                        raise RuntimeError("real session has no tool-result receipt for the read-only probe")
                    receipt = {"live": True, "profile": args.profile, "channel_id": channel,
                        "reply": asdict(reply), "native_text_envelopes": len(history),
                        "status": run["status"], "runtime": run.get("runtime"), "tool_results": tool_messages}
                    print(json.dumps(receipt, ensure_ascii=False), flush=True)


def credential_options(parser, prefix: str):
    source = parser.add_mutually_exclusive_group()
    source.add_argument(f"--{prefix}-key-file")
    source.add_argument(f"--{prefix}-key-env", default="API_SERVER_KEY" if prefix == "api" else "AG2_HUB_KEY")
    parser.add_argument(f"--{prefix}-key-field", help="dotenv field name (omit for raw-token file)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    hub = commands.add_parser("hub", help="native durable authenticated loopback WS hub")
    hub.add_argument("--store", required=True)
    hub.add_argument("--keys-file", required=True, help="protected JSON mapping identity names to tokens")
    hub.add_argument("--port", type=int, default=8765)
    bridge = commands.add_parser("bridge", help="one enrolled Hermes profile, no AG2 model")
    bridge.add_argument("--hub-url", required=True)
    bridge.add_argument("--name", required=True)
    bridge.add_argument("--allow-peer", action="append", default=[],
                        help="profile-wide enrolled peer; project grants override this list")
    bridge.add_argument("--project-peer", action="append", default=[], metavar="PROJECT=PEER",
                        help="peer grant for one project; repeat for additional peers")
    bridge.add_argument("--ledger", required=True)
    bridge.add_argument("--control-db", required=True,
                        help="same shared admission SQLite path for every controlled participant (same host)")
    bridge.add_argument("--max-active", type=int, default=16,
                        help="global active/uncertain Run capacity; identical for every participant")
    bridge.add_argument("--api-url", required=True, help="multiplex base URL, without /p/profile")
    bridge.add_argument("--timeout", type=float, default=300,
                        help="maximum request/executor deadline in seconds (0 < value <= 300)")
    bridge.add_argument("--max-hops", type=int, default=8)
    bridge.add_argument("--max-turns", type=int, default=16)
    bridge.add_argument("--max-pending", type=int, default=16)
    bridge.add_argument("--tool-api-port", type=int,
                        help="optional authenticated loopback tool API port (0 selects an ephemeral port)")
    bridge.add_argument("--tool-api-key-file", help="owner-only bearer key file for the optional Hermes plugin")
    credential_options(bridge, "hub")
    credential_options(bridge, "api")
    probe = commands.add_parser("smoke", help="run a real Hermes tool through a native AG2 request/reply")
    probe.add_argument("--api-url", required=True)
    probe.add_argument("--profile", required=True)
    probe.add_argument("--store", required=True)
    probe.add_argument("--operation-id", required=True,
                       help="stable ID; reuse it with the same payload if retrying an uncertain request")
    probe.add_argument("--timeout", type=float, default=300)
    credential_options(probe, "api")
    args = parser.parse_args()
    # Never dump argparse namespace (may later contain secret-bearing fields).
    try:
        asyncio.run({"hub": serve_hub, "bridge": serve_bridge, "smoke": smoke}[args.command](args))
    except Exception as exc:  # health: allow BLE001 -- secret-safe CLI boundary; emit class only, never credential-bearing exception text
        parser.exit(1, f"{type(exc).__name__}: command failed; no automatic execution retry\n")


if __name__ == "__main__":
    main()
