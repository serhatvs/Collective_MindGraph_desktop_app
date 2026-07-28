# Windows Demo and Packaging Quickstart

## Source run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[transcription,local-ai]"
mindgraph
```

The desktop manages a localhost engine and stores canonical data at:

```text
%LOCALAPPDATA%\CollectiveMindGraph\collective_mindgraph.sqlite3
```

Use `mindgraph-engine --help` for explicit host/port options. Non-loopback
binding is rejected.

## Build

```powershell
python -m pip install -e ".[build]"
.\scripts\packaging\build_windows_exe.ps1
```

The PyInstaller specification packages the desktop entry point, embedded engine,
language catalogs, and transcription glossary. Output is written under ignored
`dist/`.

Verify the embedded engine without touching canonical user data:

```powershell
python .\scripts\validation\smoke_packaged_engine.py `
  .\dist\CollectiveMindGraph.exe
```

## Packaged smoke check

On a clean Windows user profile:

1. Start the executable without a pre-existing database.
2. Confirm the engine becomes Ready and stops when the desktop closes.
3. Switch Turkish and English and inspect all six workspaces.
4. Import a small audio file using the mock or configured local ASR provider.
5. Correct a transcript segment and review an insight.
6. Search and ask from Memory; verify evidence is visible.
7. Restart and confirm data persists.
8. Repeat once with a copied legacy database; confirm a timestamped backup and
   preserved corrections.
9. Confirm no listener is exposed beyond localhost.
10. Confirm no cloud request is made by default.

Record the exact artifact, Python version, Windows version, test data, and
results. A successful local build does not imply signing, installer, or broad
hardware certification.
