# Ticket 21 live acceptance

## Current implementation checkpoint

The reproducible ten-step executor is now implemented. Current HTTP 200 invalid Sessions
JSON was documented API-shape drift (`object=list, data=[…]`), not HTML fallback; readiness
passes after the correction. Actual Coding/Architect live execution remains blocked by the
empty explicit bridge enrollment catalog, before any Hermes Session/Run. Enrollment/runtime
repair, live Gateway restart and issue closure were not performed.

See [ACCEPTANCE_MAP.md](ACCEPTANCE_MAP.md) for the current executable command, complete
criterion/evidence map and limits; [VERIFICATION.md](VERIFICATION.md) for test receipts.

## Historical prerequisite-only checkpoint (superseded readiness)

The remainder preserves the earlier unreachable-runtime report and its historical commands.
Its "not implemented" and "current" wording refers only to that earlier checkpoint; old scratch
environments are not reproducibility prerequisites for the new executor.

## Outcome

The current ten-step Coding/Architect scenario **did not execute**. Both authenticated
profile Sessions endpoints at `http://127.0.0.1:8642` returned connection failures.
The read-only prerequisite probe exited **2** with `live_scenario_completed=false` and
`mutations=[]`. No old sessions or historical receipts replace this missing acceptance.
The ten-step scenario executor is **not implemented** in this checkpoint; the reusable
command below is only its fail-closed prerequisite gate.

Worktree: `/home/vottak/Проекты/Hermes-workspace-wt/ag2-live-acceptance`.
Branch: `implement/ag2-live-acceptance`, created exactly from
`1c018ed7ad7858e519e2e9757cb0f2722820a94e` (`feat/ag2-network-bridge`).

## Genuine blocker evidence

- Receipt: `/home/vottak/.hermes/cache/scratch/ag2-ticket21-live-readiness.json`.
- Both `/p/coding/api/sessions?limit=1` and `/p/architect/api/sessions?limit=1`:
  `authenticated=false`, `error_class=ConnectError`. No credentials or existing session
  contents are emitted.
- `curl --silent --max-time 5 --output /dev/null --write-out 'API health HTTP %{http_code}\n' http://127.0.0.1:8642/health`:
  HTTP `000`, exit 7.
- The inspected runtime status file reports PID `745`, `active_agents=0`,
  `active_work=null`, but systemd reported changing Gateway PIDs (`379721`, `383283`,
  `385295`, then `0`) and `NRestarts=1764`, later `1778`. The stale file **does not
  establish current IDLE**. Gateway restart/repair was not performed; the root cause
  of the service restart failures was not diagnosed by this ticket.
- No Hub, bridge or background service was created. No Gateway/profile configuration,
  plugin enrollment, backend flag, memory, SOUL, MCP, Skills or user conversation changed.

## Executed quick checks only

Matt implement-spec implementer + TDD; agreed `agent_network` seam preserved.
Read live GH #21/#15 full bodies/comments, spec, ticket 06, glossary and ADR 0003.

```sh
HERMES_PYTHON=/home/vottak/.hermes/cache/scratch/ag2-ticket20-network-env/bin/python \
  scripts/run_tests.sh integrations/hermes-ag2-network/tests/test_live_acceptance.py \
  -j1 --file-retries 0 --tb=short
# RED exit 1: missing hermes_ag2_network.live_acceptance module (collection error).

# A new standalone environment was built through pm.operations.build_environment,
# groups=["test"], from this worktree; no live environment was mutated.
HERMES_PYTHON=/home/vottak/.hermes/cache/scratch/ag2-ticket21-network-env/bin/python \
  scripts/run_tests.sh integrations/hermes-ag2-network/tests/test_live_acceptance.py \
  -j1 --file-retries 0 --tb=short
# Final GREEN: 3 passed, 0 failed, 1.7 s, no retries.
```

