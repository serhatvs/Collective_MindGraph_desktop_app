"""Domain models for the user-facing companion app."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MapItemKind = Literal["main_category", "sub_category", "session"]
SessionFlowKind = Literal["created", "template", "context", "idea"]
SessionGraphKind = Literal[
    "session_root",
    "context_group",
    "category",
    "template",
    "idea_group",
    "idea",
    "related_group",
    "related_session",
]


@dataclass(frozen=True, slots=True)
class MainCategory:
    id: int
    name: str
    created_at: str


@dataclass(frozen=True, slots=True)
class SubCategory:
    id: int
    main_category_id: int
    name: str
    created_at: str


@dataclass(frozen=True, slots=True)
class UserSession:
    id: int
    title: str
    main_category_id: int
    main_category_name: str
    sub_category_id: int | None
    sub_category_name: str | None
    template_name: str
    mood: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class NoteEntry:
    id: int
    session_id: int
    content: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class WorkspaceMapItem:
    key: str
    parent_key: str | None
    title: str
    subtitle: str
    kind: MapItemKind
    entity_id: int
    is_selected: bool


@dataclass(frozen=True, slots=True)
class SessionFlowItem:
    title: str
    detail: str
    kind: SessionFlowKind


@dataclass(frozen=True, slots=True)
class SessionGraphNode:
    key: str
    parent_key: str | None
    title: str
    subtitle: str
    kind: SessionGraphKind
    session_id: int | None


@dataclass(frozen=True, slots=True)
class SessionDetail:
    session: UserSession
    note: NoteEntry | None
    main_category: MainCategory
    sub_category: SubCategory | None
    main_categories: list[MainCategory]
    sub_categories: list[SubCategory]
    session_flow: list[SessionFlowItem]
    session_graph: list[SessionGraphNode]
    related_sessions: list[UserSession]
    workspace_map: list[WorkspaceMapItem]


@dataclass(frozen=True, slots=True)
class AppSummary:
    total_sessions: int
    total_main_categories: int
    total_sub_categories: int
    total_notes: int
    total_map_nodes: int
