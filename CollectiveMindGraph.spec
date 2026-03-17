# -*- mode: python ; coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
import shutil
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


project_root = Path(SPECPATH).resolve()
src_root = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_root))


datas: list[tuple[str, str]] = []
binaries: list[tuple[str, str]] = []
hiddenimports: list[str] = []
datas += collect_data_files("vosk")
binaries += collect_dynamic_libs("vosk")
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("websockets")
hiddenimports += [
    "sounddevice",
    "soundfile",
    "vosk",
    "multipart",
]

for tool_name in ("ffmpeg", "ffprobe"):
    resolved = shutil.which(tool_name)
    if resolved:
        binaries.append((str(Path(resolved).resolve()), "."))

analysis = Analysis(
    [str(src_root / "collective_mindgraph_desktop" / "__main__.py")],
    pathex=[str(project_root), str(src_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "torchaudio",
        "torchvision",
        "pyannote",
        "pyannote.audio",
        "speechbrain",
        "lightning",
        "silero_vad",
        "faster_whisper",
        "ctranslate2",
        "av",
        "onnxruntime",
        "pandas",
        "scipy",
        "sklearn",
        "matplotlib",
        "pytest",
        "tensorboard",
    ],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="CollectiveMindGraph",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
