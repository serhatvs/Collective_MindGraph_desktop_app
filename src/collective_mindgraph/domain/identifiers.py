"""Typed identifiers used by domain entities."""

from __future__ import annotations

from typing import NewType

MeetingId = NewType("MeetingId", int)
RecordingId = NewType("RecordingId", str)
TranscriptId = NewType("TranscriptId", int)
SegmentId = NewType("SegmentId", str)
InsightId = NewType("InsightId", str)
EvidenceId = NewType("EvidenceId", str)
KnowledgeNodeId = NewType("KnowledgeNodeId", str)
EdgeId = NewType("EdgeId", str)
JobId = NewType("JobId", str)
