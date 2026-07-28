# Runtime Status

The maintained runtime consists of the PySide6 desktop and one localhost
FastAPI engine from the `collective_mindgraph` package.

## Default providers

- ASR: local provider selected by engine settings; mock is used only when
  explicitly configured for diagnostics/tests.
- VAD: local energy adapter with optional Silero configuration.
- Speaker labels: fallback labels; speaker separation is experimental and not
  validated.
- Embeddings: disabled/mock unless a local Sentence Transformer is configured.
- Language model: disabled unless an allowed localhost endpoint is configured.

## Persistence

The engine owns
`%LOCALAPPDATA%\CollectiveMindGraph\collective_mindgraph.sqlite3`.
Legacy desktop, engine, and transcript-archive sources are imported through the
backup-first migration.

## Verified automation

The repository validates product workflows, compatibility routes, migrations,
offscreen desktop rendering, import safety, Ruff, strict domain/application
typing, and source compilation. The current Windows development machine also
passes source-engine startup, packaged-engine health, and packaged-desktop
engine-autostart smoke checks. A clean-machine packaging run and real-model
hardware checks remain separate validation work.

See [Product Status](../product/STATUS.md) for claim boundaries.
