"""Transcription adapters for recorded audio files."""

from __future__ import annotations

from collections.abc import Callable
import mimetypes
import os
import json
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from uuid import uuid4

from .audio_capture import AutoStopConfig
from .runtime_paths import default_transcription_settings_path, is_frozen_build
from .wake_phrase import DEFAULT_SHUTDOWN_PHRASE, DEFAULT_WAKE_PHRASE


DEFAULT_REALTIME_BACKEND_URL = "http://127.0.0.1:8080"
DEFAULT_REALTIME_TIMEOUT_SECONDS = 240
DEFAULT_STREAM_FLUSH_INTERVAL_MS = 1200


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    text: str
    model_id: str
    audio_path: str
    conversation_id: str | None = None
    raw_text_output: str | None = None
    corrected_text_output: str | None = None
    speaker_count: int | None = None
    summary: str | None = None
    topics: list[dict[str, object]] = field(default_factory=list)
    action_items: list[dict[str, object]] = field(default_factory=list)
    decisions: list[dict[str, object]] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    speaker_stats: list[dict[str, object]] = field(default_factory=list)
    segments: list[dict[str, object]] = field(default_factory=list)
    quality_report: dict[str, object] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StreamingTranscriptionUpdate:
    conversation_id: str | None
    audio_path: str
    text: str
    raw_text_output: str | None = None
    corrected_text_output: str | None = None
    speaker_count: int | None = None
    speaker_stats: list[dict[str, object]] = field(default_factory=list)
    segments: list[dict[str, object]] = field(default_factory=list)
    action_items: list[dict[str, object]] = field(default_factory=list)
    decisions: list[dict[str, object]] = field(default_factory=list)
    is_final: bool = False


@dataclass(frozen=True, slots=True)
class QueryResultItem:
    result_type: str
    text: str
    source_session_id: str
    source_segment_id: str | None = None
    matched_field: str | None = None
    matched_terms: list[str] = field(default_factory=list)
    score: float = 1.0
    preview: str | None = None
    timestamp: str | None = None
    # Phase 3 Fields
    matched_by: str | None = None
    score_breakdown: dict[str, float] = field(default_factory=dict)
    edge_path: str | None = None
    node_id: str | None = None


