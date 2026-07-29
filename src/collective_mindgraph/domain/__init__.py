"""Pure domain contracts for Collective MindGraph."""

from .health import EngineHealth, ProviderHealth
from .identifiers import (
    ActivityEventId,
    CommentId,
    ConflictId,
    DeviceId,
    EdgeId,
    EvidenceId,
    InsightId,
    JobId,
    KnowledgeNodeId,
    MeetingId,
    OperationId,
    RecordingId,
    SegmentId,
    SyncId,
    TranscriptId,
    WorkspaceId,
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
from .sync import SyncIdentity, SyncOperation, SyncOperationState, Workspace, WorkspaceKind
from .transcripts import Recording, RecordingStorageStatus, Transcript, TranscriptSegment

__all__ = [
    "ActivityEventId",
    "CommentId",
    "ConflictId",
    "DeviceId",
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
    "OperationId",
    "ProcessingJob",
    "ProcessingStatus",
    "ProviderHealth",
    "Recording",
    "RecordingId",
    "RecordingStorageStatus",
    "RelationshipKind",
    "ReviewDecision",
    "SegmentId",
    "SyncId",
    "SyncIdentity",
    "SyncOperation",
    "SyncOperationState",
    "Transcript",
    "TranscriptId",
    "TranscriptSegment",
    "Workspace",
    "WorkspaceId",
    "WorkspaceKind",
]
