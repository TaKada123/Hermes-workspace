# Wiring a custom persona / policy bundle into the runtime

Pattern: a git-tracked bundle in the checkout + an installer + a verifier + a bundled
system-prompt plugin. Four load classes, and confusing them is the usual source of false
"it is configured" claims.

## Landing map

| Source in checkout | Lands at | Load class |
|---|---|---|
| `runtime-config/SOUL.md` | `$HERMES_HOME/SOUL.md` | native identity loader (in every prompt) |
| `runtime-config/memories/USER.md` | `$HERMES_HOME/memories/USER.md` | native MemoryStore profile snapshot |
| `runtime-config/policies/*.md`, `MASTER_SPEC.md`, `CHANGELOG.md` | `$HERMES_HOME/policies/` | always-on / on-demand / audit-only (below) |
| `runtime-config/reference/*.md` | not installed | provenance only — never loaded |

Always-on sections are rendered by the plugin from fixed file lists; the sections are
compacted (headings, metadata, fenced blocks dropped) before injection, so a source file and
its injected text are NOT identical — assert on prose markers, not on the file.

On-demand files are only *named* in the prompt (e.g. `[On demand] quality->QUALITY_POLICY.md`):
the agent must open the file itself. Do not describe them as "in the prompt" and do not call
them always-on. Audit-only files (`CHANGELOG.md`) are installed but never injected.

## Enablement and budgets

- The plugin registers bounded sections (`ctx.register_system_prompt_section(id, provider,
  position="after_memory", max_chars=...)`). Hermes caps per-section and aggregate characters;
  the plugin's declared limits must fit inside them.
- A bundled/in-repo plugin is inert until its id is listed in `config.yaml` -> `plugins.enabled`.
  "The directory exists" and "hermes plugins list shows it" are different facts from "enabled in
  config".
- After ANY edit to a policy file, re-read the combined rendered size (the verifier prints
  per-section and aggregate chars). Policy prose grows and silently eats the headroom; a
  comfortable margin is part of the deliverable, not decoration.
- `memory.user_char_limit` must exceed the character count of `memories/USER.md` (bytes ÷ ~2 for
  Cyrillic), otherwise the file loads with a warning and blocks further memory writes.

## Install / verify loop

1. Run the installer, then the verifier, with the **install's own Python** (repo dev venv or a
   `source ./activate` shell) — both scripts import `hermes_cli`/`agent` modules and fail on a
   bare system interpreter.
2. The installer is idempotent and byte-compares each target: if it creates no new timestamped
   backup directory, every installed copy was already identical to the checkout (zero drift).
   Use that as evidence, not as an assumption.
3. The verifier is the authority. It asserts content markers inside the rendered sections and
   that the plugin is enabled in config — the two things that actually determine whether the
   persona reaches the model.
4. Re-run the verifier after any event that rewrote `config.yaml` (setup wizard, model/provider
   switch, other tooling): the installer's config additions can be lost by a later full-state
   write even when every file on disk is correct. Detection is the verifier, repair is the
   installer, and the order is install -> verify -> report.
   - **Codify every config key the bundle depends on in the installer.** Hold it as a `REQUIRED_*`
     constant there, so `setup-hermes.sh` reproduces it on a re-install, and assert the same
     constant in the verifier. A key that lives only in `config.yaml` is a key the next full-state
     write, profile clone or fresh install silently loses — while every file on disk still looks
     correct. Pin the union, never the user's raw list: keep names the user added by hand after
     yours, and say in the report that a pinned explicit list also stops the platform from
     auto-extending it in future versions.
5. Confirm the wiring end-to-end with `scripts/dump_system_prompt.py` (see the parent SKILL.md):
   the verifier proves the plugin renders, the dump proves the rendered text is inside the real
   prompt, in the expected order after the memory block.
