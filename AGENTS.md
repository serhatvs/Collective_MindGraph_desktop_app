# AGENTS.md

## Repo Memory Workflow

- Read `codex.md` at the start of every session before planning, editing, or answering substantial repo questions.
- Treat `codex.md` as the living working memory for this repository.
- After each user prompt, update `codex.md` if the durable context changed:
  - project state
  - architecture
  - user preferences
  - open decisions or risks
  - next likely tasks
- Rewrite the summary in place. Do not append raw prompt transcripts or command logs.
- Keep `codex.md` concise and current. Remove stale details instead of accumulating history.
- Do not store secrets, tokens, or unrelated personal data in `codex.md`.
- If `codex.md` is missing, create it at the repository root using the standard section layout.
