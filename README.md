# Collective MindGraph

Collective MindGraph is a Windows-first, local-first desktop workspace for
capturing meetings, reviewing transcripts and insights, and retrieving
evidence-backed organizational memory.

The application uses a native PySide6 interface and a localhost-only FastAPI
engine. The engine owns processing and persistent data; the desktop accesses it
through a typed client. Core workflows do not require a cloud service.

## Product workspaces

- **Home** — quick capture, recent meetings, pending reviews, memory questions,
  and engine status.
- **Capture** — live recording or audio-file ingest with progressive disclosure
  for transcription controls, background progress, cancellation, and retry.
- **Meetings** — overview, raw and corrected transcript segments, insights, and
  evidence.
- **Memory** — keyword, semantic, or hybrid retrieval and evidence-only or
  optional local-model answers.
- **Knowledge** — review queue plus filterable knowledge and relationship
  tables.
- **Settings** — language, audio, transcription, local AI, privacy, diagnostics,
  and clearly labelled experimental controls.

The interface supports Turkish and English and can switch language without a
restart.

## Install and run

Python 3.11 or newer is required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[transcription,local-ai,dev]"
mindgraph
```

`mindgraph` opens the desktop and starts the local engine when necessary.
Individual entry points are also available:

```powershell
mindgraph-engine
mindgraph-annotate --help
```

For repository launchers and operational scripts, see
[scripts/README.md](scripts/README.md).

## Local data and privacy

The canonical database remains at:

```text
%LOCALAPPDATA%\CollectiveMindGraph\collective_mindgraph.sqlite3
```

On first use, legacy desktop, engine, and transcript-archive data is detected
and imported through a backup-first migration. The migration builds and
validates a separate `.migrating` database before atomic activation. Source
databases and JSON archives are never deleted automatically.

The engine binds to localhost. Remote model endpoints and downloads remain
disabled unless an explicit local-safe configuration allows them.

Uploaded audio is copied into contained managed storage. Successful job audio
is removed by default; failed or cancelled audio remains available for retry.
Permanent raw-audio retention is an explicit Privacy/Storage preference.

## Validation

```powershell
python -m pytest -q
python -m ruff check src tests scripts
python -m mypy
```

Hardware and real-model checks are marked separately and skip when their local
prerequisites are unavailable. Confidence estimates are not presented as
WER/CER or real meeting-room accuracy.

## Documentation

- [Architecture](docs/dev/ARCHITECTURE.md)
- [Repository structure](docs/dev/REPOSITORY_STRUCTURE.md)
- [Developer setup](docs/dev/SETUP.md)
- [Product status](docs/product/STATUS.md)
- [Demo flow](docs/demo/DEMO_FLOW.md)
- [Documentation index](docs/README.md)
- [Dated validation reports](docs/reports/README.md)
