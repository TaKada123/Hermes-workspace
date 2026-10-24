# Prompt size: units, estimation, and what it actually costs

Every audit ends with a number the user will interrogate. Get the unit right, then answer the
question behind it ("is this a lot?").

## Units: say which one you mean

| Reported as | What it is | Notes |
|---|---|---|
| B / bytes | what `hermes prompt-size` prints | UTF-8: ASCII 1 B/char, Cyrillic/Greek 2 B/char |
| chars / символы | the parenthesised number from the same command | byte count minus the multi-byte inflation |
| ≈tokens | always an estimate from an approximation | never present it as a measurement |

Estimate tokens with Hermes's own rule, not `chars / 4`:
`agent/model_metadata.py::estimate_tokens_rough` counts **ASCII: bytes ÷ 4** (== chars ÷ 4, since
ASCII bytes equal characters) and **non-ASCII: UTF-8 bytes ÷ 4** as well, which for Cyrillic means
roughly 2 characters per token. `chars / 4` under-counts Russian about 2x — enough to let a session
ride into the provider ceiling below the compaction threshold. CJK/Hangul/Kana codepoints count as
one token each. `/context` and `/usage` use the same engine, so quote it instead of inventing one.

## What the static prefix is made of

Two separate blocks, each sent on every API call: the **system prompt** (tiers: stable identity and
guidance / project context / volatile memory, profile, custom policy sections, timestamp) and the
**tool schemas**. `hermes prompt-size --json` returns the tiers and the per-toolset totals; the
per-tool census is in `references/tool-surface-audit.md`.

Two blocks are usually removable rather than essential:

- **Project context** (a repo's `AGENTS.md` chain) is present only because the session's cwd is a
  code workspace (`agent.coding_context: auto`). Starting Hermes elsewhere drops it entirely; say so
  instead of counting it as a fixed cost.
- **The skills index** grows with the number of installed skills, one description line each.

## Price it from the user's own billing data, never from vendor guesses

`$HERMES_HOME/state.db` → table `session_model_usage` has one row per (session, model, task) with
`api_call_count, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
reasoning_tokens, estimated_cost_usd`. Fit the three unknown per-token prices:

    cost = input_miss * p_miss + cache_read * p_hit + output * p_out

Build the normal equations and solve the 3x3 system with plain Python (numpy is often not
importable in the sandbox): `M = AᵀA | Aᵀy`, then Gaussian elimination. **Check the fit error**: with
enough rows it is exactly 0%, which is the proof that the prices are the ones actually billed (a
loose fit means the price model is wrong, not that the data is noisy). Report the fitted prices per
million tokens and derive from them; do not quote a public price list for the provider.

Then state the number in money:

- A cached prefix is an order of magnitude cheaper than a cache miss (observed ~50x). Give both: the
  cold cost of the static prefix and its warm cost.
- In a real long agentic session, the overwhelming majority of input tokens (>95%) are cache reads;
  **output tokens are usually the single largest cost component**, larger than the whole input.
- Compare the prefix against the model's context length to show it as a share (a 20k prefix on a 1M
  context is 2%) — that is what answers "is this a lot?" in the dimension the user cares about.
- Mark `estimated_cost_usd` as an estimate when `actual_cost_usd` is zero, and name the rollup you
  used (per session, per model, per task).

## Why prefix stability beats prefix size

Tool schemas and the system prompt live inside the provider's cached prefix. Changing any of it mid
session (toolset edit, `/reload-mcp`, a changed always-on section) turns every later request into a
miss until the cache rebuilds — worth more than the tokens that were saved. So the recommendation is
never "shrink between turns": shrink once, at session start, and keep it stable after that.

## Framing "is 20k tokens нормально?"

- A bare chat completion with no tools, no skills, no persona is 1-2k tokens. That is the shape the
  user is usually comparing against.
- Any tool-using agent ships 10-25k of static prefix; the tool schemas alone are the biggest block.
  So a ~20k prefix is normal, and saying so is part of the answer.
- Don't assert a quality or latency penalty you have not measured; the honest lines are money (small
  for the prefix), cache behaviour (large), and capability lost per token saved.
- If the user still wants smaller, give the ordered list with what each one costs in capability:
  project context (leave the repo / narrow it), skills index (prune or demote), tool schemas (defer
  cold tools — expect one extra round trip on first use).

## Pitfalls

- Quoting `chars / 4` for Cyrillic-heavy text: under-counts ~2x. Use bytes ÷ 4.
- Presenting the `prompt-size` figure as tokens: it is bytes, with characters in parentheses.
- Selling a byte saving as a money saving without the cache/cold-warm context.
- Fitting prices by eyeballing one row: solve the system and check the residual is zero.
- Treating a size delta as the headline when the user asked about money — lead with the unit-correct
  size, then the cash, then the capability trade-off.
