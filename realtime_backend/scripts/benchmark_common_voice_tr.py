"""
Benchmark script for Mozilla Common Voice Turkish ASR quality.
Provides detailed keyword overlap scoring and generates a structured report.
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, UTC
from pathlib import Path
from pprint import pprint

# Ensure we can import from app
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from app.config import get_settings
from app.pipeline.orchestrator import TranscriptionPipeline
from app.utils.logging import configure_logging

def levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def calculate_overlap_metrics(expected: str, actual: str):
    def tokenize(t):
        return [w.lower().strip(".,?!") for w in t.split() if w.strip(".,?!")]
    
    expected_tokens = tokenize(expected)
    actual_tokens = tokenize(actual)
    
    expected_set = set(expected_tokens)
    actual_set = set(actual_tokens)
    
    if not expected_set:
        return [], [], 0.0, 0.0, 0.0
        
    matched = expected_set.intersection(actual_set)
    missing = expected_set - actual_set
    overlap_score = len(matched) / len(expected_set)
    
    # CER Approximation
    exp_norm = expected.lower().strip()
    act_norm = actual.lower().strip()
    char_dist = levenshtein_distance(exp_norm, act_norm)
    cer = char_dist / len(exp_norm) if exp_norm else 0.0
    
    # WER Approximation
    word_dist = levenshtein_distance(expected_tokens, actual_tokens)
    wer = word_dist / len(expected_tokens) if expected_tokens else 0.0
    
    return sorted(list(matched)), sorted(list(missing)), overlap_score, cer, wer

async def main():
    parser = argparse.ArgumentParser(description="Benchmark Turkish ASR quality.")
    parser.add_argument("--num-samples", default="20", help="Number of samples (int or 'all').")
    parser.add_argument("--quality", default="balanced", choices=["fast", "balanced", "accurate"], help="Quality mode.")
    parser.add_argument("--output-json", type=Path, help="Save results to JSON file.")
    parser.add_argument("--manifest", type=Path, default=Path("realtime_backend/tests/fixtures/expected/common_voice_tr_manifest.json"))
    
    args = parser.parse_args()
    configure_logging("INFO")
    settings = get_settings()
    
    if not args.manifest.exists():
        print(f"❌ Manifest missing at {args.manifest}")
        sys.exit(1)

    with args.manifest.open(encoding="utf-8") as f:
        manifest = json.load(f)

    samples = manifest.get("samples", [])
    if args.num_samples != "all":
        samples = samples[:int(args.num_samples)]

    pipeline = TranscriptionPipeline(settings)
    
    print(f"--- Benchmarking {len(samples)} samples ---")
    print(f"Mode: {args.quality} | Metric: keyword_overlap_quality_score, CER, WER")
    
    results = []
    
    sum_raw_overlap = 0.0
    sum_cleaned_overlap = 0.0
    sum_raw_cer = 0.0
    sum_cleaned_cer = 0.0
    sum_raw_wer = 0.0
    sum_cleaned_wer = 0.0

    for i, sample in enumerate(samples):
        audio_path = Path("realtime_backend/tests/fixtures") / sample["audio_path"]
        expected = sample["expected_sentence"]
        
        print(f"[{i+1}/{len(samples)}] {sample['id']}...", end="\r")
        
        try:
            transcript = await pipeline.process_audio_path(
                audio_path,
                source="benchmark",
                language="tr",
                quality_mode=args.quality
            )
            
            raw_text = " ".join(s.raw_text for s in transcript.segments)
            cleaned_text = " ".join(s.corrected_text for s in transcript.segments)
            
            raw_matched, raw_missing, raw_overlap, raw_cer, raw_wer = calculate_overlap_metrics(expected, raw_text)
            clean_matched, clean_missing, clean_overlap, clean_cer, clean_wer = calculate_overlap_metrics(expected, cleaned_text)
            
            sum_raw_overlap += raw_overlap
            sum_cleaned_overlap += clean_overlap
            sum_raw_cer += raw_cer
            sum_cleaned_cer += clean_cer
            sum_raw_wer += raw_wer
            sum_cleaned_wer += clean_wer
            
            results.append({
                "id": sample["id"],
                "audio_path": str(sample["audio_path"]),
                "expected_sentence": expected,
                "raw_transcript": raw_text,
                "cleaned_transcript": cleaned_text,
                "raw": {
                    "matched_terms": raw_matched,
                    "missing_terms": raw_missing,
                    "keyword_overlap_quality_score": round(raw_overlap, 4),
                    "character_error_rate": round(raw_cer, 4),
                    "word_error_rate": round(raw_wer, 4)
                },
                "cleaned": {
                    "matched_terms": clean_matched,
                    "missing_terms": clean_missing,
                    "keyword_overlap_quality_score": round(clean_overlap, 4),
                    "character_error_rate": round(clean_cer, 4),
                    "word_error_rate": round(clean_wer, 4)
                }
            })
        except Exception as exc:
            print(f"\n❌ Error processing {sample['id']}: {exc}")

    count = len(results)
    avg_raw_overlap = sum_raw_overlap / count if count else 0
    avg_cleaned_overlap = sum_cleaned_overlap / count if count else 0
    avg_raw_cer = sum_raw_cer / count if count else 0
    avg_cleaned_cer = sum_cleaned_cer / count if count else 0
    avg_raw_wer = sum_raw_wer / count if count else 0
    avg_cleaned_wer = sum_cleaned_wer / count if count else 0
    
    report = {
        "dataset": "Mozilla Common Voice Turkish",
        "metric": "keyword_overlap_quality_score",
        "sample_count": count,
        "quality_mode": args.quality,
        "model": settings.asr_model_name,
        "summary": {
            "avg_raw_keyword_overlap": round(avg_raw_overlap, 4),
            "avg_cleaned_keyword_overlap": round(avg_cleaned_overlap, 4),
            "avg_raw_cer": round(avg_raw_cer, 4),
            "avg_cleaned_cer": round(avg_cleaned_cer, 4),
            "avg_raw_wer": round(avg_raw_wer, 4),
            "avg_cleaned_wer": round(avg_cleaned_wer, 4),
            "improvement_delta_overlap": round(avg_cleaned_overlap - avg_raw_overlap, 4)
        },
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "results": results
    }

    print(f"\n\n✅ Benchmark Complete")
    print(f"Average Raw Overlap: {avg_raw_overlap:.2%}")
    print(f"Average Cleaned Overlap: {avg_cleaned_overlap:.2%}")
    print(f"Improvement Delta: {avg_cleaned_overlap - avg_raw_overlap:+.2%}")
    print(f"Average Raw WER: {avg_raw_wer:.2%}")
    print(f"Average Cleaned WER: {avg_cleaned_wer:.2%}")
    
    if args.output_json:
        with args.output_json.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"📄 Report saved to: {args.output_json}")

if __name__ == "__main__":
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())
