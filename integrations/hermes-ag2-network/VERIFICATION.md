# AG2 ticket verification receipts

## Ticket 21 — current authorized post-reload live

Tested executable SHA `531201f68c77cd348f3d4addbd9351e40307c436`, package SHA-256
`99e693e0fc8bafe1ff9a2defa94a52ed3f9e1175b10d2032460ce7ae6468ad7e`.
Fresh actual execution after supported plugin reload: **exit 2 / blocked**, not a pass.
Full sanitized deployment/reload/live/cleanup receipt:
`evidence/live-postreload-blocked.json`; current acceptance map describes the blocker.

- Interrupted side effects inspected first: both plugins were already deployed. Existing
  protected backup contents and installed source hashes reverified; no second deployment.
  Backup root: `/home/vottak/.hermes/cache/scratch/ag2-ticket21-deploy-b546b911e41b4510a0d92682b3a976da`.
- Supported `reload_gateway_plugins(..., profile_home=...)` read back `reloaded=true`
  for both profiles, seven deferred network tools each. Gateway unchanged: PID 772,
  start-time 1197, `restart_requested=false`; no Gateway restart or core/config edit.
- Fresh Coding session `ag2-4370f928d6f550cc9226304435757b39`, Run
  `run_6bd9b60c00cc43969ad4b9f7976080d8`, terminal `completed` read back via public API.
  Actual `agent_network_ask` tool result: `ok=false`, `network request budget exceeded`.
  This is the updated client's unique 429 mapping, absent in both backed-up clients.
  Peer native WAL contains channel lifecycle only, no request/reply; Architect mapping empty.
- Actual loaded release has **no** `run_context_id` support in Runs admission or tool dispatch.
  Updated plugin forwards this kwarg only if supplied. Missing-header diagnosis is source-based,
  not captured HTTP headers. End-to-end context propagation/Architect execution remain unverified.
- All ten gates `not_run`; first consultation attempted and blocked. Multi-turn, errors,
  two projects, memory, Hub/Bridge restart/history and idle were not reached. Executor's
  additional step-10 queued-Run-discovery blocker is preserved; no criteria weakened.
- Cleanup independently read back: owned PIDs 74551/74533/74508 absent, temporary credentials
  absent, ports 8766/8767 free, `held=[]`, no memory canaries attempted, protected profile
  config/.env/SOUL hashes unchanged, backend `file`, health HTTP 200, active Runs/agents zero
  at final operator control-socket readback (not a timed idle-acceptance proof).
- `execution_build.dirty=true` came only from nine preserved untracked repair logs; all
  executable package/plugin files were verified byte-equal to the tested commit. No code
  edits/tests rerun in this evidence-only follow-up; no slow local suite, push or issue closure.
  Independent review is parent's responsibility; no new independent pass claimed.
- New scope requires operator approval: compatible Gateway/core deployment (admitted Run
  context validation/binding through tool/deferred dispatch) and a separately approved
  restart/reexec; agreed authenticated queued-Run discovery/equivalent seam for full step 10.

## Ticket 21 — historical enrolled live follow-up

Exact clean live-tested source: `57d39e553ed05d5f9c5ad657f1ea611c9b0774ed`.
Branch `feat/ag2-live-acceptance-executor`. Source SHA-256:
`1616bc66be102e5f1576fb71abe69685102be0e3f20ab65a391451f813851fcd`.

- Genuine fresh execution after parent enrollment: **exit 2**, not completed. Receipt:
  `/home/vottak/.hermes/cache/scratch/ag2-ticket21-enrolled-live-receipt-03.json`;
  committed sanitized copy `evidence/live-enrolled-blocked.json`.
- Coding Run `run_5c4cee218abe4480890ff7d5bd130202`, fresh session
  `ag2-547d267875695bcfaf8ce7fc75fefadd`, completed, actual deferred `agent_network_ask`
  invocations recorded; no Architect request/reply in native peer WAL. Ten scenario steps
  remain `not_run`, first consultation attempted but blocked. Errors/two-project/restart/
  memory/idle acceptance was not reached and is not claimed.
- Actual RED regression: new public Runs/Sessions test expected deferred invocation names;
  old verifier returned only `tool_describe,tool_call`. GREEN targeted **2 passed**, including
  existing real-process controlled executor; full standalone **28 files, 128 passed,
  0 failed, 1 skipped**, 44.1 s, zero retries. Same PM/canonical commands below plus
  `test_live_run_readbacks.py`. Scoped health/Ruff **0 blocking, 0 advisory**; ty passes.
- Installed Coding/Architect plugin client files are identical legacy copies, SHA-256
  `f2f5d61b2476b38fe5fb85d4ff8253e69a543ba90d918d3d6612149908daccb6`.
  Both lack Run-context forwarding and HTTP-429 mapping. Current public ToolAPI refuses
  missing-context nested work while Coding is active. The likely 429 is inferred from this
  contract, not captured live HTTP evidence; first class-only 502 probe recorded no 502.
  Diagnostic instrumentation was removed; no runtime plugin/Gateway/config repair occurred.
