"""
Manual script to run transcription on a local file for quality evaluation.
Prints raw transcript, cleaned transcript, and diagnostics.
"""

import argparse
import asyncio
from pathlib import Path
from pprint import pprint

from collective_mindgraph.engine.logging import configure_logging
from collective_mindgraph.engine.settings import get_engine_settings
from collective_mindgraph.infrastructure.transcription.recording_processor import RecordingProcessor


async def main():
    parser = argparse.ArgumentParser(description="Transcribe a local file for quality check.")
    parser.add_argument("audio_path", type=Path, help="Path to the audio file.")
    parser.add_argument("--language", default="tr", help="Transcription language.")
    parser.add_argument(
        "--quality",
        default="balanced",
        choices=["fast", "balanced", "accurate"],
        help="Quality mode.",
    )
    parser.add_argument("--debug", action="store_true", help="Print full diagnostics.")

    args = parser.parse_args()

    configure_logging("INFO")
    settings = get_engine_settings()

    if not args.audio_path.exists():
        print(f"Error: File not found at {args.audio_path}")
        raise SystemExit(1)

    pipeline = RecordingProcessor(settings)

    print(f"--- Transcribing: {args.audio_path.name} ---")
    print(f"Language: {args.language} | Mode: {args.quality}")

    transcript = await pipeline.process_audio_path(
        args.audio_path, source="manual_test", language=args.language, quality_mode=args.quality
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
