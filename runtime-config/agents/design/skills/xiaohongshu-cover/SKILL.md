---
name: xiaohongshu-cover
description: Create product covers for Xiaohongshu in a 3:4 ratio.
version: 1.0.0
author: MaynorAI team (xianyu110)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ecommerce, xiaohongshu, cover]
    related_skills: []
---

# Xiaohongshu Cover · 小红书种草封面

3:4 covers that stop the scroll in the 小红书 feed — bold Chinese title, real product, one strong visual anchor.

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
- Ratio **3:4**, 1080 × 1440 recommended (generate 1024×1536 and crop to 3:4).
- Title readable at thumbnail size: ≤ 12 Chinese characters, occupies ≥ 20% of height.
- Avoid hard-sell words that hurt reach (最、第一、绝对、全网最低), QR codes, phone numbers, external platform names.
- Real-looking photos outperform obvious AI renders — ask for natural light and slight imperfection.

## Viral layouts (爆款版式)
| Layout | When |
|---|---|
| 大字报 Big title + product | new product, one key benefit |
| 对比 Before/After split | cleaning, beauty, organising |
| 清单 List / grid of 4–6 | hauls, "必买清单" |
| 测评 Review with score stickers | reviews, comparisons |
| 氛围 Mood flat-lay | lifestyle, gifting |
| 价格锚点 Price anchor | deals (only true prices) |

## Prompt template
```text
Xiaohongshu note cover, 3:4 portrait.
{IDENTITY_LOCK}
Layout: {layout}. Scene: {bright airy flat-lay on cream linen with {props} | hand holding the product on a city street | desk setup}.
Large bold Chinese headline at the top in a {rounded friendly | handwritten | heavy sans} font: "{一整天都冰的水杯}".
Smaller tag line: "{通勤 · 健身 · 露营}". Sticker in a corner: "{亲测24h}".
Fresh cozy lifestyle aesthetic, soft natural window light, natural saturation, slight real-photo imperfection.
All Chinese text spelled exactly, clearly legible; no other text.
```

Make 3 variants (different layouts) and let the user pick; covers are cheap to A/B test.

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
