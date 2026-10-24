---
name: multi-angle-set
description: Create consistent multi-angle product image sets.
version: 1.0.0
author: MaynorAI team (xianyu110)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ecommerce, product-image, multi-angle]
    related_skills: []
---

# Multi-Angle Set · 多角度套图

One product, 6–9 matching angles — same light, same background, same colour — so the gallery looks shot in one session.

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
- Amazon gallery: up to 9 images (7 visible on desktop), 1:1.
- Taobao/Tmall: 5 main images 800×800, plus detail screens.
- Shopify: 1:1 or 4:5; keep the same ratio for the whole set.
- Give the model **every real angle you have** (front, back, side, logo close-up) — it can't know what the back looks like.

## Shot list (default 6)
1. Front, straight on · 2. 45° front-left · 3. Side profile · 4. Back · 5. Top-down · 6. Detail macro of {lid/texture/port/logo}
Optional: 7. Packaging + product · 8. In hand for scale · 9. Exploded / parts laid out.

## Set lock (prepend to every shot)
```text
SET LOCK: background {seamless light warm-grey #EDEBE8 | white #FFFFFF}; lighting {large softbox front-left 45°, white fill right, soft floor shadow};
camera {85mm, f/8, product centred, fills 80% of frame}; colour grading neutral.
```

## Prompt template (one per angle)
```text
Ecommerce product photo, angle {N}/{total}: {angle description}.
{IDENTITY_LOCK}
{SET LOCK}
Show only what is physically on this side of the product; do not move logos or text to faces where they don't exist.
Photorealistic studio photography, sharp detail, no added text. Square 1:1.
```

## Grid (optional)
Pillow is supplied by the Hermes-managed runtime. If unavailable, stop and run
`hermes pm doctor` followed by `hermes pm repair`.

```bash
python scripts/make_grid.py out/angle-*.png --cols 3 --out out/multi-angle-grid.png
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
