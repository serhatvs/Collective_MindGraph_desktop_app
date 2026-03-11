"""Application configuration for the realtime transcription backend."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional at import time
    load_dotenv = None


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_local_dotenv() -> None:
    if load_dotenv is None:
        return

    candidates = [
        _backend_root() / ".env",
        Path.cwd() / ".env",
    ]
    loaded: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in loaded or not resolved.exists():
            continue
        load_dotenv(resolved, override=False)
        loaded.add(resolved)


def _huggingface_token_paths() -> list[Path]:
    candidates = [
        Path.home() / ".cache" / "huggingface" / "token",
        Path.home() / ".huggingface" / "token",
    ]
    appdata = os.getenv("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "huggingface" / "token")
    return candidates


def _resolve_pyannote_token() -> str | None:
    for env_name in (
        "CMG_RT_PYANNOTE_TOKEN",
        "HF_TOKEN",
        "HUGGINGFACE_HUB_TOKEN",
        "HUGGING_FACE_HUB_TOKEN",
    ):
        value = os.getenv(env_name)
        if value:
            return value

    for path in _huggingface_token_paths():
        if not path.exists():
            continue
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token
    return None


_load_local_dotenv()


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass(slots=True)
class Settings:
    app_name: str = "Collective MindGraph Realtime Backend"
    host: str = field(default_factory=lambda: _env("CMG_RT_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("CMG_RT_PORT", 8080))
    log_level: str = field(default_factory=lambda: _env("CMG_RT_LOG_LEVEL", "INFO"))

    data_dir: Path = field(
        default_factory=lambda: Path(_env("CMG_RT_DATA_DIR", str(Path.cwd() / "realtime_backend_data")))
    )
    temp_dir: Path = field(
        default_factory=lambda: Path(_env("CMG_RT_TEMP_DIR", str(Path.cwd() / "realtime_backend_temp")))
    )

    sample_rate: int = field(default_factory=lambda: _env_int("CMG_RT_SAMPLE_RATE", 16000))
    channels: int = field(default_factory=lambda: _env_int("CMG_RT_CHANNELS", 1))
    sample_width_bytes: int = field(default_factory=lambda: _env_int("CMG_RT_SAMPLE_WIDTH_BYTES", 2))
    default_language: str | None = field(
        default_factory=lambda: os.getenv("CMG_RT_LANGUAGE") or None
    )

    stream_partial_window_seconds: float = field(
        default_factory=lambda: _env_float("CMG_RT_STREAM_PARTIAL_WINDOW_SECONDS", 8.0)
    )
    stream_overlap_seconds: float = field(
        default_factory=lambda: _env_float("CMG_RT_STREAM_OVERLAP_SECONDS", 1.5)
    )
    stream_min_emit_seconds: float = field(
        default_factory=lambda: _env_float("CMG_RT_STREAM_MIN_EMIT_SECONDS", 4.0)
    )
    stream_buffer_retention_seconds: float = field(
        default_factory=lambda: _env_float("CMG_RT_STREAM_BUFFER_RETENTION_SECONDS", 24.0)
    )

    vad_provider: str = field(default_factory=lambda: _env("CMG_RT_VAD_PROVIDER", "silero"))
    vad_frame_ms: int = field(default_factory=lambda: _env_int("CMG_RT_VAD_FRAME_MS", 30))
    vad_min_speech_ms: int = field(default_factory=lambda: _env_int("CMG_RT_VAD_MIN_SPEECH_MS", 250))
    vad_min_silence_ms: int = field(default_factory=lambda: _env_int("CMG_RT_VAD_MIN_SILENCE_MS", 300))
    vad_padding_ms: int = field(default_factory=lambda: _env_int("CMG_RT_VAD_PADDING_MS", 120))
    vad_merge_gap_ms: int = field(default_factory=lambda: _env_int("CMG_RT_VAD_MERGE_GAP_MS", 120))
    vad_smoothing_frames: int = field(default_factory=lambda: _env_int("CMG_RT_VAD_SMOOTHING_FRAMES", 5))
    vad_max_region_seconds: float = field(
        default_factory=lambda: _env_float("CMG_RT_VAD_MAX_REGION_SECONDS", 24.0)
    )
    vad_target_region_seconds: float = field(
        default_factory=lambda: _env_float("CMG_RT_VAD_TARGET_REGION_SECONDS", 12.0)
    )
    vad_split_search_seconds: float = field(
        default_factory=lambda: _env_float("CMG_RT_VAD_SPLIT_SEARCH_SECONDS", 1.5)
    )
    vad_adaptive_multiplier: float = field(
        default_factory=lambda: _env_float("CMG_RT_VAD_ADAPTIVE_MULTIPLIER", 2.2)
    )
    vad_energy_threshold: float = field(
        default_factory=lambda: _env_float("CMG_RT_VAD_ENERGY_THRESHOLD", 0.015)
    )

    asr_provider: str = field(default_factory=lambda: _env("CMG_RT_ASR_PROVIDER", "faster_whisper"))
    asr_model_name: str = field(
        default_factory=lambda: _env("CMG_RT_ASR_MODEL", "large-v3-turbo")
    )
    asr_device: str = field(default_factory=lambda: _env("CMG_RT_ASR_DEVICE", "cuda"))
    asr_compute_type: str = field(
        default_factory=lambda: _env("CMG_RT_ASR_COMPUTE_TYPE", "float16")
    )
    asr_beam_size: int = field(default_factory=lambda: _env_int("CMG_RT_ASR_BEAM_SIZE", 5))
    asr_region_padding_seconds: float = field(
        default_factory=lambda: _env_float("CMG_RT_ASR_REGION_PADDING_SECONDS", 0.10)
    )

    diarizer_provider: str = field(default_factory=lambda: _env("CMG_RT_DIARIZER_PROVIDER", "pyannote"))
    diarizer_device: str = field(default_factory=lambda: _env("CMG_RT_DIARIZER_DEVICE", "cuda"))
    diarizer_model_name: str = field(
        default_factory=lambda: _env("CMG_RT_DIARIZER_MODEL", "pyannote/speaker-diarization-3.1")
    )
    diarizer_auth_token: str | None = field(
        default_factory=_resolve_pyannote_token
    )
    diarizer_region_padding_seconds: float = field(
        default_factory=lambda: _env_float("CMG_RT_DIARIZER_REGION_PADDING_SECONDS", 0.25)
    )
    diarizer_merge_gap_seconds: float = field(
        default_factory=lambda: _env_float("CMG_RT_DIARIZER_MERGE_GAP_SECONDS", 0.75)
    )
    diarizer_max_window_seconds: float = field(
        default_factory=lambda: _env_float("CMG_RT_DIARIZER_MAX_WINDOW_SECONDS", 18.0)
    )
    diarizer_overlap_threshold: float = field(
        default_factory=lambda: _env_float("CMG_RT_DIARIZER_OVERLAP_THRESHOLD", 0.35)
    )

    pipeline_max_window_seconds: float = field(
        default_factory=lambda: _env_float("CMG_RT_PIPELINE_MAX_WINDOW_SECONDS", 90.0)
    )
    pipeline_window_overlap_seconds: float = field(
        default_factory=lambda: _env_float("CMG_RT_PIPELINE_WINDOW_OVERLAP_SECONDS", 2.0)
    )

    llm_provider: str = field(default_factory=lambda: _env("CMG_RT_LLM_PROVIDER", "mock"))
    llm_model_name: str = field(default_factory=lambda: _env("CMG_RT_LLM_MODEL", "mock"))
    llm_endpoint: str | None = field(default_factory=lambda: os.getenv("CMG_RT_LLM_ENDPOINT") or None)
    llm_api_key: str | None = field(default_factory=lambda: os.getenv("CMG_RT_LLM_API_KEY") or None)
    llm_timeout_seconds: float = field(
        default_factory=lambda: _env_float("CMG_RT_LLM_TIMEOUT_SECONDS", 30.0)
    )
    llm_batch_size: int = field(default_factory=lambda: _env_int("CMG_RT_LLM_BATCH_SIZE", 12))
    llm_context_segments: int = field(
        default_factory=lambda: _env_int("CMG_RT_LLM_CONTEXT_SEGMENTS", 4)
    )

    enable_summary: bool = field(
        default_factory=lambda: _env("CMG_RT_ENABLE_SUMMARY", "true").lower() == "true"
    )

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "transcripts").mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