Logs: `/home/vottak/.hermes/cache/scratch/ag2-ticket21-readiness-{red,green,final}.log`.
The parameterized HTTP fixture tests are explicitly controlled data, not live models.
They cover both profiles' authenticated API readiness, unreachable/invalid runtime
responses, no writes, and exclusion of existing user-session metadata from receipts.

Scoped Ruff and ty passed using the existing PM development interpreter
`/home/vottak/.hermes/cache/scratch/ag2-ticket19-hermes-ci-bf74a5aa/bin/python`:

```sh
DEV=/home/vottak/.hermes/cache/scratch/ag2-ticket19-hermes-ci-bf74a5aa/bin/python
"$DEV" -m ruff check integrations/hermes-ag2-network/src/hermes_ag2_network/live_acceptance.py integrations/hermes-ag2-network/tests/test_live_acceptance.py
"$DEV" -m ty check --python /home/vottak/.hermes/cache/scratch/ag2-ticket21-network-env --project integrations/hermes-ag2-network integrations/hermes-ag2-network/src/hermes_ag2_network/live_acceptance.py integrations/hermes-ag2-network/tests/test_live_acceptance.py --output-format concise
```

Initial historical development interpreter paths lacked ruff/ty or no longer existed;
those failed attempts were not counted as checks. `git diff --check` passed.

## Repeat read-only prerequisites

```sh
/home/vottak/.hermes/cache/scratch/ag2-ticket21-network-env/bin/python \
  -m hermes_ag2_network.live_acceptance \
  --api-url http://127.0.0.1:8642 \
  --coding-api-key-file /home/vottak/.hermes/agent-network/secrets/coding-hermes-api.key \
  --architect-api-key-file /home/vottak/.hermes/agent-network/secrets/architect-hermes-api.key \
  --receipt /home/vottak/.hermes/cache/scratch/ag2-ticket21-live-readiness-next.json
```

Receipt targets must be new. Exit 0 means only authenticated Sessions API readiness,
NOT plugin/model readiness, network enrollment, idle proof or ten-step acceptance.
Exit 2 blocks live execution or rejects unusable input/output. Credential and receipt
errors go to stderr with cause/remediation, without a traceback, token or path echo;
stdout is emitted only after a new receipt is saved. HTTP blockers distinguish rejected
authentication, denied permission, other status failures, invalid Sessions JSON and
transport failures without retaining response bodies.
Recovery needs the owning operator/parent to establish a
healthy current Gateway and authenticated API without changing existing sessions.

## GitHub Actions, not a slow local suite

Per user steering, complete standalone tests and relevant Hermes regressions were
**not rerun locally**. `.github/workflows/ag2-network.yml` is prepared to run on the
parent's authorized integration push:

1. Complete standalone integration suite through the canonical runner.
2. Five relevant Hermes files: dispatch session, Run context, Runs, Profiles, memory V2.
3. Blocking static/type checks.
4. An actual canonical `scripts/run_tests.sh -v --tb=short` default-discovery full-suite
   attempt, with zero retries and no paths/-k/marker narrowing. It still attempts the full
   suite after a focused check failure if environment creation succeeded and the run
   wasn't cancelled. The job has a 90-minute limit and the full-suite step a 60-minute
   limit, leaving artifact-upload headroom; timeout is not a pass. Default discovery
   still excludes `tests/integration/`, `tests/e2e/` and `tests/docker/`; these dedicated
   lanes are not claimed as covered. Environment creation and focused checks also
   have shorter step limits; artifact upload uses `always()`.
5. Archive controlled test logs plus exact tested SHA/ref/Run ID using a SHA-pinned
   upload-artifact action, even on failure. Artifact: `ag2-controlled-ci-<SHA>`.
   No live-home receipts/private runtime logs are uploaded by this workflow.

Remote state freshly read: baseline integration ref and successful run
`38285642140` both test `1c018ed7ad7858e519e2e9757cb0f2722820a94e`.
URL: https://github.com/TaKada123/Hermes-workspace/actions/runs/38285642140 .
This historical green run **does not test this checkpoint's changes**.

