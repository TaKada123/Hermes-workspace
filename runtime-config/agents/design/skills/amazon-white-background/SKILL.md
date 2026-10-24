---
name: amazon-white-background
description: Create and verify white-background product hero images.
version: 1.0.0
author: MaynorAI team (xianyu110)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ecommerce, product-image, amazon]
    related_skills: []
---

# Amazon White-Background Main Image · 亚马逊白底主图

Turns a phone snapshot or supplier photo into a marketplace main image that passes Amazon's main-image rules, and checks the result automatically.

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

## Platform specs (Amazon main image)

| Rule | Value |
|---|---|
| Background | Pure white RGB 255,255,255 (#FFFFFF) |
| Product coverage | Product should fill **≥85%** of the image frame |
| Size | Longest side ≥1000 px for zoom; **1600–2000 px recommended**; max 10,000 px |
| Format | JPEG preferred (TIFF/PNG/GIF accepted), sRGB |
| Content | Only the product being sold; no text, logos added, badges, borders, watermarks, props, or extra items not included |
| Presentation | Whole product visible, in focus, realistic colour; no mannequins (apparel may use flat/on-model per category rules) |

Walmart / eBay / Shopee "main image" rules are similar — use the same output, then crop to the platform ratio.

## Prompt template

```text
Amazon main product image.
{IDENTITY_LOCK}
Remove the original background and every object that is not the product.
Product alone, {orientation: upright | lying flat | 3/4 front view}, centered.
Pure white seamless background, #FFFFFF (RGB 255,255,255) everywhere outside the product.
Product fills about 87% of the frame (longest side), with even margins.
Soft diffused studio lighting from front-left, very subtle natural contact shadow directly under the product,
razor-sharp edges, true-to-life colour and material.
No added text, no badges, no props, no reflections of a room, no watermark, no border. Square 1:1.
```

Variants:
- **Packaging included:** add `Product box placed slightly behind and to the right, both fully visible, combined group fills 87% of the frame.`
- **Multi-pack:** add `Exactly {N} identical units arranged in a neat row, no other items.`
- **Apparel (ghost mannequin):** replace orientation with `invisible-mannequin 3D shape, front view, neckline interior visible`.

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
