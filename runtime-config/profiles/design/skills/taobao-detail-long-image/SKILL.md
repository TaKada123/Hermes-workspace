---
name: taobao-detail-long-image
description: Build 750px Taobao product-detail long images.
version: 1.0.0
author: MaynorAI team (xianyu110)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ecommerce, taobao, product-detail]
    related_skills: []
---

# Taobao Detail Long Image · 淘宝详情长图 (750 宽)

A full 详情页 in one go: screen plan → style lock → one prompt per screen → stitched 750-px long image.

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

## Specs
| Platform | Width | Notes |
|---|---|---|
| Taobao / Tmall 手机详情 | **750 px** | each screen ≈ 750×1000 (≤ 1546 high per slice recommended); JPG; total size limits apply in 千牛 |
| Pinduoduo | 750 px (≥ 480) | |
| JD | 750 px (mobile) / 990 px (PC) | |
| Douyin 抖店 | 750 px | |

广告法：avoid 最/第一/国家级/绝对 etc.; claims (保温 24h, 食品级) must be provable.

## Default 8-screen plan (confirm/edit with user)
1. 首屏 hero: product + core promise
2. 痛点 pain point → solution
3–5. 卖点 ×3 (one per screen)
6. 场景 usage scenes (2–3 mini scenes)
7. 细节 macro details / materials
8. 参数 + 售后 specs table, what's in the box, guarantee

## Style lock (paste into every screen)
```text
DETAIL PAGE STYLE LOCK: palette {sage #8FA58C, cream #F4EFE6, charcoal #2B2B2B}; type {思源黑体 heavy titles, regular body};
light {soft daylight}; layout {generous margins, title top-left, product right}; mood {natural, premium, calm}.
```

## Screen prompt template
```text
Taobao product detail page screen {n}/8, portrait 3:4 (will be resized to 750 px wide).
{IDENTITY_LOCK}
{STYLE LOCK}
Purpose: {screen purpose}. Visual: {composition}.
Chinese text (exact, nothing else): title "{标题}", subtitle "{副标题}"{, bullets "{…}"}.
Text large enough to read on a phone; clean layout, no clutter.
```

## Stitch
Pillow is supplied by the Hermes-managed runtime. If unavailable, stop and run
`hermes pm doctor` followed by `hermes pm repair`.

```bash
python scripts/stitch_long_image.py out/screen-*.png --width 750 --out out/detail-750.jpg
# also writes out/detail-750-slices/ (≤1546 px each) for upload
```

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
