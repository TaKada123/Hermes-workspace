---
name: amazon-a-plus
description: Design consistent Amazon A+ content modules.
version: 1.0.0
author: MaynorAI team (xianyu110)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ecommerce, amazon, a-plus]
    related_skills: []
---

# Amazon A+ Content Modules · A+ 页面模块图

Builds a complete, visually consistent A+ page: module plan → style lock → one prompt per module → exact pixel sizes.

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

## A+ module sizes (Basic A+)

| Module | Image size (px) |
|---|---|
| Standard image header with text | **970 × 600** |
| Standard company logo | 600 × 180 |
| Standard image & dark/light text overlay | 970 × 300 |
| Standard single image & sidebar | 300 × 400 (main) / 350 × 175 (sidebar) |
| Standard four image & text | 220 × 220 ×4 |
| Standard three images & text | 300 × 300 ×3 |
| Standard comparison chart | 150 × 300 per product |
| Standard single left/right image | 300 × 300 |
| Brand story background | 1464 × 625 |
| Premium A+ full image | 1464 × 600 (desktop) / 600 × 450 (mobile) |

Max file size 2 MB per image; JPG/PNG; no prices, promos, shipping claims, or competitor references; text in images should also appear in alt text.

## Step A · Module plan (confirm with user)
Default 5-module story: ① 970×600 header (brand promise) → ② 3×300×300 key benefits → ③ 970×300 lifestyle banner → ④ 4×220×220 details → ⑤ comparison chart (own range only).

## Step B · Campaign style lock (paste into every module prompt)
```text
CAMPAIGN STYLE LOCK: palette {hex1, hex2, hex3}; light {soft daylight from left}; background family {warm stone + linen};
type {geometric sans, bold headlines, sentence case}; mood {calm premium outdoor}; camera {50mm, eye level}.
```

## Step C · Module prompt template
```text
Amazon A+ module image, {module name}, final size {W}×{H} px (generate at {closest supported ratio}, then crop).
{IDENTITY_LOCK}
{CAMPAIGN STYLE LOCK}
Content: {what this module must communicate, e.g. 'brand promise: keeps drinks cold for 24h on any adventure'}.
Composition: product {left third | centre}, {scene}, leave {right 40% | top band} clean for the headline.
{Headline (exact): "..." — or: no text, copy will be added in Seller Central.}
Photorealistic, consistent with the campaign style lock.
```

Generate at 1536×1024 (≈ 970×600) or 1024×1024 for square tiles, then resize/crop exactly:

```bash
python scripts/crop_to_modules.py out/header.png --module header   # → 970x600
python scripts/crop_to_modules.py out/tile.png --module tile300      # → 300x300
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
