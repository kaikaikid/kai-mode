# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root — this repo's canonical vocabulary file. `/domain-modeling` writes it under exactly this name (22 references), and it is what the other skills should be reading.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in. Numbering starts at `0001` and is self-contained — see `docs/adr/0001-repo-independence.md`. The live rulings are `docs/adr/0002-single-entry-and-dual-lane.md` (single-sentence entry, grilling, one-shot approval), `docs/adr/0003-airport-rebuild-four-roles.md` (four-role airport), `docs/adr/0010-role-wake-fence.md` (roles never wake each other), `docs/adr/0011-package-layout-three-layers.md` (dev records / host payload / project scaffold), and `docs/adr/0012-global-agent-data-root.md` (non-project agent data root).

Some skills in this family (notably `/setup-matt-pocock-skills` and `/improve-codebase-architecture`) name the same object `CONTEXT.md` / `CONTEXT-MAP.md`. **Read `GLOSSARY.md` in their place** — this repo keeps no `CONTEXT.md`. The writer skill (`/domain-modeling`) is what creates the file, and it only ever writes `GLOSSARY.md`, so the reader docs follow it. If the repo ever splits into multiple contexts, the map file is `GLOSSARY-MAP.md` and it points at per-context `GLOSSARY.md` files.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

This repo is **single-context** (most repos):

```
/
├── GLOSSARY.md
├── docs/adr/
│   ├── 0001-event-sourced-orders.md
│   └── 0002-postgres-for-write-model.md
└── src/
```

Multi-context repo (presence of `GLOSSARY-MAP.md` at the root) — not this repo:

```
/
├── GLOSSARY-MAP.md
├── docs/adr/                          ← system-wide decisions
└── src/
    ├── ordering/
    │   ├── GLOSSARY.md
    │   └── docs/adr/                  ← context-specific decisions
    └── billing/
        ├── GLOSSARY.md
        └── docs/adr/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because…_
