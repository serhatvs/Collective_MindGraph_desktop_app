# Documentation Index

Documentation is organized by audience and lifecycle. Maintained documents may be updated as the product changes; reports and archives preserve dated evidence and must not be treated as current operating instructions.

## Maintained documentation

- `dev/`: engineering setup, architecture, runtime status, transcription design, and repository memory. `dev/SETUP.md` is the authoritative local setup guide; `dev/ARCHITECTURE.md` is the authoritative current architecture overview; `dev/codex.md` is concise repository working memory.
- `product/`: current product status, roadmap, release notes, and claim boundaries.
- `demo/`: maintained demo flow and packaging instructions.
- `alpha/`: friend-alpha installation and testing instructions.
- `patent/`: patent and safe-claim material.

Prefer links to those canonical pages over copying setup or architecture instructions into new documents.

## Dated reports

- `reports/YYYY-MM-DD/<topic>/`: benchmark outputs, validation checkpoints, simulation results, and generated report placeholders.
- `reports/archive/`: superseded report artifacts retained for traceability.

A report records what was measured at a point in time. It is evidence, not a current configuration guide. See `reports/README.md` for the report inventory and claim boundaries.

## Historical documentation

- `archive/handovers/YYYY-MM-DD/`: project handoffs, branch boundaries, dated current-state snapshots, and superseded development plans.
- `archive/companion/`, `archive/concept_modules/`, and `archive/old/`: retired concepts and earlier documentation sets.

Historical documents are retained as evidence. Do not rewrite their conclusions to look current; when a file or command moves, update only the path needed to keep navigation usable.

## Adding documentation

1. Put current operating instructions in the narrowest maintained subject directory.
2. Put measured or generated outputs in a dated `reports/` topic directory.
3. Put superseded decisions, handoffs, and plans in a dated `archive/` directory.
4. Link to the authoritative document instead of creating a second setup, architecture, or status owner.