- Cleanup readback: owned PIDs 525154/525147/525125 absent; temporary `.key` files absent;
  no memory canaries written; `held=[]`; durable state retained at
  `/home/vottak/.hermes/cache/scratch/ag2-ticket21-enrolled-live-state-03`.
  Original configs unchanged, both backends `file`; `/health` HTTP 200. Earlier attempts'
  fresh states/receipts `-01`, `-02` also retained and owned processes reaped.
- Remaining blocker: operator-authorized deployment of current plugin/context-compatible
  runtime, followed by a new genuine complete acceptance. No push or issue closure.
  Parent owns independent review, including this two-file code delta; review not claimed here.

## Ticket 21 executor — historical pre-enrollment verified source

Exact tested source commit: `d7c2bebe6c031cbbdf9faff5db716babeb01d0f0`, implementation branch
`feat/ag2-live-acceptance-executor`, base `122e97644ff6cd688d1d61c6deb0a305e1288089`.
The later evidence-only commit does not change executable source. See [ACCEPTANCE_MAP.md](ACCEPTANCE_MAP.md).

Final canonical results on this exact clean source, zero retries:
- Complete standalone suite: **27 files, 127 passed, 0 failed, 1 skipped**, 49.1 s.
- Relevant Hermes regressions: **5 files, 273 passed, 0 failed, 3 Windows-only skips**, 56.9 s.
- Scoped code health/Ruff: **0 blocking, 0 advisory**. Scoped ty: **All checks passed**.
- Actual `--execute`: exit **2**, both authenticated Sessions probes HTTP **200**, schema
  `list.data`; explicit bridge enrollment missing for `architect,coding`; `mutations=[]`,
  `runs=[]`, all ten live steps `not_run`. Both real backends `file`, configuration hashes unchanged.

Committed verbatim sanitized tool logs and machine-readable totals are under `evidence/`:
`standalone.log`, `core.log`, `static.log`, `types.log`, `verification.json`, `live-blocked.json`.
The live receipt records clean Git SHA and package source SHA-256. Controlled process fixtures
exercise the whole executor using actual Hub/Bridge processes and synthetic HTTP model actions;
**they do not replace a missing live Hermes/model receipt**.

Commands (source checkout; disposable PM environments, no live environment mutation):
```sh
NET=/home/vottak/.hermes/cache/scratch/ag2-live-executor-tests-env-02/bin/python
CORE=/home/vottak/.hermes/cache/scratch/ag2-live-core-tests-env-03/bin/python
# NET built through pm.operations.build_environment(groups=["test"]).
# CORE built through PM with groups=["dev", "test"], extras=["slack"] (aiohttp API fixtures).
HERMES_PYTHON="$NET" scripts/run_tests.sh integrations/hermes-ag2-network/tests/ \
  -q --tb=short --file-retries 0 -- --hermes-core-python "$CORE"
HERMES_PYTHON="$CORE" scripts/run_tests.sh tests/test_dispatch_session_id.py \
  tests/gateway/test_api_server_run_context.py tests/gateway/test_api_server_runs.py \
  tests/hermes_cli/test_profiles.py tests/agent/test_memory_store_v2.py \
  -q --tb=short --file-retries 0
"$CORE" scripts/check --only health,ruff --base 122e97644ff6cd688d1d61c6deb0a305e1288089
# ty uses --python <NET environment> --project integrations/hermes-ag2-network
# and the changed acceptance/replay source and fixture files, --output-format concise.
```

TDD console receipts: Sessions shape/HTML diagnosis RED (2 failures), executor public contract
RED (3 failures), completed-operation replay RED (different native envelope/causation IDs).
The replay defect was repaired without new Hermes Runs or duplicate WAL messages; altered input
and cached-artifact corruption preserve `ExecutionUncertain` semantics. Existing-state credentials
and invalid evidence-output paths are guarded before mutation. Fixture reuse moved to conftest,
not test-module imports. An initial runtime-only Python lacked pytest; a first core environment
lacked aiohttp. These setup failures were corrected with isolated PM builds, not pip or live repair.

