---
name: telegram-client-sourcing
description: "Use when finding clients or orders in Telegram."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Clients, Freelance, Telegram, Leadgen, HTML]
    category: research
    related_skills: [grounded-citations]
---

# Telegram Client Sourcing

Find where a niche's buyers already sit, verify the handles are real, then hand the user a
self-contained HTML panel they can open offline to track outreach.

The failure mode this prevents: quoting channel handles from memory. Handles rot, rename,
and get faked in listicles, so every handle is verified at the traffic source before it is
presented.

## When to Use

- "Where can I find clients / orders for X?" (design, video, editing, AI content, dev)
- Building or refreshing a niche contact list (marketplace sellers, arbitrage teams, agencies)
- Any request for a set of Telegram channels/chats the user will act on

## Procedure

① **Split the ask into niches, not one flat list.** Buyers differ by segment and so do the
places they sit. For creative/AI production the reliable segments are: performance and
traffic arbitrage (buys creatives by the hundred), agencies (subcontract), info-business
producers (constant Reels), marketplace sellers, and job-board channels. Lead with the
segment that spends the most, not the biggest chat.

② **Search each niche separately**, mixing niche + platform + role:
`"телеграм чаты <ниша> список"`, `"tgstat чаты <ниша>"`, `"<ниша> чат поставщиков"`.
Aggregators (tgstat, telegram.menu, leadradar, tg-cat, telemetr) surface handles inside
their page text — harvest handles from the search descriptions AND extract the pages.

③ **Verify every handle at the source.** `web_extract` the bare `https://t.me/<handle>`
URL — the Telegram preview page carries the real title and member count as
`<N> members` / `<N> subscribers`.

- `NO COUNT` or empty content = the handle does not exist. Drop it silently; never ship a
  guessed handle.
- **`web_extract` accepts at most 5 URLs per call.** Batch in fives or you will silently
  lose results and think a channel is missing.
- Chats are `members`; channels are `subscribers`. Keeping the two apart matters for search
  links (below) and for how the user can post.

④ **Read each preview's description for posting rules.** Many large chats state
`самореклама запрещена`, and some (`market_chatplace`) ban a member for merely mentioning
services. Surface that per entry — it decides whether the user posts or replies by DM.

⑤ **Register every verified URL in the citations ledger** and cite inline, since a channel
list is a factual deliverable users will click.

⑥ **Build the panel** — one self-contained HTML file, no CDN, opens offline. Include: niche
sections, real member counts, per-row status saved in `localStorage`, a note field, keyword
chips, JSON/CSV export. Put it OUTSIDE the user's git repo (e.g. `~/Проекты/<topic>/panel.html`)
so it does not dirty `git status`.

⑦ **Verify the panel before delivering** — see below.

## The one thing that breaks in the browser

`t.me/s/<handle>?q=<keyword>` is a post search that works in a browser for **public channels
only**. Telegram serves no web preview for groups/chats, so a search deep-link is dead weight
on a chat row. Render a search button for `channel` rows and a copy-keyword button for `chat`
rows. Do not promise web search inside a chat.

## Verifying the HTML panel

`file://` and `127.0.0.1` are usually blocked in the browser tool, so the panel cannot be
opened there to check. Verify in two steps instead:

1. `node --check` on the extracted `<script>` body — catches syntax errors.
2. Re-run the render in node against a ~60-line fake DOM (Element with
   `children`/`classList`/`textContent`/`innerHTML`, `getElementById`, `createElement`,
   `createTextNode`, `querySelectorAll`, a `localStorage` stub) and assert the output: card
   count equals the data length, section count equals the niche count, changing a `select`
   writes through to the store, and a text filter reduces the count.

Fake-DOM pitfalls that look like page bugs but are not: `innerHTML = ""` must also clear
`children` or every re-render stacks duplicate cards; a `querySelectorAll` matcher needs
compound selector support (`h2.sec`, not just single class/tag); `textContent` on an element
built via `innerHTML` returns "" unless the shim parses HTML.

## Pitfalls

- **Shipping handles from memory or from a listicle.** Always hit `t.me/<handle>` first.
- **Treating a job-board channel as the client list.** Job channels are inbound and crowded;
  the real buyers are in seller/producer/agency communities. Give both, labelled.
- **Promising "parsing" that does not exist.** A static HTML file cannot read Telegram. Be
  explicit: chat reading needs a Telegram userbot (Telethon/TDLib, `api_id`/`api_hash` from
  my.telegram.org, a warmed-up non-primary account) or a paid lead feed. Offer to build the
  script; do not imply the page does it.
- **Writing the panel into the user's repo.** It shows up in `git status` and gets committed
  by accident.
- **Self-promo in chats that ban it.** Either reply by DM on a concrete request or buy
  placement through the chat's ad bot.

## Verification

```bash
python3 -c "import re;s=open('panel.html',encoding='utf-8').read();open('/tmp/p.js','w').write(re.search(r'<script>(.*?)</script>',s,re.S).group(1))"
node --check /tmp/p.js && node /tmp/fake-dom-test.js
```

Green means: valid JS syntax, card count matches the dataset, filters actually filter, and
status changes persist to the store.