6. Keep the checkout clean (bundle + plugin + scripts committed). An install that is a git
   checkout of a fork is updated by pulling upstream, so uncommitted custom files are what an
   update destroys first — say this when you report an update risk.

## Minimizing the always-on bundle

Every request pays for the always-on text. Keep only what the model must know before it decides
anything; point at the rest.

1. **Select, never paraphrase.** Inject only the rule-bearing H2 sections of each policy (hold them
   as `(file, heading)` tables in the plugin) and let everything else fall to on-demand. The policy
   files themselves stay untouched — a semantic rewrite is the user's decision, never a side effect
   of the bridge, and `git diff` on the policy files is the evidence that meaning was preserved.
2. **Keep each heading as a label line above its body.** Compacted markdown without headings turns
   `- git push` next to `- чтение разрешённых файлов` into one ambiguous list: the risk tier that
   decides whether confirmation is required disappears. A label costs ~40 characters and prevents a
   wrong autonomous action — never trade it away for prompt bytes.
3. **Metadata stripping can swallow a rule.** A `**Mode:** ...` header carries the memory mode, and
   the usual "drop lines starting with `**`" filter deletes it silently, so the rule never reached
   the prompt at all. Extract such header lines explicitly and assert them as required markers.
4. **Assert absence, not just presence.** For every file pulled out of the prompt, add a FORBIDDEN
   marker (a distinctive line that only exists in its full text) to the verifier. Presence checks
   alone cannot prove "minimal" — only the absence checks catch full text creeping back.
5. **Set local ceilings well below the platform's.** The verifier's own per-section and aggregate
   budgets must fail loudly on the next policy edit, and must keep real headroom: adding label lines
   and new rules is normal work, so a near-zero margin blocks the user's own edits. Growing the rule
   set is that same normal work: put new rules in the section that still has headroom and rename its
   id to match the new content, instead of pushing a safety-critical section past the platform's
   per-section cap, where rules are truncated silently.
6. **Declare the selection where the verifier can iterate it.** One table of `(file, heading)` plus a
   check that every declared section resolves to non-empty text: a renamed heading must break
   verification, not silently drop a rule from the prompt.
7. **Moving a markdown registry into data.** Install the machine-readable form as a bundle artifact
   and add its mapping row to the installer — the installer copies an explicit list, so a new file
   type without a row never reaches `$HERMES_HOME`. Ship a standalone loader/validator module: a
   hyphenated plugin directory is not an importable package when loaded by path, so use no relative
   imports and load by file path through an `importlib` spec from both the verifier and the router.
8. **Confirm in this order:** install -> verify -> prompt dump -> restart the gateway (or open a new
   session). Plugins and prompt sections are read at process start, so a running gateway keeps the
   old prompt until it is restarted; report "effective for new sessions" instead of "live".
9. **Restore a rule that a deferral removed.** Removing a tool from the array can remove prompt
   guidance with it (the builder gates some blocks on the tool's presence — parent SKILL.md pitfall).
   Keep the deferral and move the lost rule text into the always-on `(file, heading)` selection,
   sourced from a policy file so policy stays the single source of truth, then assert it as a
   required marker. Do not revert the deferral to get the text back: the rule belongs in the policy,
   the tool belongs in the catalog.

### Where the remaining weight is

Measure before quoting a number: custom always-on sections are a few KB while tool schemas are
~45 KB and the project context file can add ~13 KB. Report the section delta AND the whole-prompt
deltas separately instead of equating them, and offer the tool surface as the bigger lever when the
user wants cheaper requests — per-**toolset** totals come from `hermes prompt-size --json`, while
per-**tool** bytes need the inspection-agent probe and the deferred-tool accounting in
`references/tool-surface-audit.md`.

The other honest finding is duplication: a natively loaded profile (`USER.md`) usually repeats the
response-format, permission and memory rules that also live in the policies, so it is paid for
twice. Name the overlap with measured sizes and let the user decide — never delete policy or
profile text under the guise of minimizing.
