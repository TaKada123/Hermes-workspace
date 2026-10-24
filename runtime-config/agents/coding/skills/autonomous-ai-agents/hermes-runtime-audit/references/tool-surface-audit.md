# Auditing the tool surface (toolsets, schema cost, switching)

The tool array is the other half of what a session pays for. It is a **separate block from the
system prompt** and is sent on **every API call**, living inside the provider's cached prefix — so
the report always quotes two sizes (system prompt, tool schemas) and never equates them.

## Four filters produce the inventory

What a session receives is not "every registered tool" and not "every enabled toolset":

1. **Toolset enabled for the platform** — `tools.<platform>.enabled/disabled`, plus
   `agent.disabled_toolsets` (a strict end-of-pipeline subtraction).
2. **`check_fn` availability** — no credential / no portal sign-in / opt-in off ⇒ the tool is
   absent even though its toolset is enabled.
3. **`tools.tool_search.defer`** — named tools are removed from the array and reachable through
   the bridge instead.
4. **Backend substitution** — e.g. `browser.backend: browser-use` replaces the whole
   `browser_*` family with one `browser_exec`; a different backend keeps the family and drops the
   replacement.

Report the chain, not a single command: "toolset enabled" ≠ "tool in the prompt".

## Commands that work in a scripted audit

| Need | Command |
|---|---|
| enabled/disabled toolsets per platform | `hermes tools list` (pipe-safe) |
| deferred list, listing budget | `hermes config get tools.tool_search` |
| excluded toolsets | `hermes config get agent.disabled_toolsets` |
| toolset + schema bytes, largest first | `hermes prompt-size --json` (per **toolset**) |
| per **tool** schema size and toolset | inspection-agent probe below |

- `hermes tools --summary` and the interactive toolset UI require a real TTY and refuse a pipe —
  do not build a scripted audit on them.
- Read config values through `hermes config get <dotted.key>`. Do not assume a third-party YAML
  module is importable in the Python you are running; use the CLI or Hermes's own loader.

## Per-tool probe (offline, no API call, real resolution path)

```python
import json
from hermes_cli.prompt_size import _build_inspection_agent
from tools.registry import registry

agent = _build_inspection_agent("cli")        # dummy creds force the direct-construction path
m = registry.get_tool_to_toolset_map()        # tool name -> canonical toolset
for t in agent.tools:
    fn = t.get("function", t)
    name = fn.get("name")
    print(len(json.dumps(t, ensure_ascii=False)), name, m.get(name, "(bridge)"))
```

- `agent.tools` is the exact array the session sends; its length is the headline count.
- The bridge tools (`tool_search` / `tool_describe` / `tool_call`) are built dynamically: they
  have no registry entry, so read their sizes from `agent.tools` only.
- **Deferred tools are absent from `agent.tools`.** Size them from
  `registry.get_entry(name).schema`, and say they are deferred rather than missing. A registry
  lookup can return a schema that `registry.get_definitions()` filtered out (policy/`check_fn`
  gating) — for a tool that is legitimately available but deferred, the entry is the right source.
- Registry lookups also give the full toolset census (`registry.get_all_entries()`,
  `get_tool_names_for_toolset(name)`), which is what identifies the specialist-profile
  candidates: an entire toolset (kanban, desktop, media, per-platform messaging) that no ordinary
  turn touches.

## Assign a recommendation per tool

| Category | What belongs there |
|---|---|
| keep eager | universal fallbacks and the primitives used in half of all turns: terminal, file ops, code execution, memory, clarify, skill read, web search/extract, delegation for an orchestrator identity |
| defer (`tools.tool_search.defer`) | cold, event-triggered: voice output, credential-vault tools, skill authoring, browser driver, media generation, cron/session search |
| specialist profile | whole toolsets only one kind of task needs (kanban, desktop UI, messaging platforms, media generation) |
| drop from default | already-disabled toolsets; nothing else — never delete a capability, move it |

Cost/benefit to state explicitly: a deferred tool saves its schema on **every** turn and costs
**one extra round trip** (describe → call) the first time it is used; the bridge's listing keeps
it discoverable by name, which is what stops the model from substituting a visible tool
(e.g. shelling out instead of searching for the real one).

Do not defer the inline agent-level tools (memory/todo-shaped) without evidence that the bridge
dispatches them — they are intercepted before normal tool dispatch.

## Changing the defer list safely

**`tools.tool_search.defer` is replace-not-append.** Writing the key replaces the curated default
wholesale, so a list containing only the new names makes every shipped cold built-in
(`computer_use`, `cronjob_manage`, `session_search`, `process_manage`, `todo_list`,
`image_generate`, the desktop helpers) eager again — tens of thousands of characters back into
every request, while the config diff looks like a two-line addition.

Procedure:

1. Read the effective list first: `hermes config get tools.tool_search.defer` prints the
   default-merged value, i.e. the curated names even when the raw config has no `tools:` block.
2. Write the union: curated names + the additions, as one explicit list.
3. `hermes config set tools.tool_search.defer '["name-a","name-b"]'` — the CLI coerces a YAML/JSON
   literal into a real list; a bare comma string is refused.
