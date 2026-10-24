---
name: cinedance
description: "Use when creating or repairing Seedance video prompts."
---

# CINEDANCE V4 — Seedance 2.0 Prompt Director

## Required source reference
Before applying this skill, load `references/source.md` through `skill_view(name='cinedance', file_path='references/source.md')`. This complete bundled reference is required; do not depend on Downloads.

## Scope and boundaries
This skill is only for Seedance/Higgsfield Seedance video-prompt writing. For requested Blender artifacts, use blender-mcp for actual scene execution and delivery; translate only applicable craft guidance. Never substitute an English Seedance prompt for a requested Blender artifact. Preserve the requested style, including clay or stylized rendering; do not force photorealism.

Unless analysis, QA, variants, critique, or system-prompt work is requested, return only the final prompt in clear cinematic English. Use concrete observable actions; hide reasoning.

## Method
Isolate this shot and only active subjects/references/location/props, action, first frame, positions, gaze/body orientation, timing/audio, lighting, movement and exclusions. Remove stale tags and prior-scene context. Diagnose empty start, wrong placement/gaze/camera side, lens drift, flat light, duplicates, prop/hand errors, implausible movement and dialogue/continuity risks. Structure: scene; active references; location map; first frame/blocking; format; optics; camera; timed action; physics; lighting; audio; necessary local locks. Silently QA before delivery.

## Rules
- Never invent tags or include inactive subjects.
- State exact screen/world placement, landmark proximity, body facing, gaze and movement direction. Anchor proximity physically.
- If needed, make all required subjects visible in frame one; no empty opening.
- Default to one continuous take. If cuts are required, explicitly define each shot, duration, subjects, blocking, action and cut; preserve screen direction, geography, light and prop/state continuity.
- Choose lens by content; describe observable FOV outcomes and physical distance. Keep lens stable within a shot.
- Respect gravity, mass, inertia, contact, friction and follow-through; motion has cause and effect.
- Lock light direction, camera side and exposure priority; backlight must not flatten into front-light.
- Use only supplied dialogue; no invented speech, subtitles or narration.
- Timed actions must fit the provided duration and remain physically possible.
- No generic negative dump. Omit irrelevant or UI-controlled settings.

Default sections: SCENE CONTEXT; ACTIVE REFERENCES; LOCATION MAP; FIRST FRAME AND SPATIAL BLOCKING; FORMAT MODE; OPTICS; CAMERA; ACTION TIMING; PHYSICS; LIGHTING; AUDIO; POSITIVE CONSTRAINTS.