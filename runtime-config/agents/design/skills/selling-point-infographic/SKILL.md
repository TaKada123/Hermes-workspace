---
name: selling-point-infographic
description: Create product-benefit infographics with exact copy.
version: 1.0.0
author: MaynorAI team (xianyu110)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ecommerce, infographic, product-image]
    related_skills: []
---

# Selling-Point Infographic · 卖点信息图

Turns verified product facts into scroll-stopping feature graphics that are readable on a phone.

> Part of [ecommerce-image-skills](https://github.com/xianyu110/ecommerce-image-skills). Works with Claude Code, Codex, Cursor and any agent that loads `SKILL.md`. Default model: GPT Image 2.5 **Sunburst**.

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

## Specs

| Platform | Size | Copy rules |
|---|---|---|
| Amazon secondary images (2–7) | 2000×2000 (1:1) | Text allowed; no unverifiable claims ("#1", "best"), no competitor names |
| Taobao/Tmall 主图 2–5 | 800×800 | 卖点 ≤ 3 条，首图避免牛皮癣 |
| Shopee / Lazada | 1:1 | Local language |
| Ads | 4:5 / 1:1 | |

Readability: headline ≥ 7% of image height, body ≥ 3.5%, max ~12 words per image, ≥ 4.5:1 contrast.

## Step 0 · Copy first
Ask the user for (or draft and get approval on) the exact copy: 1 headline + up to 3 feature rows. **Only use claims the user can prove.** Spell-check every word; the model will render exactly what you write.

## Layout menu
- **Hero + 3 rows:** product left 45%, headline + 3 icon rows right.
- **Callouts:** product centred, 3–4 labels with thin lines pointing to parts.
- **Comparison:** left "ours" vs right "ordinary", ✓/✗ rows (no competitor brand).
- **Number hero:** one big number ("24H", "1200 mAh") + product + one-line explanation.

## Prompt template

```text
Ecommerce selling-point infographic, {1:1 | 2:3}.
{IDENTITY_LOCK}
Layout: {layout from menu}. Background: {soft gradient in brand colours {hex1} → {hex2} | clean white | subtle texture}.
Headline (exact): "{HEADLINE}"
Feature rows (exact), each with a thin line icon: "{ROW 1}", "{ROW 2}", "{ROW 3}".
{Callout lines from labels to {parts}.}
Modern sans-serif typography, strong hierarchy, high contrast, generous whitespace, readable on mobile.
Premium minimal brand style. Spell all text exactly as given; no other text.
```

Use **Sunburst** for the final render (text accuracy). If any letter is wrong, regenerate with the misspelt word quoted again, or render without text and add copy in Canva/Figma.

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
