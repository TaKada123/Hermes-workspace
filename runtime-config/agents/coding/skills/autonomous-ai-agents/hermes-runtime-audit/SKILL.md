---
name: hermes-runtime-audit
description: "Audit a Hermes install, prompt, persona, memory state."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, diagnostics, audit, verification, system-prompt, persona, policies, memory, plugins, skills]
    related_skills: [hermes-agent]
---

# Hermes runtime audit

Read-only, evidence-first verification of a live Hermes install: is it healthy, what is
configured, and what does a new session actually receive? Complements the bundled
`hermes-agent` hub (which maps features and CLI surface) — this skill is the *procedure*
for auditing, plus the probe script that answers "what is really in the system prompt".

## When to Use

Load this when the user asks to check, verify, diagnose or audit their Hermes setup — in any
phrasing: "проверь мою установку", "всё ли настроено", is my persona/policy/plugin loaded, what
is really in the system prompt, which provider/model/credentials/plugins/skills are active, or
"не предполагай, что всё работает, проверь командами". Also load it before touching a custom
persona/policy bundle: `references/policy-bundle-wiring.md` holds the install/verify loop, the procedure for minimizing what stays always-on, and the pattern
for moving a markdown registry into machine-readable data.
Not for answering "does Hermes have feature X" (that is the `hermes-agent` hub and `llms.txt`),
and not for fixing a known-broken install unless the user asks for the repair.

## Rules that hold for every audit

- **Never answer from memory or assumption.** Every status line in the report traces to a
  command output or a file read from this session. "Files exist on disk" is not evidence
  that something is loaded — a plugin/policy can be installed, look enabled, and still be
  absent from the prompt.
- **Quote measured before/after pairs, and name what was NOT touched.** The user asks "до/после"
  and reads a bare post-change number as an unsupported estimate; pair every size with its
  baseline from the same measurement method, and close a change report with the list of surfaces
  left untouched (other profiles, other policies, the architecture) — that list is the user's
  read-only guarantee made visible, not filler.
- **A terse arrow chain is a complete work order.** `A → B → C → changelog` names ordered steps,
  not topics to discuss: execute all of them in that order, then report one section per step
  (what changed, the command that proves it, the number before/after).
- **Read-only by default.** Diagnose, do not repair. Repair only on an explicit ask (Russian
  "ничего не изменяй" / "пока не меняй" means probe only and end with findings). When you do
  repair, snapshot the file you are about to change first and name the rollback point.
- **Disclose side effects and cost.** A live end-to-end test spends tokens and writes a
  session row; config writes create backups. Say so in one line instead of doing it silently.
- **Never print secret values.** `.env` → key names only; `hermes auth list` / `status --full`
  output may include identifiers — trim to provider + auth kind + status.
- **Report in Russian, plain text** (CLI does not render markdown). The user explicitly wants a
  final table with the columns `Компонент | Статус | Как проверено | Проблема/что исправить`,
  short cells, then short per-component detail sections below it, then a numbered list of
  problems ordered by priority and a closing offer of the next action.

## Procedure (in this order)

1. **Install identity and health** — `hermes --version` (prints install dir, install method,
   Python, SDK version), `hermes status --full`, `hermes doctor` (tail it: "All checks passed"
   is the verdict; the interesting lines are the ⚠ ones). Run these through BOTH the user's own
   launcher (`~/.local/bin/hermes`) and the install's dev venv python — the launcher resolves the
   runtime venv, so a dependency gap can exist only there. `hermes doctor` covers config version,
   deprecated keys, required packages, SSL, tool availability and provider connectivity.
2. **Provider / model / credentials** — `config.yaml` `model:` block + `hermes status --full`
   (lines "Provider"/"Model"/"Auth Providers"/"API Keys") + `hermes auth list` (pooled creds) +
   `.env` key NAMES. Cross-check the model the gateway warmed: `$HERMES_HOME/logs/gateway.log`
   logs `Model context warmed: <model> -> <N> tokens`.
3. **Plugins** — `hermes plugins list`. Status strings are `enabled` and `not enabled` (there is
   no "disabled" string) — `grep "not enabled"` lists the off ones. An in-repo/bundled plugin is
   NOT active just because it exists: it must be listed in `config.yaml` → `plugins.enabled`.
   After editing plugin code, prove it loads through the real loader — `hermes plugins doctor <id>`
   (discovery, manifest, import, registration) and `hermes plugins validate <dir>` (declared vs
   registered tools/hooks, security scan, isolation). Your own importlib probe bypasses
   PluginManager, so it can pass on a plugin the runtime would reject.
