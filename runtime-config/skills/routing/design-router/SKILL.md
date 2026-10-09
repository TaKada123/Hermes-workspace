---
name: design-router
description: Route visual work to the isolated design profile.
version: 0.1.0
author: Gumar Bi, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [routing, design, profiles]
    related_skills: []
---

# Design Profile Router

A narrow Main-Hermes handoff to the native `design` profile. It contains no design manuals and never substitutes for the Design Agent.

## When to Use

Use for requests about design, websites, presentations, portfolios, visual systems, graphics, layout, branding or visual editing.

Do not use for ordinary research, coding, engineering analysis without a visual deliverable, home, finance or document extraction. Do not load Superdesign, Impeccable or engineering-portfolio in Main Hermes.

## Handoff Contract

Select registered action `design.route` and create one JSON file in the Hermes scratch directory:

```json
{
  "schema_version": 1,
  "route_type": "profile",
  "route_id": "design",
  "action_id": "design.route",
  "source_profile": "default",
  "original_user_request": "verbatim user text",
  "attachments": ["explicit paths or URLs only"],
  "project_context": ["minimal explicit paths or identifiers only"]
}
```

Preserve `original_user_request` exactly. Do not include Main Hermes reasoning, memories, summaries or unrelated history. Include attachments only when the user supplied them or the current task explicitly identified them.

## Procedure

1. Validate that the request belongs to the design domain.
2. Use `write_file` to create the handoff JSON under `$TMPDIR`; never put it in a project repository.
3. Run the bundled script with `terminal`:
   `python <skill-directory>/scripts/route_design_profile.py --handoff-file <absolute-json-path>`
4. Return the Design Agent result after checking it against the original request. Do not restate the design instructions in Main.

## Pitfalls

- A profile is isolation, not an OS sandbox; explicit project paths remain accessible through tools.
- Do not use `delegate_task`: it creates a temporary child, not the persistent design profile.
- Do not call `hermes -p design` through shell interpolation; the bundled script uses an argv list.
- Never route an unrelated research request merely because it mentions a company with a website.

## Verification

The script must report `profile=design`, and a new session must be recorded under the design profile only. Main's new-session skill index must omit Superdesign/Impeccable while the design profile index contains them on demand.
