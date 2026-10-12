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

Discover profile names without reading their configuration or memory, then explicitly enroll each runtime identity before starting its bridge. Run this from the same Hermes home used by the bridge service:

```sh
"$ENV/bin/hermes-ag2-network" profiles
"$ENV/bin/hermes-ag2-network" profiles --enroll coding
```

The `profiles` command emits JSON with `available` and `enrolled` names. It includes `default` for the root profile and discovers valid named directories under `profiles/`, without opening their config, credentials, or memory. A named profile's `HERMES_HOME=<root>/profiles/NAME` resolves to `<root>` rather than looking for profiles inside that profile. An unset home defaults to `~/.hermes`; custom roots and `--home ROOT` are supported. Pass the same `--home` to `profiles` and `bridge`, or set `HERMES_HOME` in the instance's service environment. Directory discovery alone cannot validate a runtime's health or its configuration.

Discovery grants no execution permission. `bridge --name NAME` refuses startup unless NAME is explicitly listed in `<root>/agent-network/enrolled-profiles.json`. Enrollment/revocation writes only names, under a persistent POSIX advisory lock, then fsyncs and atomically replaces a `0600` file in a user-owned `0700` directory. Concurrent cooperating CLI updates preserve other enrollments; insecure ownership/permissions or symlink paths are rejected, not silently repaired. Enrollment does not create Hub credentials, peer grants, or a running service.

```sh
"$ENV/bin/hermes-ag2-network" profiles --home /owning/hermes-root --enroll NEW_NAME
"$ENV/bin/hermes-ag2-network" profiles --home /owning/hermes-root --revoke NEW_NAME
```

`--revoke` is idempotent and also works after the profile directory disappears. It revokes **future bridge starts**, not an already-running process or native Hub identity. For immediate disablement, stop/disable the bridge first (below), then revoke enrollment. Do not hand-edit this file concurrently with managed CLI updates.

Prepare an owner-only (`0600`) JSON key file mapping the explicitly enrolled **network identities** to tokens. Use different tokens per identity. Provide each bridge only its own hub token (raw-token `0600` file or `AG2_HUB_KEY` secret environment variable). Hermes API credentials are separate and profile-scoped. Never pass tokens as CLI values, prompts, tool schema parameters or AG2 messages.

```sh
"$ENV/bin/hermes-ag2-network" hub --store /approved/state/ag2-hub \
  --keys-file /protected/ag2-identities.json --port 8765

"$ENV/bin/hermes-ag2-network" bridge --hub-url ws://127.0.0.1:8765 \
  --name coding --project-peer demo=architect --project-peer docs=caller \
  --ledger /approved/state/coding-delivery.sqlite --control-db /approved/state/network-admission.sqlite \
  --hub-key-file /protected/coding-ag2-token \
  --api-url http://127.0.0.1:8642 --api-key-file /protected/coding-api-token \
  --max-hops 8 --max-turns 16 --max-pending 16 --max-active 16 --timeout 300
```

`--allow-peer` is the profile-wide fallback. If a project has one or more `--project-peer PROJECT=PEER` entries, that project's entries replace the fallback list (including an empty explicit grant); peers must also allow the other identity for that project. `agent_network_peers` accepts an optional project ID and returns that project's effective grants.

The hub binds loopback only, uses `AuthRegistry([ApiKeyAuth(name_to_token)])` without `NoAuth`, and holds an exclusive store-owner lock. Clients reject cleartext non-loopback URLs and embedded URL credentials. SIGTERM/SIGINT disconnect the bridge without unregistering native identities. Do **not** use `AgentClient.close()` or `HubClient.shutdown()` for stop: those unregister.

## Public `agent_network` seam

