---
name: lifestyle-scene
description: Place real products into believable lifestyle scenes.
version: 1.0.0
author: MaynorAI team (xianyu110)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ecommerce, product-image, lifestyle]
    related_skills: []
---

# Lifestyle Scene · 生活场景图

Puts the exact product into a scene that shows who uses it, where and how — the image buyers imagine themselves in.

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

## Platform specs

| Platform | Ratio / size | Notes |
|---|---|---|
| Amazon secondary images | 1:1, 2000×2000 | Text allowed but keep it minimal; product must stay the hero |
| Shopify / DTC PDP | 4:5 (1600×2000) or 1:1 | Keep 10% safe margin for crops |
| Taobao / Tmall | 1:1, 800×800+ (750 wide inside detail pages) | |
| Social / ads | 4:5 feed, 9:16 stories | Leave top/bottom 14% clean for UI |

## Scene library (pick one, fill the braces)

| Category | Scene seed |
|---|---|
| Kitchen | marble countertop by a window, morning light, fresh ingredients, steam |
| Bathroom / beauty | stone vanity, soft towel, water droplets, eucalyptus sprig |
| Desk / tech | oak desk, laptop edge, notebook, warm lamp, evening |
| Outdoor | granite rock on a trail / picnic blanket / beach at golden hour |
| Fitness | gym bench, towel, dumbbells, cool daylight |
| Bedroom / home | linen bedding, side table, plant, soft afternoon light |
| Festive | gift wrap, fairy lights, seasonal props (Christmas, CNY, Ramadan) |

## Prompt template

```text
Lifestyle product photo for an ecommerce listing.
{IDENTITY_LOCK}
Scene: {scene seed}. {Optional person: a {age/region} {persona}'s hand reaching for / using the product — face out of frame}.
The product is the clear hero: sharp focus, about {35–55}% of the frame, realistic scale relative to {reference object}.
Lighting: {golden-hour backlight | soft window light | warm lamp}, shallow depth of field, natural shadows that match the scene.
Photorealistic editorial brand photography, {brand mood: calm minimal | vibrant | premium}. No added text, no extra logos.
Aspect ratio {4:5 | 1:1 | 9:16}.
```

Tips: describe the **story** (who/where/when) in one sentence; name one reference object for scale; keep props to 2–4.

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
