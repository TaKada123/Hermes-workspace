---
name: model-try-on
description: Create on-model product images from apparel references.
version: 1.0.0
author: MaynorAI team (xianyu110)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ecommerce, product-image, apparel]
    related_skills: []
---

# Model Try-On · 模特上身图

From a flat-lay or hanger shot to catalogue-quality on-model photos — without a studio or a model booking.

> Part of [ecommerce-image-skills](https://github.com/xianyu110/ecommerce-image-skills). Works with Claude Code, Codex, Cursor and any agent that loads `SKILL.md`. Default model: GPT Image 2.5 **Sunburst**.

## Step 1 · Product identity lock (always first)

Before writing any prompt, study every reference photo and write a short **identity lock** for the garment. Paste it verbatim into **every** prompt this skill produces, and never let a creative instruction override it.

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

## Specs & ethics

| Platform | Ratio | Notes |
|---|---|---|
| Amazon fashion | 1:1 or 5:6 (e.g. 1500×1800) | Main image: product on model or flat; light grey/white backdrop |
| Taobao / Tmall | 3:4 (750×1000) | |
| Shopee / TikTok Shop | 1:1 or 3:4 | |
| Lookbook / social | 4:5, 9:16 | |

- Use synthetic models only (no real person's likeness unless the user owns the rights). Don't sexualise; keep body proportions natural.
- Offer at least two body types / sizes when the user sells a size range.

## Inputs
1. Garment photo(s): flat-lay or hanger, front (+ back / detail if available).
2. Optional pose / scene reference image.
3. Model brief: gender, age range, region, body type, hair, styling (bottoms, shoes).

## Prompt template

```text
On-model ecommerce photo.
GARMENT IDENTITY LOCK: {identity lock — colour, fabric texture, cut/fit, neckline, sleeve, hem, prints, logo text and position, trims}.
Keep the garment 100% faithful; do not change colour, pattern, logo or length.
Model: {a natural-looking {region} {gender} in their {age}s, {body type}, {hair}}, wearing the garment with {styling}.
Pose: {relaxed standing, one hand in pocket | walking | seated}, {full body | three-quarter | waist-up}, {front | 3/4 | back} view.
{If pose reference: Copy pose, framing and lighting from image 2; take the garment only from image 1.}
Background: {plain light-grey studio | white | urban street | cafe}. Soft key light, realistic fabric folds and drape.
Catalogue photography, photorealistic. No text, no watermark.
```

Variants: `ghost mannequin` (invisible body, hollow neckline), `jewellery close-up` (ear/neck/hand crop, macro lens, skin texture natural), `size comparison` (same outfit on S and XL models side by side).

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