```python
from pathlib import Path
from hermes_ag2_network import Network

async with Network.connect(
    hub_url, name="caller", token=secret_from_protected_storage,
    allowed_peers={"coding"}, ledger_path=Path("/approved/state/caller.sqlite"),
    control_path=Path("/approved/state/network-admission.sqlite"),
) as agent_network:
    peers = await agent_network.peers()  # name + stable native agent_id; no secrets
    channel = await agent_network.open(peer="coding", project_id="demo")
    reply = await agent_network.ask(channel, "Review this approach.", operation_id="unique-operation-id")
    assert reply.request_id  # native causation_id of the correlated request
    history = await agent_network.history(channel)
    # Send/ask require a caller-supplied stable operation ID; reuse it on the same retry.
    request_envelope_id = await agent_network.send(
        channel, "Another explicit request.", operation_id="unique-operation-id-2",
    )
```

An enrolled recipient adds `executor=HermesHTTPExecutor(...)` (an async callable; controlled fixtures are permitted in deterministic tests). `open` waits for the native invite ACK; disallowed invites receive a native rejection. `send` posts an explicitly addressed request. `ask` adapts native send into a correlated wait; it is **not** a fictional `Channel.ask`. `history` returns request/reply/status/rejected messages from native WAL plus recipient-local recovery notices for unanswered terminal-channel requests anywhere in the same project (their IDs only; these are marked with `local-recovery:` envelope IDs). Other profiles cannot see those local notices. `send` and `ask` require a caller-supplied stable `operation_id`. Reuse the same ID and exact payload when retrying; a conflicting payload under that ID is rejected. Request/reply/status/rejected tags are explicit: receipt of a reply never invokes the executor, so there is no automatic ping-pong.

The sender includes a stable operation ID and a bounded interaction budget in each request. Defaults are at most 8 network hops, 16 Hermes turns, 16 pending requests per profile, and a 300-second wall-clock deadline; the hard ceilings are 16 hops, 32 turns, 64 pending requests, and 300 seconds. The deadline is propagated through nested consultations and the HTTP executor. Incoming Hermes runs are serialized per profile, while independent project channels can be in flight up to the pending cap. Each receiver applies its own stricter limits. Capacity/budget exhaustion before admission returns an explicit `rejected` status, so the same operation ID is safe to retry once capacity is available. A timeout after admission is marked uncertain and held; it is never automatically re-run. Retry only with the same operation ID: a committed result is replayed from the ledger, while an unsettled run remains held for explicit reconciliation.

### Shared admission and explicit reconciliation

Every controlled participant (including local callers) must use **one same-host SQLite
`control_path` / required CLI `--control-db`** per network, with identical `max_active` /
`--max-active` (default 16, hard ceiling 64). The API default is `network-admission.sqlite`
beside the delivery ledger, suitable only when all ledgers share that directory. A
receiver with a different authority rejects the unknown interaction rather than granting
a fresh turn budget. Do not fork/delete this authority to clear a held Run.

The authority atomically debits a single interaction balance for every admitted descendant,
so branching cannot reuse copied turns. Hop bounds remain path-local. Before a controlled
`send`/`ask` writes a request to native WAL, it reserves shared capacity. A submitted request
and its active/uncertain Hermes admission count as **one** global slot, not two. Shared pending
transport capacity is the strictest enrolled `max_pending` / `--max-pending` (default 16,
hard ceiling 64); it does not silently expand on disconnect. A stricter participant cannot
enroll while outstanding transports exceed its limit. Per-profile serialization and local
pending/waiter limits remain additional bounds. SQLite transactions are the coordination
seam, not an invented AG2 RPC or a replacement Hermes memory backend.

