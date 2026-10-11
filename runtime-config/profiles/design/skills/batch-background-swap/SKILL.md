---
name: batch-background-swap
description: Batch-change product backgrounds with budget controls.
version: 1.0.0
author: MaynorAI team (xianyu110)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ecommerce, product-image, batch]
    related_skills: []
---

# Batch Background Swap & SKU Recolour · 批量换背景 / SKU 换色

Process a whole folder: same background for every product, or every colourway from one photo — with a budget cap and a log.

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
- Output ratio/size per target platform (see `amazon-white-background` for main images).
- Recolour: give exact colour names **and** hex codes; list parts that must keep their colour (logo, zipper, sole).
- Always do a 2-image pilot before running the full batch.

## Prompt templates

Background swap:
```text
Edit this product photo. Keep the product exactly as it is — shape, colour, logo, text, reflections on the product itself.
Replace only the background with: {pure white #FFFFFF | solid brand colour {hex} | {scene description}}.
Match lighting direction and add a soft natural contact shadow. No other changes, no added text.
```

SKU recolour:
```text
Edit this product photo. Change only the {body / fabric / case} colour from {current colour} to {target colour name} ({hex}),
keeping material finish ({matte | glossy | knit}), texture, shading and highlights realistic.
Do NOT change: {logo colour, lid, zipper, stitching, background}. Same framing, no other edits.
```

## Prepare the batch locally

Use the deterministic helper to create a local CSV manifest of inputs, variants,
prompts, and output paths. It performs no network calls and uploads nothing:

```bash
python scripts/batch_edit.py ./photos ./out \
  --prompt-file swap.txt \
  --var 'colour=Navy (#1F2A44)' \
  --var 'colour=Sand (#D8C3A5)' \
  --max-images 20
```

After the manifest is reviewed, process its rows with built-in Hermes
`image_generate` only, subject to the approval gate below.

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
