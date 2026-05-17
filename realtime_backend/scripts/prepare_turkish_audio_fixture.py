"""
Helper script to prepare Turkish audio fixtures for ASR quality testing.
Guides the user through manual recording or attempts local TTS if available.
"""

import os
import subprocess
from pathlib import Path

# Paths
FIXTURE_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "audio"
SCRIPT_PATH = FIXTURE_DIR / "turkish_meeting_sample.script.txt"
WAV_PATH = FIXTURE_DIR / "turkish_meeting_sample.wav"

def check_local_tts():
    """Checks if espeak-ng is available for local generation."""
    try:
        subprocess.run(["espeak-ng", "--version"], capture_output=True, check=True)
        return "espeak-ng"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def main():
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    
    if WAV_PATH.exists():
        print(f"✅ Turkish audio fixture already exists at: {WAV_PATH}")
        return

    if not SCRIPT_PATH.exists():
        print(f"❌ Script file missing at {SCRIPT_PATH}")
        return

    script_text = SCRIPT_PATH.read_text(encoding="utf-8").strip()
    
    print("--- Project-Specific Turkish Meeting Script ---")
    print("\nPlease record yourself reading the following script:")
    print("-" * 60)
    print(script_text)
    print("-" * 60)
    print(f"\nSave the recording as: {WAV_PATH}")
    print("Recommended settings: WAV, mono, 16kHz or 48kHz, no background noise.")
    
    tts_tool = check_local_tts()
    if tts_tool == "espeak-ng":
        print(f"\n💡 Found {tts_tool}. You can generate a basic fixture with:")
        print(f'espeak-ng -v tr -w "{WAV_PATH}" "{script_text}"')
        
    print("\nAfter creating the file, run the meeting quality test with:")
    print("PYTHONPATH=. pytest realtime_backend/tests/test_project_turkish_meeting_asr_quality.py -s")

if __name__ == "__main__":
    main()
