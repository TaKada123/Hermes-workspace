---
name: sale-banner
description: Create platform-sized ecommerce campaign banners.
version: 1.0.0
author: MaynorAI team (xianyu110)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ecommerce, banner, campaign]
    related_skills: []
---

# Sale Banner · 大促海报 / 店铺 Banner

Campaign-ready banners in the exact sizes each platform wants, with your real product and correctly spelled offer copy.

> Part of [ecommerce-image-skills](https://github.com/xianyu110/ecommerce-image-skills). Works with Claude Code, Codex, Cursor and any agent that loads `SKILL.md`. Default model: GPT Image 2.5 **Flare**.

## Step 1 · Product identity lock (always first)

Before writing any prompt, study every reference photo and write a short **identity lock** for the product. Paste it verbatim into **every** prompt this skill produces, and never let a creative instruction override it.

```text
PRODUCT IDENTITY LOCK (do not change):
- Shape & proportions: <e.g. tall cylinder, rounded shoulders, 26 cm high, 7.5 cm wide>
- Colour & finish: <e.g. matte sage green #8FA58C body, natural bamboo lid>
- Logo & printed text: <exact spelling, font feel, position, colour — e.g. white "AURA" wordmark centred on upper body>
- Parts & details: <lid, loop, buttons, ports, seams, labels, accessories that are included>
- Must NOT appear: <accessories not in the box, extra logos, invented claims>
```

Rules:
- Only use facts visible in the photos or confirmed by the user. If something is unknown (size, capacity, material), ask or leave it out — never invent specs or certifications.
- If the user gave no photo, ask for one (front view at minimum). Text-only generation is allowed but say the result is a concept, not the real product.

## Step 2 · Pick the model

| Use **Flare** (`gpt-image-2.5-flare`, default) | Switch to **Sunburst** (`gpt-image-2.5-sunburst`) |
|---|---|
| New scenes, backgrounds, layouts, many quick variations | The product's logo / label / small text must survive exactly |
| Text-to-image concepts | Local edits: swap background, recolour, remove objects, keep everything else |
| Drafts for the user to pick from | Final hero assets and anything with dense typography |

## Common sizes

| Placement | Size (px) |
|---|---|
| Taobao/Tmall PC 首焦 / full-width hero | 1920 × 600–900 (safe content width 990/1200) |
| Taobao/Tmall 无线首页 banner | 750 × 300–950 |
| Shopee shop banner (desktop / mobile) | 2000 × 600 (desktop), 1200 × 1200 / 1:1 carousel |
| Lazada store banner | 1200 × 500 (approx.) |
| TikTok Shop store banner | 1:1 or 3:1 per store decoration editor |
| Amazon Store hero | 3000 × 600 (min 1500 × 300) |
| Amazon Sponsored Brands custom image | 1200 × 628 |
| Meta / TikTok feed ad | 1080 × 1080, 1080 × 1350, 1080 × 1920 |

Store editors change often — confirm the current size in the seller centre and crop from a larger render. Keep key copy inside the central 80%.

## Campaign presets
| Campaign | Palette & motifs |
|---|---|
| 双11 / 11.11 | red-orange → magenta gradient, gold foil numbers, confetti |
| 618 | bright red + yellow, bold numerals |
| 年货节 / CNY | lucky red, gold, lanterns, paper-cut patterns (no clichés overload) |
| 9.9 / 12.12 | orange/teal, coins, gift boxes |
| Black Friday | black + neon accent, high contrast |
| Prime Day | deep blue + cyan, clean |
| Summer sale | teal → orange, ice, splash, sunlight |

## Prompt template
```text
Ecommerce sale banner, {ratio, e.g. 3:1 wide}, for {platform/placement}.
{IDENTITY_LOCK}
Product: {1 hero unit | 3 units, middle one larger} on {a podium | floating}, {ice splash | ribbons | light rays}.
Background: {campaign palette + motifs}.
Text (exact, nothing else): headline "{11.11 MEGA SALE}", sub "{UP TO 50% OFF}", button "{SHOP NOW}".
Text on the {left 40%}, product on the right; keep all text inside the central 80% safe area.
Bold commercial advertising style, punchy lighting, crisp, all text spelled exactly.
```

Chinese copy works well (e.g. `"双11 狂欢价"`, `"第二件半价"`) — quote it exactly. Don't print prices you can't guarantee; prefer "up to / 低至" phrasing the user approves.

## Generate · built-in Hermes route only

Use the built-in Hermes `image_generate` tool with the final prompt and the
product photo(s) as references. Do not use external API clients, browser upload
sites, affiliate links, mirrors, or third-party generation endpoints.

### Mandatory approval gate

Before any paid generation **or any upload to an external service**, the current
request must contain both:

1. explicit approval from the **USER** for that paid generation or external
   upload; and
2. a stated maximum budget (a zero budget is valid when the approved upload is
   not billable).

Approval by Design Agent or another agent is not user approval. If either item
is absent, do not call `image_generate`, do not upload anything, and return
`NEEDS_APPROVAL` with the approval and budget required. After approval, stay
within the stated scope and budget.

## Deliver

1. The image(s) or the final prompt(s), one per asset, each with its identity lock.
2. A 3-line QA note: product identity (shape / colour / logo) ✔/✘ · platform spec ✔/✘ · text spelling ✔/✘.
3. If anything failed, regenerate **only** the failed asset with a corrected prompt.