@dataclass(frozen=True, slots=True)
class QueryResponse:
    query: str
    results: list[QueryResultItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class EvidenceStep:
    node_id: str
    node_type: str
    text: str
    edge_type: str | None = None
    direction: str = "out"


@dataclass(frozen=True, slots=True)
class EvidenceChain:
    steps: list[EvidenceStep] = field(default_factory=list)
    explanation: str = ""


@dataclass(frozen=True, slots=True)
class ReasoningResponse:
    query: str
    chains: list[EvidenceChain] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class MemoryAskResponse:
    query: str
    mode: str
    answer_type: str
    short_answer: str
    confidence_level: str
    evidence_chains: list[EvidenceChain] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_session_ids: list[str] = field(default_factory=list)
    source_segment_ids: list[str] = field(default_factory=list)
    missing_evidence_note: str | None = None


@dataclass(frozen=True, slots=True)
class BackendHealthStatus:
    status: str
    app_name: str
    vad_provider: str
    asr_provider: str
    asr_provider_resolved: str | None = None
    asr_fallback_provider: str | None = None
    asr_status: str | None = None
    asr_mock_fallback_used: bool = False
    asr_model_name: str | None = None
    asr_quality_profile: str | None = None
    asr_runtime_profile: str | None = None
    asr_device: str | None = None
    asr_compute_type: str | None = None
    asr_language: str | None = None
    gpu_enabled: bool | None = None
    gpu_required: bool | None = None
    cuda_available_through_torch: bool | None = None
    gpu_requested: bool | None = None
    gpu_actually_used_by_asr: bool | None = None
    faster_whisper_cuda_load_status: str | None = None
    gpu_fallback_happened: bool | None = None
    gpu_fallback_reason: str | None = None
    embedding_device: str | None = None
    local_llm_enabled: bool | None = None
    diarizer_provider: str = ""
    llm_provider: str = ""
    llm_provider_resolved: str | None = None
    llm_fallback_provider: str | None = None


@dataclass(frozen=True, slots=True)
class RealtimeBackendTranscriptionConfig:
    base_url: str = DEFAULT_REALTIME_BACKEND_URL
    language: str | None = None
    request_timeout_seconds: int = DEFAULT_REALTIME_TIMEOUT_SECONDS
    stream_live_transcription: bool = True
    stream_flush_interval_ms: int = DEFAULT_STREAM_FLUSH_INTERVAL_MS
    audio_input_device_id: str | None = None
    audio_input_device_label: str | None = None
    auto_stop_enabled: bool = True
    auto_stop_min_speech_seconds: float = 0.35
    auto_stop_silence_seconds: float = 1.25
    auto_stop_silence_threshold: float = 0.012
    wake_trigger_enabled: bool = True
    wake_phrase: str = DEFAULT_WAKE_PHRASE
    shutdown_phrase: str = DEFAULT_SHUTDOWN_PHRASE
    wake_cooldown_seconds: float = 2.0
    # Phase 3 Fields
    embeddings_enabled: bool = True
    embedding_provider: str = "mock"
    embedding_model_path: str = ""
    embedding_dimension: int = 384
    allow_remote_model_download: bool = False

    @classmethod
    def from_env(cls) -> "RealtimeBackendTranscriptionConfig":
        timeout_raw = os.getenv("CMG_TRANSCRIPTION_TIMEOUT_SECONDS")
        timeout_seconds = int(timeout_raw) if timeout_raw else DEFAULT_REALTIME_TIMEOUT_SECONDS
        return cls(
            base_url=(
                os.getenv("CMG_TRANSCRIPTION_BACKEND_URL")
                or os.getenv("CMG_RT_BACKEND_URL")
                or DEFAULT_REALTIME_BACKEND_URL
            ).rstrip("/"),
            language=(os.getenv("CMG_TRANSCRIPTION_LANGUAGE") or "").strip() or None,
            request_timeout_seconds=timeout_seconds,
            stream_live_transcription=_parse_bool(os.getenv("CMG_TRANSCRIPTION_STREAM_LIVE"), True),
            stream_flush_interval_ms=int(
                os.getenv("CMG_TRANSCRIPTION_STREAM_FLUSH_INTERVAL_MS") or DEFAULT_STREAM_FLUSH_INTERVAL_MS
            ),
            audio_input_device_id=(os.getenv("CMG_AUDIO_INPUT_DEVICE_ID") or "").strip() or None,
            audio_input_device_label=(os.getenv("CMG_AUDIO_INPUT_DEVICE_LABEL") or "").strip() or None,
            auto_stop_enabled=_parse_bool(os.getenv("CMG_AUTO_STOP_ENABLED"), True),
            auto_stop_min_speech_seconds=float(os.getenv("CMG_AUTO_STOP_MIN_SPEECH_SECONDS") or 0.35),
            auto_stop_silence_seconds=float(os.getenv("CMG_AUTO_STOP_SILENCE_SECONDS") or 1.25),
            auto_stop_silence_threshold=float(os.getenv("CMG_AUTO_STOP_SILENCE_THRESHOLD") or 0.012),
            wake_trigger_enabled=_parse_bool(os.getenv("CMG_WAKE_TRIGGER_ENABLED"), True),
            wake_phrase=(os.getenv("CMG_WAKE_PHRASE") or DEFAULT_WAKE_PHRASE).strip() or DEFAULT_WAKE_PHRASE,
            shutdown_phrase=(
                os.getenv("CMG_SHUTDOWN_PHRASE") or DEFAULT_SHUTDOWN_PHRASE
            ).strip() or DEFAULT_SHUTDOWN_PHRASE,
            wake_cooldown_seconds=float(os.getenv("CMG_WAKE_COOLDOWN_SECONDS") or 2.0),
            embeddings_enabled=_parse_bool(os.getenv("CMG_EMBEDDINGS_ENABLED"), True),
            embedding_provider=os.getenv("CMG_EMBEDDING_PROVIDER", "mock"),
            embedding_model_path=os.getenv("CMG_EMBEDDING_MODEL_PATH", ""),
            embedding_dimension=int(os.getenv("CMG_EMBEDDING_DIMENSION") or 384),
            allow_remote_model_download=_parse_bool(os.getenv("CMG_ALLOW_REMOTE_MODEL_DOWNLOAD"), False),
        )

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "RealtimeBackendTranscriptionConfig":
        base = cls.from_env()
        base_url = str(payload.get("base_url") or payload.get("backend_url") or base.base_url).strip().rstrip("/")
        language_value = payload.get("language")
        timeout_value = payload.get("request_timeout_seconds")
        stream_live_value = payload.get("stream_live_transcription")
        stream_flush_interval_value = payload.get("stream_flush_interval_ms")
        audio_input_device_id = payload.get("audio_input_device_id")
        audio_input_device_label = payload.get("audio_input_device_label")
        auto_stop_enabled_value = payload.get("auto_stop_enabled")
        auto_stop_min_speech_value = payload.get("auto_stop_min_speech_seconds")
        auto_stop_silence_value = payload.get("auto_stop_silence_seconds")
        auto_stop_threshold_value = payload.get("auto_stop_silence_threshold")
        wake_trigger_enabled_value = payload.get("wake_trigger_enabled")
        wake_phrase_value = payload.get("wake_phrase")
        shutdown_phrase_value = payload.get("shutdown_phrase")
        wake_cooldown_value = payload.get("wake_cooldown_seconds")
        return cls(
            base_url=base_url or base.base_url,
            language=str(language_value).strip() or None if language_value is not None else base.language,
            request_timeout_seconds=(
                int(timeout_value) if timeout_value is not None else base.request_timeout_seconds
            ),
            stream_live_transcription=(
                _parse_bool(stream_live_value, base.stream_live_transcription)
                if stream_live_value is not None
                else base.stream_live_transcription
            ),
            stream_flush_interval_ms=(
                int(stream_flush_interval_value)
                if stream_flush_interval_value is not None
                else base.stream_flush_interval_ms
            ),
            audio_input_device_id=(
                str(audio_input_device_id).strip() or None
                if audio_input_device_id is not None
                else base.audio_input_device_id
            ),
            audio_input_device_label=(
                str(audio_input_device_label).strip() or None
                if audio_input_device_label is not None
                else base.audio_input_device_label
            ),
            auto_stop_enabled=(
                _parse_bool(auto_stop_enabled_value, base.auto_stop_enabled)
                if auto_stop_enabled_value is not None
                else base.auto_stop_enabled
            ),
            auto_stop_min_speech_seconds=(
                float(auto_stop_min_speech_value)
                if auto_stop_min_speech_value is not None
                else base.auto_stop_min_speech_seconds
            ),
            auto_stop_silence_seconds=(
                float(auto_stop_silence_value)
                if auto_stop_silence_value is not None
                else base.auto_stop_silence_seconds
            ),
            auto_stop_silence_threshold=(
                float(auto_stop_threshold_value)
                if auto_stop_threshold_value is not None
                else base.auto_stop_silence_threshold
            ),
            wake_trigger_enabled=(
                _parse_bool(wake_trigger_enabled_value, base.wake_trigger_enabled)
                if wake_trigger_enabled_value is not None
                else base.wake_trigger_enabled
            ),
            wake_phrase=(
                str(wake_phrase_value).strip() or base.wake_phrase
                if wake_phrase_value is not None
                else base.wake_phrase
            ),
            shutdown_phrase=(
                str(shutdown_phrase_value).strip() or base.shutdown_phrase
                if shutdown_phrase_value is not None
                else base.shutdown_phrase
            ),
            wake_cooldown_seconds=(
                float(wake_cooldown_value)
                if wake_cooldown_value is not None
                else base.wake_cooldown_seconds
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_auto_stop_config(self) -> AutoStopConfig:
        return AutoStopConfig(
            enabled=self.auto_stop_enabled,
            min_speech_seconds=self.auto_stop_min_speech_seconds,
            silence_seconds=self.auto_stop_silence_seconds,
            silence_threshold=self.auto_stop_silence_threshold,
        )

    def websocket_stream_url(self) -> str:
        base = self.base_url.rstrip("/")
        if base.startswith("https://"):
            base = "wss://" + base[len("https://") :]
        elif base.startswith("http://"):
            base = "ws://" + base[len("http://") :]
        return f"{base}/transcribe/stream"


class RealtimeBackendTranscriptionSettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = (path or default_transcription_settings_path()).resolve()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> RealtimeBackendTranscriptionConfig:
        if not self._path.exists():
            return RealtimeBackendTranscriptionConfig.from_env()

        payload = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Transcription settings file is invalid.")
        return RealtimeBackendTranscriptionConfig.from_dict(payload)

    def save(self, config: RealtimeBackendTranscriptionConfig) -> Path:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
        return self._path


class RealtimeBackendTranscriptionService:
    def __init__(
        self,
        config: RealtimeBackendTranscriptionConfig | None = None,
        request_opener: Callable[..., object] | None = None,
    ) -> None:
        self._config = config or RealtimeBackendTranscriptionConfig.from_env()
        self._request_opener = request_opener or urlopen

    def transcribe_file(self, audio_path: str | Path) -> TranscriptionResult:
        path = Path(audio_path).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"Audio file was not found: {path}")

        file_size = path.stat().st_size
        if file_size <= 0:
            raise ValueError("Audio file is empty.")

        payload, content_type = self._build_multipart_payload(path)
        request = Request(
            urljoin(f"{self._config.base_url}/", "transcribe/file"),
            data=payload,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": content_type,
            },
        )
        try:
            response_payload = self._read_json_response(request)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise ValueError(
                f"Realtime transcription backend request failed: {detail or exc.reason or exc.code}"
            ) from exc
        except URLError as exc:
            raise ValueError(_backend_unreachable_message(self._config.base_url)) from exc
        except TimeoutError as exc:
            raise ValueError("Realtime transcription backend request timed out.") from exc

        return self.result_from_payload(response_payload, audio_path=path)

    def reason_memory(self, query: str, max_depth: int = 3) -> ReasoningResponse:
        import urllib.parse

        safe_query = urllib.parse.quote(query)
        request = Request(
            urljoin(f"{self._config.base_url}/", f"reason?q={safe_query}&max_depth={max_depth}"),
            method="GET",
            headers={"Accept": "application/json"},
        )
        try:
            payload = self._read_json_response(request)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise ValueError(f"Memory reasoning failed: {detail or exc.reason or exc.code}") from exc
        except URLError as exc:
            raise ValueError(_backend_unreachable_message(self._config.base_url)) from exc
        except TimeoutError:
            raise ValueError("Reasoning request timed out.")

        chains_payload = payload.get("chains") or []
        chains = [
            EvidenceChain(
                steps=[
                    EvidenceStep(
                        node_id=str(s.get("node_id") or ""),
                        node_type=str(s.get("node_type") or "unknown"),
                        text=str(s.get("text") or ""),
                        edge_type=self._extract_string(s, "edge_type"),
                        direction=str(s.get("direction") or "out"),
                    )
                    for s in (c.get("steps") or [])
                ],
                explanation=str(c.get("explanation") or ""),
            )
            for c in chains_payload
            if isinstance(c, dict)
        ]
        return ReasoningResponse(query=query, chains=chains, warnings=payload.get("warnings") or [])

    def query_memory(self, query: str, mode: str = "hybrid") -> QueryResponse:
        import urllib.parse

        safe_query = urllib.parse.quote(query)
        safe_mode = urllib.parse.quote(mode)
        request = Request(
            urljoin(f"{self._config.base_url}/", f"query?q={safe_query}&mode={safe_mode}"),
            method="GET",
            headers={"Accept": "application/json"},
        )
        try:
            payload = self._read_json_response(request)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise ValueError(f"Memory query failed: {detail or exc.reason or exc.code}") from exc
        except URLError as exc:
            raise ValueError(_backend_unreachable_message(self._config.base_url)) from exc
        except TimeoutError as exc:
            raise ValueError("Memory query timed out.") from exc

        results_payload = payload.get("results") or []
        results = [
            QueryResultItem(
                result_type=str(item.get("result_type") or "unknown"),
                text=str(item.get("text") or ""),
                source_session_id=str(item.get("source_session_id") or ""),
                source_segment_id=self._extract_string(item, "source_segment_id"),
                matched_field=self._extract_string(item, "matched_field"),
                matched_terms=self._extract_string_list(item, "matched_terms"),
                score=float(item.get("score") or 1.0),
                preview=self._extract_string(item, "preview"),
                timestamp=self._extract_string(item, "timestamp"),
                matched_by=self._extract_string(item, "matched_by"),
                score_breakdown=item.get("score_breakdown") if isinstance(item.get("score_breakdown"), dict) else {},
                edge_path=self._extract_string(item, "edge_path"),
                node_id=self._extract_string(item, "node_id"),
            )
            for item in results_payload
            if isinstance(item, dict)
        ]
        return QueryResponse(query=query, results=results, warnings=payload.get("warnings") or [])

    def ask_memory(
        self, 
        query: str, 
        mode: str = "evidence_only", 
        session_id: str | None = None,
        include_pending: bool = False
    ) -> MemoryAskResponse:
        import urllib.parse

        params = {"q": query, "mode": mode, "include_pending": str(include_pending).lower()}
        if session_id:
            params["session_id"] = session_id
        
        query_string = urllib.parse.urlencode(params)
        request = Request(
            urljoin(f"{self._config.base_url}/", f"memory/ask?{query_string}"),
            method="GET",
            headers={"Accept": "application/json"},
        )
        try:
            payload = self._read_json_response(request)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise ValueError(f"Memory ask failed: {detail or exc.reason or exc.code}") from exc
        except URLError as exc:
            raise ValueError(_backend_unreachable_message(self._config.base_url)) from exc
        except TimeoutError:
            raise ValueError("Ask request timed out.")

        chains_payload = payload.get("evidence_chains") or []
        chains = [
            EvidenceChain(
                steps=[
                    EvidenceStep(
                        node_id=str(s.get("node_id") or ""),
                        node_type=str(s.get("node_type") or "unknown"),
                        text=str(s.get("text") or ""),
                        edge_type=self._extract_string(s, "edge_type"),
                        direction=str(s.get("direction") or "out"),
                    )
                    for s in (c.get("steps") or [])
                ],
                explanation=str(c.get("explanation") or ""),
            )
            for c in chains_payload
            if isinstance(c, dict)
        ]
        
        return MemoryAskResponse(
            query=query,
            mode=mode,
            answer_type=str(payload.get("answer_type") or "evidence_only"),
            short_answer=str(payload.get("short_answer") or ""),
            evidence_chains=chains,
            warnings=payload.get("warnings") or [],
            confidence_level=str(payload.get("confidence_level") or "low"),
            source_session_ids=self._extract_string_list(payload, "source_session_ids"),
            source_segment_ids=self._extract_string_list(payload, "source_segment_ids"),
            missing_evidence_note=self._extract_string(payload, "missing_evidence_note")
        )

    def fetch_health(self) -> BackendHealthStatus:
        request = Request(
            urljoin(f"{self._config.base_url}/", "health"),
            method="GET",
            headers={"Accept": "application/json"},
        )
        try:
            payload = self._read_json_response(request)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise ValueError(f"Backend health request failed: {detail or exc.reason or exc.code}") from exc
        except URLError as exc:
            raise ValueError("Realtime transcription backend is not reachable.") from exc
        except TimeoutError as exc:
            raise ValueError("Realtime transcription backend health request timed out.") from exc

        return BackendHealthStatus(
            status=self._extract_string(payload, "status") or "unknown",
            app_name=self._extract_string(payload, "app_name") or "Realtime Backend",
            vad_provider=self._extract_string(payload, "vad_provider") or "-",
            asr_provider=self._extract_string(payload, "asr_provider") or "-",
            asr_provider_resolved=self._extract_string(payload, "asr_provider_resolved"),
            asr_fallback_provider=self._extract_string(payload, "asr_fallback_provider"),
            asr_status=self._extract_string(payload, "asr_status"),
            asr_mock_fallback_used=bool(payload.get("asr_mock_fallback_used") or False),
            asr_model_name=self._extract_string(payload, "asr_model_name"),
            asr_quality_profile=self._extract_string(payload, "asr_quality_profile"),
            asr_runtime_profile=self._extract_string(payload, "asr_runtime_profile"),
            asr_device=self._extract_string(payload, "asr_device"),
            asr_compute_type=self._extract_string(payload, "asr_compute_type"),
            asr_language=self._extract_string(payload, "asr_language"),
            gpu_enabled=self._extract_bool(payload, "gpu_enabled"),
            gpu_required=self._extract_bool(payload, "gpu_required"),
            cuda_available_through_torch=self._extract_bool(payload, "cuda_available_through_torch"),
            gpu_requested=self._extract_bool(payload, "gpu_requested"),
            gpu_actually_used_by_asr=self._extract_bool(payload, "gpu_actually_used_by_asr"),
            faster_whisper_cuda_load_status=self._extract_string(payload, "faster_whisper_cuda_load_status"),
            gpu_fallback_happened=self._extract_bool(payload, "gpu_fallback_happened"),
            gpu_fallback_reason=self._extract_string(payload, "gpu_fallback_reason"),
            embedding_device=self._extract_string(payload, "embedding_device"),
            local_llm_enabled=self._extract_bool(payload, "local_llm_enabled"),
            diarizer_provider=self._extract_string(payload, "diarizer_provider") or "-",
            llm_provider=self._extract_string(payload, "llm_provider") or "-",
            llm_provider_resolved=self._extract_string(payload, "llm_provider_resolved"),
            llm_fallback_provider=self._extract_string(payload, "llm_fallback_provider"),
        )

    def result_from_payload(self, payload: dict[str, object], audio_path: str | Path) -> TranscriptionResult:
        transcript_text = self._extract_text(payload)
        if not transcript_text:
            raise ValueError("Realtime transcription backend returned an empty transcript.")

        normalized_audio_path = str(Path(audio_path).expanduser().resolve())
        transcript_payload = payload.get("transcript")
        if not isinstance(transcript_payload, dict):
            transcript_payload = {}

        speaker_stats = payload.get("speaker_stats")
        normalized_speaker_stats = speaker_stats if isinstance(speaker_stats, list) else []
        segments = transcript_payload.get("segments") if transcript_payload else payload.get("segments")
        normalized_segments = segments if isinstance(segments, list) else []
        conversation_id = self._extract_string(transcript_payload, "conversation_id") or self._extract_string(
            payload,
            "conversation_id",
        )
        summary_payload: dict[str, object] = payload if self._extract_string(payload, "summary") else {}
        quality_payload: dict[str, object] | None = payload.get("quality_report") if isinstance(
            payload.get("quality_report"),
            dict,
        ) else None
        if conversation_id:
            if not summary_payload:
                summary_payload = self._fetch_optional_json(f"summary/{conversation_id}") or {}
            if quality_payload is None:
                quality_payload = self._fetch_optional_json(f"quality/{conversation_id}")

        metadata = {}
        if transcript_payload and "metadata" in transcript_payload:
            metadata = transcript_payload.get("metadata", {})
            
        return TranscriptionResult(
            text=transcript_text,
            model_id="realtime_backend",
            audio_path=normalized_audio_path,
            conversation_id=conversation_id,
            raw_text_output=self._extract_string(payload, "raw_text_output"),
            corrected_text_output=self._extract_string(payload, "corrected_text_output"),
            speaker_count=len(normalized_speaker_stats) or None,
            summary=self._extract_string(summary_payload, "summary"),
            topics=self._extract_list(summary_payload, "topics"),
            action_items=self._extract_list(summary_payload, "action_items"),
            decisions=self._extract_list(summary_payload, "decisions"),
            people=self._extract_string_list(summary_payload, "people") or self._extract_string_list(payload.get("transcript") or {}, "people"),
            speaker_stats=[item for item in normalized_speaker_stats if isinstance(item, dict)],
            segments=[item for item in normalized_segments if isinstance(item, dict)],
            quality_report=quality_payload,
            metadata=metadata,
        )

    def stream_update_from_payload(
        self,
        payload: dict[str, object],
        audio_path: str | Path,
    ) -> StreamingTranscriptionUpdate:
        normalized_audio_path = str(Path(audio_path).expanduser().resolve())
        segments = payload.get("segments")
        speaker_stats = payload.get("speaker_stats")
        normalized_speaker_stats = [item for item in speaker_stats if isinstance(item, dict)] if isinstance(
            speaker_stats,
            list,
        ) else []
        return StreamingTranscriptionUpdate(
            conversation_id=self._extract_string(payload, "conversation_id"),
            audio_path=normalized_audio_path,
            text=self._extract_text(payload),
            raw_text_output=self._extract_string(payload, "raw_text_output"),
            corrected_text_output=self._extract_string(payload, "corrected_text_output"),
            speaker_count=len(normalized_speaker_stats) or None,
            speaker_stats=normalized_speaker_stats,
            segments=[item for item in segments if isinstance(item, dict)] if isinstance(segments, list) else [],
            action_items=self._extract_list(payload, "action_items"),
            decisions=self._extract_list(payload, "decisions"),
            is_final=bool(payload.get("is_final") or False),
        )

    def _read_json_response(self, request: Request) -> dict[str, object]:
        try:
            with self._request_opener(request, timeout=self._config.request_timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except HTTPError:
            raise
        except URLError:
            raise
        except TimeoutError:
            raise
        try:
            payload = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise ValueError("Realtime transcription backend returned an invalid JSON response.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Realtime transcription backend returned an unexpected JSON payload.")
        return payload

    def _fetch_optional_json(self, path: str) -> dict[str, object] | None:
        request = Request(
            urljoin(f"{self._config.base_url}/", path),
            method="GET",
            headers={"Accept": "application/json"},
        )
        try:
            return self._read_json_response(request)
        except (ValueError, HTTPError, URLError, TimeoutError):
            return None

    def _build_multipart_payload(self, audio_path: Path) -> tuple[bytes, str]:
        boundary = f"----CollectiveMindGraphBoundary{uuid4().hex}"
        chunks: list[bytes] = []

        def append_text_field(name: str, value: str) -> None:
            chunks.append(f"--{boundary}\r\n".encode("utf-8"))
            chunks.append(
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8")
            )
            chunks.append(value.encode("utf-8"))
            chunks.append(b"\r\n")

        def append_file_field(name: str, path: Path) -> None:
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            chunks.append(f"--{boundary}\r\n".encode("utf-8"))
            chunks.append(
                (
                    f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'
                    f"Content-Type: {content_type}\r\n\r\n"
                ).encode("utf-8")
            )
            chunks.append(path.read_bytes())
            chunks.append(b"\r\n")

        append_file_field("upload", audio_path)
        if self._config.language:
            append_text_field("language", self._config.language)
        chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
        return b"".join(chunks), f"multipart/form-data; boundary={boundary}"

    @staticmethod
    def _extract_text(payload: dict[str, object]) -> str:
        transcript_payload = payload.get("transcript")
        if isinstance(transcript_payload, dict):
            segments = transcript_payload.get("segments")
            if isinstance(segments, list):
                lines: list[str] = []
                for item in segments:
                    if not isinstance(item, dict):
                        continue
                    text = str(item.get("corrected_text") or item.get("raw_text") or "").strip()
                    if not text:
                        continue
                    speaker = str(item.get("speaker") or "").strip()
                    lines.append(f"{speaker}: {text}" if speaker else text)
                if lines:
                    return "\n".join(lines)

        for key in ("corrected_text_output", "text_output", "raw_text_output"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _extract_string(payload: dict[str, object], key: str) -> str | None:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @staticmethod
    def _extract_bool(payload: dict[str, object], key: str) -> bool | None:
        value = payload.get(key)
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
        return None

    @staticmethod
    def _extract_list(payload: dict[str, object], key: str) -> list[dict[str, object]]:
        value = payload.get(key)
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    @staticmethod
    def _extract_string_list(payload: dict[str, object], key: str) -> list[str]:
        value = payload.get(key)
        return [str(item) for item in value] if isinstance(value, list) else []


def _parse_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _backend_unreachable_message(base_url: str) -> str:
    if is_frozen_build() and base_url.startswith(("http://127.0.0.1", "http://localhost")):
        return (
            "Realtime transcription backend is not reachable. "
            "Use `Refresh Backend` or restart the app to re-launch the bundled local backend."
        )
    return (
        "Realtime transcription backend is not reachable. "
        f"Start `realtime_backend` at {base_url} and try again."
    )
