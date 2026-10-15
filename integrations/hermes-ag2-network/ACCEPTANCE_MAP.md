# Live Coding/Architect executor: acceptance map

## Current outcome — authorized plugin deployment and fresh post-reload live

**#21 remains blocked; no full live pass.** Exact tested executable commit:
`531201f68c77cd348f3d4addbd9351e40307c436`; package SHA-256
`99e693e0fc8bafe1ff9a2defa94a52ed3f9e1175b10d2032460ce7ae6468ad7e`.
Interrupted deployment had already updated both profile plugins with verified protected
backups. Reconciliation confirmed installed hashes and unchanged config/.env/SOUL;
no duplicate plugin writes. Supported profile-scoped `reload-plugins` succeeded for
Coding/Architect; Gateway PID 772/start-time 1197 stayed unchanged.

A new genuine `--execute` used only a fresh acceptance session. Exit **2**:
Coding Run `run_6bd9b60c00cc43969ad4b9f7976080d8` completed and called
`agent_network_open`/`agent_network_ask`, but the ask returned the updated client's
HTTP-429 mapping, `network request budget exceeded`. No Architect session/request/reply.
Actual Gateway release `memv2-20261011T130106Z` lacks Run-context header parsing/binding
and tool dispatch propagation; deploying the plugin alone cannot provide missing core
kwargs. New client behavior is demonstrated in Coding; end-to-end context forwarding
and Architect runtime behavior are **not** verified. No core/runtime repair or Gateway restart.

All ten step gates remain `not_run`: step 1 attempted, success gate blocked. Multi-turn,
two-project, error-matrix, memory, network-restart/history and idle criteria were not reached.
Independent later blocker: executor deliberately refuses full step 10 without new queued-Run
discovery; actual public Runs API has GET by known ID only. Operator control-socket idle
metrics are supplemental, not a substitute for acceptance-scoped public Run discovery.

Cleanup readback: all three owned processes absent, temporary credentials removed, ToolAPI
ports free, owning Run completed, `held=[]`, no memory canary attempted, configs/env/SOUL
unchanged, both backends remain `file`, health HTTP 200. Source was unchanged; dirty flag
came from preserved untracked repair logs. Sanitized evidence:
[`evidence/live-postreload-blocked.json`](evidence/live-postreload-blocked.json).

**Approval needed for a new scope:** compatible Gateway/core release with admitted Run
context validation/binding and propagation through tool/deferred dispatch, plus separately
authorized Gateway restart/reexec. Full step 10 also needs agreed authenticated Run discovery
or a proven equivalent public seam. No push/issue closure; independent Spec delta remains
with parent. Earlier receipts below are historical and do not supersede this result.

## Historical outcome — enrolled live follow-up

**#21 is still blocked, not completed.** Parent authorized and enrolled Coding/Architect.
Fresh genuine `--execute` on clean source `57d39e553ed05d5f9c5ad657f1ea611c9b0774ed`
returned exit 2. Coding actually called `agent_network_ask` through deferred `tool_call`,
but Architect's native WAL contained no corresponding request/reply. Installed profile
plugin clients predate #19: neither accepts nor forwards `X-Hermes-Run-Context-Id`, and
neither maps HTTP 429. Current ToolAPI safely refuses nested requests without the owning
active context. The 429 diagnosis follows the inspected contract; live HTTP status was
not captured, so it is not represented as a captured response.

Evidence: `evidence/live-enrolled-blocked.json`, `evidence/live-enrolled-diagnosis.json`.
All ten step statuses remain `not_run` because the executor stops during the first consultation;
criterion 1 was attempted but its success gate did not pass. No memory canary was written;
all three temporary processes were reaped, credential copies removed, durable state retained,
profile configs unchanged, owning backends still `file`, Gateway health HTTP 200.
Runtime plugins were not updated: authorization permits enrollment, not plugin deployment.
A parent/operator decision is required before any runtime repair or another acceptance run.

The evidence-only follow-up commit does not change executable source. Deferred-tool evidence
recognition was repaired with actual RED→GREEN at the agreed Runs/Sessions seam; standalone
suite: 28 files, 128 passed, 0 failed, 1 skip. Parent's independent review remains separate.

## Historical pre-enrollment outcome

