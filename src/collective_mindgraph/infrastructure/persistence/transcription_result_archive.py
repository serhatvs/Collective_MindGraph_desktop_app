"""Adapter between ASR result contracts and the canonical meeting schema."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from collective_mindgraph.application import PageRequest
from collective_mindgraph.application.transcription.contracts import (
    ConversationTranscript,
    DecisionItem,
    TaskItem,
    TopicSegment,
)
from collective_mindgraph.domain import (
    EvidenceReference,
    Insight,
    InsightId,
    InsightKind,
    KnowledgeEdge,
    KnowledgeNode,
    KnowledgeNodeId,
    KnowledgeNodeKind,
    MeetingId,
    MeetingStatus,
    Recording,
    RecordingId,
    RecordingStorageStatus,
    RelationshipKind,
    ReviewDecision,
    Transcript,
)

from .insight_store import SqliteInsightStore
from .knowledge_store import SqliteKnowledgeGraphStore
from .meeting_store import SqliteMeetingStore
from .recording_store import SqliteRecordingStore
from .transcript_store import SqliteTranscriptStore
from .transcription_archive_mapping import (
    duration_seconds as _duration_seconds,
)
from .transcription_archive_mapping import edge_id as _edge_id
from .transcription_archive_mapping import evidence_id as _evidence_id
from .transcription_archive_mapping import meeting_node_id as _meeting_node_id
from .transcription_archive_mapping import optional_text as _optional_text
from .transcription_archive_mapping import person_node_id as _person_node_id
from .transcription_archive_mapping import segment_at as _segment_at
from .transcription_archive_mapping import segment_node_id as _segment_node_id
from .transcription_archive_mapping import segment_title as _segment_title
from .transcription_archive_mapping import (
    to_domain_transcript as _to_domain_transcript,
)
from .transcription_archive_mapping import (
    to_processing_segment as _to_processing_segment,
)


class CanonicalTranscriptionResultArchive:
    def __init__(
        self,
        meetings: SqliteMeetingStore,
        recordings: SqliteRecordingStore,
        transcripts: SqliteTranscriptStore,
        insights: SqliteInsightStore,
        knowledge: SqliteKnowledgeGraphStore,
    ) -> None:
        self._meetings = meetings
        self._recordings = recordings
        self._transcripts = transcripts
        self._insights = insights
        self._knowledge = knowledge

    def save(
        self,
        result: ConversationTranscript,
        *,
        meeting_id: MeetingId | None = None,
        source_path: Path | None = None,
        source_uri: str | None = None,
        recording_id: RecordingId | None = None,
    ) -> MeetingId:
        now = (
            result.updated_at if result.updated_at.tzinfo else result.updated_at.replace(tzinfo=UTC)
        )
        selected_meeting = self._resolve_meeting(result, meeting_id, now)
        self._meetings.set_status(
            selected_meeting,
            status=MeetingStatus.PROCESSING,
            now=now,
        )
        selected_source_uri = source_uri or (str(source_path) if source_path is not None else None)
        if selected_source_uri is not None:
            existing_recording = (
                self._recordings.get(recording_id) if recording_id is not None else None
            )
            self._recordings.save(
                Recording(
                    id=recording_id
                    or RecordingId(
                        str(uuid5(NAMESPACE_URL, f"{result.conversation_id}:{selected_source_uri}"))
                    ),
                    meeting_id=selected_meeting,
                    source_uri=selected_source_uri,
                    duration_seconds=_duration_seconds(result),
                    captured_at=result.created_at,
                    input_device=(
                        existing_recording.input_device if existing_recording is not None else None
                    ),
                    storage_status=(
                        existing_recording.storage_status
                        if existing_recording is not None
                        else RecordingStorageStatus.MANAGED
                    ),
                    keep_audio=(
                        existing_recording.keep_audio if existing_recording is not None else False
                    ),
                    deleted_at=(
                        existing_recording.deleted_at if existing_recording is not None else None
                    ),
                )
            )
        transcript = self._transcripts.save(_to_domain_transcript(result, selected_meeting))
        self._persist_evidence(result, transcript)
        self._persist_meeting_structure(result, transcript, now)
        self._persist_insights(result, selected_meeting, now)
        self._meetings.set_status(
            selected_meeting,
            status=MeetingStatus.READY,
            now=now,
        )
        result.metadata = {
            **result.metadata,
            "meeting_id": int(selected_meeting),
            "transcript_id": int(transcript.id),
        }
        return selected_meeting

    def get(self, conversation_id: str) -> ConversationTranscript | None:
        transcript = self._transcripts.get_by_conversation_id(conversation_id)
        if transcript is None:
            return None
        page = self._insights.list(
            PageRequest(limit=200),
            meeting_id=transcript.meeting_id,
        )
        diagnostics = dict(transcript.diagnostics)
        result = ConversationTranscript(
            conversation_id=conversation_id,
            created_at=transcript.created_at,
            updated_at=transcript.updated_at,
            source=str(diagnostics.pop("source", "canonical_store")),
            language=transcript.language,
            quality_mode=_optional_text(diagnostics.pop("quality_mode", None)),
            segments=[_to_processing_segment(item) for item in transcript.segments],
            summary=_optional_text(diagnostics.pop("summary", None)),
            metadata={
                "meeting_id": int(transcript.meeting_id),
                "transcript_id": int(transcript.id),
                **diagnostics,
            },
        )
        for insight in reversed(page.items):
            source_segment_id = _optional_text(insight.attributes.get("source_segment_id"))
            if insight.kind is InsightKind.TASK:
                result.action_items.append(
                    TaskItem(
                        title=insight.title,
                        responsible_person=_optional_text(
                            insight.attributes.get("responsible_person")
                        ),
                        due_date_reference=_optional_text(
                            insight.attributes.get("due_date_reference")
                        ),
                        source_segment_id=source_segment_id,
                    )
                )
            elif insight.kind is InsightKind.DECISION:
                result.decisions.append(
                    DecisionItem(
                        decision=insight.body or insight.title,
                        reason_context=_optional_text(insight.attributes.get("reason_context")),
                        source_segment_id=source_segment_id,
                    )
                )
            elif insight.kind is InsightKind.TOPIC:
                result.topics.append(
                    TopicSegment(
                        label=insight.title,
                        start=float(insight.attributes.get("start", 0.0)),
                        end=float(insight.attributes.get("end", 0.0)),
                    )
                )
            elif insight.kind is InsightKind.PERSON:
                result.people.append(insight.title)
        return result

    def _resolve_meeting(
        self,
        result: ConversationTranscript,
        meeting_id: MeetingId | None,
        now: datetime,
    ) -> MeetingId:
        metadata_id = result.metadata.get("meeting_id")
        candidate = meeting_id
        if candidate is None and isinstance(metadata_id, int):
            candidate = MeetingId(metadata_id)
        if candidate is not None and self._meetings.get(candidate) is not None:
            return candidate
        title = _optional_text(result.metadata.get("meeting_title"))
        meeting = self._meetings.create(
            title=title or f"Meeting {result.created_at:%Y-%m-%d %H:%M}",
            status=MeetingStatus.PROCESSING,
            input_device=None,
            now=now,
        )
        return meeting.id

    def _persist_evidence(
        self,
        result: ConversationTranscript,
        transcript: Transcript,
    ) -> None:
        for segment in transcript.segments:
            self._knowledge.save_evidence(
                EvidenceReference(
                    id=_evidence_id(result.conversation_id, str(segment.id)),
                    meeting_id=transcript.meeting_id,
                    segment_id=segment.id,
                    start_seconds=segment.start_seconds,
                    end_seconds=segment.end_seconds,
                    text_preview=segment.corrected_text or segment.raw_text,
                    confidence=segment.confidence,
                    extractor=transcript.provider,
                    created_at=transcript.created_at,
                )
            )

    def _persist_insights(
        self,
        result: ConversationTranscript,
        meeting_id: MeetingId,
        now: datetime,
    ) -> None:
        candidates: list[tuple[InsightKind, str, str, str | None, dict[str, object]]] = []
        for item in result.action_items:
            candidates.append(
                (
                    InsightKind.TASK,
                    item.title,
                    item.title,
                    item.source_segment_id,
                    {
                        "responsible_person": item.responsible_person,
                        "due_date_reference": item.due_date_reference,
                    },
                )
            )
        for item in result.decisions:
            candidates.append(
                (
                    InsightKind.DECISION,
                    item.decision,
                    item.decision,
                    item.source_segment_id,
                    {"reason_context": item.reason_context},
                )
            )
        for item in result.topics:
            candidates.append(
                (
                    InsightKind.TOPIC,
                    item.label,
                    item.label,
                    _segment_at(result, item.start),
                    {"start": item.start, "end": item.end},
                )
            )
        for person in result.people:
            candidates.append((InsightKind.PERSON, person, person, None, {}))

        for index, (kind, title, body, segment_id, attributes) in enumerate(candidates):
            insight_id = InsightId(
                str(uuid5(NAMESPACE_URL, f"{result.conversation_id}:{kind.value}:{index}"))
            )
            evidence_id = _evidence_id(result.conversation_id, segment_id) if segment_id else None
            attributes = {
                **attributes,
                "source_segment_id": segment_id,
                "review": ReviewDecision.PENDING.value,
            }
            insight = Insight(
                id=insight_id,
                meeting_id=meeting_id,
                kind=kind,
                title=title,
                body=body,
                review=ReviewDecision.PENDING,
                evidence_id=evidence_id,
                confidence=None,
                created_at=now,
                updated_at=now,
                attributes=attributes,
            )
            self._insights.save(insight)
            self._knowledge.save_node(
                KnowledgeNode(
                    id=KnowledgeNodeId(str(insight_id)),
                    meeting_id=meeting_id,
                    kind=KnowledgeNodeKind(kind.value),
                    title=title,
                    body=body,
                    evidence_id=evidence_id,
                    attributes=attributes,
                    created_at=now,
                    updated_at=now,
                )
            )
            meeting_node_id = _meeting_node_id(result.conversation_id)
            insight_node_id = KnowledgeNodeId(str(insight_id))
            self._knowledge.save_edge(
                KnowledgeEdge(
                    id=_edge_id(meeting_node_id, insight_node_id, "contains"),
                    source_id=meeting_node_id,
                    target_id=insight_node_id,
                    kind=RelationshipKind.CONTAINS,
                    evidence_id=evidence_id,
                    created_at=now,
                )
            )
            segment_node_id = (
                _segment_node_id(result.conversation_id, segment_id) if segment_id else None
            )
            if (
                segment_node_id is not None
                and self._knowledge.get_node(segment_node_id) is not None
            ):
                self._knowledge.save_edge(
                    KnowledgeEdge(
                        id=_edge_id(
                            insight_node_id,
                            segment_node_id,
                            "derived_from",
                        ),
                        source_id=insight_node_id,
                        target_id=segment_node_id,
                        kind=RelationshipKind.DERIVED_FROM,
                        evidence_id=evidence_id,
                        created_at=now,
                    )
                )
                if kind in {InsightKind.PERSON, InsightKind.ENTITY}:
                    self._knowledge.save_edge(
                        KnowledgeEdge(
                            id=_edge_id(
                                segment_node_id,
                                insight_node_id,
                                "mentions",
                            ),
                            source_id=segment_node_id,
                            target_id=insight_node_id,
                            kind=RelationshipKind.MENTIONS,
                            evidence_id=evidence_id,
                            created_at=now,
                        )
                    )
            responsible = _optional_text(attributes.get("responsible_person"))
            if kind is InsightKind.TASK and responsible:
                person_node_id = _person_node_id(
                    result.conversation_id,
                    responsible,
                )
                self._knowledge.save_node(
                    KnowledgeNode(
                        id=person_node_id,
                        meeting_id=meeting_id,
                        kind=KnowledgeNodeKind.PERSON,
                        title=responsible,
                        body=responsible,
                        evidence_id=evidence_id,
                        attributes={
                            "review": ReviewDecision.PENDING.value,
                            "needs_review": False,
                        },
                        created_at=now,
                        updated_at=now,
                    )
                )
                self._knowledge.save_edge(
                    KnowledgeEdge(
                        id=_edge_id(insight_node_id, person_node_id, "assigned_to"),
                        source_id=insight_node_id,
                        target_id=person_node_id,
                        kind=RelationshipKind.ASSIGNED_TO,
                        evidence_id=evidence_id,
                        created_at=now,
                    )
                )

    def _persist_meeting_structure(
        self,
        result: ConversationTranscript,
        transcript: Transcript,
        now: datetime,
    ) -> None:
        meeting = self._meetings.get(transcript.meeting_id)
        meeting_node_id = _meeting_node_id(result.conversation_id)
        title = meeting.title if meeting is not None else f"Meeting {transcript.meeting_id}"
        self._knowledge.save_node(
            KnowledgeNode(
                id=meeting_node_id,
                meeting_id=transcript.meeting_id,
                kind=KnowledgeNodeKind.MEETING,
                title=title,
                body=transcript.corrected_text or transcript.raw_text,
                attributes={
                    "review": ReviewDecision.ACCEPTED.value,
                    "needs_review": False,
                },
                created_at=transcript.created_at,
                updated_at=now,
            )
        )
        for segment in transcript.segments:
            evidence_id = _evidence_id(result.conversation_id, str(segment.id))
            segment_node_id = _segment_node_id(
                result.conversation_id,
                str(segment.id),
            )
            self._knowledge.save_node(
                KnowledgeNode(
                    id=segment_node_id,
                    meeting_id=transcript.meeting_id,
                    kind=KnowledgeNodeKind.SEGMENT,
                    title=_segment_title(segment),
                    body=segment.corrected_text or segment.raw_text,
                    evidence_id=evidence_id,
                    attributes={
                        "review": ReviewDecision.ACCEPTED.value,
                        "needs_review": False,
                        "segment_id": str(segment.id),
                    },
                    created_at=transcript.created_at,
                    updated_at=now,
                )
            )
            self._knowledge.save_edge(
                KnowledgeEdge(
                    id=_edge_id(meeting_node_id, segment_node_id, "contains"),
                    source_id=meeting_node_id,
                    target_id=segment_node_id,
                    kind=RelationshipKind.CONTAINS,
                    evidence_id=evidence_id,
                    created_at=now,
                )
            )
