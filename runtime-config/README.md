# Hermes runtime configuration

This directory is the source-of-truth bundle for the customized Hermes runtime.

## Native Hermes files

- `SOUL.md` → `$HERMES_HOME/SOUL.md`; native Hermes identity loader.
- `memories/USER.md` → `$HERMES_HOME/memories/USER.md`; native MemoryStore snapshot in the system prompt.

The installer keeps `memory.user_profile_enabled: true` and raises
`memory.user_char_limit` to at least 4000 so the supplied USER profile fits safely.

## Master and reference files

- `MASTER_SPEC.md` is the human-readable configuration source of truth. It is copied to
  `$HERMES_HOME/policies/MASTER_SPEC.md`, but the whole document is not injected every turn.
  The runtime bridge loads only its **instruction priority** and **source of truth** sections.
- `reference/HERMES_USER_PROFILE.md` is the original monolithic profile kept for provenance
  and migration reference. It is **not loaded at runtime**, because its content has been split
  into SOUL, USER and dedicated policies and loading it again would duplicate/conflict with them.

## Runtime policies

The authoritative policy files live under `runtime-config/policies/` and are copied to
`$HERMES_HOME/policies/`.

Always-on plugin prompt content:

1. `PERMISSIONS.md`
2. `EXECUTION_POLICY.md`
3. `RESPONSE_POLICY.md`
4. `ARCHITECTURE.md`
5. `ACTION_REGISTRY.md`
6. `MEMORY_POLICY.md`
7. the priority/source-of-truth sections from `MASTER_SPEC.md`

The bridge removes Markdown headings, metadata and fenced schemas/examples before injection.
The source files themselves remain unchanged.

On-demand policy files stay connected without consuming permanent prompt space:

- `QUALITY_POLICY.md` — read before the final quality/acceptance gate;
- `SELF_IMPROVEMENT.md` — read before promoting a solution into reusable/stable action;
- `ACTIVE_TASKS_POLICY.md` — read when creating/updating temporary task state.

`CHANGELOG.md` is installed for audit/history and is never injected as behavioral context.

## Prompt budgets

Hermes allows 4,000 characters per plugin system-prompt section and 8,000 characters total.
The bridge uses two bounded sections and `scripts/verify_gumar_runtime.py` fails if either
section or the aggregate framed prompt exceeds Hermes' native limits.

## Why AGENTS.md is not used

Hermes loads `HERMES.md` / `AGENTS.md` as project/worktree context. These policies are
global user-runtime rules that must also apply in CLI, gateway and desktop sessions outside a
specific repository. Therefore SOUL/USER use native Hermes loaders and the remaining runtime
rules use the native plugin system-prompt API.

## Installation and verification

`scripts/install_gumar_runtime.py`:

- copies the runtime bundle into the active `HERMES_HOME`;
- backs up changed runtime copies;
- enables `gumar-runtime-policy` in `plugins.enabled` without replacing unrelated config;
- keeps the native USER profile enabled with enough character budget.

`scripts/verify_gumar_runtime.py` verifies native SOUL loading, native USER loading,
plugin enablement, system-prompt registration, prompt budgets, and critical markers for
permissions, execution, response, memory, master priority/source-of-truth and architecture.

`setup-hermes.sh` runs installation and verification automatically and stops on failure.
