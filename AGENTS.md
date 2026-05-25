# AGENTS.md

## Repo Memory Workflow

- Read `docs/dev/codex.md` at the start of every session before planning, editing, or answering substantial repo questions.
- Treat `docs/dev/codex.md` as the living working memory for this repository.
- After each user prompt, update `docs/dev/codex.md` if the durable context changed:
  - project state
  - architecture
  - user preferences
  - open decisions or risks
  - next likely tasks
- Rewrite the summary in place. Do not append raw prompt transcripts or command logs.
- Keep `docs/dev/codex.md` concise and current. Remove stale details instead of accumulating history.
- Do not store secrets, tokens, or unrelated personal data in `docs/dev/codex.md`.
- If `docs/dev/codex.md` is missing, create it at `docs/dev/` using the standard section layout.
