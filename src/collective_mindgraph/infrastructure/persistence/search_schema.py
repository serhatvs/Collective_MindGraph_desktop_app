"""Full-text search over knowledge nodes.

The index is an FTS5 mirror of `knowledge_nodes`, kept current by triggers and
fully rebuildable from the table. Nothing here is a source of truth, so a
corrupt or missing index is repaired by rebuilding rather than by migration.
"""

from __future__ import annotations

import re
import sqlite3

SEARCH_TABLE = "knowledge_search"

# `unicode61 remove_diacritics 2` folds ü, ö, ç, ş, and ğ, but Turkish dotless
# "ı" and dotted "İ" are separate letters rather than accented forms, so it
# leaves them alone. Without help, a search for "farkli" would never reach
# "farklı". Both the indexed text and the query are therefore folded to plain
# "i" first, which is what a user typing on a non-Turkish keyboard expects.
TURKISH_I_FORMS = ("ı", "İ", "I")

_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)


def fold_turkish(text: str) -> str:
    """Map the Turkish i-variants onto plain "i"."""

    for form in TURKISH_I_FORMS:
        text = text.replace(form, "i")
    return text


def _fold_sql(column: str) -> str:
    expression = column
    for form in TURKISH_I_FORMS:
        expression = f"replace({expression}, '{form}', 'i')"
    return expression


SEARCH_SCHEMA_SQL = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS {SEARCH_TABLE} USING fts5(
    node_id UNINDEXED,
    title,
    body,
    tokenize = "unicode61 remove_diacritics 2"
);

CREATE TRIGGER IF NOT EXISTS trg_knowledge_search_insert
AFTER INSERT ON knowledge_nodes
BEGIN
    INSERT INTO {SEARCH_TABLE}(node_id, title, body)
    VALUES (NEW.id, {_fold_sql("NEW.title")}, {_fold_sql("NEW.body")});
END;

CREATE TRIGGER IF NOT EXISTS trg_knowledge_search_update
AFTER UPDATE OF title, body ON knowledge_nodes
BEGIN
    DELETE FROM {SEARCH_TABLE} WHERE node_id = OLD.id;
    INSERT INTO {SEARCH_TABLE}(node_id, title, body)
    VALUES (NEW.id, {_fold_sql("NEW.title")}, {_fold_sql("NEW.body")});
END;

CREATE TRIGGER IF NOT EXISTS trg_knowledge_search_delete
AFTER DELETE ON knowledge_nodes
BEGIN
    DELETE FROM {SEARCH_TABLE} WHERE node_id = OLD.id;
END;
"""


def install_search_index(connection: sqlite3.Connection) -> None:
    """Create the index and triggers, then backfill anything missing."""

    connection.executescript(SEARCH_SCHEMA_SQL)
    rebuild_search_index(connection)


def rebuild_search_index(connection: sqlite3.Connection) -> int:
    """Rebuild the index from the table and report how many rows it holds."""

    connection.execute(f"DELETE FROM {SEARCH_TABLE}")
    connection.execute(
        f"INSERT INTO {SEARCH_TABLE}(node_id, title, body) "
        f"SELECT id, {_fold_sql('title')}, {_fold_sql('body')} FROM knowledge_nodes"
    )
    row = connection.execute(f"SELECT COUNT(*) FROM {SEARCH_TABLE}").fetchone()
    return int(row[0]) if row else 0


def build_match_expression(query: str) -> str:
    """Turn a user's words into a safe FTS5 prefix query.

    Every token is quoted, so punctuation a user typed cannot become FTS5
    syntax, and an unmatched quote cannot make the query unparseable.
    """

    tokens = _TOKEN_PATTERN.findall(fold_turkish(query))
    if not tokens:
        raise ValueError("A search needs at least one word.")
    return " AND ".join(f'"{token}"*' for token in tokens)


def node_match_clause(query: str) -> tuple[str, list[object]]:
    """Return the SQL clause and parameters that filter nodes by a query.

    A query of only punctuation has no searchable term, so it matches nothing.
    Matching everything would be the friendlier-looking answer and the wrong
    one: the user asked for something specific.
    """

    if not has_searchable_terms(query):
        return "1 = 0", []
    return (
        f"id IN (SELECT node_id FROM {SEARCH_TABLE} WHERE {SEARCH_TABLE} MATCH ?)",
        [build_match_expression(query)],
    )


def has_searchable_terms(query: str) -> bool:
    """Whether a query contains anything the index can match."""

    return bool(_TOKEN_PATTERN.findall(query))


__all__ = [
    "SEARCH_SCHEMA_SQL",
    "TURKISH_I_FORMS",
    "fold_turkish",
    "SEARCH_TABLE",
    "build_match_expression",
    "has_searchable_terms",
    "node_match_clause",
    "install_search_index",
    "rebuild_search_index",
]
