---
name: design-production-pipeline
description: "Use when creating designs with Superdesign and Impeccable."
version: 1.0.0
author: Gumar Bi and Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [design, superdesign, impeccable, critique, workflow]
    related_skills: [creative/superdesign, creative/impeccable]
---

# Design Production Pipeline

## When to Use

Use this workflow for design tasks that move from source material through concepts, user selection, implementation, critique, improvement, and final deliverables. It applies to interfaces, websites, product screens, presentations, graphics, portfolios, and other visual artifacts.

## Tool roles

- **Profile-specific skill** supplies domain truth, terminology, content structure, and constraints for the requested design.
- **Superdesign** develops visual concepts and canvas drafts. It owns concept exploration, not the final quality gate.
- **Hermes** remains the orchestrator and implementation owner: it gathers inputs, selects context, builds the approved direction into the requested artifact, and verifies every handoff.
- **Impeccable** gives the current model design rules and performs critique/improvement: composition, typography, color, spacing, hierarchy, readability, responsiveness, accessibility, and consistency. It is not a separate neural model.

## Required pipeline

Follow this order unless the user explicitly changes the scope:

1. **Source material**
   - Inventory the supplied data, copy, photographs, brand assets, references, requirements, target platform, and output formats.
   - Never invent factual content, measurements, provenance, claims, or credits.
   - Classify assets by purpose: brand identity, content, reference, hero, detail, process, context, or support.

2. **Profile-specific skill**
   - Load the domain skill matching the task before shaping the design.
   - Use it to establish vocabulary, information architecture, user needs, factual constraints, and acceptance criteria.
   - If no domain skill exists, state that and build a concise factual brief from the supplied material instead of pretending one was loaded.

3. **Superdesign concepts**
   - Load and follow `creative/superdesign`.
   - Generate exactly three genuinely distinct concepts by default unless the user changes the number.
   - Concepts should differ in composition and information architecture, not through arbitrary fonts or off-brand colors.
   - Before any paid generation, show the real quoted cost and wait for explicit permission. A model marked `free plan` indicates availability, not necessarily zero generation cost; never infer price from the plan label.
   - Surface the canvas and preview URLs for every concept.

4. **User chooses the direction**
   - Stop after concept delivery and ask the user to select one direction.
   - Do not silently choose a winner or begin final assembly before selection.
   - Record the selected draft/direction and preserve unselected concepts for comparison.

5. **Hermes assembles the design**
   - Build the complete requested artifact from the selected direction using the real content and assets.
   - Preserve the approved visual logic while completing responsive/device states, interactions, navigation, copy, captions, edge states, and implementation details that apply to the task.
   - Produce a working artifact and verify it; a concept image, partial mockup, or code stub is not a finished deliverable.

6. **Impeccable checks and improves**
   - Load `creative/impeccable` after the selected design has been assembled.
   - Use `critique` first for hierarchy, composition, typography, color, spacing, density, emphasis, and cognitive load.
   - Use `audit` when the artifact has responsive, accessibility, interaction, or technical UI requirements.
   - Use `polish` to correct verified defects while preserving factual content and the approved direction.
   - Inspect in bounded passes: one combined review of required sizes/devices, one batch of fixes, and at most one confirmation pass.
   - Do not substitute `dogfood` for design critique. Dogfood is optional functional exploratory QA after the visual quality gate.

7. **Final deliverables**
   - Produce only the formats requested by the user, such as a website, application UI, presentation, graphic, document, PDF, or reusable design system.
   - Adapt each format deliberately rather than mechanically copying another format.
   - Verify rendering, content presence, clipping, legibility, and required interactions in an appropriate viewer.
   - Report exact file paths or URLs and any remaining limitations.

## Quality and approval gates

- User approval is required for paid generation, publishing, purchases, and production deployment.
- The user’s concept selection is a hard gate before final assembly.
- Impeccable review happens after assembly and before final delivery.
- Every external write or upload must be read back or otherwise verified before claiming completion.
- Never claim visual verification from HTML or source inspection alone; render the artifact in a browser or appropriate viewer.
