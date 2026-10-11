# Hermes ↔ native AG2 tracer

Independent Python distribution, **not a Hermes core/plugin-tree change**. AG2 owns the authenticated native transport, registry, invitations, conversation channels and disk WAL. An enrolled Hermes Profile executes new input through its own HTTP Runs API. No `ag2.Agent` is constructed; no provider/model/history is passed from this package.

## Install (isolated, PM-owned)

From a Hermes source checkout with its PM/test interpreter, set `BRIDGE` to this directory and `ENV` to a **new** standalone destination outside the live Hermes environment:

```sh
export BRIDGE="$PWD/integrations/hermes-ag2-network"
export ENV="$HOME/.cache/hermes-ag2-network-env"
# Use your checkout's PM-capable Python, not an arbitrary system interpreter.
"$HERMES_PYTHON" -c 'import os; from pathlib import Path; from pm.operations import build_environment; print(build_environment(source=Path(os.environ["BRIDGE"]), out=Path(os.environ["ENV"]), groups=["test"], explicit=True))'
"$ENV/bin/hermes-ag2-network" --help
```

`uv.lock` belongs solely to this distribution. Core's lock/environment stays unchanged. For dependency edits, use `pm.operations.lock_project(Path(BRIDGE), explicit=True)` and rebuild a fresh destination. The manifest exempts only the deliberately reviewed/pinned `ag2==1.1.2` from inherited core quarantine; it does not change core quarantine. Wheel contains only `hermes_ag2_network`, no vendored AG2 or Hermes code. Tested on Linux / Python 3.14.7; hub/CLI process locking and signal handling currently require POSIX.

## Separate optional services

Prepare an owner-only (`0600`) JSON key file mapping the explicitly enrolled **network identities** to tokens. Use different tokens per identity. Provide each bridge only its own hub token (raw-token `0600` file or `AG2_HUB_KEY` secret environment variable). Hermes API credentials are separate and profile-scoped. Never pass tokens as CLI values, prompts, tool schema parameters or AG2 messages.

```sh
"$ENV/bin/hermes-ag2-network" hub --store /approved/state/ag2-hub \
  --keys-file /protected/ag2-identities.json --port 8765

"$ENV/bin/hermes-ag2-network" bridge --hub-url ws://127.0.0.1:8765 \
  --name coding --allow-peer caller --ledger /approved/state/coding-delivery.sqlite \
  --hub-key-file /protected/coding-ag2-token \
  --api-url http://127.0.0.1:8642 --api-key-file /protected/coding-api-token
```

The hub binds loopback only, uses `AuthRegistry([ApiKeyAuth(name_to_token)])` without `NoAuth`, and holds an exclusive store-owner lock. Clients reject cleartext non-loopback URLs and embedded URL credentials. SIGTERM/SIGINT disconnect the bridge without unregistering native identities. Do **not** use `AgentClient.close()` or `HubClient.shutdown()` for stop: those unregister.

## Public `agent_network` seam

```python
from pathlib import Path
from hermes_ag2_network import Network

async with Network.connect(
    hub_url, name="caller", token=secret_from_protected_storage,
    allowed_peers={"coding"}, ledger_path=Path("/approved/state/caller.sqlite"),
) as agent_network:
    peers = await agent_network.peers()  # name + stable native agent_id; no secrets
    channel = await agent_network.open(peer="coding", project_id="demo")
    reply = await agent_network.ask(channel, "Review this approach.", operation_id="unique-operation-id")
    assert reply.request_id  # native causation_id of the correlated request
    history = await agent_network.history(channel)
    # send() is asynchronous request delivery, returning the native envelope id.
    request_envelope_id = await agent_network.send(channel, "Another explicit request.")
```

An enrolled recipient adds `executor=HermesHTTPExecutor(...)` (an async callable; controlled fixtures are permitted in deterministic tests). `open` waits for the native invite ACK; disallowed invites receive a native rejection. `send` posts an explicitly addressed request. `ask` adapts native send into a correlated wait; it is **not** a fictional `Channel.ask`. `history` returns request/reply/status text from native WAL. Each outbound request has a distinct operation ID. Request/reply/status tags are explicit: receipt of a reply never invokes the executor, so there is no automatic ping-pong.

## Real-runtime smoke

This command generates ephemeral **network** credentials in memory, starts a real native disk/WS hub, enrolls one existing Hermes Profile with the supplied **Hermes API** credential, asks it to run a read-only terminal SHA256 probe, verifies the digest, reads the native WAL and reads back the exact completed Hermes run/session tool receipts. It does not configure profiles, gateways or providers. API must already be enabled/authenticated by the operator. It creates only a new API session, a run and the chosen bridge state directory; the model may still perform its normal runtime housekeeping.