Native send ACK only proves Hub acceptance: offline/queued work keeps the reservation.
Completion or a definite pre-execution refusal releases it after a terminal receipt; a
terminal Run reconciliation also releases it. Timeout, cancellation, lost ACK, unsettled
status and disconnect retain it. Retrying a pending/uncertain operation fails locally rather
than appending duplicate requests. Each submission has a distinct transport token (AG2
assigns its own envelope ID), so a late receipt cannot free a newer reservation. Reconnect
reads durable terminal receipts to close reply-persistence/release crash gaps. Global or
pending saturation rejects **before submission**, without waiting on a slot held by a nested
call's parent. Structured allowlisted admission causes/remediation cross reply and ToolAPI
boundaries; arbitrary executor exception text is never exposed.
This supports cooperating same-host user services, not a cross-host/shared-network filesystem
distributed semaphore and not a cap on arbitrary native AG2 clients' transport traffic.

An admitted execution retains its opaque context, ancestry, Run ID when observed, and lease
on timeout, disconnect, cancellation or exception; no timer expires that lease. Unknown or
stale supplied Run context IDs are rejected, even when the profile is idle. Fresh requests
cannot bypass a held profile. An expired held context still exists, but cannot acquire fresh
network budget. On reconnect the held metadata and admission are restored before readiness.
Legacy unsettled operation rows also fail closed with zero inherited budget.

`await network.reconcile(context_id)` is an explicit **operator/library** action, not a model
tool or an automatic startup retry. `HermesHTTPExecutor.reconcile` performs only authenticated
GET readback of the recorded Run ID and canonical session tip; it never reposts input. A
completed Run records its result and releases admission. A failed/cancelled/interrupted or
incomplete terminal Run raises `ExecutionTerminated`, records terminal evidence and releases
admission, while its operation stays non-retryable. A still-live Run or failed readback retains
protection. There is no deployed CLI/tool-API reconciliation command in this slice.

If the Run submit response was lost (or the bridge crashed before persisting an observed
Run ID), the bridge cannot prove the Run identity via this readback seam. It retains admission
and requires owning-runtime/operator evidence; **no automatic resend or successful recovery
is claimed**. Crash gaps between the admission authority and delivery ledger fail closed and
may require operator repair. Arbitrary deletion/corruption of either database is not supported.

## systemd user services (Linux)

The packaged templates are optional. They do not modify Hermes core or any profile configuration. Build the isolated distribution through PM as in the Install section, then link its executable to the unit's fixed path and install the units:

```sh
mkdir -p ~/.local/share/hermes-ag2-network/bin
ln -sf "$ENV/bin/hermes-ag2-network" ~/.local/share/hermes-ag2-network/bin/hermes-ag2-network
mkdir -p ~/.config/systemd/user
install -d -m 0700 ~/.config/hermes-ag2-network ~/.config/hermes-ag2-network/bridges ~/.local/state/hermes-ag2-network
install -m 0644 integrations/hermes-ag2-network/systemd/hermes-ag2-hub.service ~/.config/systemd/user/
install -m 0644 integrations/hermes-ag2-network/systemd/hermes-ag2-bridge@.service ~/.config/systemd/user/
```

Create `~/.config/hermes-ag2-network/identity-keys.json` as an owner-only JSON map of every enrolled network identity to its distinct AG2 token. Configure the hub unit's `--keys-file` path if storing it elsewhere. Create `~/.config/hermes-ag2-network/bridges/coding.env` (mode `0600`) with `HUB_URL=ws://127.0.0.1:8765`, `API_URL=http://127.0.0.1:8642`, `PROJECT_PEER=demo=architect`, and an unused loopback `TOOL_API_PORT`. Put distinct owner-only API, hub and tool API key files beside it, using the exact `%i` filenames referenced by the unit. Add one explicit `--project-peer` grant per project/peer by extending that instance's `ExecStart`; discovery alone never enrolls or authorizes execution. Check the unit with `systemd-analyze --user verify` before enabling.

```sh
systemctl --user daemon-reload
systemctl --user enable --now hermes-ag2-hub.service
systemctl --user enable --now hermes-ag2-bridge@coding.service
systemctl --user status hermes-ag2-hub hermes-ag2-bridge@coding
journalctl --user -u hermes-ag2-bridge@coding
```

