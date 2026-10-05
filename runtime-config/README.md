# Hermes runtime configuration

This directory is the source of truth for the customized Hermes runtime.

## Native Hermes files

- `SOUL.md` → installed to `$HERMES_HOME/SOUL.md`. Hermes loads it natively as the primary identity.
- `memories/USER.md` → installed to `$HERMES_HOME/memories/USER.md`. Hermes loads it through the built-in MemoryStore into the system prompt at session start.

## Policy files

The files under `policies/` remain separate source-of-truth documents. The bundled
`gumar-runtime-policy` plugin reads them from `$HERMES_HOME/policies/`, compacts only
metadata/Markdown fence noise, and injects them into two native plugin system-prompt sections:

1. governance: permissions, execution, quality, active tasks;
2. architecture: architecture, action registry, self-improvement.

Hermes limits plugin prompt sections to 4,000 characters each and 8,000 total, so the
two-group split is deliberate. `CHANGELOG.md` is installed for audit/history but is not
injected into the prompt because it is not a behavioral rule.

## Installation

`scripts/install_gumar_runtime.py` copies the source-of-truth files into the active
`HERMES_HOME`, backs up changed runtime copies, and enables `gumar-runtime-policy`
under `plugins.enabled` without replacing unrelated config.
