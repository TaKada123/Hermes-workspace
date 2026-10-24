# Upstream provenance

- Repository: https://github.com/howdeploy/Z.A.E.B.A.L.git
- Revision: `16927bdbb03cf97dc81d914648cc192fe71201d3`
- Vendored scope: entire `core/` (zaebal.py, platform_runtime.py, config.json, protocol/, wordlists/).
- These source files are copied byte-for-byte; `vendor/SHA256.json` records checksums.
- No upstream install.sh is included or executed. No Codex/Claude/Kimi/OpenCode installation/configuration is performed.
- **No LICENSE file exists in the inspected upstream revision.** No license grant is invented here. Retain upstream authorship/copyright from source. This private local integration is not permission to redistribute; obtain an explicit license before publishing or distributing the vendored code.
- Local adapter files outside `vendor/core` are separately authored for Hermes; this does not relicense upstream.

`--host hermes` works through the generic prompt/session_history contract (core/zaebal.py extract_text, inline_transcript_tail, mode_prompt). This adapter sends only the current prompt and session id, never history. The host's working agent already has its own context. Every session has an explicit isolated ZAEBAL_STATE_DIR; `auditor=none`, empty audit_levels and empty auditor_command are enforced by worker, and subprocess/network attempts in the runtime are blocked by a Python audit hook. This is defense in depth for pinned trusted Python code, not an OS sandbox against arbitrary modified Python code.

All upstream levels request two internal auditors. The separately appended `zaebal-hermes-policy` explicitly forbids additional agents/models and transcript forwarding for this installation; the existing upstream degraded/self-audit branch applies. No upstream protocol bytes were rewritten.
