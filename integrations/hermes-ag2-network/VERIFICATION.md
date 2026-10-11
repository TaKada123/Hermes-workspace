# AG2 ticket verification receipts

## Result / scope

The standalone tracer works through real native AG2 1.1.2 disk/WS/channel/WAL and the public `Network` seam. A real Coding Hermes Profile E2E now passed (receipt below). No existing user session was reused. API keys live in owner-only files under `$HERMES_HOME/agent-network/secrets/`; original `.env`/`config.yaml` snapshots are owner-only under `deployment-backup/`.

## Actual RED → GREEN

Commands ran from `/home/vottak/Проекты/Hermes-workspace-wt/ag2-real-profile`.

```sh
HERMES_PYTHON=/home/vottak/.hermes/cache/scratch/ag2-tracer-env/bin/python \
  scripts/run_tests.sh integrations/hermes-ag2-network/tests/test_network.py -v --tb=short
```

RED exit 1: `ImportError: cannot import name 'ExecutionResult' from 'hermes_ag2_network'` before facade implementation. Full actual runner output: `/home/vottak/.hermes/cache/scratch/ag2-tracer-red.log`.

GREEN exit 0: **1 passed, 0 failed**, real authenticated native disk Hub/WS request and correlated reply, explicit ACK activation, reply non-execution, stable identity and WAL after clean native Hub restart. Actual output: `/home/vottak/.hermes/cache/scratch/ag2-tracer-green.log`.

Second vertical slice at the same public seam:

```sh
HERMES_PYTHON=/home/vottak/.hermes/cache/scratch/ag2-tracer-env/bin/python \
  scripts/run_tests.sh integrations/hermes-ag2-network/tests/test_http_executor.py -v --tb=short
```

RED exit 1: `ModuleNotFoundError: No module named 'hermes_ag2_network.executor'`, actual output `/home/vottak/.hermes/cache/scratch/ag2-http-red.log`. After implementation, full current-project GREEN **2 passed, 0 failed** (`ag2-http-green.log`). The executor fixture is an actual HTTP server observing profile path, Authorization, exact Idempotency-Key and only new input/session payload; its fabricated terminal response is explicitly controlled test data, never a claimed runtime result.

Final full **standalone project** suite:

```sh
HERMES_PYTHON=/home/vottak/.hermes/cache/scratch/ag2-tracer-env/bin/python \
  scripts/run_tests.sh integrations/hermes-ag2-network/tests/ -v --tb=short
```

Exit 0: **4 files, 4 passed, 0 failed**. Actual output `/home/vottak/.hermes/cache/scratch/ag2-tracer-final-green.log`. Includes separate-process hub + bridge CLI request/reply and uncertain external execution held without automatic retry or secret-bearing exception text in the status.

## Relevant unchanged Hermes regressions

```sh
HERMES_PYTHON=/home/vottak/Проекты/Hermes-workspace-wt/ag2-network-bridge/.venv-network-tests/bin/python \
  scripts/run_tests.sh -j3 tests/gateway/test_api_server_runs.py \
  tests/hermes_cli/test_profiles.py tests/agent/test_memory_store_v2.py
```

Exit 0: **270 passed, 0 failed, 3 Windows-only skipped**, 41.6 seconds. Actual output `/home/vottak/.hermes/cache/scratch/ag2-tracer-hermes-regressions.log`. This is not a claim that the complete Hermes monorepo suite passed; only the complete standalone suite and these three core regression files were run by this worker.

## Build / static checks

PM generated an isolated standalone environment, without raw pip/uv mutation of Hermes. Exact resolved versions observed through `importlib.metadata`: AG2 1.1.2, watchdog 6.0.0, websockets 15.0.1, httpx 0.28.1, pytest 9.1.1. `pm.operations.lock_project` initially failed because inherited core's 14-day quarantine excluded AG2 1.1.2; the project's explicit `tool.uv.exclude-newer-package.ag2=false` permits only the requested release. PM then successfully locked and built the project with `groups=["test"]`.

```sh
/home/vottak/Проекты/Hermes-workspace-wt/ag2-network-bridge/.venv-network-tests/bin/python \
  -m ruff check integrations/hermes-ag2-network
/home/vottak/Проекты/Hermes-workspace-wt/ag2-network-bridge/.venv-network-tests/bin/python \
  -m ty check --python /home/vottak/.hermes/cache/scratch/ag2-tracer-env \
  --project integrations/hermes-ag2-network integrations/hermes-ag2-network/src \
  integrations/hermes-ag2-network/tests --output-format concise
/home/vottak/Проекты/Hermes-workspace-wt/ag2-network-bridge/.venv-network-tests/bin/python \
  scripts/check --only health,ruff --staged --base 1ae1f384
```

