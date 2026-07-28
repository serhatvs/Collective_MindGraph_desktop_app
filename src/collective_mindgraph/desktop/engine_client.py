"""Typed HTTP client for the local-only engine API."""

from __future__ import annotations

import time
import urllib.parse
from pathlib import Path

from .client_mapping import evidence as _evidence
from .client_mapping import (
    insight as _insight,
)
from .client_mapping import (
    meeting as _meeting,
)
from .client_mapping import (
    object_list as _object_list,
)
from .client_mapping import (
    optional_text as _optional_text,
)
from .client_mapping import (
    preferences as _preferences,
)
from .client_mapping import processing_job as _processing_job
from .client_mapping import (
    segment as _segment,
)
from .client_mapping import (
    transcript as _transcript,
)
from .contracts import (
    DashboardSnapshot,
    EngineHealth,
    EnginePreferencesSnapshot,
    EngineSettings,
    EvidenceItem,
    InsightItem,
    KnowledgeItem,
    KnowledgeRelationship,
    MeetingSummary,
    MeetingTranscript,
    MemoryAnswer,
    MemorySearchItem,
    ProcessingJob,
    TranscriptionPreferences,
    TranscriptSegment,
)
from .http_transport import EngineClientError as EngineClientError
from .http_transport import LocalHttpTransport
from .http_transport import is_engine_offline_error as is_engine_offline_error


