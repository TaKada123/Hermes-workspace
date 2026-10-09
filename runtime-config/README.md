# Hermes runtime configuration

This directory is the source-of-truth bundle for the customized Hermes runtime.

## Native Hermes files

- `SOUL.md` → `$HERMES_HOME/SOUL.md`; native Hermes identity loader.
- `memories/USER.md` → `$HERMES_HOME/memories/USER.md`; native MemoryStore snapshot in the system prompt.

The installer keeps `memory.user_profile_enabled: true` and raises
`memory.user_char_limit` to at least 4000 so the supplied USER profile fits safely.

## Master spec and reference

- `MASTER_SPEC.md` is the human-readable configuration source of truth. It is copied to
  `$HERMES_HOME/policies/MASTER_SPEC.md`. Only its **core** reaches the prompt: the instruction
  priority ladder and the source-of-truth rule (675 chars of the 5150-byte file).
- `reference/HERMES_USER_PROFILE.md` is the original monolithic profile kept for provenance and
  migration reference. It is **not installed and not loaded**, because its content has been split
  into SOUL, USER and the dedicated policies; loading it again would duplicate and conflict.

## What is always-on

Injected through the `gumar-runtime-policy` native system-prompt API (two bounded sections,
`position=after_memory`). The bridge keeps the H2 heading as a label and strips only markdown
structure, fenced schemas and metadata — the rule wording itself is never rewritten.

| File | Injected part | Chars |
|---|---|---|
| `MASTER_SPEC.md` | priority ladder + source-of-truth rule | 651 |
| `PERMISSIONS.md` | LOW / MEDIUM / HIGH risk sections + confirmation rules | 1009 |
| `EXECUTION_POLICY.md` | principle, working order, internet rule | 968 |
| `RESPONSE_POLICY.md` | first lines, depth, unfamiliar topic, practical tasks, recommendations | 944 |
| `MEMORY_POLICY.md` | `Mode: B` header + save/update rules, skip list, secrets | 1002 |

Governance section = 3660 chars (includes the per-file block labels). Memory section = 1002 chars of
rules + a 672-char on-demand index = 1695 chars. Framed prompt = 5607 chars.

## What is on demand

The always-on index names the file and the trigger; the agent reads the file with its own file
tools before that kind of work. Loading is therefore an explicit instruction, not an automatic
injection — nothing is cached into the system prompt.

| File | Read when |
|---|---|
| `ARCHITECTURE.md` | архитектура, Profile, specialist, subagent, делегирование |
| `ACTION_REGISTRY.md` | выбор, регистрация или изменение действия |
| `MEMORY_POLICY.md` | уровни памяти CORE/DOMAIN/EPISODIC и изоляция агентов |
| `EXECUTION_POLICY.md` | новый постоянный script или action |
| `QUALITY_POLICY.md` | финальный quality gate |
| `SELF_IMPROVEMENT.md` | перевод проверенного решения в reusable/stable |
| `ACTIVE_TASKS_POLICY.md` | временные задачи, планы и их статусы |

## Action registry

`ACTION_REGISTRY.md` is no longer injected as text. It is installed twice:

- `$HERMES_HOME/policies/ACTION_REGISTRY.md` — the human-readable source;
- `$HERMES_HOME/policies/action_registry.json` — the machine-readable registry a router reads to
  pick an `action_id` (fields: `id, type, description, when_to_use, input_schema, profile,
  permissions, risk, verification, version, status`).

`plugins/gumar-runtime-policy/registry.py` is the loader/validator
(`load_registry`, `validate_registry`, `get_action`, `action_ids`); it never executes an action.
The always-on rule stays short: actions come only from the registry, arbitrary shell commands are
forbidden. `python plugins/gumar-runtime-policy/registry.py` validates the installed copy.

## Never injected

- `CHANGELOG.md` — audit/history only, installs to `$HERMES_HOME/policies/CHANGELOG.md`.

## Prompt budgets

Hermes allows 4,000 chars per plugin system-prompt section and 8,000 total. This bundle enforces
its own smaller ceilings in `scripts/verify_gumar_runtime.py`: 3,900 per section and 6,300 framed
total, so ordinary policy edits fail the verification instead of silently refilling the prompt.
The verifier also fails if full policy text leaks back into the always-on sections.

## Known overlap

`USER.md` (native, always in the prompt) repeats parts of `RESPONSE_POLICY.md`, `PERMISSIONS.md`
and the memory rules. That is duplication in every request, but removing it means editing either
the user profile or a policy's content — a deliberate decision, not a side effect of this bridge.

## Why AGENTS.md is not used

Hermes loads `HERMES.md` / `AGENTS.md` as project/worktree context. These policies are global
user-runtime rules that must also apply in CLI, gateway and desktop sessions outside a specific
repository. Therefore SOUL/USER use native Hermes loaders and the remaining runtime rules use the
native plugin system-prompt API.

## Installation and verification

`scripts/install_gumar_runtime.py`:

- copies the runtime bundle (SOUL, USER, all policies, `action_registry.json`) into `HERMES_HOME`;
- backs up changed runtime copies;
- enables `gumar-runtime-policy` in `plugins.enabled` without replacing unrelated config;
- keeps the native USER profile enabled with enough character budget.

`scripts/verify_gumar_runtime.py` verifies native SOUL loading, native USER loading, plugin
enablement, section registration, per-section resolution, prompt budgets, the required always-on
markers, the absence of full-text policy leakage, the on-demand pointers and the action registry.

`setup-hermes.sh` runs installation and verification automatically and stops on failure.