Scoped checks pass. Health permits two explicit reviewed catch-all boundary comments: class-only CLI error output prevents leaking credentials; external executor failures produce held status/ACK rather than native NACK immediate replay. No hidden suppression of unrelated findings.

The complete root `scripts/check --staged --base 1ae1f384` was attempted: unrelated baseline failures are a BOM-intolerant read in `agent/memory_downgrade.py:207` and literal system-temp paths in `docs/memv2-integration-report.md:11,79`. They are outside this project and were not changed. Initial new-code catch-all findings were resolved with the documented security-boundary reasons; scoped health/ruff then passed.

Built `hermes_ag2_network-0.1.0-py3-none-any.whl` with PM-isolated `build`/`hatchling`; inspected ZIP and metadata. Wheel has only seven `hermes_ag2_network` source modules and its dist-info, exact `Requires-Dist: ag2==1.1.2`, explicit disk/WS dependencies and an executable `hermes-ag2-network` entry point. No AG2 or Hermes source was copied. Artifact: `/home/vottak/.hermes/cache/scratch/ag2-tracer-dist/hermes_ag2_network-0.1.0-py3-none-any.whl`.

## Real Hermes Runtime E2E

Executed the published `smoke` command through the running multiplex API at `127.0.0.1:8642`, authenticated with Coding's owner-only key. The smoke created a fresh native AG2 hub/channel and a deterministic new Coding Hermes API session; it did not resume a pre-existing user session.

```json
{"live":true,"profile":"coding","channel_id":"18dd8ca736e24f0c6621c529005aa8ed","request_envelopes":1,"reply_envelopes":1,"session_id":"ag2-ea151c140929529a928c409107b7c023","run_id":"run_f339770eb477454f88526e4adaa3cb1b","run_status":"completed","runtime":{"provider":"openai-codex","model":"gpt-6-sol-900k","route_source":"global"},"tool_results":1,"sha256":"b3ed69c98444d20097dd8ce0bdf524c27e8a4fb122945be8c73e96f015f5a872"}
```

The Hermes runtime used its normal provider, tools and profile configuration; its actual terminal tool computed the expected SHA-256. The bridge read back the completed Run and exact session messages before emitting the receipt. No API key or private memory contents were emitted.

Before restart, live `gateway_state.json` reported `active_agents=0`, `active_work=null`, and the API port refused connections. Added protected API keys for `default`, `coding`, and `architect` (preserving any usable existing key); kept `.env`/`config.yaml` snapshots with mode 0600. Restarted the authorized user Gateway once; read back `/health` = 200 and confirmed only the loopback API listener on 8642. Post-smoke the Gateway remained active with `active_work=null`, `active_agents=0`. Existing memory backend settings were not changed: Coding/Architect remain legacy file memory.

## Ticket 17: restart and rotation

Canonical suite: `HERMES_PYTHON=/home/vottak/.hermes/cache/scratch/ag2-session-lineage-env/bin/python scripts/run_tests.sh integrations/hermes-ag2-network/tests/ -v --tb=short` — **9 passed across 8 test files, 0 failed**. Ruff and ty pass against that isolated environment.

The session-lineage test performs Hermes HTTP turns across a disk Hub + bridge restart, removes the caller's local channel mapping and verifies the same native channel is rediscovered, checks repeated `open` returns the same channel, checks terminal-channel replacement, and exercises two distinct projects with distinct AG2 channels and Hermes origin sessions. It deliberately reuses `operation_id=request-1` in both projects, verifying the scoped bridge ledger and Hermes idempotency keys remain independent. It also simulates Hermes rotating after the prior result while the bridge's last current-session write is lost; the next request resolves the canonical tip from the stable origin before validating the target session. The fixture models Hermes session creation, `session_exists`, in-run rotation with stale run ID, and `GET /api/sessions/<origin>/messages?limit=0`; only that tip endpoint provides the current ID. The next run resumes it. The real Hermes API contract was verified in source: `hermes_cli/web_routers/sessions.py:get_session_messages` passes the requested origin through `SessionDB.resolve_resume_session_id`; that resolver follows the compression tip and chooses the deepest message-bearing continuation. The session-lineage test models the stale-current-after-downtime case, and the live run confirmed the authenticated endpoint works for the current Coding profile.

The recovery test persists an addressed request in native AG2 WAL while the Hermes recipient is offline, restarts the disk Hub, and reconnects the bridge. WAL reconciliation executes the unseen operation once, replies with matching causation, and history contains exactly one request/reply pair. A terminal-channel test closes a channel with an unanswered request, reconnects twice, confirms the executor is never invoked, and verifies the owning profile sees one durable local-recovery notice in both the old channel history and a newly opened channel in the same project; the caller profile sees no notice. It then deletes the recipient ledger and confirms reconnect reconstructs the notice from terminal AG2 WAL. A migration test confirms legacy operation results are preserved while identical operation IDs remain independent across project channels.