4. **MCP** — `hermes mcp list` (no servers prints a friendly empty state; `hermes doctor` adds an
   MCP stdio security line).
5. **Skills** — `hermes skills list` + `find $HERMES_HOME/skills -name SKILL.md | wc -l`, then
   reconcile THREE numbers: files on disk, the list total, and the skill lines in the prompt.
   They legitimately differ — see Pitfalls before calling it a bug.
6. **What the prompt really contains** — run `scripts/dump_system_prompt.py` (offline, no API
   call) and `hermes prompt-size --json` (tier sizes, tool-schema bytes, per-skill index cost).
   This is the only real answer to "загружается ли SOUL/USER/policies".
7. **Tool surface and its cost** — `hermes tools list` (enabled/disabled toolsets per platform),
   `hermes config get tools.tool_search` + `agent.disabled_toolsets`, then the per-tool probe for
   sizes and toolset names: `hermes prompt-size --json` for the toolset totals, and the
   inspection-agent probe in `references/tool-surface-audit.md` for the per-tool table. Report the
   filter chain (toolset → `check_fn` → defer list → backend substitution) and the three numbers
   the user asks for: current total, minimal safe default, size after optimization.
8. **Logs and config errors** — grep `$HERMES_HOME/logs/errors.log` and `agent.log` for
   `ERROR`/`WARNING` with timestamps, and note which warnings predate a fix and which are current.
9. **End-to-end proof (optional, paid)** — `hermes -z "Ответь ровно одним словом: ok"
   --usage-file <path>`: proves launch → prompt → provider → response. Read the usage JSON for
   `turn_exit_reason`, api_calls and cost, and state the cost and the created session id. Never
   use a prompt that could invite a tool call for this test.
10. **Cache/timing check** — compare the change time against process start times
   (`hermes gateway status`, `$HERMES_HOME/gateway.pid`): plugin and prompt state load at process
   start, so a gateway or CLI session started earlier keeps the old prompt. Report
   "effective for new sessions only" instead of claiming it is live everywhere.

## Pitfalls

- **Parse `hermes plugins list` by `enabled` / `not enabled`.** Grepping for "disabled" returns
  nothing and silently reports every plugin as active.
- **A `hermes config set` warning that a key "is not a recognized config key" is a registry gap,
  not proof the setting is dead.** Grep the source for a reader (`grep -rn '"<key>"' agent/`) before
  telling the user the value does nothing; per-model knobs such as `agent.reasoning_overrides` are
  read by code that the CLI's registry does not list.
- **Skill-count mismatches are usually gating, not breakage.** Verify from frontmatter before
  reporting: `platforms: [macos]` skills are hidden on Linux, and `requires_toolsets:` skills
  disappear from the index while that toolset is runtime-gated (e.g. kanban). Check
  `sed -n '1,12p'` of the SKILL.md in question.
- **Over-limit persistent memory still loads but stops accepting writes.** A memory file above
  `memory.user_char_limit` produces a load warning and blocks further additions — report both the
  warning and the raised limit, not just "memory works".
- **A writer can drop keys another writer added.** Additive saves need the merge path; a later
  full-state write from a different entry point can leave the file without the installer's keys.
  Snapshot `config.yaml` before touching anything, diff after, and re-run the verifier that
  asserts the keys.
- **`backups/config/config.yaml.good.<stamp>` are PRE-write snapshots**, so the newest one older
  than your change is the rollback point: quote it in the report. `*.pre-setup.*` snapshots come
  from the setup wizard.
- **Prompt budget is a hard ceiling, not a target.** Custom always-on sections are capped per
  section and in aggregate; a policy edit can push the total over and make the verifier fail.
  Always re-read the combined size after editing policy text and report remaining headroom. When new
  rules must be added, place them in the section that still has headroom and rename that section's
  id to match its content — pushing a section past the platform's per-section cap truncates rules
  the verifier never sees.
- **Report the two size numbers separately, never one as the other.** The custom always-on sections
  and the whole session prompt are different quantities: a bundle that shrank by a third can be a
  few percent of the total, because tool schemas and the project context file dominate. Quote both
  (section chars and prompt chars) whenever you claim a prompt cost change.
- **Label every size with its unit, and answer the magnitude question it provokes.** `hermes
  prompt-size` prints **bytes** (characters in parentheses), and a bare "92 879" invites "байты или
  токены?". Estimate tokens with Hermes's own rule — UTF-8 **bytes ÷ 4**, not chars ÷ 4: Cyrillic is
  2 bytes per character, so chars/4 under-counts Russian roughly 2x
  (`agent/model_metadata.py::estimate_tokens_rough`; `/context` and `/usage` use the same engine).
  Then say whether the number is a lot — a bare chatbot is 1-2k, a tool-using agent 10-25k, so 20k is
  normal — and price it, because a static prefix is a rounding error next to output and history.
  `references/prompt-size-and-cost.md` carries the estimator and the price fit.
