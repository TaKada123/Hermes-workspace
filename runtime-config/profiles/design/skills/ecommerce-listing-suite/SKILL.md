---
name: ecommerce-listing-suite
description: Plan and produce complete ecommerce listing image sets.
version: 1.0.0
author: MaynorAI team (xianyu110)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ecommerce, product-image, orchestration]
    related_skills: []
---

# Ecommerce Listing Suite · 全套电商图编排

The entry point: one product in, a full platform-ready image set out — planned, consistent, and checked.

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

## Default plans

**Amazon (7 images):** 1 white-background main → 2 key-benefit infographic → 3 lifestyle → 4 second benefit / comparison → 5 size chart → 6 detail macro / multi-angle → 7 in-use or what's in the box. (+ A+ modules)

**Taobao / Tmall:** 5 main images 800×800 (1 白底/场景首图, 2–4 卖点, 5 白底 for 搜索) + 750 详情长图.

**Shopee / Lazada / TikTok Shop:** 1 main 1:1 (white or clean scene) + 4–8 benefit/scene images + campaign banner.

**Xiaohongshu:** 3 cover variants 3:4 + 3–6 inner images.

## Workflow

1. **Intake.** Product photos (front + other angles + logo close-up), product name, category, target platform(s) and market/language, verified facts (size, material, capacity, certifications), brand colours, what's in the box.
2. **Identity lock** (Step 1 below) — confirm it with the user.
3. **Campaign style lock** — palette, light, background family, type, mood. Same block goes into every prompt.
4. **Plan** — a table: `# | skill | purpose | size | model | copy`. Get a ✔ from the user before generating (saves money).
5. **Generate** each row with the matching skill:

| Asset | Skill |
|---|---|
| White-background main | `amazon-white-background` (then run its check script) |
| Scenes | `lifestyle-scene` |
| Apparel on model | `model-try-on` |
| Benefits / comparison | `selling-point-infographic` |
| A+ | `amazon-a-plus` |
| Dimensions | `size-chart` |
| Angles | `multi-angle-set` |
| Banners | `sale-banner` |
| Bulk backgrounds / colourways | `batch-background-swap` |
| RED covers | `xiaohongshu-cover` |
| 详情页 | `taobao-detail-long-image` |

If a sibling skill isn't installed, use the templates in this repo's `skills/<name>/SKILL.md` directly.

6. **QA every image** — identity ✔, spec ✔, text ✔, set consistency ✔. Regenerate only failures.
7. **Hand-off** — file list named `01-main.jpg … 07-…`, prompts in `prompts.md`, QA table.

## Plan output format
```markdown
| # | Asset | Skill | Size | Model | Copy (exact) |
|---|---|---|---|---|---|
| 1 | Main image | amazon-white-background | 2000×2000 | Sunburst | — |
| 2 | 24h cold benefit | selling-point-infographic | 2000×2000 | Sunburst | "KEEPS ICE 24H" … |
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