4. Re-read the raw `config.yaml`, not only `config get`: the section must be present and unrelated
   keys (`plugins.enabled`, `memory.*`) must have survived — a full-state write can drop them.

Account for the bridge: its schema embeds the deferred catalog manifest, so it **grows** as you
  defer more. Report `removed schemas − bridge growth`, both numbers from the same measurement
(`hermes prompt-size` before/after), never by hand.

The deferred count is not the list length. `registry.get_definitions(defer_names, quiet=True)`
returns nothing for a name whose `check_fn` fails in the current context (cron/session-scoped
built-ins), so report "N of M deferrable in this context" and name the exceptions.

Changing the defer list is a **surface** change: it lands in a new session / after the gateway
restart, exactly like a toolset change, even though it lives under `tools.tool_search`.

**A deferral can remove prompt guidance, not just a schema.** Some guidance blocks are gated on the
tool's presence in the assembled array (`agent/system_prompt.py` renders the skills guidance and its
`## Skill Safety Rule` only when `skill_manage` is visible, and the memory/skill-routing wording
shifts with it). Diff the built prompt before and after every defer change; when the lost text is a
rule the user needs, keep the tool deferred and restore the rule as an always-on policy section —
see `references/policy-bundle-wiring.md`.

## Verifying a deferred tool is still reachable

Do both halves — finding it in a search result is not proof that a call works.

Deterministic (offline, no API call), through the real bridge code in `tools/tool_search.py`:

```python
import tools.tool_search as ts
pre = visible_defs + registry.get_definitions(set(ts.load_config().effective_defer_tools), quiet=True)
res = ts.assemble_tool_defs(pre, context_length=<model context length>)
json.loads(ts.dispatch_tool_search({"queries": ["<exact tool name>"]}, current_tool_defs=pre))
json.loads(ts.dispatch_tool_describe({"names": ["<tool>"]}, current_tool_defs=pre))
ts.resolve_underlying_call({"calls": [{"name": "<tool>", "arguments": {}}]})   # -> (name, args, error)
```

`assemble_tool_defs` is idempotent, and it must reproduce the live `agent.tools` names exactly —
that equality is the proof that the offline model of the surface matches the session's.

Then dispatch for real: `from model_tools import handle_function_call; handle_function_call(name, {})`.
Pick a read-only call (a list/lookup tool), or an intentionally invalid argument so the tool's
**own** validation error proves the bridge reached the real handler — an "unknown tool" answer
would prove the opposite. Never use a probe that mutates state.

Real-model half: one `hermes -z` turn that must call `tool_search` → `tool_describe` → `tool_call`
and report what came back. This catches two things the offline probe cannot:

- **Retrieval is lexical (BM25 plus a rarest-token floor).** A paraphrased query can come back
  empty while the tool is sitting in the catalog; the exact tool name always matches. Report a
  paraphrase miss as a retrieval caveat, not as a broken defer.
- Which listing tier the model actually got (name+description manifest, names-only, or the bare
  server-summary bridge).

## The three numbers the user will ask for

1. **current total** — bytes, characters, ≈tokens, and tool count.
2. **minimal safe default** — the keep-eager set plus the bridge, as an absolute size.
3. **expected after optimization** — current minus the defer candidates; give a realistic and an
   aggressive variant instead of one number.

Tokens: use Hermes's own rule — UTF-8 **bytes ÷ 4** (`estimate_tokens_rough`), never `chars / 4`:
Cyrillic is 2 bytes per character, so chars/4 under-counts Russian roughly 2x. Label the unit
(`B` / симв / токены) and call the token figure an estimate; the fit and the cost math are in
`references/prompt-size-and-cost.md`.

## Switching the surface (what is actually possible)

- **Per session:** toolsets resolve at agent build from `tools.<platform>` + `agent.disabled_toolsets`;
  the CLI's own text is "Changes take effect on next 'hermes' or gateway restart" — no OS-level
  restart, but a live process keeps its old surface.
- **Per profile:** each profile has its own `config.yaml`, so a narrow surface for a specialist is a
  config fact, not a runtime trick.
- **Per delegation call:** `delegate_task(toolsets=[...])` narrows a child for that call only
  (bounded by `delegation.inherit_mcp_toolsets`).
- **Mid-conversation:** only heavy reload paths exist (auto-reload on config change, `/reload-mcp`),
  and tool schemas live in the cached prefix, so a surface change invalidates the provider prompt
  cache and the next message re-sends the full prefix. Never recommend mutating the surface
  mid-turn — the defer bridge is the sanctioned progressive-disclosure path.
- **Client surfaces** (`project`, `desktop_ui`) are added to a session by the client, not by config —
  precedent that a surface can be a property of the session.

## Fitting a router (action → toolset)

- Route the action id to a **profile** and let that profile's config decide the surface; decide at
  session start, never mid-conversation.
- Keep cold capabilities in the defer list: the bridge's catalog is scoped to the session's granted
  toolsets, so a specialist cannot reach outside its own subset even through the bridge.
- A schema must not name tools from other toolsets, and an action that declares a required toolset
  must be verified against the profile that serves it — otherwise the model hallucinates calls to
  tools that are not in its array.
- Carry required toolset(s), profile, risk and verification in the action registry record.
