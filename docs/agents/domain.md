# Domain Docs

How engineering skills consume domain documentation in this multi-context repository.

## Before exploring

- Read `GLOSSARY-MAP.md` at the repository root when it exists. It points to the glossary for each relevant subsystem.
- Read system-wide decisions under `docs/adr/`.
- Read subsystem-specific ADRs referenced by the map or located near the subsystem being changed.

If these files do not exist yet, proceed silently. Do not create empty placeholders. `/domain-modeling`, reached through `/grill-with-docs` and `/improve-codebase-architecture`, creates or updates them when terminology or a durable decision is actually resolved.

## Multi-context layout

```text
/
├── GLOSSARY-MAP.md                 # routes topics to subsystem glossaries
├── docs/adr/                       # system-wide architecture decisions
└── <subsystem>/
    ├── GLOSSARY.md                 # subsystem vocabulary
    └── docs/adr/                   # subsystem-specific decisions
```

Subsystem paths are defined by `GLOSSARY-MAP.md`; do not assume every context lives under `src/`.

## Use established vocabulary

When an issue title, specification, test, hypothesis, or refactor proposal names a domain concept, use the term defined by the relevant `GLOSSARY.md`. Do not drift to synonyms that the glossary explicitly avoids.

If a needed concept is absent, reconsider whether the project uses another established term. If the gap is real, record it for `/domain-modeling`.

## Flag ADR conflicts

If proposed work contradicts an existing ADR, surface the conflict explicitly rather than silently overriding the decision. Name the ADR and explain why reopening it may be justified.
