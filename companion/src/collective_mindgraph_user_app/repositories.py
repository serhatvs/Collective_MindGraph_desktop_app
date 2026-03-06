"""Repository layer for the companion app."""

from __future__ import annotations

import sqlite3

from .database import Database
from .models import AppSummary, MainCategory, NoteEntry, SubCategory, UserSession


def _main_category_from_row(row: sqlite3.Row) -> MainCategory:
    return MainCategory(
        id=row["id"],
        name=row["name"],
        created_at=row["created_at"],
    )


def _sub_category_from_row(row: sqlite3.Row) -> SubCategory:
    return SubCategory(
        id=row["id"],
        main_category_id=row["main_category_id"],
        name=row["name"],
        created_at=row["created_at"],
    )


def _session_from_row(row: sqlite3.Row) -> UserSession:
    return UserSession(
        id=row["id"],
        title=row["title"],
        main_category_id=row["main_category_id"],
        main_category_name=row["main_category_name"],
        sub_category_id=row["sub_category_id"],
        sub_category_name=row["sub_category_name"],
        template_name=row["template_name"],
        mood=row["mood"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _note_from_row(row: sqlite3.Row) -> NoteEntry:
    return NoteEntry(
        id=row["id"],
        session_id=row["session_id"],
        content=row["content"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class MainCategoryRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, name: str, timestamp: str) -> MainCategory:
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO main_categories (name, created_at)
                VALUES (?, ?)
                """,
                (name, timestamp),
            )
            category_id = int(cursor.lastrowid)
            row = connection.execute(
                "SELECT * FROM main_categories WHERE id = ?",
                (category_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("Failed to create main category.")
        return _main_category_from_row(row)

    def get(self, category_id: int) -> MainCategory | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM main_categories WHERE id = ?",
                (category_id,),
            ).fetchone()
        return _main_category_from_row(row) if row else None

    def get_by_name(self, name: str) -> MainCategory | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM main_categories WHERE lower(name) = lower(?)",
                (name,),
            ).fetchone()
        return _main_category_from_row(row) if row else None

    def list(self) -> list[MainCategory]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM main_categories
                ORDER BY name COLLATE NOCASE ASC, id ASC
                """
            ).fetchall()
        return [_main_category_from_row(row) for row in rows]

    def update_name(self, category_id: int, name: str) -> MainCategory | None:
        with self._database.connect() as connection:
            connection.execute(
                "UPDATE main_categories SET name = ? WHERE id = ?",
                (name, category_id),
            )
            row = connection.execute(
                "SELECT * FROM main_categories WHERE id = ?",
                (category_id,),
            ).fetchone()
        return _main_category_from_row(row) if row else None

    def delete(self, category_id: int) -> bool:
        with self._database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM main_categories WHERE id = ?",
                (category_id,),
            )
        return cursor.rowcount > 0


class SubCategoryRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, main_category_id: int, name: str, timestamp: str) -> SubCategory:
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO sub_categories (main_category_id, name, created_at)
                VALUES (?, ?, ?)
                """,
                (main_category_id, name, timestamp),
            )
            category_id = int(cursor.lastrowid)
            row = connection.execute(
                "SELECT * FROM sub_categories WHERE id = ?",
                (category_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("Failed to create sub category.")
        return _sub_category_from_row(row)

    def get(self, category_id: int) -> SubCategory | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM sub_categories WHERE id = ?",
                (category_id,),
            ).fetchone()
        return _sub_category_from_row(row) if row else None

    def get_by_name(self, main_category_id: int, name: str) -> SubCategory | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM sub_categories
                WHERE main_category_id = ? AND lower(name) = lower(?)
                """,
                (main_category_id, name),
            ).fetchone()
        return _sub_category_from_row(row) if row else None

    def list(self, main_category_id: int | None = None) -> list[SubCategory]:
        sql = "SELECT * FROM sub_categories"
        parameters: tuple[int, ...] = ()
        if main_category_id is not None:
            sql += " WHERE main_category_id = ?"
            parameters = (main_category_id,)
        sql += " ORDER BY name COLLATE NOCASE ASC, id ASC"
        with self._database.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [_sub_category_from_row(row) for row in rows]

    def update_name(self, category_id: int, name: str) -> SubCategory | None:
        with self._database.connect() as connection:
            connection.execute(
                "UPDATE sub_categories SET name = ? WHERE id = ?",
                (name, category_id),
            )
            row = connection.execute(
                "SELECT * FROM sub_categories WHERE id = ?",
                (category_id,),
            ).fetchone()
        return _sub_category_from_row(row) if row else None

    def delete(self, category_id: int) -> bool:
        with self._database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM sub_categories WHERE id = ?",
                (category_id,),
            )
        return cursor.rowcount > 0


class SessionRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(
        self,
        title: str,
        main_category_id: int,
        sub_category_id: int | None,
        template_name: str,
        mood: str,
        timestamp: str,
    ) -> UserSession:
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO user_sessions (
                    title, main_category_id, sub_category_id, template_name, mood, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (title, main_category_id, sub_category_id, template_name, mood, timestamp, timestamp),
            )
            session_id = int(cursor.lastrowid)
            row = connection.execute(self._session_query() + " WHERE s.id = ?", (session_id,)).fetchone()
        if row is None:
            raise RuntimeError("Failed to create session.")
        return _session_from_row(row)

    def update(
        self,
        session_id: int,
        title: str,
        main_category_id: int,
        sub_category_id: int | None,
        template_name: str,
        mood: str,
        updated_at: str,
    ) -> UserSession | None:
        with self._database.connect() as connection:
            connection.execute(
                """
                UPDATE user_sessions
                SET title = ?, main_category_id = ?, sub_category_id = ?, template_name = ?, mood = ?, updated_at = ?
                WHERE id = ?
                """,
                (title, main_category_id, sub_category_id, template_name, mood, updated_at, session_id),
            )
            row = connection.execute(self._session_query() + " WHERE s.id = ?", (session_id,)).fetchone()
        return _session_from_row(row) if row else None

    def touch(self, session_id: int, updated_at: str) -> UserSession | None:
        with self._database.connect() as connection:
            connection.execute(
                "UPDATE user_sessions SET updated_at = ? WHERE id = ?",
                (updated_at, session_id),
            )
            row = connection.execute(self._session_query() + " WHERE s.id = ?", (session_id,)).fetchone()
        return _session_from_row(row) if row else None

    def get(self, session_id: int) -> UserSession | None:
        with self._database.connect() as connection:
            row = connection.execute(self._session_query() + " WHERE s.id = ?", (session_id,)).fetchone()
        return _session_from_row(row) if row else None

    def list(self, query: str = "") -> list[UserSession]:
        sql = self._session_query()
        parameters: tuple[str, ...] = ()
        normalized = query.strip()
        if normalized:
            like_query = f"%{normalized}%"
            sql += (
                " WHERE s.title LIKE ? OR mc.name LIKE ? OR COALESCE(sc.name, '') LIKE ? OR s.template_name LIKE ?"
            )
            parameters = (like_query, like_query, like_query, like_query)
        sql += " ORDER BY s.updated_at DESC, s.created_at DESC, s.id DESC"
        with self._database.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [_session_from_row(row) for row in rows]

    def delete(self, session_id: int) -> bool:
        with self._database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM user_sessions WHERE id = ?",
                (session_id,),
            )
        return cursor.rowcount > 0

    def count_by_main_category(self, main_category_id: int) -> int:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS item_count FROM user_sessions WHERE main_category_id = ?",
                (main_category_id,),
            ).fetchone()
        return int(row["item_count"]) if row else 0

    def count_by_sub_category(self, sub_category_id: int) -> int:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS item_count FROM user_sessions WHERE sub_category_id = ?",
                (sub_category_id,),
            ).fetchone()
        return int(row["item_count"]) if row else 0

    def summary_counts(self) -> AppSummary:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM user_sessions) AS total_sessions,
                    (SELECT COUNT(*) FROM main_categories) AS total_main_categories,
                    (SELECT COUNT(*) FROM sub_categories) AS total_sub_categories,
                    (SELECT COUNT(*) FROM note_entries) AS total_notes
                """
            ).fetchone()
        if row is None:
            raise RuntimeError("Failed to load app summary.")
        total_map_nodes = (
            int(row["total_sessions"])
            + int(row["total_main_categories"])
            + int(row["total_sub_categories"])
        )
        return AppSummary(
            total_sessions=int(row["total_sessions"]),
            total_main_categories=int(row["total_main_categories"]),
            total_sub_categories=int(row["total_sub_categories"]),
            total_notes=int(row["total_notes"]),
            total_map_nodes=total_map_nodes,
        )

    @staticmethod
    def _session_query() -> str:
        return """
            SELECT
                s.*,
                mc.name AS main_category_name,
                sc.name AS sub_category_name
            FROM user_sessions AS s
            JOIN main_categories AS mc ON mc.id = s.main_category_id
            LEFT JOIN sub_categories AS sc ON sc.id = s.sub_category_id
        """


class NoteRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def get_by_session(self, session_id: int) -> NoteEntry | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM note_entries WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return _note_from_row(row) if row else None

    def upsert(self, session_id: int, content: str, timestamp: str) -> NoteEntry:
        existing = self.get_by_session(session_id)
        with self._database.connect() as connection:
            if existing is None:
                cursor = connection.execute(
                    """
                    INSERT INTO note_entries (session_id, content, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session_id, content, timestamp, timestamp),
                )
                note_id = int(cursor.lastrowid)
            else:
                connection.execute(
                    """
                    UPDATE note_entries
                    SET content = ?, updated_at = ?
                    WHERE session_id = ?
                    """,
                    (content, timestamp, session_id),
                )
                note_id = existing.id
            row = connection.execute(
                "SELECT * FROM note_entries WHERE id = ?",
                (note_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("Failed to save note.")
        return _note_from_row(row)
