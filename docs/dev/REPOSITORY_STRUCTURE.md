# Repository Structure and Ownership

This is the authoritative map for maintained code and local-data ownership.

```text
Collective-MindGraph-2/
├── src/collective_mindgraph/
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   ├── engine/
│   ├── desktop/
│   └── tooling/
├── tests/
│   └── transcription/          transcription fixtures and focused tests
├── scripts/
│   ├── launch/
│   ├── benchmarks/
│   ├── datasets/
│   ├── operations/
│   ├── validation/
│   ├── setup/
│   └── packaging/
├── docs/
│   ├── dev/
│   ├── product/
│   ├── demo/
│   ├── reports/
│   └── archive/
├── datasets/                   ignored local datasets; policy README tracked
├── models/                     ignored local model assets; policy README tracked
├── CollectiveMindGraph.spec
└── pyproject.toml
```

## Code ownership

| Responsibility | Owner |
| --- | --- |
| Domain entities, identifiers, and lifecycle rules | `src/collective_mindgraph/domain/` |
| Use cases and external-resource ports | `src/collective_mindgraph/application/` |
| SQLite stores and migration | `src/collective_mindgraph/infrastructure/persistence/` |
| Audio normalization and inspection | `src/collective_mindgraph/infrastructure/audio/` |
| ASR, VAD, alignment, and retranscription adapters | `src/collective_mindgraph/infrastructure/transcription/` |
| Local embeddings and language-model adapters | `src/collective_mindgraph/infrastructure/ai/` |
| Composition, settings, FastAPI, and engine CLI | `src/collective_mindgraph/engine/` |
| Typed engine client and PySide6 product shell | `src/collective_mindgraph/desktop/` |
| Annotation dataset, experiments, export, and UI | `src/collective_mindgraph/tooling/transcript_annotation/` |
| Reference WER/CER and domain-term evaluation | `src/collective_mindgraph/application/transcription/evaluation/` |

There is no second desktop package, backend package, graph repository, or
database owner. Old internal import paths are intentionally unsupported.

## Tests

Pytest discovers only `tests/`; `pyproject.toml` adds `src` without manual path
mutation. Transcription fixtures live under `tests/transcription/fixtures/`.

Important acceptance suites cover:

- dependency direction, module naming, line limits, and language-key parity;
- migration conflict, idempotency, corruption, interruption, and legacy import;
- product and compatibility HTTP/WebSocket contracts;
- review, correction, memory, evidence, jobs, settings, and export/import;
- offscreen Turkish and English desktop rendering;
- import side effects and startup time.

Real hardware/model tests use explicit `hardware` and `local_model` markers.

## Scripts

Scripts are thin entry points grouped by purpose. They import the installed
package without runtime import-path mutation.
`scripts/README.md` is the maintained inventory.

The public installed commands are:

```text
mindgraph
mindgraph-engine
mindgraph-annotate
```

## Generated and local data

- Canonical user data:
  `%LOCALAPPDATA%\CollectiveMindGraph\collective_mindgraph.sqlite3`
- Ignored runtime content: local SQLite files, recordings, uploads, temp audio,
  logs, model weights, downloaded datasets, build output, and caches
- Curated validation evidence: `docs/reports/YYYY-MM-DD/<topic>/`
- Superseded plans and snapshots: `docs/archive/`

Never commit real meeting audio, personal device identifiers, databases,
credentials, local-model weights, or machine-specific absolute paths.

Legacy local directories are ignored and are not removed automatically. Their
content is read only by the migration boundary when configured or detected.

## Quality policy

- Runtime modules are limited to 500 lines. The allowlist in `pyproject.toml`
  is intentionally empty.
- Ruff enforces import, naming, modern-Python, correctness, and complexity
  rules. The two stateful signal-processing algorithms exempted from the
  complexity threshold are explicitly listed with rationale.
- Mypy runs strict over `domain` and `application`; UI and infrastructure can
  be tightened incrementally without weakening those core boundaries.
- Package import and test discovery must not create data, load models, or open
  network connections.