- **Don't rebuild the environment to "fix" a mismatch you have not reproduced.** Re-run the
  probe and the verifier first; an audit that mutates state is no longer an audit.
- **"Enabled toolset" is not "tool in the prompt".** Availability is a four-stage filter (toolset
  for the platform → `check_fn` credentials/opt-in → `tools.tool_search.defer` → backend
  substitution such as `browser_exec` replacing the `browser_*` family). Report the chain; a tool
  whose toolset is enabled can still be absent, and a disabled-looking one can still be deferred
  rather than gone.
- **A file name in the prompt is not its content.** An on-demand link names the policy/registry
  file while its text stays out of the prompt, and the inverse (content injected with the name
  mentioned nowhere) is normal too. Classify per H2 section by probing normalized body text, not by
  grepping for the file name.
- **Per-tool schema sizes need the inspection-agent probe, not `hermes prompt-size --json`**
  (that one is per toolset) — and deferred tools are absent from the session array, so size them
  from `registry.get_entry(name).schema` instead of reporting them as missing.
  `references/tool-surface-audit.md` has the probe and the census commands.
- **Never propose mutating the tool surface mid-conversation.** Tool schemas live in the cached
  system-prompt prefix and are re-sent in full when they change; the reload paths that exist
  (`/reload-mcp`, config-watch reload) warn about exactly that. For cold capabilities the answer is
  `tools.tool_search.defer`, which keeps them out of the prefix and loads them on demand.
- **`tools.tool_search.defer` is replace-not-append.** Writing that key replaces the curated
  default wholesale, so a list holding only your new names silently makes every shipped cold
  built-in eager again (tens of thousands of characters back into every request) while the config
  diff looks like a small addition. Read the effective list first and write the union — procedure
  in `references/tool-surface-audit.md`.
- **Deferring a tool can edit the system prompt, not just the tool array.** Guidance blocks are
  gated on tool-name presence in the assembled array (`agent/system_prompt.py` includes the skills
  guidance and its `## Skill Safety Rule` block only when `skill_manage` is in the names, and the
  memory/skill-routing wording changes with it). Diff the built prompt before and after any defer
  change, grep `system_prompt.py` for the tool name, and report the guidance that disappeared as
  part of the trade-off instead of presenting a pure byte saving. Remedy when the lost text is a
  rule the user needs: keep the tool deferred and re-add the rule as an always-on policy section
  (the plugin's `(file, heading)` selection) rather than reverting the defer, and assert it as a
  required marker so the next edit cannot drop it again — recipe in
  `references/policy-bundle-wiring.md`.
- **Interactive-only commands refuse a pipe.** `hermes tools --summary` and the curses toolset UI
  error out in a scripted audit; `hermes tools list` and `hermes config get <dotted.key>` are the
  pipe-safe equivalents (and the way to read config without assuming a YAML module is importable).

## Support files

- `scripts/dump_system_prompt.py` — builds the fresh-session system prompt offline and audits it:
  dumps the text, prints part/tier sizes, checks every `$HERMES_HOME/policies/*.md` name for
  presence, and fails (exit 2) if a `--marker` you asked for is missing. Use it for SOUL/USER/
  policy questions instead of trusting file existence.
- `references/tool-surface-audit.md` — the tool side of the audit: the four filters that decide
  which tools a session actually sends, the offline per-tool schema probe, how to read deferred vs
  absent tools, the keep-eager / defer / specialist-profile split with its cost trade-off, how to
  change the defer list without losing the curated names, how to prove a deferred tool is still
  findable and callable, the three size numbers, and what is (and is not) possible when switching
  toolsets per session, profile, turn or delegation — plus how to fit an action→toolset router on top.
- `references/prompt-size-and-cost.md` — what a quoted size actually means and costs: bytes vs
  characters vs tokens, Hermes's own bytes/4 estimator (chars/4 under-counts Cyrillic ~2x), how to
  fit the real per-model prices from the local billing table instead of guessing vendor numbers,
  why a prefix's stability matters more than its size, and how to frame the "is this a lot?"
  question for an agent versus a bare chatbot.
- `references/policy-bundle-wiring.md` — how a custom persona/policy bundle is wired (native
  loaders vs always-on plugin sections vs on-demand links vs audit-only), the enablement and
  budget rules, the installer/verifier loop, the procedure for minimizing what is always-on, and the
  pattern for turning a markdown registry into machine-readable data for a router.
