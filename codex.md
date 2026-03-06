# codex.md

## Project

- Name: Collective MindGraph
- Type: Native Windows-first desktop application
- Stack: Python 3.11+, PySide6, SQLite
- Entry command: `python -m collective_mindgraph_desktop`

## Current State

- The repo contains a working local-first desktop app scaffold under `src/collective_mindgraph_desktop`.
- The repo now also contains a separate end-user desktop subproject under `companion/`.
- The application includes a `QMainWindow`, session explorer, detail panels, demo seed flow, snapshot rebuild flow, and JSON export.
- The MVP UI now exposes direct empty-state actions for `New Session` and `Seed Demo Data`, and menu actions are enabled or disabled based on current selection/state.
- Persistence is handled locally with SQLite; there are no external services, browsers, webviews, or network dependencies in the app architecture.
- Automated tests cover schema creation, session create/list/search, demo seeding, snapshot hash determinism, and export payload structure.
- Root-level repo memory is now defined through `AGENTS.md` plus this `codex.md` file.
- This workspace is now a git repository and has been pushed to `https://github.com/serhatvs/Collective_MindGraph_desktop_app.git`.
- A separate end-user application concept is now in scope as a sibling product to the current AI or reasoning-facing desktop app.
- The companion app is implemented as `Collective MindGraph Companion` with its own package, tests, local SQLite storage, notes autosave, main-category and sub-category hierarchy, and a generated workspace map that displays session templates inside that category tree.
- `tests/README.md` now contains the original project README for comparison: the original product was a Docker-first distributed multi-agent reasoning demo with MQTT, Postgres, agents, and a browser dashboard.
- The companion UI has been realigned again so the selected session is the center of the experience, with a readable session flow and a session-centered mindgraph derived from notes, template choice, branch context, and related sessions.

## Architecture

- Source layout uses `src/collective_mindgraph_desktop`.
- Main layers are `models`, `database`, `repositories`, `services`, and `ui`.
- UI is built with native Qt widgets through PySide6.
- Repository classes own SQLite access; service layer owns higher-level workflows.
- The sibling user-facing product lives in `companion/src/collective_mindgraph_user_app` with the same layered structure and its own `companion/pyproject.toml`.
- The companion app now uses category-first data modeling: `main_categories`, `sub_categories`, `user_sessions`, and `note_entries`. Its workspace map is derived from categories plus sessions rather than stored as a separate editable graph table.
- The companion service now also derives `session_flow` and `session_graph` views from each session's notes and branch context so the UI can stay closer to the original product's session/graph semantics without introducing external services.

## User Preferences

- Build and maintain a real native desktop app, not a web app.
- Keep the product local-first, single-process, and SQLite-backed.
- Prefer clean layering, connected runnable code, and practical implementations over over-abstraction.
- Keep this `codex.md` updated after user prompts so future work starts with current repo context.
- The desktop UI is expected to represent the AI or reasoning-facing part of the product, not generic admin tooling.
- The separate end-user app should not feel like a generic CRUD manager; it needs a clearer consumer-facing product shape.
- The companion app should prioritize easy idea capture, visible category hierarchy, and session-template visualization over abstract `insight` or `action item` features.
- When comparing against the original project README, preserve more of the original product DNA around sessions, reasoning structure, and "mindgraph" semantics instead of drifting into a generic personal organizer.
- For the companion UI specifically, categories are context, not the center; the selected session, its flow, and its generated graph should lead the screen.

## Open Decisions / Risks

- Repo memory is enforced through `AGENTS.md`; there is no visible global Codex hook for automatic runtime-wide updates.
- `codex.md` must stay compact and rewritten in place, not turn into an append-only log.

## Next Likely Tasks

- Keep this file aligned with any durable changes to architecture, workflow, or user preferences.
- If the desktop app gains or loses major features, update the `Current State` and `Architecture` sections.
- If UI polish continues, focus next on transcript/node creation flows and richer session editing, not web-style scaffolding.
- If work splits by audience, keep the current app AI-facing and design the normal-user app as a separate product with its own package and UX.
- Further work can evolve the companion app independently from inside `companion/` using its own install, run, and test commands.
- Companion work should keep strengthening the category-first workspace map UX rather than reintroducing schema-driven CRUD panels.
- If new repo-level working rules are added, record them here only if they remain useful across prompts.

## Last Updated

- 2026-03-06: Added repo-scoped Codex memory workflow and initialized the living project summary.
- 2026-03-06: Refined the desktop UI MVP with actionable empty-state controls and state-aware menu actions.
- 2026-03-06: Clarified that the desktop UI should be treated as the AI or reasoning-facing surface of the product.
- 2026-03-06: Added the idea of a separate normal-user application as a sibling to the AI-facing desktop app.
- 2026-03-06: Implemented the separate `companion/` subproject for the end-user desktop app.
- 2026-03-06: User clarified that the companion UI should be more product-shaped and less like schema-driven CRUD.
- 2026-03-06: Refactored the companion app into a category-first product with main categories, sub categories, quick idea capture, and a generated workspace map instead of insights, action items, and standalone mind map CRUD.
- 2026-03-06: Added the original project README under `tests/README.md` as a comparison source for keeping future UX closer to the repo's original product DNA.
- 2026-03-06: Reworked the companion UI again around session-first flow and a generated mindgraph, keeping category management only as supporting workspace context.
- 2026-03-06: Initialized git for this workspace and pushed the current history to `serhatvs/Collective_MindGraph_desktop_app` with several small history commits plus a final full project commit.