A real Coding Profile E2E exercised two distinct, read-only requests through one channel across a native Hub restart. Both authenticated Hermes Runs completed, invoked the profile's terminal tool, and returned independently verified SHA-256 digests. The session ID remained the same, and the persisted AG2 WAL retained both request/reply pairs:

```json
{"live":true,"profile":"coding","channel_id":"18dd9169edd028b5755c2d16cba0081b","first_session_id":"ag2-458a674b7bef5d89a49aa89d56594c2a","second_session_id":"ag2-458a674b7bef5d89a49aa89d56594c2a","session_reused":true,"first_run_id":"run_580ea71b821e41e6a9090e24bc7ac6e0","second_run_id":"run_564b1a2732e747b5b81479b04621c66f","first_reply":"AG2-LINEAGE-V8-FIRST 0d5e0549b17d928e401142af63d0f12ddb9f53349a94ec6abff57cf9509b4ee8","second_reply":"AG2-LINEAGE-V8-SECOND 49da15659ef90fa326cc23a15401ba71f6450b5d35628df6f48b4b2709617f3a — продолжение проверки после AG2-LINEAGE-V8-FIRST.","persisted_wal_texts":4,"hub_restarted":true}
```

This is a fresh network channel/session, not an existing user conversation. The live smoke used two authorized, read-only terminal/hash prompts. It left the service configuration, profile settings and existing sessions unchanged.

## Independent review and correction

Final Standards review found no hard documented-standard breaches; remaining items are judgement-call design smells. The Spec review's recovery checks are covered by the terminal-WAL test, including reconstruction after deleting the recipient ledger, and the tip contract is confirmed from Hermes source. The review also checked operation-ID scoping and the legacy ledger migration tests. Ticket #17 was merged into `feat/ag2-network-bridge` as `67c89f75`; the main branch remains unchanged.

## Ticket 18: profile-bound Hermes network tools

TDD targeted RED/GREEN tests cover the public network/API seams. The original nested-cycle test reproduced a real timeout; the fix propagates visited-profile ancestry and rejects re-entry before posting a second network request. The loopback API tests verify bearer authentication, profile binding, allowlisted peers, correlated ask/reply/history/send, 404 for a foreign channel, and listener shutdown. The plugin test drives all five registered tools through an authenticated bridge, repeats an ask on one channel/session, and verifies a misbound profile is denied. Current targeted results: `test_nested_cycles.py`, `test_tool_api.py`, `test_plugin.py` — **1 passed each**. Ruff and ty both pass. `hermes plugins doctor` on the installed Hermes release passed for both live profile copies: **5 tools, 0 hooks**.

A real Coding profile made two completed API Runs in one newly created Coding session. In the first turn it independently chose to consult Architect; in the second it asked a follow-up through the same project channel. Native history readback verified two requests and two correlated replies, two distinct operation IDs, one unchanged Architect Hermes session, and two completed Architect runs. No transcript text or private-memory contents were copied into this receipt. The sanitized receipt is `/home/vottak/.hermes/cache/scratch/ag2-ticket18-live/receipt.json`:

```json
{"live":true,"coding_session_id":"ag2-fb461bd21d8b43418bc5ba9d06c95091","channel_id":"18dd9b4d5f313ba85f89ff7f45b630b7","coding_network_tool_calls":["agent_network_peers","agent_network_open","agent_network_ask","agent_network_ask"],"operation_ids":["ticket18-live-design-review-context-boundary","ticket18-live-design-review-context-gap-followup-20261012"],"request_count":2,"reply_count":2,"reply_session_ids":["ag2-a041939b7e13503baedccbe258685eee"],"reply_run_ids":["run_4974f46430364f1d8eae2df219184078","run_378e9a1ef64744fa95b0267df4c67dd3"],"architect_run_statuses":["completed","completed"],"correlated_pairs":true,"coding_messages_count":21,"coding_final_answer_chars":672}
```

Profile-scoped plugin copies/configuration and distinct owner-only tool API credentials are in place for Coding and Architect, as authorized. The Gateway was not restarted; it reloaded the plugin and deferred the new tool schema to fresh sessions, which the live run used. Temporary Hub/Bridge processes were stopped after verification. Until ticket #20 installs/starts the optional services, the enabled network tools will report the bridge unavailable. Ticket #18 still needs independent Standards/Spec review, fixes if any, and a commit; no push or main change has occurred.