### Add a specialist, reconnect, stop and roll back

New Profiles need no source edit: discover names, explicitly enroll NAME, create its distinct env/credential files, add its Hub identity/token to the protected key map, and grant the intended peers/projects on both sides. Restart the Hub **after a coordinated bridge stop** to load a changed key map (the Hub reads it at startup, not dynamically), then start the intended enrolled bridges. Use unique `TOOL_API_PORT` values. A `default` instance addresses the root profile; named instances address their own HTTP `/p/NAME` runtime. Do not copy private profile files into Hub state.

The bridge uses `Wants`/`After` (not `Requires`) and `Restart=always`, with a three-second restart delay and no start-limit window. On established WS disconnect it exits nonzero; systemd constructs a fresh bridge connection, restores ledger/channel/session mappings and recovers native WAL. The pinned AG2 1.1.2 receive task is observed because upstream has no public disconnect notification; no periodic registry polling or idle model runs are introduced. The Hub uses `Restart=on-failure`. Restarting a service does **not** prove that an already-admitted Hermes Run stopped and does not automatically re-execute uncertain work. Follow the reconciliation limitations above.

```sh
# For planned maintenance: stop every bridge before stopping the Hub.
systemctl --user stop hermes-ag2-bridge@coding.service
systemctl --user stop hermes-ag2-hub.service
# Restart in dependency order; durable state must stay in place.
systemctl --user start hermes-ag2-hub.service hermes-ag2-bridge@coding.service
systemctl --user show hermes-ag2-bridge@coding.service -p MainPID -p ActiveState -p NRestarts

# Disable a specialist immediately, then revoke future startup authorization.
systemctl --user disable --now hermes-ag2-bridge@coding.service
"$ENV/bin/hermes-ag2-network" profiles --revoke coding
systemctl --user is-active hermes-ag2-bridge@coding.service   # expected: inactive
systemctl --user is-enabled hermes-ag2-bridge@coding.service  # expected: disabled
# Only after ALL bridges are disabled/stopped:
systemctl --user disable --now hermes-ag2-hub.service
```

Manual `stop`/`disable --now` suppresses systemd restart even with `Restart=always`; `disable` alone does not stop a process. A remaining enabled bridge may pull its Wanted Hub up, so do not stop only the Hub to disable the network. Removal of an enrollment or Hub token is not a hot revocation of an existing connection.

Rollback: after readback confirms all relevant units inactive/disabled, remove **only the two unit copies installed for this network** and its executable symlink, then `systemctl --user daemon-reload`. Disable the optional plugin only in the profiles where it was installed; absent bridges make its tools unavailable, not an alternative runtime. Retain or deliberately archive Hub WAL, delivery ledgers and the shared admission authority together before any state removal; do not delete a database to bypass an uncertain Run. Remove credentials only through the owning secret workflow. Core/Gateway services and private profile configuration/memory do not need migration, restart, or modification to stop this network.

`test_systemd_units.py` uses `systemd-analyze verify`. Opt-in `test_systemd_lifecycle.py` actually runs isolated temporary user units with the packaged restart/sandbox policies, real AG2 Hub/WS and a controlled authenticated HTTP runtime. It tests bridge process crash, Hub process outage, saved-result replay without another POST, channel/session lineage reuse, and clean disable/readback/cleanup. This is real service acceptance, **not** a live Hermes/model run or crash-atomic WAL/exactly-once proof. See the receipt in `VERIFICATION.md`.

### Artifact references and real limits

`hermes_ag2_network.artifacts.ArtifactRef` is the typed descriptor model for file/image/check-report/Git-reference/result/error/status references. `send`/`ask`, history, the loopback ToolAPI and Hermes plugin carry bounded descriptor metadata; the recipient Hermes Run sees the descriptors separately from the message text. The bridge does not transfer or fetch artifact bytes, host an artifact server, or verify the remote object against its declared digest. `verify_local_file` hashes a regular file only inside explicitly approved roots and under a byte cap, but local `file:` URIs are rejected at the network boundary so host paths cannot leak. Private memory is never searched or attached. Consumers must independently authorize access and verify bytes before use. Thus current artifact support is typed metadata exchange, not content exchange; Git references must be supplied explicitly rather than triggering repository reads.

