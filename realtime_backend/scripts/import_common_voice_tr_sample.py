"""
Importer for Mozilla Common Voice Turkish dataset samples.
Converts to WAV and generates a local manifest for ASR quality testing.
"""

import argparse
import csv
import json
import random
import shutil
import subprocess
from datetime import datetime, UTC
from pathlib import Path

# Paths
BASE_FIXTURE_DIR = Path("realtime_backend/tests/fixtures")
AUDIO_TARGET_DIR = BASE_FIXTURE_DIR / "audio" / "common_voice_tr"
MANIFEST_PATH = BASE_FIXTURE_DIR / "expected" / "common_voice_tr_manifest.json"

def convert_to_wav(source: Path, target: Path):
    """Convert audio to standard WAV format using ffmpeg."""
    command = [
        "ffmpeg", "-y", "-i", str(source),
        "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
        str(target)
    ]
    subprocess.run(command, capture_output=True, check=True)

def main():
    parser = argparse.ArgumentParser(description="Import Common Voice Turkish samples.")
    parser.add_argument("cv_path", type=Path, help="Path to Common Voice Turkish root (e.g., cv-corpus-25.0/tr)")
    parser.add_argument("--num-samples", type=int, default=20)
    parser.add_argument("--split", default="test", choices=["test", "validated", "dev", "train"])
    parser.add_argument("--seed", type=int, default=42)
    
    args = parser.parse_args()
    random.seed(args.seed)

    if not args.cv_path.exists():
        print(f"❌ Common Voice path not found: {args.cv_path}")
        print("Expected structure: tr/ clips/, test.tsv, etc.")
        return

    tsv_path = args.cv_path / f"{args.split}.tsv"
    if not tsv_path.exists() and args.split == "test":
        tsv_path = args.cv_path / "validated.tsv"
        print(f"⚠️ test.tsv not found, falling back to validated.tsv")

    if not tsv_path.exists():
        print(f"❌ Split file not found: {tsv_path}")
        return

    clips_dir = args.cv_path / "clips"
    if not clips_dir.exists():
        print(f"❌ Clips directory not found: {clips_dir}")
        return

    AUDIO_TARGET_DIR.mkdir(parents=True, exist_ok=True)

    print(f"🔍 Reading {tsv_path.name}...")
    samples = []
    with tsv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        all_rows = list(reader)

    # Filter for interesting samples (containing Turkish characters)
    tr_chars = set("çğışöüÇĞİŞÖÜ")
    with_tr = [r for r in all_rows if any(c in r["sentence"] for c in tr_chars)]
    
    # Prioritize those, otherwise fallback to any
    pool = with_tr if len(with_tr) >= args.num_samples else all_rows
    selected_rows = random.sample(pool, min(len(pool), args.num_samples))

    manifest_samples = []
    for i, row in enumerate(selected_rows):
        source_clip = clips_dir / row["path"]
        target_name = f"cv_tr_{i:03d}.wav"
        target_path = AUDIO_TARGET_DIR / target_name
        
        print(f"📦 [{i+1}/{len(selected_rows)}] Converting {row['path']} -> {target_name}")
        try:
            convert_to_wav(source_clip, target_path)
            
            manifest_samples.append({
                "id": f"cv_tr_{i:03d}",
                "audio_path": str(Path("audio/common_voice_tr") / target_name),
                "expected_sentence": row["sentence"],
                "source_split": args.split,
                "original_path": row["path"],
                "license": "CC0-1.0"
            })
        except Exception as exc:
            print(f"  ❌ Failed to convert {row['path']}: {exc}")

    manifest = {
        "source_dataset": "Mozilla Common Voice Turkish",
        "source_version": "Common Voice Scripted Speech 25.0",
        "locale": "tr",
        "license": "CC0-1.0",
        "source_split": args.split,
        "imported_count": len(manifest_samples),
        "created_at": datetime.now(tz=UTC).isoformat(),
        "notes": "Imported for local ASR quality regression testing.",
        "samples": manifest_samples
    }

    with MANIFEST_PATH.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Imported {len(manifest_samples)} samples.")
    print(f"📄 Manifest written to: {MANIFEST_PATH}")
    print(f"🎵 Audio files stored in: {AUDIO_TARGET_DIR}")

if __name__ == "__main__":
    main()
