"""
Manual script to run transcription on a local file for quality evaluation.
Prints raw transcript, cleaned transcript, and diagnostics.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from pprint import pprint

# Ensure we can import from app
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from app.config import get_settings
from app.pipeline.orchestrator import TranscriptionPipeline
from app.utils.logging import configure_logging

async def main():
    parser = argparse.ArgumentParser(description="Transcribe a local file for quality check.")
    parser.add_argument("audio_path", type=Path, help="Path to the audio file.")
    parser.add_argument("--language", default="tr", help="Transcription language.")
    parser.add_argument("--quality", default="balanced", choices=["fast", "balanced", "accurate"], help="Quality mode.")
    parser.add_argument("--debug", action="store_true", help="Print full diagnostics.")
    
    args = parser.parse_args()
    
    configure_logging("INFO")
    settings = get_settings()
    
    if not args.audio_path.exists():
        print(f"Error: File not found at {args.audio_path}")
        sys.exit(1)

    pipeline = TranscriptionPipeline(settings)
    
    print(f"--- Transcribing: {args.audio_path.name} ---")
    print(f"Language: {args.language} | Mode: {args.quality}")
    
    transcript = await pipeline.process_audio_path(
        args.audio_path,
        source="manual_test",
        language=args.language,
        quality_mode=args.quality
    )
    
    print("\n--- RAW TRANSCRIPT ---")
    for s in transcript.segments:
        print(f"[{s.start:0.2f}s - {s.end:0.2f}s] {s.speaker}: {s.raw_text}")
        
    print("\n--- CLEANED TRANSCRIPT ---")
    for s in transcript.segments:
        print(f"[{s.start:0.2f}s - {s.end:0.2f}s] {s.speaker}: {s.corrected_text}")

    if transcript.diagnostics:
        print("\n--- DIAGNOSTICS ---")
        pprint(transcript.diagnostics.model_dump())

if __name__ == "__main__":
    asyncio.run(main())
