# Collective MindGraph

Collective MindGraph is a native Windows-first desktop application built with Python, PySide6, and SQLite. It is a single-process, local-first tool for browsing reasoning sessions, transcripts, graph trees, and snapshot history without any external services.

## Features

- Native `QMainWindow` application with a modern Qt widget UI
- SQLite persistence created automatically on first launch
- Session explorer with search, create, delete, and detail view
- Transcript timeline, graph tree, and snapshot history panels
- Demo data seeding and deterministic snapshot rebuilding
- JSON export for a selected session

## Installation

```powershell
python -m pip install -e .
```

## Run

```powershell
python -m collective_mindgraph_desktop
```

## Test

```powershell
python -m pytest
```