AG2/hub API limitations remain: registration lacks a public external-runtime handler attach (the tested name-only shim and attach race are documented above); JSONL WAL is not crash-transactional; and Hermes Runs has no project cwd/sandbox binding. These controls do not provide multi-host shared admission or limit arbitrary native AG2 clients.

## Optional Hermes tool plugin

`plugin/` is a standalone general Hermes plugin; it does not add or monkeypatch Hermes core. Copy it into the specific profile's `plugins/agent-network` directory, enable it only for that profile, and configure a loopback URL for that profile's bridge. The plugin registers provider-safe names `agent_network_peers`, `agent_network_open`, `agent_network_send`, `agent_network_ask`, and `agent_network_history` (dots are not valid provider tool names). Each request goes to the authenticated local bridge API; the active profile name is attached by the plugin, never supplied by the model. The model sees no credentials or profile selector. The secret `AGENT_NETWORK_TOOLS_KEY` belongs in the owning profile's `.env` (through the owner's secret workflow); the network bridge uses the same value from an owner-only key file. Other Hermes profiles must have different credentials.

```sh
PROFILE_HOME="$(dirname "$(hermes -p coding config path)")"
mkdir -p "$PROFILE_HOME/plugins"
cp -a integrations/hermes-ag2-network/plugin "$PROFILE_HOME/plugins/agent-network"
hermes -p coding config set plugins.entries.agent-network.settings.bridge_url http://127.0.0.1:8766
hermes -p coding plugins enable agent-network
```

Run that per enrolled profile, using a different loopback port and key for each. Add `--tool-api-port 8766 --tool-api-key-file "$HERMES_HOME/agent-network/secrets/agent-network-tools.key"` to that profile's `bridge` command. The API listener binds **only** `127.0.0.1`, is disabled by default, caps JSON bodies at 64 KiB, verifies a constant-time bearer token plus the expected profile name, and exposes only peers/open/send/ask/history. The owner-only key file must be mode `0600`; the bridge refuses insecure permissions. The API server binds an opaque `run_context_id` (the operation's SHA-256 Idempotency-Key) to the admitted run, and Hermes injects it into tool handlers out-of-band. The plugin returns it in a bridge-only header; it does not replace Hermes' session-scoped `task_id`, so terminal/browser continuity is preserved. The bridge rejects nested requests without the matching active context, preventing another run—even in the same session—from inheriting ancestry or budget. `ask` caps its wait at 300 seconds. A visited-profile ancestry travels in native request metadata; a repeated profile in the current chain is rejected before delivery, so nested consultation returns a useful tool error instead of locking an active Hermes session. No polling occurs: when the plugin is idle it makes no requests and causes no model activity.

## Real-runtime smoke

This command generates ephemeral **network** credentials in memory, starts a real native disk/WS hub, enrolls one existing Hermes Profile with the supplied **Hermes API** credential, asks it to run a read-only terminal SHA256 probe, verifies the digest, reads the native WAL and reads back the exact completed Hermes run/session tool receipts. It does not configure profiles, gateways or providers. API must already be enabled/authenticated by the operator. It creates only a new API session, a run and the chosen bridge state directory; the model may still perform its normal runtime housekeeping.

```sh
"$ENV/bin/hermes-ag2-network" smoke \
  --api-url http://127.0.0.1:8642 --profile coding \
  --api-key-file /protected/coding-api-token \
  --operation-id live-tracer-smoke-001 \
  --store /approved/scratch/ag2-live-tracer --timeout 300
```

