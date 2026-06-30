"""Smoke-check the real Collective MindGraph ASR backend on GPU.

This script uses the same backend Settings and ASR builder as the app. It does
not instantiate Faster-Whisper directly except through the CMG ASR provider.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time


REPO_ROOT = Path(__file__).resolve().parents[1]
REALTIME_BACKEND_ROOT = REPO_ROOT / "realtime_backend"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REALTIME_BACKEND_ROOT))

from app.config import Settings  # noqa: E402
from app.pipeline.asr import ASR_STATUS_MOCK_FALLBACK, build_asr  # noqa: E402
from app.pipeline.asr_runtime_config import (  # noqa: E402
    build_asr_diagnostics,
    format_asr_diagnostics,
    probe_torch_cuda,
)
from app.utils.logging import configure_logging  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether CMG ASR loads Faster-Whisper on GPU.")
    parser.add_argument("--audio", type=Path, help="Optional audio file to transcribe after model load.")
    parser.add_argument("--profile", choices=["cpu", "gpu_asr"], help="Override CMG_RUNTIME_PROFILE for this run.")
    parser.add_argument(
        "--observation-seconds",
        type=int,
        default=30,
        help="Seconds to keep the process alive after model load for nvidia-smi observation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.profile:
        import os

        os.environ["CMG_RUNTIME_PROFILE"] = args.profile

    configure_logging("INFO")
    settings = Settings()
    settings.ensure_directories()

    cuda_probe = probe_torch_cuda()
    try:
        asr = build_asr(settings)
    except Exception as exc:
        print_selected_config(settings, cuda_probe)
        print(f"ASR backend failed to load: {type(exc).__name__}: {exc}")
        return 1

    diagnostics = build_asr_diagnostics(settings, asr)
    print(format_asr_diagnostics(diagnostics))
    print(f"Model loaded on CUDA: {'yes' if getattr(asr, 'gpu_loaded', False) else 'no'}")
    print(f"GPU observation window: {max(0, args.observation_seconds)} seconds")
    if args.observation_seconds > 0:
        time.sleep(args.observation_seconds)

    if args.audio:
        audio_path = args.audio.expanduser().resolve()
        if not audio_path.exists():
            print(f"Audio file not found: {audio_path}")
            return 1
        segments = asr.transcribe(
            audio_path,
            language=settings.default_language,
            quality_mode=settings.transcription_quality_mode,
        )
        raw_transcript = "\n".join(segment.text for segment in segments).strip()
        print(f"Transcribed audio: {audio_path}")
        print(f"Segment count: {len(segments)}")
        print("Raw transcript:")
        print(raw_transcript or "[empty]")

    if getattr(asr, "asr_status", None) == ASR_STATUS_MOCK_FALLBACK or getattr(asr, "mock_fallback_used", False):
        print(f"Invalid ASR smoke output: {ASR_STATUS_MOCK_FALLBACK}")
        return 2
    if getattr(asr, "gpu_requested", False) and not getattr(asr, "gpu_loaded", False):
        print(f"GPU requested but ASR did not load on CUDA. Reason: {getattr(asr, 'gpu_fallback_reason', None)}")
        return 2
    return 0


def print_selected_config(settings: Settings, cuda_probe) -> None:
    print(f"ASR runtime profile: {settings.asr_runtime_profile}")
    print(f"ASR backend: {settings.asr_provider}")
    print(f"ASR model: {settings.asr_model_name}")
    print(f"ASR device: {settings.asr_device}")
    print(f"ASR compute type: {settings.asr_compute_type}")
    print(f"ASR language: {settings.default_language}")
    print(f"CUDA available through torch: {cuda_probe.available}")
    print(f"Torch CUDA probe status: {cuda_probe.status}")
    if cuda_probe.error:
        print(f"Torch CUDA probe error: {cuda_probe.error}")


if __name__ == "__main__":
    raise SystemExit(main())
