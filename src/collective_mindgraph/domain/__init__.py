"""Pure domain contracts for Collective MindGraph."""

from .health import EngineHealth, ProviderHealth
from .identifiers import (
    EdgeId,
    EvidenceId,
    InsightId,
    JobId,
    KnowledgeNodeId,
    MeetingId,
    RecordingId,
    SegmentId,
    TranscriptId,
)
from .insights import Insight, InsightKind, ReviewDecision
from .jobs import ProcessingJob, ProcessingStatus
from .knowledge import (
    EvidenceReference,
    KnowledgeEdge,
    KnowledgeNode,
    KnowledgeNodeKind,
    RelationshipKind,
)
from .meetings import Meeting, MeetingStatus
from .transcripts import Recording, RecordingStorageStatus, Transcript, TranscriptSegment

__all__ = [
    "EdgeId",
    "EngineHealth",
    "EvidenceId",
    "EvidenceReference",
    "Insight",
    "InsightId",
    "InsightKind",
    "JobId",
    "KnowledgeEdge",
    "KnowledgeNode",
    "KnowledgeNodeId",
    "KnowledgeNodeKind",
    "Meeting",
    "MeetingId",
    "MeetingStatus",
    "ProcessingJob",
    "ProcessingStatus",
    "ProviderHealth",
    "Recording",
    "RecordingId",
    "RecordingStorageStatus",
    "RelationshipKind",
    "ReviewDecision",
    "SegmentId",
    "Transcript",
    "TranscriptId",
    "TranscriptSegment",
]
