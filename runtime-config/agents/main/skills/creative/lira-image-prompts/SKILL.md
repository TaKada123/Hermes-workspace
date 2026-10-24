---
name: lira-image-prompts
description: "Use when writing or optimizing AI image prompts."
---

# Lira — Image Prompt Optimization

## Required source reference
Before applying this skill, load `references/source.md` through `skill_view(name='lira-image-prompts', file_path='references/source.md')`. This complete bundled reference is required; do not depend on Downloads.

## Scope and boundaries
This skill is for image-generation and image-edit prompts only. For requested Blender artifacts, use blender-mcp for actual scene execution and delivery; translate only applicable image/craft constraints. Do not replace a Blender deliverable with a text prompt, and preserve the user's requested visual style rather than imposing photorealism. Respond in user's language; prompt text in English. Lead with prompt, keep concise. Ask up to three targeted questions only when ambiguity materially changes the result.

## Model routing
- Character generation/casting: Higgsfield Soul 2.0 (Soul ID for consistency); character sheets may use Cinema Studio AI Cast.
- Locations/environments/cinematic stills: Soul Cinema.
- Props/product objects: Nano Banana Pro (NBP) or GPT Image 2.
- Finished-frame edit: NBP first, minimal post-processing on original.
- Texture cleanup only: Seedream 4.5; never point edits.
- Finest local edit NBP cannot do: GPT Image 2 last resort, with warning about wider-frame drift.
- Location reverse/view change: GPT Image 2; on NBP explicitly map new positions of major objects.

## Rules
Aspect ratio, resolution, quality and Soul ID are UI parameters, not prompt prose. Soul 2.0 has no 21:9; use Soul Cinema with Soul ID for widescreen character frames. Write natural prose, precise not bloated. Prefer positive description; no negative-prompt field exists. Specify camera anchor, real materials/finishes, light source/direction and palette only from brief/references. Never invent facts or override references. For photoreal work reinforce photographic/material anchors; avoid illustration-triggering wording. Do not name real people or brands/IP in prompts.

Edits: one change per pass; exhaustive PRESERVE EXACTLY; preserve everything else. Removal specifies what fills the gap. Rebuild means regenerate, not edit. Video prompts use action states rather than long transitions; include rule of thirds except character sheets.

Edit template:
Edit the image: [goal].
CHANGE: [one precise change].
PRESERVE EXACTLY: [identity, composition, objects, lighting, shadows, grade, texture].
ONLY CHANGE: [restate single change].

For non-trivial builds consult the full source for model-specific constraints and templates.