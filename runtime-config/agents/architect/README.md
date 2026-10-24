# Architect direct-agent pilot

Public definitions only. Never add private memory, sessions, databases, `.env`, auth,
logs or caches to this directory. `SOUL.md` is the approved role; the old Architect
profile remains the rollback path.

## Install (parent/reviewer runs after review)

From `/home/vottak/Проекты/Hermes-workspace`. **Before deployment**, add and verify
`/agents/architect/` in the repository's `.gitignore`; this runtime home contains
private state and must never be tracked. Public definitions remain only under
`runtime-config/agents/architect/`.

```sh
python scripts/direct_agent.py install \
  --source /home/vottak/.hermes/profiles/architect \
  --target /home/vottak/Проекты/Hermes-workspace/agents/architect \
  --definitions runtime-config/agents/architect \
  --hermes /home/vottak/.hermes/installs/f5aff7c256d636c5/environments/6f5d589fc0194816958eac6d821526cd/venv/bin/hermes \
  --allow-capability-root /home/vottak/.hermes/plugins \
  --allow-capability-root /home/vottak/.hermes/profiles/.claude/skills \
  --launcher /home/vottak/.local/bin/architect-direct
```

The explicit existing venv launcher is intentional: the currently installed
`/home/vottak/.local/bin/hermes` fails under an arbitrary new `HERMES_HOME` with
`ModuleNotFoundError: No module named 'ruamel'`. The existing venv launcher was
checked with a scratch home and successfully executed `config get display.skin --json`.
No dependencies are installed by this script. A future runtime upgrade may require
recreating the direct launcher against that runtime; no automatic upgrade occurs.

Target must be absent or empty. Alias must not exist, even as a dangling symlink.
Source, definitions and target must not overlap. The installer refuses unsafe links
before creating the target. If an I/O/config failure happens later, the partial target
is deliberately retained for inspection; rerunning must not overwrite it. Do not
blindly delete a target with user state.

## What is transferred

- Private copies of `memories/` and `sessions/`, plus an online SQLite backup of
  `state.db` including committed WAL data; backup integrity is checked. A private
  original snapshot lives at `TARGET/.direct-agent/source-snapshot/`.
- Initial `config.yaml` is copied unchanged, then modified only through Hermes
  `config set`: remove `agent-network` and `gumar-runtime-policy` from enabled plugins
  and add them to disabled, retaining other entries. Model, file-memory backend and
  limits, tool defer, MCP commands and other configuration are not rewritten.
- Only capability directories `skills`, `scripts`, `references`, `plugins`, `skins`.
  Ordinary resources are copied; caches, locks, known credential/state files, Git
  metadata and network/cron data are excluded. Local `zaebal-hermes` is retained.
- Internal capability links are rebound to the new copy. External links require an
  explicit capability root and are audited for further escapes. They remain shared
  dependencies, not independent copies. Existing dangling capability links are
  retained as absolute links to their original location, not silently repaired.
  In the current source, ten `.claude/skills` links are already dangling.
- Approved SOUL and manifest, executable `TARGET/architect-direct`, optional new alias.

The target home and launcher are mode `0700`. No `.env`/OAuth token is copied;
Hermes shared-root OAuth fallback remains responsible for authentication. Any
credential-only `.env` link requires a separate explicit parent decision. No
Gateway/AG2 restart, old-profile edit, Git commit/push, or model call is performed.

## Launch and verify

```sh
# From your actual project directory:
architect-direct --help
architect-direct config get model --json
architect-direct config get memory --json
architect-direct config get plugins --json
```

The launcher pins `HERMES_HOME`, unsets `HERMES_PROFILE`, preserves caller cwd and
argument boundaries, and refuses `-p`/`--profile` overrides. It does not select the
old profile. The directory from which it is called remains the process cwd;
any explicit `terminal.cwd` already configured in the source remains configuration.

Focused synthetic tests (real Hermes config CLI, no API calls):

```sh
HERMES_PYTHON=/home/vottak/.hermes/installs/7d27e89e058145aa/test-environment/gen-61e60788dcb64beeaab611091e631020/venv/bin/python \
  scripts/run_tests.sh tests/scripts/install/test_direct_agent.py --file-retries 0
```

Tests exercise private state/FTS with an open WAL connection, configuration
preservation, executable launcher and alias, shell-argument boundaries, safe links,
exclusions and refusal paths. This is not full CI or a live agent acceptance test.
Parent must independently review, install, compare private hashes/DB counts without
printing content, inspect the fresh prompt, verify MCP reachability and perform any
bounded model smoke. Until that is done, deployment is **not verified**.
