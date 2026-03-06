"""Service layer for the companion app."""

from __future__ import annotations

import html
import json
import re
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .database import Database
from .models import (
    AppSummary,
    MainCategory,
    NoteEntry,
    SessionDetail,
    SessionFlowItem,
    SessionGraphNode,
    SubCategory,
    UserSession,
    WorkspaceMapItem,
)
from .repositories import (
    MainCategoryRepository,
    NoteRepository,
    SessionRepository,
    SubCategoryRepository,
)

DEFAULT_MAIN_CATEGORY = "Inbox"
DEFAULT_TEMPLATE = "Idea Canvas"
TEMPLATE_OPTIONS = [
    "Idea Canvas",
    "Weekly Review",
    "Study Sprint",
    "Project Outline",
    "Journal Reflection",
    "Freeform Session",
]


def current_timestamp() -> str:
    return datetime.now(tz=UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S")


class CollectiveMindGraphCompanionService:
    def __init__(self, database: Database | None = None) -> None:
        self._database = database or Database()
        self._database.initialize()
        self.main_categories = MainCategoryRepository(self._database)
        self.sub_categories = SubCategoryRepository(self._database)
        self.sessions = SessionRepository(self._database)
        self.notes = NoteRepository(self._database)
        self._ensure_base_workspace()

    def create_session(
        self,
        title: str,
        main_category_name: str,
        sub_category_name: str,
        template_name: str,
        mood: str,
    ) -> UserSession:
        cleaned_title = title.strip()
        cleaned_template = template_name.strip() or DEFAULT_TEMPLATE
        cleaned_mood = mood.strip() or "Focused"
        if not cleaned_title:
            raise ValueError("Please enter a session title.")
        main_category, sub_category = self.resolve_category_path(main_category_name, sub_category_name)
        timestamp = current_timestamp()
        return self.sessions.create(
            cleaned_title,
            main_category.id,
            sub_category.id if sub_category else None,
            cleaned_template,
            cleaned_mood,
            timestamp,
        )

    def update_session(
        self,
        session_id: int,
        title: str,
        main_category_name: str,
        sub_category_name: str,
        template_name: str,
        mood: str,
    ) -> UserSession:
        cleaned_title = title.strip()
        cleaned_template = template_name.strip() or DEFAULT_TEMPLATE
        cleaned_mood = mood.strip() or "Focused"
        if not cleaned_title:
            raise ValueError("Please enter a session title.")
        main_category, sub_category = self.resolve_category_path(main_category_name, sub_category_name)
        session = self.sessions.update(
            session_id,
            cleaned_title,
            main_category.id,
            sub_category.id if sub_category else None,
            cleaned_template,
            cleaned_mood,
            current_timestamp(),
        )
        if session is None:
            raise ValueError("Session not found.")
        return session

    def create_related_session(self, source_session_id: int, title: str) -> UserSession:
        source = self.sessions.get(source_session_id)
        if source is None:
            raise ValueError("Session not found.")
        return self.create_session(
            title,
            source.main_category_name,
            source.sub_category_name or "",
            source.template_name,
            "Curious",
        )

    def list_sessions(self, query: str = "") -> list[UserSession]:
        return self.sessions.list(query)

    def list_main_categories(self) -> list[MainCategory]:
        return self.main_categories.list()

    def list_sub_categories(self, main_category_id: int | None = None) -> list[SubCategory]:
        return self.sub_categories.list(main_category_id)

    def get_category_options(self) -> dict[str, list[str]]:
        options = {category.name: [] for category in self.main_categories.list()}
        for sub_category in self.sub_categories.list():
            main_category = self.main_categories.get(sub_category.main_category_id)
            if main_category is None:
                continue
            options.setdefault(main_category.name, []).append(sub_category.name)
        return {name: sorted(values, key=str.casefold) for name, values in sorted(options.items())}

    def get_session_detail(self, session_id: int) -> SessionDetail | None:
        session = self.sessions.get(session_id)
        if session is None:
            return None
        main_category = self.main_categories.get(session.main_category_id)
        if main_category is None:
            raise ValueError("Main category not found.")
        sub_category = self.sub_categories.get(session.sub_category_id) if session.sub_category_id else None
        session_flow = self.get_session_flow(session_id)
        related_sessions = self.get_related_sessions(session_id)
        return SessionDetail(
            session=session,
            note=self.notes.get_by_session(session_id),
            main_category=main_category,
            sub_category=sub_category,
            main_categories=self.main_categories.list(),
            sub_categories=self.sub_categories.list(),
            session_flow=session_flow,
            session_graph=self.get_session_graph(session_id, session_flow, related_sessions),
            related_sessions=related_sessions,
            workspace_map=self.get_workspace_map(session_id),
        )

    def delete_session(self, session_id: int) -> bool:
        return self.sessions.delete(session_id)

    def save_note(self, session_id: int, content: str) -> NoteEntry:
        note = self.notes.upsert(session_id, content, current_timestamp())
        self.sessions.touch(session_id, note.updated_at)
        return note

    def append_quick_idea(self, session_id: int, idea_text: str) -> NoteEntry:
        cleaned_idea = idea_text.strip()
        if not cleaned_idea:
            raise ValueError("Please write a short idea first.")
        existing = self.notes.get_by_session(session_id)
        block = f"<p><b>Idea:</b> {html.escape(cleaned_idea)}</p>"
        if existing is None or not existing.content.strip():
            content = f"<html><body>{block}</body></html>"
        else:
            content = self._append_html_block(existing.content, block)
        return self.save_note(session_id, content)

    def create_main_category(self, name: str) -> MainCategory:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValueError("Please enter a main category name.")
        existing = self.main_categories.get_by_name(cleaned_name)
        if existing is not None:
            return existing
        try:
            return self.main_categories.create(cleaned_name, current_timestamp())
        except sqlite3.IntegrityError as exc:
            raise ValueError("That main category already exists.") from exc

    def rename_main_category(self, category_id: int, name: str) -> MainCategory:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValueError("Please enter a main category name.")
        try:
            category = self.main_categories.update_name(category_id, cleaned_name)
        except sqlite3.IntegrityError as exc:
            raise ValueError("That main category name is already in use.") from exc
        if category is None:
            raise ValueError("Main category not found.")
        return category

    def delete_main_category(self, category_id: int) -> bool:
        if self.sessions.count_by_main_category(category_id) > 0:
            raise ValueError("Move or delete sessions linked to this main category first.")
        if self.sub_categories.list(category_id):
            raise ValueError("Delete the sub categories inside this main category first.")
        category = self.main_categories.get(category_id)
        if category is None:
            return False
        if category.name == DEFAULT_MAIN_CATEGORY:
            raise ValueError("The default Inbox category should stay available.")
        return self.main_categories.delete(category_id)

    def create_sub_category(self, main_category_id: int, name: str) -> SubCategory:
        main_category = self.main_categories.get(main_category_id)
        if main_category is None:
            raise ValueError("Pick a valid main category first.")
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValueError("Please enter a sub category name.")
        existing = self.sub_categories.get_by_name(main_category_id, cleaned_name)
        if existing is not None:
            return existing
        try:
            return self.sub_categories.create(main_category_id, cleaned_name, current_timestamp())
        except sqlite3.IntegrityError as exc:
            raise ValueError("That sub category already exists in this main category.") from exc

    def rename_sub_category(self, category_id: int, name: str) -> SubCategory:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValueError("Please enter a sub category name.")
        existing = self.sub_categories.get(category_id)
        if existing is None:
            raise ValueError("Sub category not found.")
        try:
            category = self.sub_categories.update_name(category_id, cleaned_name)
        except sqlite3.IntegrityError as exc:
            raise ValueError("That sub category name is already in use here.") from exc
        if category is None:
            raise ValueError("Sub category not found.")
        return category

    def delete_sub_category(self, category_id: int) -> bool:
        if self.sessions.count_by_sub_category(category_id) > 0:
            raise ValueError("Move or delete sessions linked to this sub category first.")
        return self.sub_categories.delete(category_id)

    def resolve_category_path(
        self,
        main_category_name: str,
        sub_category_name: str | None = None,
    ) -> tuple[MainCategory, SubCategory | None]:
        cleaned_main = main_category_name.strip() or DEFAULT_MAIN_CATEGORY
        cleaned_sub = (sub_category_name or "").strip()
        main_category = self.create_main_category(cleaned_main)
        sub_category = None
        if cleaned_sub:
            sub_category = self.create_sub_category(main_category.id, cleaned_sub)
        return main_category, sub_category

    def get_workspace_map(self, selected_session_id: int | None = None) -> list[WorkspaceMapItem]:
        sessions = self.sessions.list()
        main_categories = self.main_categories.list()
        sub_categories = self.sub_categories.list()
        sub_by_main: dict[int, list[SubCategory]] = {}
        session_by_parent: dict[str, list[UserSession]] = {}

        for sub_category in sub_categories:
            sub_by_main.setdefault(sub_category.main_category_id, []).append(sub_category)

        for session in sessions:
            parent_key = (
                f"sub:{session.sub_category_id}"
                if session.sub_category_id is not None
                else f"main:{session.main_category_id}"
            )
            session_by_parent.setdefault(parent_key, []).append(session)

        items: list[WorkspaceMapItem] = []
        for main_category in main_categories:
            direct_count = len(session_by_parent.get(f"main:{main_category.id}", []))
            sub_count = len(sub_by_main.get(main_category.id, []))
            items.append(
                WorkspaceMapItem(
                    key=f"main:{main_category.id}",
                    parent_key=None,
                    title=main_category.name,
                    subtitle=f"{sub_count} sub categories / {direct_count} direct sessions",
                    kind="main_category",
                    entity_id=main_category.id,
                    is_selected=False,
                )
            )

            for sub_category in sub_by_main.get(main_category.id, []):
                sub_sessions = session_by_parent.get(f"sub:{sub_category.id}", [])
                items.append(
                    WorkspaceMapItem(
                        key=f"sub:{sub_category.id}",
                        parent_key=f"main:{main_category.id}",
                        title=sub_category.name,
                        subtitle=f"{len(sub_sessions)} sessions",
                        kind="sub_category",
                        entity_id=sub_category.id,
                        is_selected=False,
                    )
                )
                for session in sub_sessions:
                    items.append(
                        self._workspace_session_item(
                            session=session,
                            parent_key=f"sub:{sub_category.id}",
                            selected_session_id=selected_session_id,
                        )
                    )

            for session in session_by_parent.get(f"main:{main_category.id}", []):
                items.append(
                    self._workspace_session_item(
                        session=session,
                        parent_key=f"main:{main_category.id}",
                        selected_session_id=selected_session_id,
                    )
                )

        return items

    def get_related_sessions(self, session_id: int, limit: int = 6) -> list[UserSession]:
        current_session = self.sessions.get(session_id)
        if current_session is None:
            return []
        related: list[UserSession] = []
        seen_ids = {session_id}

        for session in self.sessions.list():
            if session.id in seen_ids:
                continue
            same_sub_category = (
                current_session.sub_category_id is not None
                and session.sub_category_id == current_session.sub_category_id
            )
            same_main_category = session.main_category_id == current_session.main_category_id
            if same_sub_category or same_main_category:
                related.append(session)
                seen_ids.add(session.id)
            if len(related) >= limit:
                break
        return related

    def get_session_flow(self, session_id: int) -> list[SessionFlowItem]:
        session = self.sessions.get(session_id)
        if session is None:
            return []
        blocks = self._extract_note_blocks(self.notes.get_by_session(session_id))
        category_path = session.main_category_name
        if session.sub_category_name:
            category_path = f"{category_path} / {session.sub_category_name}"

        flow = [
            SessionFlowItem("Session created", session.created_at, "created"),
            SessionFlowItem("Template", session.template_name, "template"),
            SessionFlowItem("Context", category_path, "context"),
        ]
        for index, block in enumerate(blocks[:8], start=1):
            flow.append(SessionFlowItem(f"Idea {index}", block, "idea"))
        if len(flow) == 3:
            flow.append(
                SessionFlowItem(
                    "Next move",
                    "Capture the first idea or note to grow this session into a graph.",
                    "idea",
                )
            )
        return flow

    def get_session_graph(
        self,
        session_id: int,
        session_flow: list[SessionFlowItem] | None = None,
        related_sessions: list[UserSession] | None = None,
    ) -> list[SessionGraphNode]:
        session = self.sessions.get(session_id)
        if session is None:
            return []
        flow = session_flow if session_flow is not None else self.get_session_flow(session_id)
        related = related_sessions if related_sessions is not None else self.get_related_sessions(session_id)

        root_key = f"session-root:{session.id}"
        graph = [
            SessionGraphNode(
                key=root_key,
                parent_key=None,
                title=session.title,
                subtitle=f"{session.template_name} / {session.mood}",
                kind="session_root",
                session_id=session.id,
            )
        ]

        context_group_key = f"context:{session.id}"
        graph.append(
            SessionGraphNode(
                key=context_group_key,
                parent_key=root_key,
                title="Context",
                subtitle="Where this session lives",
                kind="context_group",
                session_id=None,
            )
        )
        graph.append(
            SessionGraphNode(
                key=f"main-category:{session.main_category_id}:{session.id}",
                parent_key=context_group_key,
                title=session.main_category_name,
                subtitle="Main category",
                kind="category",
                session_id=None,
            )
        )
        if session.sub_category_name:
            graph.append(
                SessionGraphNode(
                    key=f"sub-category:{session.sub_category_id}:{session.id}",
                    parent_key=context_group_key,
                    title=session.sub_category_name,
                    subtitle="Sub category",
                    kind="category",
                    session_id=None,
                )
            )
        graph.append(
            SessionGraphNode(
                key=f"template:{session.id}",
                parent_key=root_key,
                title=session.template_name,
                subtitle="Template branch",
                kind="template",
                session_id=None,
            )
        )

        idea_group_key = f"ideas:{session.id}"
        graph.append(
            SessionGraphNode(
                key=idea_group_key,
                parent_key=root_key,
                title="Idea branches",
                subtitle="Built from the current note",
                kind="idea_group",
                session_id=None,
            )
        )
        for index, item in enumerate(flow):
            if item.kind != "idea":
                continue
            graph.append(
                SessionGraphNode(
                    key=f"idea:{session.id}:{index}",
                    parent_key=idea_group_key,
                    title=item.title,
                    subtitle=item.detail,
                    kind="idea",
                    session_id=None,
                )
            )

        related_group_key = f"related:{session.id}"
        graph.append(
            SessionGraphNode(
                key=related_group_key,
                parent_key=root_key,
                title="Related sessions",
                subtitle="Same branch or nearby context",
                kind="related_group",
                session_id=None,
            )
        )
        if related:
            for related_session in related:
                graph.append(
                    SessionGraphNode(
                        key=f"related-session:{related_session.id}:{session.id}",
                        parent_key=related_group_key,
                        title=related_session.title,
                        subtitle=f"{related_session.template_name} / {related_session.updated_at}",
                        kind="related_session",
                        session_id=related_session.id,
                    )
                )
        else:
            graph.append(
                SessionGraphNode(
                    key=f"related-empty:{session.id}",
                    parent_key=related_group_key,
                    title="No related sessions yet",
                    subtitle="Create another session in this branch to connect it here.",
                    kind="related_session",
                    session_id=None,
                )
            )
        return graph

    def seed_demo_data(self) -> list[UserSession]:
        existing = self.sessions.list()
        if existing:
            return existing

        dataset = [
            {
                "title": "Feature Concepts",
                "main_category": "Product",
                "sub_category": "Discovery",
                "template_name": "Idea Canvas",
                "mood": "Curious",
                "note": (
                    "<h3>Feature Concepts</h3>"
                    "<p>Capture fast product ideas before they disappear.</p>"
                    "<ul><li>Voice capture for quick thoughts</li><li>Template-based session starters</li></ul>"
                ),
            },
            {
                "title": "Python Learning Path",
                "main_category": "Learning",
                "sub_category": "Python",
                "template_name": "Study Sprint",
                "mood": "Focused",
                "note": (
                    "<h3>Python Learning Path</h3>"
                    "<p>Keep the study flow simple and visual.</p>"
                    "<p>Next: build one small example for each topic.</p>"
                ),
            },
            {
                "title": "Weekly Reset",
                "main_category": "Personal",
                "sub_category": "Routines",
                "template_name": "Weekly Review",
                "mood": "Reflective",
                "note": (
                    "<h3>Weekly Reset</h3>"
                    "<p>Review what helped, what drained energy, and what to carry forward.</p>"
                ),
            },
        ]
        created_sessions: list[UserSession] = []
        start_time = datetime.now().replace(microsecond=0) - timedelta(days=2)
        for offset, item in enumerate(dataset):
            created_sessions.append(self._seed_single_session(item, start_time + timedelta(hours=offset * 10)))
        return created_sessions

    def export_session(self, session_id: int, target_path: str | Path) -> dict[str, object]:
        detail = self.get_session_detail(session_id)
        if detail is None:
            raise ValueError("Session not found.")
        payload = {
            "session": asdict(detail.session),
            "note": asdict(detail.note) if detail.note is not None else None,
            "main_category": asdict(detail.main_category),
            "sub_category": asdict(detail.sub_category) if detail.sub_category is not None else None,
            "session_flow": [asdict(item) for item in detail.session_flow],
            "session_graph": [asdict(item) for item in detail.session_graph],
            "workspace_map": [asdict(item) for item in detail.workspace_map],
        }
        path = Path(target_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return payload

    def get_app_summary(self) -> AppSummary:
        return self.sessions.summary_counts()

    def _ensure_base_workspace(self) -> None:
        if not self.main_categories.list():
            self.create_main_category(DEFAULT_MAIN_CATEGORY)

    @staticmethod
    def _append_html_block(content: str, block: str) -> str:
        marker = "</body>"
        lower_content = content.lower()
        marker_index = lower_content.rfind(marker)
        if marker_index == -1:
            return f"{content}{block}"
        return f"{content[:marker_index]}{block}{content[marker_index:]}"

    def _workspace_session_item(
        self,
        session: UserSession,
        parent_key: str,
        selected_session_id: int | None,
    ) -> WorkspaceMapItem:
        return WorkspaceMapItem(
            key=f"session:{session.id}",
            parent_key=parent_key,
            title=session.title,
            subtitle=f"{session.template_name} / {session.mood}",
            kind="session",
            entity_id=session.id,
            is_selected=session.id == selected_session_id,
        )

    @staticmethod
    def _extract_note_blocks(note: NoteEntry | None) -> list[str]:
        if note is None or not note.content.strip():
            return []
        content = note.content
        block_tags = ("p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "br")
        for tag in block_tags:
            content = re.sub(rf"<\s*{tag}\b[^>]*>", "\n", content, flags=re.IGNORECASE)
            if tag != "br":
                content = re.sub(rf"<\s*/\s*{tag}\s*>", "\n", content, flags=re.IGNORECASE)
        content = re.sub(r"<[^>]+>", "", content)
        lines = [html.unescape(line).strip(" -\u2022\t\r") for line in content.splitlines()]
        blocks = [line for line in lines if line]

        deduped: list[str] = []
        for block in blocks:
            if not deduped or deduped[-1] != block:
                deduped.append(block)
        return deduped

    def _seed_single_session(self, item: dict[str, str], created_at: datetime) -> UserSession:
        timestamp = created_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        main_category, sub_category = self.resolve_category_path(
            item["main_category"],
            item["sub_category"],
        )
        session = self.sessions.create(
            item["title"],
            main_category.id,
            sub_category.id if sub_category else None,
            item["template_name"],
            item["mood"],
            timestamp,
        )
        self.notes.upsert(session.id, item["note"], timestamp)
        refreshed_session = self.sessions.touch(session.id, current_timestamp())
        return refreshed_session or session
