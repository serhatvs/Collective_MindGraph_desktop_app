# Collective MindGraph Companion

Collective MindGraph Companion is a native Windows-first desktop app for normal users who want to shape sessions, capture ideas, keep notes locally, and browse everything through a readable mindgraph.

## Features

- Native `QMainWindow` interface built with PySide6
- Local SQLite persistence created automatically on first launch
- Session explorer with search, create, edit, and delete flows
- Main category and sub category structure tied directly to sessions
- Auto-saving rich notes editor plus quick idea capture
- Session flow built from template, branch context, and captured ideas
- Session-centered mindgraph with related-session links
- Workspace context map generated from categories and session templates
- Demo data seeding and JSON export

## Installation

```powershell
python -m pip install -e .
```

## Run

```powershell
python -m collective_mindgraph_user_app
```

## Test

```powershell
python -m pytest
```