Executor is implemented, but **#21 live acceptance remains blocked, not passed**.
Current authenticated Coding/Architect Sessions endpoints return HTTP 200 JSON with
`object=list, data=[…]`: API-shape drift, **not web HTML fallback**. Readiness now accepts
that documented schema and the previous `sessions` schema without exporting existing rows.

The current bridge enrollment catalog is empty. A real attempt stopped at Coding Bridge
startup before any Hermes Session/Run; both owned processes were reaped and temporary
credentials removed. Preflight now refuses missing enrollment before creating network state.
The owner/parent must authorize and perform enrollment; the executor does not automatically
repair runtime configuration. See `evidence/live-blocked.json` for the final exact-source
attempt and `VERIFICATION.md` for current test receipts. The older `LIVE_ACCEPTANCE.md`
content is preserved as a **historical checkpoint**, not current readiness.

## Reproduce

Use a current standalone PM-built package/interpreter (`ENV`), as in README. Source execution
sets `PYTHONPATH` explicitly so an older installed editable package cannot supply stale code.

```sh
PYTHONPATH=integrations/hermes-ag2-network/src "$ENV/bin/python" \
  -m hermes_ag2_network.live_acceptance --api-url http://127.0.0.1:8642 \
  --coding-api-key-file /home/vottak/.hermes/agent-network/secrets/coding-hermes-api.key \
  --architect-api-key-file /home/vottak/.hermes/agent-network/secrets/architect-hermes-api.key \
  --receipt /approved/scratch/NEW-readiness.json

# Only if the owning operator authorizes the missing enrollment:
"$ENV/bin/hermes-ag2-network" profiles --home /home/vottak/.hermes --enroll coding
"$ENV/bin/hermes-ag2-network" profiles --home /home/vottak/.hermes --enroll architect
# These are operator instructions, not changes performed by this implementation.

# Existing plugin settings/secrets must resolve both unused loopback ToolAPI ports.
# Both specialists must be available for this bounded test; do not interrupt user work.
PYTHONPATH=integrations/hermes-ag2-network/src "$ENV/bin/python" \
  -m hermes_ag2_network.live_acceptance --execute --home /home/vottak/.hermes \
  --api-url http://127.0.0.1:8642 \
  --coding-api-key-file /home/vottak/.hermes/agent-network/secrets/coding-hermes-api.key \
  --architect-api-key-file /home/vottak/.hermes/agent-network/secrets/architect-hermes-api.key \
  --state-dir /approved/scratch/NEW-network-state --idle-seconds 10 \
  --receipt /approved/scratch/NEW-live.json
```

Exit 0 without `--execute` means Sessions readiness only. Exit 0 with `--execute` requires
all ten steps, readbacks and cleanup checks to pass. Receipt/state targets must be new.
The exclusive receipt descriptor is fsynced before live mutations. SIGTERM/SIGINT cancellation
stops owned temporary processes without submitting new memory cleanup Runs; uncertain state
is retained. Never delete/reuse admission state to bypass held work. No Gateway restart,
systemd unit change, plugin installation, model/credential override or paid service occurs.

## Acceptance map

Agreed public seams: `agent_network`, profile-prefixed Sessions/Runs, loopback ToolAPI.
The `acceptance` control identity has **no model/executor**. It asks the actual Coding runtime
to initiate consultation. Only existing Coding/Architect profiles run models. The receipt
distinguishes the control–Coding channel from the Coding–Architect peer channel: Coding's
initiating Run resumes its fresh control-channel session, Architect its fresh recipient session.