```sh
"$ENV/bin/hermes-ag2-network" smoke \
  --api-url http://127.0.0.1:8642 --profile coding \
  --api-key-file /protected/coding-api-token \
  --store /approved/scratch/ag2-live-tracer --timeout 300
```

For a protected dotenv file add `--api-key-field API_SERVER_KEY`. Alternatively use `--api-key-env API_SERVER_KEY`. Output is a JSON receipt with real run/session/channel/envelope IDs, verified probe output, runtime metadata returned by Hermes and persisted tool-result count. No credential values are printed. A failure prints only its exception class and exits nonzero; inspect the owning runtime or API run status for detailed operator diagnosis, **do not automatically retry uncertain work**.

## Execution and genuine limitations

- First slice only: fresh native channels and a deterministic **new Hermes session per profile/channel/operation**, using UUID5. Stable named channel/session continuation and native rotation lineage are ticket 02, not claimed here.
- Execution uses `POST /p/<profile>/api/sessions` with an explicit deterministic ID, then reads that exact session. `POST /p/<profile>/v1/runs` carries `Authorization`, `Idempotency-Key`, `X-Hermes-Session-Key`, and only `{session_id,input}`. Provider/model/tools/private memory are resolved server-side. Run completion is read back with GET. Interrupted/failed/cancelled/partial runs and timeouts are not success and are not automatically retried/stopped.
- A small SQLite admission record is committed before execution. Errors leave the operation unsettled; a repeated unsettled operation is held, not re-executed. This is not a complete exactly-once/reconnect protocol or an operator recovery UI. A lost reply can require explicit reconciliation.
- AG2 1.1.2 ships `HubClient.attach` typed for `Agent`, not a public external-runtime registration API. The pinned-tested name-only `ExternalIdentity` shim has a fail-closed `ask`. `attach_plugin=False` **does not disable** the default handler; we replace it immediately with `AgentClient.on_envelope`, skip initial replay (`since_envelope_id=None`), and do not claim automatic pending replay/recovery. A newly delivered envelope in the attach/handler-install gap cannot start an AG2 model.
- AG2's WS implementation has a read-only `endpoint_id` property where its LinkClient protocol declares a writable attribute. A narrow documented type cast bridges this upstream typing mismatch, with actual WS tests, not invented methods.
- Released AG2 requires undeclared `watchdog` for importing `DiskKnowledgeStore` and optional `websockets` for native WS. Both are explicitly bounded dependencies here. Resolved versions: AG2 1.1.2, watchdog 6.0.0, websockets 15.0.1, httpx 0.28.1.
- AG2 disk WAL is JSONL and not transactional/crash-atomic. Native envelope `idempotency_key`/`causation_id` alone do not deduplicate execution. One hub owns each store. Clean restart hydration is tested; crash-exactly-once is not claimed.
- Native local control-plane calls bypass some wire permissions; production bridge and all integration tests use authenticated WS. Peer allowlists are checked by this facade. Per-project grants, global budgets, nested-cycle guards, artifact transport, tool plugin enrollment, discovery, systemd deployment and recovery are later tickets. A project label is **not** a filesystem sandbox/cwd binding.
- `peers()` exposes enrolled identities among the native list's first 50 results, not automatic live Profile discovery. No Profile config, memory backend, private memory store, SOUL, Skills or MCP is modified or copied. Coding/Architect remain on their current legacy memory backend.

## Verification

From Hermes checkout root, always use the canonical runner, with the standalone interpreter:

```sh
HERMES_PYTHON="$ENV/bin/python" scripts/run_tests.sh integrations/hermes-ag2-network/tests/ -v --tb=short
```

Tests exercise real native disk Hub, authenticated WS, invitation activation, public request/reply/history/peers, causation correlation, reply non-execution, registry/WAL clean restart, a controlled HTTP server at the external executor boundary, and separate installed hub/bridge processes. Controlled executor tests are not live Hermes receipts. See `VERIFICATION.md` for actual RED/GREEN receipts and live acceptance status.

Sources inspected: released 1.1.2 wheel (`ag2/network/client/{hub_client,agent_client,handlers,channel}.py`, `network/auth.py`, native disk/WS modules), official upstream docs `website/docs/user-guide/network/{distributed,agent_clients,conversation}.mdx`, and [Hermes programmatic integration](https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration). The guessed published AG2 network URLs returned 404; upstream docs include stale snippets (e.g. `ApiKeyAuth` taking a set and `attach_plugin=False` disabling the default handler). Installed released signatures and real execution, not those snippets, govern this adapter.
