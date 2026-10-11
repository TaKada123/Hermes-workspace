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

Canonical suite: `HERMES_PYTHON=/home/vottak/.hermes/cache/scratch/ag2-session-lineage-env/bin/python scripts/run_tests.sh integrations/hermes-ag2-network/tests/ -v --tb=short` — **7 passed across 6 test files, 0 failed**. Ruff and ty pass against that isolated environment.

The session-lineage test performs Hermes HTTP turns across a disk Hub + bridge restart, removes the caller's local channel mapping and verifies the same native channel is rediscovered, checks repeated `open` returns the same channel, checks terminal-channel replacement, and exercises two distinct projects with distinct AG2 channels and Hermes origin sessions. The fixture models actual Hermes APIs: deterministic session create returns `session_exists` on repeat; a run rotates in-turn but returns the stale session ID; only `GET /api/sessions/<origin>/messages?limit=0` yields the new tip. The next run uses that rotated tip. A completed duplicate operation returns its recorded result and sends no extra run.

The recovery test persists an addressed request in native AG2 WAL while the Hermes recipient is offline, restarts the disk Hub, and reconnects the bridge. WAL reconciliation executes the unseen operation once, replies with matching causation, and history contains exactly one request/reply pair. A separate test continues to verify an already completed duplicate operation does not trigger another Hermes run.

A real Coding Profile E2E exercised two distinct, read-only requests through one channel across a native Hub restart. Both authenticated Hermes Runs completed, invoked the profile's terminal tool, and returned independently verified SHA-256 digests. The session ID remained the same, and the persisted AG2 WAL retained both request/reply pairs:

```json
{"live":true,"profile":"coding","channel_id":"18dd8f322e406a47fd68fa208140c903","first_session_id":"ag2-2995ac66c9355748a807717a029c122f","second_session_id":"ag2-2995ac66c9355748a807717a029c122f","session_reused":true,"first_run_id":"run_8cbe00855c0342ecbe46e274b93d7cfd","second_run_id":"run_00b0d56283254cf68246889f8fc8de53","first_reply":"AG2-LINEAGE-V4-FIRST 978f655265ebb6f63af4dff2e6e831a57229b0f83e08860dad9b8c132cf811e4","second_reply":"AG2-LINEAGE-V4-SECOND 9c3d8b0345fdcb3dfb9eb075293b8b2f8307ef1cd97dac7406d0f527e903f798 — follow-up to AG2-LINEAGE-V4-FIRST.","persisted_wal_texts":4,"hub_restarted":true}
```

This is a fresh network channel/session, not an existing user conversation. The live smoke used two authorized, read-only terminal/hash prompts. It left the service configuration, profile settings and existing sessions unchanged.

## Independent review and correction

The initial Standards-axis review found no code-standard or material security/correctness defects. The Spec-axis review identified missing stable `open` reuse and startup WAL recovery. Both are now implemented and exercised by public-network tests, including terminal-channel replacement and two-project session separation. The updated diff awaits a final two-axis review; merging remains pending. Specialist tool enrollment, project grants/budgets, artifacts and services remain in tickets 18–21.
