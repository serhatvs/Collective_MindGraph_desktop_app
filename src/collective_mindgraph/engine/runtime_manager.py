"""Atomic ownership of replaceable engine provider bundles."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock

from collective_mindgraph.application.knowledge import IndexKnowledge
from collective_mindgraph.application.memory import AnswerMemory, SearchMemory
from collective_mindgraph.application.ports import TextEmbeddingModel
from collective_mindgraph.application.transcription.live_capture import CaptureLiveAudio
from collective_mindgraph.application.transcription.process_recording import (
    ProcessRecording,
)
from collective_mindgraph.application.transcription.result_archive import (
    TranscriptionResultArchive,
)
from collective_mindgraph.application.transcription.transcribe_recording import (
    TranscribeRecording,
)
from collective_mindgraph.domain import EngineHealth, ProviderHealth
from collective_mindgraph.infrastructure.ai import (
    DeterministicEmbeddingModel,
    LocalEndpointLanguageModel,
    SentenceTransformerEmbeddingModel,
)
from collective_mindgraph.infrastructure.audio.ffmpeg_normalizer import (
    FFmpegAudioNormalizer,
)
from collective_mindgraph.infrastructure.persistence import (
    SqliteEmbeddingStore,
    SqliteJobStore,
    SqliteKnowledgeGraphStore,
)
from collective_mindgraph.infrastructure.settings import EnginePreferenceStore
from collective_mindgraph.infrastructure.transcription.recording_processor import (
    RecordingProcessor,
)

from .settings import EngineSettings


@dataclass(frozen=True, slots=True)
class EngineRuntimeBundle:
    settings: EngineSettings
    embedding_model: TextEmbeddingModel | None
    language_model: LocalEndpointLanguageModel | None
    transcribe_recording: TranscribeRecording
    process_recording: ProcessRecording
    capture_live_audio: CaptureLiveAudio
    search_memory: SearchMemory
    answer_memory: AnswerMemory
    index_knowledge: IndexKnowledge

    def health(self, *, engine_version: str) -> EngineHealth:
        runtime = self.transcribe_recording.runtime_status()
        transcription = (
            ProviderHealth.DEGRADED
            if runtime.asr_mock_fallback_used or runtime.asr_status != "ok"
            else ProviderHealth.READY
        )
        embeddings = _adapter_health(
            configured=self.settings.embedding_provider not in {"disabled", "mock"},
            available=(
                self.embedding_model is not None
                and self.embedding_model.is_available()
                and self.settings.embedding_provider != "mock"
            ),
        )
        local_llm = _adapter_health(
            configured=self.language_model is not None,
            available=(self.language_model is not None and self.language_model.is_available()),
        )
        states = (transcription, embeddings, local_llm)
        overall = (
            ProviderHealth.UNAVAILABLE
            if transcription == ProviderHealth.UNAVAILABLE
            else (
                ProviderHealth.DEGRADED
                if ProviderHealth.UNAVAILABLE in states or ProviderHealth.DEGRADED in states
                else ProviderHealth.READY
            )
        )
        return EngineHealth(
            status=overall,
            engine_version=engine_version,
            transcription=transcription,
            embeddings=embeddings,
            local_llm=local_llm,
            detail="Runtime adapters were inspected directly.",
        )


class EngineRuntimeManager:
    """Build new provider graphs before publishing preferences or runtime state."""

    def __init__(
        self,
        *,
        settings: EngineSettings,
        preferences: EnginePreferenceStore,
        archive: TranscriptionResultArchive,
        knowledge: SqliteKnowledgeGraphStore,
        embeddings: SqliteEmbeddingStore,
        jobs: SqliteJobStore,
    ) -> None:
        self._settings = settings
        self._preferences = preferences
        self._archive = archive
        self._knowledge = knowledge
        self._embeddings = embeddings
        self._jobs = jobs
        self._lock = RLock()
        self._bundle = self._build_bundle(replace(settings))

    def snapshot(self) -> EngineRuntimeBundle:
        with self._lock:
            return self._bundle

    def apply(self, changes: dict[str, object]) -> EngineRuntimeBundle:
        with self._lock:
            candidate_settings = replace(self._settings)
            for key, value in changes.items():
                if not hasattr(candidate_settings, key):
                    raise ValueError(f"Unsupported engine setting: {key}")
                setattr(candidate_settings, key, value)
            self._validate(candidate_settings)
            candidate_bundle = self._build_bundle(candidate_settings)
            self._preferences.save(changes)
            for key, value in changes.items():
                setattr(self._settings, key, value)
            self._bundle = candidate_bundle
            return candidate_bundle

    def _build_bundle(self, settings: EngineSettings) -> EngineRuntimeBundle:
        self._validate(settings)
        processor = RecordingProcessor(settings=settings)
        transcribe = TranscribeRecording(processor, self._archive)
        embedding_model = _build_embedding_model(settings)
        semantic_enabled = settings.embedding_provider == "sentence_transformer"
        search = SearchMemory(
            self._knowledge,
            self._embeddings,
            embedding_model,
            semantic_enabled=semantic_enabled,
        )
        language_model = _build_language_model(settings)
        return EngineRuntimeBundle(
            settings=settings,
            embedding_model=embedding_model,
            language_model=language_model,
            transcribe_recording=transcribe,
            process_recording=ProcessRecording(transcribe, self._jobs),
            capture_live_audio=CaptureLiveAudio(
                settings,
                processor,
                FFmpegAudioNormalizer(
                    sample_rate=settings.sample_rate,
                    channels=settings.channels,
                ),
                self._archive,
            ),
            search_memory=search,
            answer_memory=AnswerMemory(search, language_model),
            index_knowledge=IndexKnowledge(
                self._knowledge,
                self._embeddings,
                embedding_model if semantic_enabled else None,
            ),
        )

    @staticmethod
    def _validate(settings: EngineSettings) -> None:
        if settings.asr_provider not in {"mock", "auto", "faster_whisper"}:
            raise ValueError(f"Unsupported ASR provider: {settings.asr_provider}")
        if not settings.asr_model_name.strip():
            raise ValueError("ASR model cannot be empty.")
        if settings.vad_provider not in {"energy", "silero"}:
            raise ValueError(f"Unsupported VAD provider: {settings.vad_provider}")
        if settings.diarizer_provider not in {"fallback", "pyannote"}:
            raise ValueError(
                f"Unsupported speaker-separation provider: {settings.diarizer_provider}"
            )
        if settings.embedding_provider not in {
            "disabled",
            "mock",
            "sentence_transformer",
        }:
            raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")
        if settings.embedding_provider == "sentence_transformer":
            model_path = Path(settings.embedding_model_path).expanduser()
            if not settings.embedding_model_path.strip() or not model_path.exists():
                raise ValueError("The configured local embedding model path does not exist.")
        if settings.llm_provider not in {
            "disabled",
            "none",
            "auto_local",
            "mock",
            "ollama",
            "lmstudio",
            "openai_compatible",
        }:
            raise ValueError(f"Unsupported local language-model provider: {settings.llm_provider}")
        if settings.transcription_quality_mode not in {
            "fast",
            "balanced",
            "max_quality",
            "bad_mic_recovery",
            "selective_recovery",
        }:
            raise ValueError(
                f"Unsupported transcription quality: {settings.transcription_quality_mode}"
            )


def _build_embedding_model(settings: EngineSettings) -> TextEmbeddingModel | None:
    if settings.embedding_provider == "sentence_transformer":
        return SentenceTransformerEmbeddingModel(
            model_path=settings.embedding_model_path,
            dimension=settings.embedding_dimension,
            device=settings.embedding_device,
        )
    if settings.embedding_provider == "mock":
        return DeterministicEmbeddingModel(dim=settings.embedding_dimension)
    return None


def _build_language_model(settings: EngineSettings) -> LocalEndpointLanguageModel | None:
    if settings.llm_provider in {"disabled", "none"}:
        return None
    default_endpoint = (
        "http://127.0.0.1:11434/v1"
        if settings.llm_provider == "ollama"
        else "http://127.0.0.1:1234/v1"
    )
    return LocalEndpointLanguageModel(
        base_url=settings.llm_endpoint or default_endpoint,
        timeout=int(settings.llm_timeout_seconds),
        allow_remote=settings.allow_remote_access,
        model_name=settings.llm_model_name,
        api_key=settings.llm_api_key,
    )


def _adapter_health(*, configured: bool, available: bool) -> ProviderHealth:
    if not configured:
        return ProviderHealth.DISABLED
    return ProviderHealth.READY if available else ProviderHealth.UNAVAILABLE