For a protected dotenv file add `--api-key-field API_SERVER_KEY`. Alternatively use `--api-key-env API_SERVER_KEY`. Output is a JSON receipt with real run/session/channel/envelope IDs, verified probe output, runtime metadata returned by Hermes and persisted tool-result count. No credential values are printed. A failure prints only its exception class and exits nonzero; inspect the owning runtime or API run status for detailed operator diagnosis, **do not automatically retry uncertain work**.

## Execution and genuine limitations

- Each `(profile, peer, project_id)` persists one stable active AG2 channel mapping; repeated `open` returns that channel, including after bridge/Hub restart. If the local mapping is missing, the bridge adopts the unique matching active Hub channel; multiple matches fail closed for operator reconciliation. If its native channel is terminal/missing, the mapping is replaced with a new channel. Each `(profile, project_id, channel_id)` then gets one durable Hermes session lineage in the bridge's SQLite ledger: a stable deterministic origin ID plus the current continuation ID. Operation IDs are deduplicated within `(profile, project_id, channel_id)`; they may be reused in other project channels. The SQLite tables are operational channel/session/delivery metadata, not a memory backend.
- Execution uses `POST /p/<profile>/api/sessions` with the stable origin ID. Before each turn, `GET /api/sessions/<origin>/messages?limit=0` resolves Hermes' canonical current continuation tip without reading transcript contents; the bridge then verifies that resolved target with `GET /api/sessions/<tip>`. This ordering also recovers if Hermes rotated while the bridge was down and SQLite still holds the old current ID. `POST /p/<profile>/v1/runs` carries `Authorization`, a SHA-256 `Idempotency-Key` derived from profile/project/channel/operation ID, the matching `X-Hermes-Run-Context-Id`, stable `X-Hermes-Session-Key`, and only `{session_id,input}`. After a completed Run, the bridge resolves the tip again: Hermes may rotate the session during a turn while the Run status still reports the old ID. The mapping is updated transactionally before the reply is sent over AG2. Provider/model/tools/private memory are resolved only by the owning Hermes profile.
- An operation's deduplication fingerprint covers profile/project/channel/operation/input, not the derived session ID (so a retry after session rotation is still the same operation). An identical completed retry returns its saved result; conflicting input under that scoped operation ID is rejected. An admitted-but-unsettled operation remains held for explicit reconciliation and is never automatically rerun. Existing global operation rows are copied transactionally into the new project/channel-scoped ledger; old rows remain intact. Other bridge tables are created idempotently on upgrade.
- Rotation/history reconciliation uses Hermes' canonical session-tip endpoint and does not fetch the conversation transcript. Tests cover Hub restart + bridge reconnect + session rotation, stable channel reuse, recovery of a request delivered while the recipient was offline, and separate projects with distinct channels and Hermes sessions. A separate real Coding profile smoke verifies a repeated turn resumes the same session after the Hub restarts. `VERIFICATION.md` records the real receipt. No AG2 channel history is sent to Hermes; only the new user message is submitted.
- When connecting, the bridge uses AG2's `list_channels` and `read_wal` to reconcile addressed requests before accepting new messages. A request already answered in WAL is skipped; an admitted operation with a saved Hermes result gets its correlated reply resent without another Hermes run; a request with an unsettled ledger entry returns a status that requires explicit operator reconciliation; an unseen request on an active channel is admitted once through the durable operation ledger. The scan is capped below 500 visible channels and startup fails closed at the cap. On terminal channels, unanswered request IDs/operation IDs are rebuilt idempotently from Hub WAL into the recipient's local operational ledger; `history` on any channel in that project shows a `local-recovery:` status notice. The caller profile cannot see that notice. No execution or transfer to a new channel happens automatically. A later `open` replaces the stale channel mapping, while the AG2 WAL and local recovery notice remain available by ID to the owning profile.
- AG2 1.1.2 ships `HubClient.attach` typed for `Agent`, not a public external-runtime registration API. The pinned-tested name-only `ExternalIdentity` shim has a fail-closed `ask`. `attach_plugin=False` does not disable the default handler; the bridge replaces it immediately with `AgentClient.on_envelope`, then performs WAL recovery before the facade becomes ready. Because upstream provides no atomic external-handler attach, a small attach/handler-install race remains an upstream limitation; no agent LLM configuration is provided to the shim.