| Criterion | Verification and receipt | Controlled coverage | Current genuine live status |
|---|---|---|---|
| 1 Coding initiates | Coding message readback contains `agent_network_ask`; exact requested operation in native peer WAL | process executor test | blocked before Run |
| 2 Architect receives AG2 | One addressed native request with operation/envelope ID | real AG2 Hub/WS/WAL | not run |
| 3 Architect uses own Runtime | Authenticated terminal Run/canonical-tip readback; correlated reply/causation ID | controlled HTTP boundary, not model proof | not run |
| 4 Coding receives/continues | Coding terminal Run plus project marker after actual nested tool reply | nested ToolAPI fixture | not run |
| 5 Second consultation | New operation, same project/channel | process executor test | not run |
| 6 Existing sessions continue | Both stable origins and native continuation tips | process executor + existing lineage tests | not run |
| 7 Independent private memory | Each owning memory tool writes own canary directly into its new network session; only own private file contains own marker | controlled file backend + actual-core V2 isolation fixtures | not run |
| 8 Hub/Bridge restart | Three owned PIDs reaped and fresh processes started with same durable state | actual separate CLI processes | not run |
| 9 History survives | Exact history, identities, channels and origin mappings before/after restart; third consultation | process executor + restart regressions | not run |
| 10 No leaks/duplicates/idle tokens | One request/reply per operation; same envelopes on completed retry; canaries absent from peer history; explicit idle counter interval | replay/held/budget/transport tests + process executor | not run |
| Errors | Bearer 401, profile 403, malformed 400, denied peer/project 403, missing channel 404 | process executor; existing deadline/cycle/lost-connection fixtures | not run |
| Two projects | Concurrent transport submissions, serialized bounded per-profile execution; distinct channels/sessions, no other project marker | process executor + admission tests | not run |
| Cleanup | Owned processes/credential copies only; exact canary removal by owning runtime after held/terminal checks; original memory bytes/config hashes | process test + existing-state/output guards | first startup-attempt cleanup verified; full live cleanup not run |
| Standards + Spec review | Independent parent review against #21/#15/fixed base | static/self-review cannot replace independent agents | pending parent |

`test_live_executor_processes.py` exercises the whole executor with real separate Hub/Bridge
processes and an explicitly **controlled HTTP owner runtime**. Its synthetic model actions
are test data at the public HTTP seam, never live Hermes/model receipts. Production has no
injected fake executor or simulated-success mode. Receipts retain public IDs, tool names,
counters and hashes, not transcripts/private memory/secrets. Only invocation-owned operational
ledgers are read for origin/current/held-Run IDs.

## Limits and safety

- Actual Coding/Architect backend flags remain unchanged. The live canary verifier supports
  their existing legacy file backend and refuses another backend without migration/private DB
  inspection. Core V2 isolation is separate fixture evidence, not a live profile migration.
- Private canaries go directly to owning Runs, **never to AG2 envelopes**. Cleanup uses the
  same fresh network-session lineage and deletes only the exact test marker. Owned network
  processes stop before cleanup, preventing queued work from starting another writer. Held or
  unsettled Runs defer cleanup to the operator. Different unrelated memory bytes block success;
  no whole-file restore overwrites concurrent user data.
- Idle proof covers all new acceptance sessions' public `api_call_count`, token/message/tool
  counters over the recorded interval. It does not prove absence of unrelated cron/user/provider
  activity. Current `/health` has no global model/Run counters; no global-zero claim is made.
- Project labels are not filesystem/cwd sandboxes. Only new acceptance sessions are submitted;
  no existing conversation is continued or modified.
- Missing Run IDs after lost submit responses remain operator-reconciliation blockers; no
  automatic replay, new credentials/model routing or live Gateway restart is attempted.
- Acceptance found a real duplicate-message gap: replay of a saved Hermes result appended
  new native request/reply envelopes. `network_replay.py` now returns the authenticated successful
  native receipt without another envelope/Run, including after restart while the receiver is
  offline. Pending/rejected/uncertain operations retain fail-closed admission. Cached artifacts
  are reverified. Payload/integrity failure stays `ExecutionUncertain`, with no fabricated new
  native status message.

## CI boundary

Historical GitHub [run 38378874280](https://github.com/TaKada123/Hermes-workspace/actions/runs/38378874280)
tests base `122e97644ff6cd688d1d61c6deb0a305e1288089`, **not this new implementation**:
focused 120 passed/1 skipped; Hermes 273 passed/3 skipped; static/type green. Completed 20-shard
canonical attempt: 57,206 passed, 90 failed, 761 skipped, plus 12 setup ERRORs omitted from runner
failed totals. Parent read-only analysis identifies missing upstream workflow snapshots, obsolete
Nix paths and pre-existing design-router resolver violations; none are repaired here. No slow
local monorepo full suite was started. Current-commit hosted CI cannot run without publication
approval; no push or issue closure is authorized. Genuine live receipts and independent reviews
remain required before declaring #21 complete.
