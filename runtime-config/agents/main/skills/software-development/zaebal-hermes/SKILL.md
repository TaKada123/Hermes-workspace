---
name: zaebal-hermes
description: "Use when maintaining Z.A.E.B.A.L. in Hermes profiles."
---

# Local Hermes integration

Read source, README.md and ACCEPTANCE.md at `/home/vottak/Проекты/Hermes-workspace/integrations/zaebal-hermes` before maintenance. Installed shared source is `<default-home>/plugins/zaebal-hermes`; named profiles symlink to it. Discover profiles rather than assuming a fixed list.

## Invariants

- Use this adapter, not upstream install.sh: upstream has no Hermes adapter and its installer targets other clients. Keep pinned core, protocols and wordlists together and verify hashes. Pinned upstream has no LICENSE; do not publish vendored code without permission.
- Capture home during registration. State belongs in `<profile-home>/plugin-data/zaebal-hermes`, separated by session; equal session IDs in different profiles must remain independent.
- pre_llm_call uses current user/session/turn IDs, durable at-most-once dedup, and dynamic context sidecar. Never trigger from tool output/replayed history, rewrite system prefix, or mutate original user text. Uncertain worker crash can lose one signal rather than double count.
- Selected privacy mode forces auditor=none and empty audit_levels/command, denies worker child processes/network and strips ambient secrets. Host policy also disables internal audit subagents: disclose degraded self-audit, not independent verification. Changing privacy requires user authorization.
- This is a heuristic emotional detector and instructional stop, not a technical mutation lock.

## Install and verify

Read install.py; dry-run first, --all-profiles discovers existing homes. Register the installer under local action-registry workflow before reusable permanent use. Apply only authorized scope. Installer backs up configs, uses official plugins enable, reads back targets and refuses foreign destinations. Compare parsed config before/after without printing secret values; unrelated settings must not change.

Use canonical repo scripts/run_tests.sh with HERMES_PYTHON pointing to a verified Hermes environment. Bare Python may find hermes_yaml yet lack ruamel. Test actual PluginManager/dynamic-tail seam, profile/session isolation, dedup, escalation/reset, benign/praise/quotes and poisoned auditor config. These tests do not prove actual LLM compliance.

plugins enable can hot-reload gateway hooks and commands; read actual activation output. Do not restart a live session. Distinguish enabled config, host-seam consumption and end-to-end model canary.

## Commands

`/zaebal status`: adapter safety and state path. Plain message `zaebal audit`: manual audit. Plain `zaebal status`, `zaebal off/on`, `zaebal auto off/on`: per-session controls. Explicit `продолжай` resets streak, not the diagnosis or proof of recovery.
