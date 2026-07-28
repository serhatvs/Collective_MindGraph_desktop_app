# Developer Setup

## Requirements

- Windows 10/11 is the primary target
- Python 3.11 or newer
- FFmpeg available on `PATH` or configured with `CMG_FFMPEG_EXE`
- Optional NVIDIA/CUDA runtime for accelerated Faster-Whisper

## Environment

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[transcription,local-ai,dev,build]"
```

Use narrower extras when local models or packaging are not needed:

```powershell
python -m pip install -e ".[dev]"
python -m pip install -e ".[transcription,dev]"
```

All dependencies are owned by `pyproject.toml`; there is no secondary
requirements file.

## Run

The desktop starts and stops its localhost engine automatically:

```powershell
mindgraph
```

For separate process debugging:

```powershell
mindgraph-engine --host 127.0.0.1 --port 8080
mindgraph
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
python -m pytest -q
python -m ruff check src tests scripts
python -m mypy
python -m compileall -q src scripts
mindgraph --help
mindgraph-engine --help
mindgraph-annotate --help
```

Real-model and hardware validations are optional and marked explicitly:

```powershell
python -m pytest -m "hardware or local_model" -ra
```

## Build

```powershell
.\scripts\packaging\build_windows_exe.ps1
```

The script uses `CollectiveMindGraph.spec` and writes ignored output under
`build/` and `dist/`. A successful build is not a signed installer or release
certification; run the packaged smoke checklist before distribution.