Historical hosted full-suite evidence: [run 38378874280](https://github.com/TaKada123/Hermes-workspace/actions/runs/38378874280),
SHA `122e97644ff6cd688d1d61c6deb0a305e1288089` (**does not cover new code**). Parent artifact
analysis: 57,206 passed, 90 failed, 761 skipped plus 12 fixture ERRORs omitted from runner totals;
missing upstream workflow snapshots/Nix paths and existing design-router resolver violations are
baseline. No unrelated fixes, slow local full suite, push, issue closure or current-source hosted
CI was performed. Independent parent Standards + Spec review remains pending. **Live #21 blocked.**


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

Profile-scoped plugin copies/configuration and distinct owner-only tool API credentials are in place for Coding and Architect, as authorized. The Gateway was not restarted; it reloaded the plugin and deferred the new tool schema to fresh sessions, which the live run used. Temporary Hub/Bridge processes were stopped after verification. Until ticket #20 installs/starts the optional services, the enabled network tools will report the bridge unavailable. Ticket #18 is complete: review passed, commit `e98dd057` is on the integration branch, and issue #18 is closed; no push or main change occurred.

## Ticket 19: pre-independent-review receipts (superseded acceptance assessment)

Current local receipts are from `/home/vottak/Проекты/Hermes-workspace-wt/ag2-network-bridge`, branch `feat/ag2-network-bridge`, uncommitted work on base `e98dd05728e2a3d09d9a2e26d5d21edc6c6f83c3`. They do not claim remote CI or new live-model E2E acceptance.

### Deadline diagnosis: actual RED → GREEN

The original `test_propagated_deadline_holds_timed_out_run_without_reposting` passed in isolation and in a 12-worker baseline run during this follow-up; its exact historical failure was not reproduced. Its 0.2-second wall-clock bound violated the project's timing-test policy. A deterministic public-seam regression, `test_caller_deadline_after_admission_is_uncertain_and_retry_does_not_execute`, first failed with **TimeoutError** at `Network.ask` after the executor's admission event. Command:

```sh
HERMES_PYTHON=/home/vottak/.hermes/cache/scratch/ag2-ticket18-env/bin/python \
  TMPDIR=/home/vottak/.hermes/cache/scratch scripts/run_tests.sh -j2 --file-retries 0 \
  integrations/hermes-ag2-network/tests/test_safety_limits.py -k caller_deadline --tb=short
```

Actual RED: **1 failed, 7 deselected**, exit 1; `/home/vottak/.hermes/cache/scratch/ag2-ticket19-caller-red.log`. Converting post-submission timeout to `ExecutionUncertain` exposed a second actual failure: a late status from the first delivery incorrectly satisfied the retry waiter and failed causation validation. Per-operation reply queues now discard receipts for other delivery IDs and await the exact posted request's `causation_id`. Final targeted GREEN: **1 passed, 7 deselected**, exit 0; `ag2-ticket19-caller-green.log` in the same scratch directory. The regression keeps the assertion that the operation executes once.

The HTTP deadline fixture now uses a 2-second recipient cap and 5-second caller cap, following the project's minimum wall-clock bound; it still requires `ExecutionUncertain` on both attempts and exactly one admitted HTTP Run POST. A second parameter closes the HTTP connection after admitting the Run but before returning its ID: this uncertain submit also stays held, with no second POST. The reconnect test's former `(ExecutionUncertain, TimeoutError)` allowance was tightened to **ExecutionUncertain only**.

### Current canonical verification

```sh
HERMES_PYTHON=/home/vottak/.hermes/cache/scratch/ag2-ticket18-env/bin/python \
  TMPDIR=/home/vottak/.hermes/cache/scratch scripts/run_tests.sh -j2 --file-retries 0 \
  integrations/hermes-ag2-network/tests/ --tb=short

HERMES_PYTHON="$PWD/.venv-network-tests/bin/python" \
  TMPDIR=/home/vottak/.hermes/cache/scratch scripts/run_tests.sh -j4 --file-retries 0 \
  tests/test_dispatch_session_id.py tests/gateway/test_api_server_run_context.py \
  tests/gateway/test_api_server_runs.py tests/hermes_cli/test_profiles.py \
  tests/agent/test_memory_store_v2.py --tb=short
```

- Complete standalone integration suite: **12 files, 23 passed, 0 failed**, no retries. Actual output: `/home/vottak/.hermes/cache/scratch/ag2-ticket19-integration-final.log`.
- Core regression slice: **5 files, 273 passed, 0 failed, 3 Windows-only skipped**, 47.3 seconds. Actual output: `/home/vottak/.hermes/cache/scratch/ag2-ticket19-core-final.log`.
- Final repeat of the three dispatch/API-run regression files with `-j2 --file-retries 0`: **78 passed, 0 failed**, 27.6 seconds; `ag2-ticket19-run-context-final.log` in scratch.
- Before adding the second memory-config parameter, the corrected suite also passed with **12 workers: 22 passed, 0 failed**, no retries (`ag2-ticket19-integration-stress.log`). This is a separate stress receipt, not the final suite count.
- Initial use of the old `ag2-session-lineage-env` failed collection because its editable package pointed at a different worktree. It was not counted as a test verdict; the commands above use the interpreter verified to import this checkout.

### Pre-review evidence (does not establish AC4/AC5; see follow-up below)

| Ticket criterion | Current evidence |
| --- | --- |
| Simultaneous projects have disjoint sessions and controlled history | `test_projects_have_disjoint_channels_sessions_and_history_access`: concurrent distinct channels/session IDs; peer/project grant denial; foreign Hub history denied. |
| Same operation does not run twice, including reconnect and uncertain submit | Saved-result reconnect replay, unsettled reconnect, caller-deadline retry and HTTP lost-submit-response tests; same scoped ID retains one execution/Run POST. |
| Potentially executed interrupted work is not automatically resubmitted | Held ledger survives retries/reconnect; terminal-WAL recovery does not execute stranded work; HTTP queued deadline and lost response both produce held status. |
| Auth, allowlists, hop/turn/concurrency and timeout limits | Tool API/plugin authorization tests; project grants; nested-cycle and hop/turn tests; pending-cap rejection and serialized execution; deadline regressions. |
| Backend settings and private stores remain unchanged | Private-profile fixture runs with both `memory.backend: file` and `sqlite_v2`; configuration, MEMORY.md, USER.md and SQLite sentinel bytes remain unchanged, absent from WAL/ledgers/history. Core SQLite V2/profile regressions pass. Read-only live config lookup plus the canonical `resolve_memory_backend` returned `coding=file`, `architect=file`; no live private stores were read or copied. |

Opaque `run_context_id` remains separate from session-scoped `task_id`; API-run binding/restoration and handler dispatch are covered by the core slice. Core header parsing/context propagation is generic to authenticated Runs, not an import of the bridge. Stable caller-supplied operation IDs are required; conflicting input under a reused scoped ID is refused.

### Static checks and review boundaries

```sh
PATH="$PWD/.venv-network-tests/bin:$PATH" .venv-network-tests/bin/python scripts/check \
  --only health,ruff --base e98dd05728e2a3d09d9a2e26d5d21edc6c6f83c3
.venv-network-tests/bin/python -m ruff check integrations/hermes-ag2-network
.venv-network-tests/bin/python -m ty check \
  --python /home/vottak/.hermes/cache/scratch/ag2-ticket18-env \
  --project integrations/hermes-ag2-network integrations/hermes-ag2-network/src \
  integrations/hermes-ag2-network/tests --output-format concise
```

All scoped checks passed. The working-tree health ratchet reports **0 blocking, 0 advisory** against the stated base. Both working-tree and staged `git diff --check` passed. The complete `scripts/check --base <same base>` was also run and failed on unrelated existing findings: BOM-intolerant read at `agent/memory_downgrade.py:207`, literal system-temp paths at `docs/memv2-integration-report.md:11,79`, and the profile-archive guard scanning `.venv-network-tests/.../dateutil-zoneinfo.tar.gz`. No suppression or unrelated file edits were made; actual output is `ag2-ticket19-check-baseline.log` in scratch.

The full previous two-axis review was retrieved from session `20261011_194919_fb6b15`, message 19247. Its claimed unchecked criteria at VERIFICATION lines 9–20 refer in fact to the ticket source, not this receipt document; the ticket/remote checkboxes remain intentionally unchanged pending final acceptance. Fresh read-only backend evidence above addresses the historical-only verification concern. The Standards objection about in-tree third-party integration placement remains a policy decision: `CONTRIBUTING.md:88–107` requires a separate plugin repository. This follow-up neither invents an exception nor moves/deletes the existing integration; final review must resolve that placement question. The data-clump/shotgun-surgery observations remain judgement calls, not verified behavior defects.

No live profiles, backend flags, private memory stores, credentials, existing sessions, Gateway, services or runtime configuration were changed. No commit, push, PR or issue mutation was performed. Remote workflow inspection returned only the existing import/MEMV2/Dependabot workflows and **no runs on `feat/ag2-network-bridge`**; the local AG2 workflow has not been published. GitHub CI on these uncommitted changes cannot run without an authorized publication step. The monorepo full suite is not claimed; final independent review, placement decision, commit and remote CI remain outstanding.

## Ticket 19: prior independent-review correction — pre-transport-cap evidence

Scope: same worktree and unchanged HEAD `e98dd05728e2a3d09d9a2e26d5d21edc6c6f83c3`.
The complete available review logs `deleg_80d3734c/task-0.log` and `task-1.log`, spec,
ticket and root/test/plugin guides were read. Their embedded tool-output summaries are
truncated by the original logger; no fuller review text is invented here. Existing dirty
changes were preserved. No core runtime code, live home/profile, secret or memory was
modified by this correction; no commit, push or issue mutation was performed.

### Tight feedback loops and actual failures

Matt `tdd` + `diagnosing-bugs` at the already agreed public Network/ToolAPI, HTTP Run,
and production memory store/config boundaries:

- Retained-context RED, before its fix: canonical `test_retained_context.py` failed
  **DID NOT RAISE NetworkBudgetExceeded** on a foreign supplied context immediately
  after an uncertain execution. Receipt `ag2-review-retained-red.log`; GREEN
  `ag2-review-retained-green.log`. Context cleanup in `finally`, await-only serialization,
  and accepting supplied IDs while idle were the verified causes. Held request/context
  metadata now persist and fresh admissions fail closed until explicit terminal readback.
- Branching RED, before its fix: `test_shared_bounds.py` failed **DID NOT RAISE
  NetworkBudgetExceeded** inside the root executor after a child and grandchild spent
  three turns; the caller subsequently timed out. Receipt `ag2-review-branch-red.log`.
  Copied descendant balances, not an independent shared debit, were the cause. GREEN
  `ag2-review-branch-green-final.log`: only profiles `a`, `b`, `c` execute for a three-turn
  tree; a second root branch is refused.
- Global admission has a separate red-capability **negative control**, not a claimed
  historical pre-fix TDD run. A scratch-only copy of `admission.py` removed exactly the
  global capacity check; the different-profile public seam then failed **DID NOT RAISE
  NetworkBudgetExceeded**. `ag2-review-global-negative-control.diff` proves the mutation;
  `ag2-review-global-negative-control.log` is RED, and the unchanged production source
  passes in `ag2-review-global-positive-control.log`. The production worktree was not
  mutated for this control. Separate Hub plus two CLI bridge processes additionally
  prove the second profile cannot POST a Run while the first is live/uncertain, including
  first-bridge disconnect/reconnect (`test_shared_bounds.py`).
- The initial global-process fixture blocked an in-process Hub's event loop during
  synchronous child readiness: `ag2-review-bounds-http.log` failed CLI readiness. It was
  corrected to a separate Hub process; no timeout bound/assertion was weakened.
- Replacing the generic SQLite sentinel with the real store initially failed because
  the standalone interpreter lacks core `ruamel.yaml` (`ag2-review-integration-first.log`).
  A custom pytest `--hermes-core-python` option now runs the owning fixture in the existing
  PM-built core interpreter. The canonical runner requires an explicit `--` before this
  custom option; the first missing-separator attempt is `ag2-review-memory-first.log`.
- Reopening V2 for each fixture request changed its own SQLite transaction metadata;
  the strict private-store byte assertion failed (`ag2-review-memory-green.log`, despite
  that early filename). The fixture now keeps one actual owning runtime/store alive
  throughout the bridge scenario, matching a session-start snapshot. Both file and V2
  pass **without dropping the byte assertion** (`ag2-review-memory-green-final.log`).

All receipt names above resolve under `/home/vottak/.hermes/cache/scratch/`.

### Final commands and results

```sh
HERMES_PYTHON=/home/vottak/.hermes/cache/scratch/ag2-ticket18-env/bin/python \
  TMPDIR=/home/vottak/.hermes/cache/scratch scripts/run_tests.sh -j2 --file-retries 0 \
  integrations/hermes-ag2-network/tests/ -- \
  --hermes-core-python "$PWD/.venv-network-tests/bin/python" --tb=short

HERMES_PYTHON="$PWD/.venv-network-tests/bin/python" \
  TMPDIR=/home/vottak/.hermes/cache/scratch scripts/run_tests.sh -j4 --file-retries 0 \
  tests/test_dispatch_session_id.py tests/gateway/test_api_server_run_context.py \
  tests/gateway/test_api_server_runs.py tests/hermes_cli/test_profiles.py \
  tests/agent/test_memory_store_v2.py --tb=short

PATH="$PWD/.venv-network-tests/bin:$PATH" .venv-network-tests/bin/python scripts/check \
  --only health,ruff --base e98dd05728e2a3d09d9a2e26d5d21edc6c6f83c3
.venv-network-tests/bin/python -m ruff check integrations/hermes-ag2-network
.venv-network-tests/bin/python -m ty check \
  --python /home/vottak/.hermes/cache/scratch/ag2-ticket18-env \
  --project integrations/hermes-ag2-network integrations/hermes-ag2-network/src \
  integrations/hermes-ag2-network/tests --output-format concise
```

- Full integration: **14 files, 31 passed, 0 failed**, 37.7 seconds, zero retries;
  `ag2-review-integration-final-receipt.log`. The runner's `~25` is a static discovery
  estimate, not the actual parametrized total; the terminal summary is 31.
- Relevant core: **5 files, 273 passed, 0 failed, 3 Windows-only skips**, 42.3 seconds;
  `ag2-review-core-check.log`. Core code was not changed after that run.
- Ruff, ty, health pass; health **0 blocking, 0 advisory**, untracked files included;
  `ag2-review-static-verified.log`. Initial nullable-pipe ty errors were fixed by local
  narrowing, not suppressed. `git diff --check` and `git diff --cached --check` pass.
- Full root check still fails only on previously recorded BOM read, two literal system-temp
  paths, and the existing environment's dateutil archive. Receipt
  `ag2-review-baseline-check-check.log`. No unrelated fixes or exemptions were added.

### What the corrected evidence establishes

- An actual queued HTTP Run survives timeout independently of the bridge await. Its
  context/ancestry and observed Run ID remain held across bridge reconnect. Unknown,
  stale and missing supplied contexts cannot turn into fresh roots or join another Run.
- Explicit GET-only reconciliation refuses live work and releases completed or unsuccessful
  terminal work. Completed results are cached; unsuccessful terminal operations remain
  non-retryable. Tests cover `completed`, `failed`, `cancelled`, `interrupted`, fresh work
  afterwards, and another reconnect without reviving a terminal hold.
- A same-host shared SQLite authority, not per-profile counters, atomically debits descendant
  turns and caps active/uncertain admissions across controlled participants/processes.
  CLI requires `--control-db`; all participants use the same file and `max_active` value.
- AC5 uses `load_on_disk_store()` with the actual temporary config, asserts the selected
  `MemoryStoreV2` type, seeds/recalls real typed V2 entries, loads its session-start snapshot,
  and serves the bridge execution scenario from that owning process. Config and all private
  store/projection/sidecar bytes remain identical during bridge activity; private fixture
  contents are absent from response/history/Hub/ledgers/**shared admission DB**. This is a
  deterministic production-store fixture, not live-model acceptance or a generic facts table.
- `X-Hermes-Task-Id` had no consumer and was removed from client signature, validation,
  handler forwarding, header construction and nested tests. Generic core `task_id` remains
  untouched for terminal/browser continuity. Only the consumed opaque Run-context header
  is forwarded by this plugin.

### Limits / still not a closure receipt

- At this preceding review, shared authority bounded only Hermes admissions. Reviewer
  `deleg_ac8ea8d8/task-1.log` then demonstrated that controlled `Network.send` still appended
  five requests while capacity was held. That material spec-line-45 gap is corrected by
  the final transport-cap receipt below. Same-host cooperation remains the supported scope;
  neither arbitrary native traffic nor a fictional multi-host semaphore is claimed.
- Missing Run ID after lost submit response/crash remains fail-closed and needs authenticated
  owning-runtime/operator evidence. `reconcile()` cannot discover that ID via its current
  GET-by-ID seam; it does not resend. Crash gaps across the two bookkeeping databases can
  leave safe but orphaned leases. There is no automated orphan repair or CLI/ToolAPI
  reconciliation command in this slice; the explicit seam is `Network.reconcile()`.
- No new live profile/model run or remote Actions run occurred. Remote CI must use the
  parent-approved publication path after re-review. The workflow now passes the explicit
  core fixture interpreter. The complete monorepo suite is not claimed.
- Separate-plugin-repository placement is a **baseline** policy conflict predating #19;
  this ticket did not create the existing integration. It was neither moved nor granted
  an invented exception. Final Standards/Spec review and the parent acceptance decision
  remain required; no issue checkbox/closure is claimed.


## Ticket 19: final controlled-transport correction — current local receipt

Worktree `/home/vottak/Проекты/Hermes-workspace-wt/ag2-network-bridge`; unchanged HEAD
`e98dd05728e2a3d09d9a2e26d5d21edc6c6f83c3`. Both final reviewer logs
`deleg_ac8ea8d8/task-{0,1}.log` and the actual scratch transport probe were read. Their
embedded summaries are truncated by the logger; no missing review text is invented.
Matt `tdd` / `diagnosing-bugs` were used at the agreed public Network/native transport
and ToolAPI seams. Spec text and architectural placement were not changed.

### Actual RED → GREEN and lifecycle behavior

- Before implementation, the probe-derived crossparticipant regression failed
  **DID NOT RAISE NetworkBudgetExceeded** on its first saturated `send`. Canonical runner
  `-j1 --file-retries 0 .../test_transport_bounds.py --tb=short`, exit 1, receipt
  `ag2-final-transport-red.log`. Its final completed/failed reconciliation variants pass:
  five other-participant sends are refused before WAL append, history has no new requests,
  and only the originally held operation executed. Authenticated terminal reconciliation
  then permits fresh work without ever re-executing the held operation.
- The original unmodified reviewer probe was also rerun after the fix. Its expectation
  that five sends succeed is now invalid: it stops at **line 25, first additional send**,
  with `NetworkBudgetExceeded: Global controlled network capacity is full`. Expected
  negative probe exit 1 is recorded in `ag2-final-reviewer-probe-after.log`; it is not
  counted as a passing suite. The corrected behavioral regression is GREEN.
- SQLite reserves controlled pending transport **before native submission**, atomically
  with a fresh root's interaction metadata. Saturated sends and local validation failures
  do not grow WAL or create root-budget rows. Occupancy is the union of transport and execution context IDs,
  so converting a submitted request to a Hermes admission does not double-count a slot.
  `max_active` remains common to all cooperating participants; shared pending capacity is
  the strictest enrolled `max_pending`, cannot be lowered below current outstanding work,
  and does not expand when a participant disconnects.
- A real native ACK with an offline recipient retains capacity across caller reconnect.
  Identical pending/uncertain retries are refused locally, not appended as more requests.
  Recipient recovery executes unseen work once; terminal reply/refusal releases the exact
  transport token. Replies/status bypass request admission so completion can make progress.
- AG2 1.1.2 **always replaces supplied envelope IDs**. The first implementation discovered
  empty-ID uniqueness failures, then unreleased reservations when using a proposed ID.
  Receipts `ag2-final-transport-first-green.log`, `ag2-final-integration-first.log` and
  `ag2-final-integration-second.log` are actual intermediate failures, not acceptance.
  A separate UUID `transport_id` now crosses request/receipt metadata; late receipts cannot
  release a newer reservation. Reconnect scans durable terminal receipts for cleanup.
- Completion, definite pre-execution refusal (including payload conflict and no executor),
  and authenticated terminal Run readback release protection appropriately. Uncertain
  submit, lost ACK, deadline, cancellation, unsettled status and disconnect retain it.
  Terminal unsuccessful operations remain non-retryable; their later status does not leak
  another transport slot. Admission bookkeeping failure before executor invocation releases
  its execution lease, while uncertain transport remains fail-closed.
- A lost-ACK fixture actually posts through native WS/disk, then withholds only the ACK.
  The two-second submission deadline returns `ExecutionUncertain`, blocks fresh work, and
  retry leaves exactly one WAL request. This is explicit fault injection, not a fabricated
  Hub response or live Hermes/model acceptance.
- Saturation rejects immediately instead of waiting for a nested parent's slot. Two root
  operations at capacity one complete despite refused child calls; no child request is
  persisted. The existing branching-turn and recursive-cycle regressions still pass.
- Allowlisted structured cause/remediation survives remote rejection, `Network.ask`, history
  and ToolAPI: global capacity, pending capacity, held profile, stale context and absent
  executor are distinguished. Arbitrary exception text stays private. The nested-cycle
  API regression now checks the specific stale-context cause rather than the former
  identical generic error. The held-retry history assertion is strengthened to one request
  plus status, since retry is no longer transported.
- Privacy fixture uses reader threads plus `Queue.get(timeout=30)` instead of POSIX-only
  `select` on pipes; stderr is drained concurrently and child shutdown is bounded. The
  real file/V2-store privacy and byte-preservation assertions are unchanged. Native Windows
  execution was not performed by this worker; portability is not claimed as Windows E2E.

### Verified commands/results

All receipts below are under `/home/vottak/.hermes/cache/scratch/`.

```sh
HERMES_PYTHON=/home/vottak/.hermes/cache/scratch/ag2-ticket18-env/bin/python \
  TMPDIR=/home/vottak/.hermes/cache/scratch scripts/run_tests.sh -j4 --file-retries 0 \
  integrations/hermes-ag2-network/tests/ -- \
  --hermes-core-python "$PWD/.venv-network-tests/bin/python" --tb=short

HERMES_PYTHON="$PWD/.venv-network-tests/bin/python" \
  TMPDIR=/home/vottak/.hermes/cache/scratch scripts/run_tests.sh -j4 --file-retries 0 \
  tests/test_dispatch_session_id.py tests/gateway/test_api_server_run_context.py \
  tests/gateway/test_api_server_runs.py tests/hermes_cli/test_profiles.py \
  tests/agent/test_memory_store_v2.py --tb=short
```

- Complete integration: **15 files, 39 passed, 0 failed**, 18.5 seconds, zero retries;
  `ag2-final-integration-repeat-final.log`. Prior complete `-j2` run also passed **39**, in
  31.1 seconds (`ag2-final-integration-final.log`). The added transport file has **8** actual
  parametrized cases; static discovery estimates are not acceptance totals.
- Relevant core: **5 files, 273 passed, 0 failed, 3 Windows-only skipped**, 42.5 seconds;
  `ag2-final-core-final.log`. No core code was changed by this correction.
- Scoped health/ruff against the stated base, standalone ruff, ty against the actual isolated
  interpreter, explicit Windows-footgun scan of all ten code/test files changed by this
  correction, and both working-tree/staged `git diff --check` pass. Health: **0 blocking,
  0 advisory**; `ag2-final-static-current-final.log`. Two missing write encodings in the
  touched separate-process fixture were corrected, not suppressed.
- Bare Windows-footgun invocation checks the **stale staged versions**, and reported five
  findings in staged CLI/test_cli code; `ag2-final-static-final.log`. Those staged versions
  were not overwritten or staged by this worker. `--diff <HEAD>` scanned **zero files**
  because HEAD is unchanged: `ag2-final-current-footguns-diff.log` is explicitly **not**
  a current-working-tree audit. The explicit ten-file scan above is the current receipt.
- Full root `scripts/check --base <same base>` still fails on the existing BOM-intolerant
  `agent/memory_downgrade.py:207`, literal system-temp references at
  `docs/memv2-integration-report.md:11,79`, and the existing `.venv-network-tests` dateutil
  archive. `ag2-final-root-baseline-final.log`. No check was weakened or exemption added.

### Lifecycle assessment / remaining limits

The reviewed normal lease lifecycle is bounded and fail-closed, including async sends,
reconnect, nested refusal and terminal failure. The independent separate-Hub/two-bridge
process regression now also asserts that saturated async send and ask leave **no request**
in the other project's WAL and no Hermes Run POST. It uses the same shared authority as
callers in distinct directories/participants, not a per-process semaphore.

Crash gaps across the operational ledger and shared authority are still not a distributed
transaction: reservation-before-POST with no WAL, saved result/terminal evidence before
release, or lost Run-ID persistence can leave **safe orphan leases**. A durable terminal
receipt closes its corresponding release gap on reconnect, but unprovable orphan work is
not expired, resent or silently freed. `Network.reconcile()` requires a held context and
recorded/authenticated Run evidence; no automatic orphan repair or CLI/ToolAPI reconciliation
command is claimed. Operators must not delete the authority to evade these protections.
The strictest pending policy persists; increasing it requires an explicit coordinated
operator policy change, not disconnecting a stricter participant.

Existing unrelated dirty files, including `website/docs/developer-guide/plugins/index.md`,
were preserved and remain visible in git status. No live profile/config/store/credentials,
Gateway, service, third-party source, core file, spec, commit, index, push or remote issue was
modified by this correction. No new live-model or Actions run occurred. Same-host controlled
transport is the verified scope; arbitrary native traffic/multi-host coordination are not
requirements invented here. Final parent review/publication/Actions and acceptance remain
outstanding; no full-monorepo-suite or issue-closure claim is made.

## Ticket 20: discovery/enrollment and real systemd lifecycle receipt

Local worktree `/home/vottak/Проекты/Hermes-workspace-wt/ag2-network-bridge`, branch
`feat/ag2-network-bridge`, HEAD `43ce468fad15f425e4e10c1ebcadc8bcfcc430e2` plus
uncommitted changes. This receipt covers local ticket slice 05 / GH #20 criteria 3–5.
Its blocked-by `2` means slice 02 / GH #17 session lineage, not GH #2 memory.
Artifact acceptance is owned by a concurrent worker and is **not declared complete here**.
No commit, index change, push, issue mutation, live Gateway/service/profile/config/secret
or private-memory change was performed by this lifecycle worker.

### Behavior and actual defect found

- Discovery now includes the root `default` profile and resolves named-profile
  `HERMES_HOME` to its owning root; CLI `--home` works consistently for discovery and
  bridge startup. Only directory names are inspected; enrollment is explicit.
- Managed `profiles --revoke NAME` is idempotent. Enrollment writes user-owned `0600`
  JSON names under a `0700` directory, POSIX flock, atomic replacement and file/directory
  fsync. Eight concurrent CLI enrollments retain every name. Insecure files and symlink
  directories/files are rejected. Revocation prevents bridge startup before DB/network work;
  already-running bridges still require explicit stop/disable.
- The first real systemd outage regression was **RED: 1 failed**, 41.78 seconds: after
  SIGKILL of the Hub, systemd restarted the Hub but the existing bridge PID stayed alive
  and never reconnected. `Restart=always` alone cannot repair a process waiting only for
  a signal. CLI now observes the pinned AG2 1.1.2 receive task (upstream has no public
  disconnect notification), exits nonzero on WS EOF, and lets systemd reconnect. It does
  not poll registry RPCs or initiate idle Hermes Runs.
- Real user-manager GREEN uses UUID-prefixed runtime units, the installed standalone
  executable, temporary state/enrollment/credentials, the packaged sandbox/restart
  policies, real native AG2 Hub/WS, and a controlled authenticated HTTP runtime.
  A bridge SIGKILL is restarted; a saved operation is replayed without a second Run POST.
  Hub SIGKILL changes both Hub and bridge PIDs, then a fresh operation reuses the same
  channel/session origin and observes the fixture's continuation rotation. Exactly **two**
  HTTP Run POSTs occurred (before and after outage), not three.
- `disable --runtime --now` readback shows both units inactive/disabled with PID zero;
  they remain stopped beyond the three-second restart delay with no additional Run POST.
  Cleanup removes the exact runtime unit files and enablement, reloads the manager,
  and verifies both targets `LoadState=not-found`. A separate subsequent exact-target
  readback also returned `not-found`, `inactive`, `MainPID=0` for both targets.
- The former source-string lifecycle tests were replaced with offline
  `systemd-analyze --user verify` and the behavioral process/user-manager tests. README
  covers setup, custom/default roots, new specialists, key-map reload, reconnect,
  coordinated maintenance, immediate disable/revoke, rollback, and real API boundaries.

### Reproducible commands and actual outputs

```sh
HERMES_PYTHON=/home/vottak/.hermes/cache/scratch/ag2-ticket20-network-env/bin/python \
  scripts/run_tests.sh integrations/hermes-ag2-network/tests/ --file-retries 0 -- \
  --hermes-core-python /home/vottak/.hermes/installs/7d27e89e058145aa/environments/dd909b859246486aa5db98a4fe6a538c/venv/bin/python \
  --ag2-systemd-acceptance --ag2-systemd-runtime-dir /run/user/1000 \
  --ag2-systemd-receipt /home/vottak/.hermes/cache/scratch/ag2-ticket20-systemd-receipt.json -v --tb=short

PATH="$PWD/.venv-network-tests/bin:$PATH" .venv-network-tests/bin/python scripts/check \
  --only ruff,health --base 705f4062
.venv-network-tests/bin/python -m ty check \
  --python /home/vottak/.hermes/cache/scratch/ag2-ticket20-network-env \
  --project integrations/hermes-ag2-network integrations/hermes-ag2-network/src \
  integrations/hermes-ag2-network/tests --output-format concise
```

- Complete integration snapshot including the concurrent artifact tests: **20 files,
  62 passed, 0 failed, no skips, zero retries**, 32.5 seconds. This is the actual
  parametrized count, not the runner's static `~50` estimate. Receipt:
  `/home/vottak/.hermes/cache/scratch/ag2-ticket20-complete-suite.log`.
- After adding the revoked-startup gate assertion, final discovery delta: **7 passed,
  0 failed**, 7.9 seconds; `ag2-ticket20-discovery-final.log` in the same scratch directory.
- Ruff, ty and scoped health pass; health **0 blocking, 0 advisory**. Static receipt:
  `ag2-ticket20-static-final.log`. Lifecycle-owned tracked-file `git diff --check` passed.
  Whole-tree `git diff --check` separately reported trailing EOF blank lines in the
  concurrent worker's `artifacts.py` and `test_http_executor.py`; they were not edited here.
- Sanitized persisted receipt: `ag2-ticket20-systemd-receipt.json` in scratch. Final run:
  Hub PID `291606 → 291983`; bridge `291767 → 291851 → 291990`; Hub restart count `0 → 1`,
  bridge `1 → 2 → 3` (one initial startup retry). Channel
  `18ddd69596ddca29da192b430d11b573`; session origin
  `ag2-08cf49be8aa156bf871a4a0051c82e09`; two Run POSTs; saved replay made none.
- Initial manager runs skipped because the canonical runner strips D-Bus environment;
  explicit runtime-dir support corrected this. Offline unit validation initially lacked
  a runtime directory; it now uses its own temporary directory, not a live manager.
  These intermediate skips/failures were not counted as acceptance.

This is Linux real process/service acceptance with controlled HTTP execution, **not** a
new live Hermes/model acceptance run, remote CI, a full monorepo suite, or a claim of
crash-atomic JSONL WAL/exactly-once side effects. Uncertain work remains fail-closed;
missing Run IDs/orphan leases still need operator evidence. Existing slice-02 lineage
and held-operation regressions pass in the complete suite. Artifact-worker review/results,
independent final review and parent integration/publication decisions remain separate.
