"""Check local fixtures and dependencies for transcription validation."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "transcription" / "fixtures"


def main() -> int:
    checks = {
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "faster_whisper": importlib.util.find_spec("faster_whisper") is not None,
        "common_voice_manifest": (FIXTURES / "expected" / "common_voice_tr_manifest.json").exists(),
        "common_voice_audio": any((FIXTURES / "audio" / "common_voice_tr").glob("*.wav")),
        "meeting_audio": (FIXTURES / "audio" / "turkish_meeting_sample.wav").exists(),
    }
    print("--- Turkish Transcription Test Readiness ---")
    for name, ready in checks.items():
        print(f"{name}: {'READY' if ready else 'MISSING'}")
    print("Run: python -m pytest tests/transcription")
    return 0 if checks["ffmpeg"] and checks["faster_whisper"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