The remote `MEMV2 canonical full suite (20 shards)` workflow, ID `381217397`, is
**not a generic full-suite dispatcher**: its job only runs on
`ci/memv2-57a309a-20shards`, requires ancestry `57a309a6...`, and asserts the diff
against that commit is exactly its workflow and shard script. That workflow and shard
script are absent from the AG2 branch. Dispatching it on the new integration SHA would
skip/reject rather than test our work. The generic canonical attempt was therefore added
to the existing AG2 push workflow instead; no obsolete ref is presented as coverage.

`gh api repos/TaKada123/Hermes-workspace/actions/runners` returned `total_count=0`.
Hosted runners cannot access this owner's loopback Hermes API; controlled hosted
fixtures do not prove live Coding/Architect. No fake self-hosted lane was added.

Parent publication/verification path (this implementer does not push):

```sh
# After parent merges the implementer branch, authorized push to integration only:
git push origin feat/ag2-network-bridge
# Push triggers the existing workflow; it has no workflow_dispatch trigger.
gh run list --repo TaKada123/Hermes-workspace --workflow ag2-network.yml --branch feat/ag2-network-bridge --event push --json databaseId,headSha,status,conclusion,url
# Select the run whose headSha equals the exact newly pushed integration SHA:
gh run watch RUN_ID --repo TaKada123/Hermes-workspace --exit-status
gh run view RUN_ID --repo TaKada123/Hermes-workspace --json headSha,conclusion,url,jobs
gh run download RUN_ID --repo TaKada123/Hermes-workspace --name ag2-controlled-ci-EXACT_SHA --dir APPROVED_SCRATCH_DESTINATION
```

No push, dispatch, issue write/closure, main merge or independent-review claim was made.
All #21 live criteria (multi-turn, both memory writes, restart, parallel projects, live
errors/duplicate suppression/idle counters) remain open, not simulated. Parent Standards
and Spec review remains separate. **This ticket is blocked, not done.**

## Standards repair round (controlled, not live)

Added `tests/test_live_acceptance_cli.py`: real module imports in subprocesses, isolated
`HERMES_HOME`/`HOME`, owner-only credential files, temporary receipt paths and a controlled
loopback HTTP server. Contracts cover stdout/exit status matching the saved receipt,
0600 output, preservation of existing evidence, HTTP auth/status/malformed/transport
failures, invalid API URLs and credential/file/output failures without secret/body leakage.
No new live scenario or Gateway repair is claimed.

TDD receipts in `/home/vottak/.hermes/cache/scratch/`:

- `ag2-ticket21-review-http-red.log`: 5 expected diagnostic failures, 1 success.
- `ag2-ticket21-review-http-green.log`: 6 passed after HTTP remediation mapping.
- `ag2-ticket21-review-input-red.log`: expected failures for CLI credential/input/output handling.
- `ag2-ticket21-review-input-green.log`: intermediate result, NOT final evidence;
  exposed receipt-parent misclassification and a stale ticket20 installed package lacking
  the readiness module in the pre-existing unit test.
- `ag2-ticket21-review-build.log`: fresh standalone PM build from this worktree to
  `ag2-ticket21-review-network-env`, test group only. No live environment mutated.
- `ag2-ticket21-review-final-green.log`: canonical runner, two focused files,
  **21 passed, 0 failed**, zero retries. No slow local suite was run.
- `ag2-ticket21-review-static.log`: scoped Ruff/ty and `scripts/check --only health,ruff
  --base a736b20f`; passed, code health 0 blocking/0 advisory. The initial ty diagnostic
  on the HTTP fixture's mixed-value dict was corrected with a typed state contract.

The workflow now limits the complete-suite attempt to 60 minutes inside its 90-minute
job, with shorter limits for PM builds/focused checks and `always()` artifact upload.
CI execution and independent delta review still belong to the parent on the exact merged SHA.