- AG2's WS implementation has a read-only `endpoint_id` property where its LinkClient protocol declares a writable attribute. A narrow documented type cast bridges this upstream typing mismatch, with actual WS tests, not invented methods.
- Released AG2 requires undeclared `watchdog` for importing `DiskKnowledgeStore` and optional `websockets` for native WS. Both are explicitly bounded dependencies here. Resolved versions: AG2 1.1.2, watchdog 6.0.0, websockets 15.0.1, httpx 0.28.1.
- AG2 disk WAL is JSONL and not transactional/crash-atomic. Native envelope `idempotency_key`/`causation_id` alone do not deduplicate execution. One hub owns each store. Clean restart hydration is tested; crash-exactly-once is not claimed.
- Authentication and peer/project grants are checked by this facade. A project label is **not** a filesystem sandbox/cwd binding. Profile directory discovery/enrollment and optional service lifecycle are supported as documented above; automatic enrollment and runtime configuration discovery are intentionally not supported.
- `peers()` exposes enrolled identities among the native list's first 50 results, not automatic live Profile discovery. No Profile config, memory backend, private memory store, SOUL, Skills or MCP is modified or copied. Coding/Architect remain on their current legacy memory backend.

## Verification

From Hermes checkout root, always use the canonical runner, with the standalone interpreter:

```sh
HERMES_PYTHON="$ENV/bin/python" scripts/run_tests.sh --file-retries 0 \
  integrations/hermes-ag2-network/tests/ -- --hermes-core-python "$CORE_TEST_ENV/bin/python" -v --tb=short
```

Tests exercise real native disk Hub, authenticated WS, invitation activation, public request/reply/history/peers, causation correlation, reply non-execution, registry/WAL clean restart, a controlled HTTP server at the external executor boundary, and separate installed hub/bridge processes. Controlled executor tests are not live Hermes receipts. See `VERIFICATION.md` for actual RED/GREEN receipts and live acceptance status.

For isolated systemd acceptance on a host with a user manager, explicitly opt in. The canonical runner sanitizes D-Bus environment, so provide the current user's runtime directory explicitly (discover it from the shell's `XDG_RUNTIME_DIR` before invoking the runner):

```sh
HERMES_PYTHON="$ENV/bin/python" scripts/run_tests.sh --file-retries 0 \
  integrations/hermes-ag2-network/tests/test_systemd_lifecycle.py -- \
  --ag2-systemd-acceptance --ag2-systemd-runtime-dir "$XDG_RUNTIME_DIR" \
  --ag2-systemd-receipt /approved/scratch/systemd-receipt.json -v --tb=short
```

Only UUID-prefixed runtime units are enabled; cleanup stops/disables those exact units, removes their temporary unit files and verifies `LoadState=not-found`/zero PIDs. The test keeps live installed units, Gateway and profile homes untouched. Without opt-in the manager test skips; the subprocess Hub-EOF regression and offline `systemd-analyze` validation still run.

Sources inspected: released 1.1.2 wheel (`ag2/network/client/{hub_client,agent_client,handlers,channel}.py`, `network/auth.py`, native disk/WS modules), official upstream docs `website/docs/user-guide/network/{distributed,agent_clients,conversation}.mdx`, and [Hermes programmatic integration](https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration). The guessed published AG2 network URLs returned 404; upstream docs include stale snippets (e.g. `ApiKeyAuth` taking a set and `attach_plugin=False` disabling the default handler). Installed released signatures and real execution, not those snippets, govern this adapter.
