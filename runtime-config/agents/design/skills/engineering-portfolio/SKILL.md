---
name: engineering-portfolio
description: Build and maintain engineering-network portfolios; a requested visual direction or design concept starts the concept stage (Superdesign), not a text answer.
version: 0.1.0
author: Gumar Bi, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [design, portfolio, engineering, infrastructure]
    related_skills: [superdesign, impeccable]
---

# Engineering Portfolio

Domain workflow for portfolios about heat networks, water supply, sewerage, pumping stations, pipelines, earthworks and reinforced-concrete structures. The Design Agent remains the orchestrator; this skill owns only this portfolio type.

## When to Use

Use when creating, extending or editing an engineering-infrastructure portfolio. Do not use for unrelated construction research or as a global design orchestrator.

## Mode Routing

Choose exactly one registered action before acting:

- `engineering_portfolio.create` — no approved portfolio baseline exists, or the user explicitly wants a new concept.
- `engineering_portfolio.extend` — an approved design system/baseline exists and new content must be added without redesign.
- `engineering_portfolio.edit` — a precise local text, number, link, image or style correction in an existing artifact.

When intent is ambiguous between CREATE and EXTEND, inspect project state first. A deterministic local correction is always EDIT regardless of its business importance.

## Concept Stage (CREATE with a visual-direction request)

A request for a visual direction, design concepts, style, several design variants, or a concept for
a site, PDF or presentation is a concept-stage request.

Verbal art direction is not a design concept. Three named directions with prose about composition,
colour and typography are a written brief, not comparable design work: the user cannot see them, so
nothing gets chosen. A concept is complete only when it carries concrete, visually comparable
decisions — layout/grid, hierarchy, typography, colour system, photo treatment, page rhythm, hero
composition, project-case composition, or a representative screen/page study.

On the concept stage:

1. Form the factual brief and requirements (CREATE steps 1–4).
2. Load and follow `superdesign` and develop 2–3 genuinely distinct visual directions.
   If the Superdesign preflight, CLI, authentication, dependency, permission or security check fails,
   stop the concept stage and report the exact blocker. Do not substitute another skill, handwritten
   HTML, prose concepts or simulated Superdesign output.
3. Show them to the user and stop before final assembly when the user's choice materially changes
   the result.

Lightweight studies are the expected output: hero study, cover study, one project-case page, layout
study, typography/colour specimen, representative screen, or a small HTML mockup. The concept stage
never produces the full site or PDF; that is the build after a direction is selected.

The concept stage does not wait for missing facts and does not open with a question list: record
absent data as explicit unknowns in the brief and still produce the visual directions.

Choosing the tool is the Design Agent's responsibility — never require the user to ask for
Superdesign by name. Impeccable does not run on the concept stage: it waits for a verifiable draft.

## When Superdesign is not used

- CREATE without a visual-direction request — section structure or factual content only.
- Text-only request: the user explicitly asks for textual ideas only, without visuals or mockups.
- EXTEND with an approved design system — by default; only an explicit request for alternative
  visual directions changes that.
- EDIT — the hard gate below applies.

## CREATE

1. Build a fact/source table: company facts, project claims, dates, quantities, sums, permissions, unknowns and provenance. Mark unconfirmed claims explicitly.
2. Confirm audience, deliverable, languages, publication permissions and success criteria. Reuse existing answers from project context.
3. Inventory only relevant assets. Do not assign a photograph to a project unless the mapping is supported.
4. Reuse an existing design system when appropriate; otherwise create one concise source of truth.
5. If the request asks for a visual direction or design concepts, run the Concept Stage above. Quote any credit cost and receive permission before paid generation.
6. Build the selected artifact with real content and public/embedded assets appropriate to the output format.
7. Verify the real render, links, images, responsive layout, language switch and factual constraints.
8. Load `impeccable` only for a requested or materially useful critique/polish pass after a verifiable draft exists.

Completion: the artifact opens, required content is present, unsupported facts are absent or labelled, and the user has a review URL/file.

## EXTEND

1. Load the existing design system, approved baseline and project state.
2. Add only the requested content using existing components, typography, spacing and asset rules.
3. Do not call Superdesign by default. Use it only if the user explicitly requests alternative visual directions.
4. Verify the affected pages/sections and the surrounding layout.
5. Use Impeccable only when the extension creates a non-trivial consistency or hierarchy problem.

Completion: new content is integrated without changing the approved visual direction.

## EDIT

1. Read the exact current artifact and locate every occurrence of the requested value/asset.
2. Apply the smallest deterministic edit with `patch`/direct authoring.
3. HARD GATE: do not load the Superdesign skill, do not run any Superdesign CLI command and do not inspect remote drafts. Do not load Impeccable for a trivial edit. Do not redesign adjacent sections. This gate holds before any artifact discovery: when the local target is unknown, go to step 4 — never open remote drafts, canvases or the CLI package cache to locate the value.
4. If the exact value/asset is absent from the explicitly handed-off local target, stop without changes and ask for a path, URL or screenshot; do not broaden discovery into unrelated projects or session history.
5. Verify the changed literal and the local render; preserve version history when the platform supports it.

Completion: the requested value changed everywhere intended and nowhere else.

## Truth and Legal Framing

- Separate facts about the current legal entity from experience accumulated by its owner/team before registration.
- Prefer wording such as “опыт владельца и команды” when contracts predate the entity.
- Never invent clients, dates, quantities, certificates, contacts, project-photo mappings or publication permission.
- Project source files and signed/official documents outrank memory and earlier drafts.

## Memory

Read/write only the relevant files under `memories/design/`. Project-specific facts belong in `design/projects`; accepted reusable visual patterns belong in `design/systems` or `design/experience`. Do not copy full engineering-domain memory into this profile.

## Verification

For every run report:

- selected action id and mode;
- whether this was the concept stage, and for a non-concept run the reason Superdesign was skipped;
- skill/tool invocations (including explicit “not called” for Superdesign/Impeccable when relevant);
- factual unknowns preserved;
- artifact URL/path and real verification result.
