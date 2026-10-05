# Hermes runtime configuration

This directory is the source of truth for the customized Hermes runtime.

## Native Hermes files

- `SOUL.md` → installed to `$HERMES_HOME/SOUL.md`. Hermes loads it natively as the primary identity.
- `memories/USER.md` → installed to `$HERMES_HOME/memories/USER.md`. Hermes loads it through the built-in MemoryStore into the system prompt at session start.

The installer explicitly keeps `memory.user_profile_enabled: true` and raises
`memory.user_char_limit` to at least 4000 so this USER profile is not left above
Hermes' stock 1375-character write budget.

## Policy files

The files under `policies/` remain the authoritative source documents. The bundled
`gumar-runtime-policy` plugin reads them from `$HERMES_HOME/policies/` and injects
two session-frozen native plugin system-prompt sections:

1. governance: permissions, execution, quality, active tasks;
2. architecture: architecture, action registry, self-improvement.

Hermes allows 4,000 characters per plugin prompt section and 8,000 characters total.
The runtime bridge removes document metadata, blank lines and fenced YAML examples from
the always-on prompt while keeping the original files unchanged. Full schemas/examples
remain in `$HERMES_HOME/policies/`; the runtime prompt explicitly requires reading the
relevant source file before changing profiles, action-registry entries or active-task
record formats.

`CHANGELOG.md` is installed for audit/history but is not injected into the prompt because
it is not a behavioral rule.

## Why AGENTS.md is not used for these policies

Hermes loads project context by working directory and only one project-context family wins
(`HERMES.md` → `AGENTS.md` → `CLAUDE.md` → Cursor rules). These policies are user/runtime
rules that must also apply outside a repository, including gateway and desktop sessions, so
they are connected through native SOUL/USER loaders plus the plugin system-prompt API instead.

## Installation and verification

`scripts/install_gumar_runtime.py`:

- copies source-of-truth files into the active `HERMES_HOME`;
- backs up changed runtime copies;
- enables `gumar-runtime-policy` under `plugins.enabled` without replacing unrelated config;
- enables the native USER profile with sufficient character budget.

`scripts/verify_gumar_runtime.py` verifies the native SOUL loader, native USER MemoryStore,
plugin enablement, prompt-section registration, Hermes prompt budgets, and markers from
permissions, execution, quality and architecture.

`setup-hermes.sh` runs both scripts automatically and fails installation if verification fails.
