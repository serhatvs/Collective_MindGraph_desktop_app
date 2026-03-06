"""Domain models for Collective MindGraph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BranchType = Literal["root", "main", "side"]


@dataclass(frozen=True, slots=True)
class Session:
    id: int
    title: str
    device_id: str
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Transcript:
    id: int
    session_id: int
    text: str
    confidence: float
    created_at: str


@dataclass(frozen=True, slots=True)
class GraphNode:
    id: int
    session_id: int
    transcript_id: int | None
    parent_node_id: int | None
    branch_type: BranchType
    branch_slot: int | None
    node_text: str
    override_reason: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class Snapshot:
    id: int
    session_id: int
    node_count: int
    hash_sha256: str
    created_at: str


@dataclass(frozen=True, slots=True)
class SessionDetail:
    session: Session
    transcripts: list[Transcript]
    graph_nodes: list[GraphNode]
    snapshots: list[Snapshot]


@dataclass(frozen=True, slots=True)
class AppSummary:
    total_sessions: int
    active_sessions: int
    total_transcripts: int
    total_nodes: int
    total_snapshots: int


@dataclass(frozen=True, slots=True)
class TranscriptDraft:
    text: str
    confidence: float
    created_at: str


@dataclass(frozen=True, slots=True)
class GraphNodeDraft:
    transcript_id: int | None
    parent_node_id: int | None
    branch_type: BranchType
    branch_slot: int | None
    node_text: str
    override_reason: str | None
    created_at: str
