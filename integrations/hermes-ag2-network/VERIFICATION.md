# Ticket 01 verification receipts

## Result / scope

The standalone tracer works through real native AG2 1.1.2 disk/WS/channel/WAL and the public `Network` seam. Controlled-executor tests are **not** a live Hermes receipt. Live criterion is **blocked**: parent reports the authenticated multiplex API listener is disabled; no live endpoint/credential pointer was supplied to this worker. Parent explicitly instructed not to wait or alter the gateway. No live Profile/gateway/service/secret was changed here.

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

## Two-axis worker review

**Standards:** core unchanged; standalone distribution/lock; approved public-seam tests; real PM build; narrow pinned external identity/type-adapter limitation documented; secret-safe authenticated HTTP/WS; scoped canonical tests/checks. Independent parallel reviewer agents were not available to this focused worker; parent must run the final independent Standards/Spec review.

**Spec:** pin/native custom handler/invite ACK/native request/reply/WAL/public facade/HTTP executor/executable live smoke implemented. Ticket 01's real existing-Profile acceptance is pending credentials and must not be marked done. Named native continuing channels/session lineage, enrollment plugin, project grants/budgets/artifacts/recovery/deployment remain later tickets. No speculative implementations of those features were added.
