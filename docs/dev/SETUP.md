# Developer Setup

## Requirements

- Windows 10/11 is the primary target
- Python 3.11 or newer
- `uv` for the locked development and build environment
- FFmpeg available on `PATH` or configured with `CMG_FFMPEG_EXE`
- Optional NVIDIA/CUDA runtime for accelerated Faster-Whisper

## Environment

From the repository root:

```powershell
uv sync --frozen --extra transcription --extra local-ai --extra dev --extra build
```

Use narrower extras when local models or packaging are not needed:

```powershell
uv sync --frozen --extra dev
uv sync --frozen --extra transcription --extra dev
```

All dependencies are owned by `pyproject.toml` and resolved in `uv.lock`;
there is no secondary requirements file.

## Run

The desktop starts and stops its localhost engine automatically:

```powershell
uv run mindgraph
```

For separate process debugging:

```powershell
uv run mindgraph-engine --host 127.0.0.1 --port 8080
uv run mindgraph
```

Repository launchers are also available:

```powershell
.\scripts\launch\dev_desktop.ps1
```

On Bash-compatible environments:

```bash
./scripts/launch/dev_engine.sh
./scripts/launch/dev_desktop.sh
```

## Local AI

The product remains usable with embeddings and the language model disabled.
Optional semantic retrieval can use a local Sentence Transformer directory:

```powershell
$env:CMG_EMBEDDING_PROVIDER = "sentence_transformer"
$env:CMG_EMBEDDING_MODEL_PATH = "D:\Models\embedding-model"
```

Optional language-model enrichment must use an allowed local HTTP(S) endpoint:

```powershell
$env:CMG_LOCAL_LLM_PROVIDER = "lmstudio"
$env:CMG_LOCAL_LLM_ENDPOINT = "http://127.0.0.1:1234/v1"
```

Remote endpoints and automatic remote downloads remain blocked by default.
Do not place API keys or tokens in tracked files.

## Data

The canonical database is:

```text
%LOCALAPPDATA%\CollectiveMindGraph\collective_mindgraph.sqlite3
```

Stop the desktop and engine before manually copying local data. First-run
migration creates its own timestamped backup and does not delete legacy
sources.

## Verification

```powershell
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
uv run python scripts/quality/check_mypy_baseline.py
uv run pytest -q --cov=collective_mindgraph --cov-report=term --cov-report=xml
uv run python -m compileall -q src scripts
uv run mindgraph --help
uv run mindgraph-engine --help
uv run mindgraph-annotate --help
```

Real-model and hardware validations are optional and marked explicitly:

```powershell
uv run pytest -m "hardware or local_model" -ra
```

## Build

```powershell
.\scripts\packaging\build_windows_exe.ps1
```

The script uses `CollectiveMindGraph.spec` and writes ignored output under
`build/` and `dist/`. A successful build is not a signed installer or release
certification; run the packaged smoke checklist before distribution.