class EngineClient:
    def __init__(self, settings: EngineSettings | None = None) -> None:
        self.settings = settings or EngineSettings()
        self._transport = LocalHttpTransport(self.settings)

    def health(self) -> EngineHealth:
        payload = self._request("GET", "/api/v1/health")
        return EngineHealth(
            status=str(payload["status"]),
            transcription=str(payload["transcription"]),
            embeddings=str(payload["embeddings"]),
            local_llm=str(payload["local_llm"]),
            detail=str(payload.get("detail", "")),
        )

    def get_preferences(self) -> EnginePreferencesSnapshot:
        return _preferences(self._request("GET", "/api/v1/settings"))

    def update_preferences(
        self,
        *,
        language: str | None = None,
        transcription_quality: str | None = None,
        asr_provider: str | None = None,
        asr_model: str | None = None,
        embedding_provider: str | None = None,
        local_llm_provider: str | None = None,
        diarization_enabled: bool | None = None,
        retain_raw_audio: bool | None = None,
    ) -> EnginePreferencesSnapshot:
        payload = self._request(
            "PUT",
            "/api/v1/settings",
            body={
                "language": language,
                "transcription_quality": transcription_quality,
                "asr_provider": asr_provider,
                "asr_model": asr_model,
                "embedding_provider": embedding_provider,
                "local_llm_provider": local_llm_provider,
                "diarization_enabled": diarization_enabled,
                "retain_raw_audio": retain_raw_audio,
            },
        )
        return _preferences(payload)

    def dashboard(self) -> DashboardSnapshot:
        payload = self._request("GET", "/api/v1/dashboard")
        return DashboardSnapshot(
            total_meetings=int(payload["total_meetings"]),
            total_transcripts=int(payload["total_transcripts"]),
            total_knowledge_nodes=int(payload["total_knowledge_nodes"]),
            pending_reviews=int(payload["pending_reviews"]),
            recent_meetings=tuple(
                _meeting(item) for item in _object_list(payload.get("recent_meetings"))
            ),
        )

    def list_meetings(
        self,
        query: str = "",
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[tuple[MeetingSummary, ...], str | None]:
        payload = self._request(
            "GET",
            "/api/v1/meetings",
            query={"query": query, "cursor": cursor, "limit": limit},
        )
        return (
            tuple(_meeting(item) for item in _object_list(payload.get("items"))),
            _optional_text(payload.get("next_cursor")),
        )

    def create_meeting(
        self,
        title: str,
        input_device: str | None = None,
    ) -> MeetingSummary:
        payload = self._request(
            "POST",
            "/api/v1/meetings",
            body={"title": title, "input_device": input_device},
        )
        return _meeting(payload)

    def update_meeting(
        self,
        meeting_id: int,
        *,
        title: str | None = None,
        archived: bool | None = None,
    ) -> MeetingSummary:
        payload = self._request(
            "PATCH",
            f"/api/v1/meetings/{meeting_id}",
            body={"title": title, "archived": archived},
        )
        return _meeting(payload)

    def delete_meeting(self, meeting_id: int) -> None:
        self._request("DELETE", f"/api/v1/meetings/{meeting_id}", expect_json=False)

    def ingest_recording(
        self,
        meeting_id: int,
        audio_path: Path,
        preferences: TranscriptionPreferences | None = None,
    ) -> ProcessingJob:
        selected = preferences or TranscriptionPreferences()
        fields = {
            "language": selected.language,
            "quality_mode": selected.quality_mode,
            "session_glossary": ",".join(selected.glossary) or None,
            "hotwords": ",".join(selected.hotwords) or None,
        }
        payload = self._multipart(
            f"/api/v1/meetings/{meeting_id}/recordings",
            audio_path,
            fields,
        )
        return _processing_job(payload)

    def get_job(self, job_id: str) -> ProcessingJob:
        return _processing_job(self._request("GET", f"/api/v1/jobs/{urllib.parse.quote(job_id)}"))

    def cancel_job(self, job_id: str) -> ProcessingJob:
        return _processing_job(
            self._request("POST", f"/api/v1/jobs/{urllib.parse.quote(job_id)}/cancel")
        )

    def retry_job(self, job_id: str) -> ProcessingJob:
        return _processing_job(
            self._request("POST", f"/api/v1/jobs/{urllib.parse.quote(job_id)}/retry")
        )

    def wait_for_job(
        self,
        job_id: str,
        *,
        timeout_seconds: float = 3600,
    ) -> ProcessingJob:
        deadline = time.monotonic() + timeout_seconds
        while True:
            job = self.get_job(job_id)
            if job.status in {"succeeded", "failed", "cancelled"}:
                return job
            if time.monotonic() >= deadline:
                raise EngineClientError(
                    "job_timeout",
                    "Recording processing did not finish before the local timeout.",
                    retryable=True,
                )
            time.sleep(0.2)

    def get_transcript(self, meeting_id: int) -> MeetingTranscript:
        return _transcript(self._request("GET", f"/api/v1/meetings/{meeting_id}/transcript"))

    def list_evidence(
        self,
        meeting_id: int,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[tuple[EvidenceItem, ...], str | None]:
        payload = self._request(
            "GET",
            f"/api/v1/meetings/{meeting_id}/evidence",
            query={"cursor": cursor, "limit": limit},
        )
        return (
            tuple(_evidence(item) for item in _object_list(payload.get("items"))),
            _optional_text(payload.get("next_cursor")),
        )

    def get_evidence(self, evidence_id: str) -> EvidenceItem:
        return _evidence(
            self._request(
                "GET",
                f"/api/v1/evidence/{urllib.parse.quote(evidence_id)}",
            )
        )

    def update_segment(self, segment_id: str, corrected_text: str) -> TranscriptSegment:
        payload = self._request(
            "PATCH",
            f"/api/v1/transcript-segments/{urllib.parse.quote(segment_id)}",
            body={"corrected_text": corrected_text},
        )
        return _segment(payload)

    def list_insights(
        self,
        *,
        meeting_id: int | None = None,
        review: str | None = None,
        query: str = "",
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[tuple[InsightItem, ...], str | None]:
        payload = self._request(
            "GET",
            "/api/v1/insights",
            query={
                "meeting_id": meeting_id,
                "review": review,
                "query": query,
                "cursor": cursor,
                "limit": limit,
            },
        )
        return (
            tuple(_insight(item) for item in _object_list(payload.get("items"))),
            _optional_text(payload.get("next_cursor")),
        )

    def review_insight(
        self,
        insight_id: str,
        decision: str,
        *,
        title: str | None = None,
        body: str | None = None,
    ) -> InsightItem:
        payload = self._request(
            "PATCH",
            f"/api/v1/insights/{urllib.parse.quote(insight_id)}/review",
            body={"decision": decision, "title": title, "body": body},
        )
        return _insight(payload)

    def search_memory(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[tuple[MemorySearchItem, ...], str | None]:
        payload = self._request(
            "GET",
            "/api/v1/memory/search",
            query={"q": query, "mode": mode, "cursor": cursor, "limit": limit},
        )
        results: list[MemorySearchItem] = []
        for item in _object_list(payload.get("items")):
            evidence = dict(item["evidence"]) if isinstance(item.get("evidence"), dict) else {}
            results.append(
                MemorySearchItem(
                    id=str(item.get("node_id") or ""),
                    kind=str(item.get("kind") or "entity"),
                    text=str(item.get("title") or item.get("body") or ""),
                    score=float(item.get("score") or 0),
                    meeting_id=str(
                        evidence.get("meeting_title") or evidence.get("meeting_id") or ""
                    ),
                    segment_id=_optional_text(evidence.get("segment_id")),
                    evidence_id=_optional_text(evidence.get("id")),
                    preview=_optional_text(evidence.get("text_preview")),
                )
            )
        return tuple(results), _optional_text(payload.get("next_cursor"))

    def ask_memory(
        self,
        query: str,
        *,
        mode: str = "evidence_only",
        meeting_id: int | None = None,
    ) -> MemoryAnswer:
        payload = self._request(
            "GET",
            "/api/v1/memory/ask",
            query={"q": query, "mode": mode, "meeting_id": meeting_id},
        )
        return MemoryAnswer(
            answer=str(payload.get("answer") or ""),
            mode_used=str(payload.get("mode_used") or "evidence_only"),
            confidence=str(payload.get("confidence") or "insufficient"),
            source_meeting_ids=tuple(
                str(item.get("meeting_title") or item.get("meeting_id") or "")
                for item in _object_list(payload.get("sources"))
            ),
            source_segment_ids=tuple(
                str(item["segment_id"])
                for item in _object_list(payload.get("sources"))
                if item.get("segment_id") is not None
            ),
            warnings=tuple(str(item) for item in payload.get("warnings", [])),
            evidence_chains=tuple(
                {
                    "explanation": (
                        f"{item.get('kind', '')}: {item.get('title') or item.get('body') or ''}"
                    ),
                    **item,
                }
                for item in _object_list(payload.get("reasoning_steps"))
            ),
        )

    def list_knowledge(
        self,
        *,
        query: str = "",
        meeting_id: int | None = None,
        kind: str | None = None,
        review: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[tuple[KnowledgeItem, ...], str | None]:
        payload = self._request(
            "GET",
            "/api/v1/knowledge/nodes",
            query={
                "query": query,
                "meeting_id": meeting_id,
                "kind": kind,
                "review": review,
                "cursor": cursor,
                "limit": limit,
            },
        )
        return (
            tuple(
                KnowledgeItem(
                    id=str(item["id"]),
                    kind=str(item["kind"]),
                    title=str(item["title"]),
                    body=str(item["body"]),
                    meeting_id=(
                        int(item["meeting_id"]) if item.get("meeting_id") is not None else None
                    ),
                    evidence_id=_optional_text(item.get("evidence_id")),
                    attributes=(
                        dict(item["attributes"]) if isinstance(item.get("attributes"), dict) else {}
                    ),
                )
                for item in _object_list(payload.get("items"))
            ),
            _optional_text(payload.get("next_cursor")),
        )

    def list_relationships(
        self,
        *,
        query: str = "",
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[tuple[KnowledgeRelationship, ...], str | None]:
        payload = self._request(
            "GET",
            "/api/v1/knowledge/edges",
            query={"query": query, "cursor": cursor, "limit": limit},
        )
        return (
            tuple(
                KnowledgeRelationship(
                    id=str(item["id"]),
                    source_id=str(item["source_id"]),
                    target_id=str(item["target_id"]),
                    kind=str(item["kind"]),
                    confidence=float(item.get("confidence") or 0),
                    evidence_id=_optional_text(item.get("evidence_id")),
                )
                for item in _object_list(payload.get("items"))
            ),
            _optional_text(payload.get("next_cursor")),
        )

    def list_jobs(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[tuple[ProcessingJob, ...], str | None]:
        payload = self._request(
            "GET",
            "/api/v1/jobs",
            query={"cursor": cursor, "limit": limit},
        )
        return (
            tuple(_processing_job(item) for item in _object_list(payload.get("items"))),
            _optional_text(payload.get("next_cursor")),
        )

    def export_data(self, meeting_id: int | None = None) -> dict[str, object]:
        return self._request(
            "GET",
            "/api/v1/export",
            query={"meeting_id": meeting_id},
        )

    def import_data(self, payload: dict[str, object]) -> dict[str, int]:
        response = self._request("POST", "/api/v1/import", body=payload)
        imported = response.get("imported")
        return (
            {str(key): int(value) for key, value in imported.items()}
            if isinstance(imported, dict)
            else {}
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, object] | None = None,
        body: dict[str, object] | None = None,
        expect_json: bool = True,
    ) -> dict[str, object]:
        return self._transport.request(
            method,
            path,
            query=query,
            body=body,
            expect_json=expect_json,
        )

    def _multipart(
        self,
        path: str,
        file_path: Path,
        fields: dict[str, str | None],
    ) -> dict[str, object]:
        return self._transport.multipart(path, file_path, fields)
