"""Repository layer for SQLite persistence."""

from __future__ import annotations

import json
import sqlite3

from .database import Database
from .models import (
    AppSummary,
    GraphNode,
    GraphNodeDraft,
    Session,
    Snapshot,
    Transcript,
    TranscriptAnalysis,
    TranscriptAnalysisDraft,
    TranscriptAnalysisSegment,
    TranscriptDraft,
    TranscriptQualityReport,
    TranscriptSpeakerStat,
    TranscriptTopic,
)


def _session_from_row(row: sqlite3.Row) -> Session:
    return Session(
        id=row["id"],
        title=row["title"],
        device_id=row["device_id"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _transcript_from_row(row: sqlite3.Row) -> Transcript:
    return Transcript(
        id=row["id"],
        session_id=row["session_id"],
        text=row["text"],
        confidence=row["confidence"],
        created_at=row["created_at"],
    )


def _graph_node_from_row(row: sqlite3.Row) -> GraphNode:
    return GraphNode(
        id=row["id"],
        session_id=row["session_id"],
        transcript_id=row["transcript_id"],
        parent_node_id=row["parent_node_id"],
        branch_type=row["branch_type"],
        branch_slot=row["branch_slot"],
        node_text=row["node_text"],
        override_reason=row["override_reason"],
        created_at=row["created_at"],
    )


def _snapshot_from_row(row: sqlite3.Row) -> Snapshot:
    return Snapshot(
        id=row["id"],
        session_id=row["session_id"],
        node_count=row["node_count"],
        hash_sha256=row["hash_sha256"],
        created_at=row["created_at"],
    )


def _topic_from_payload(payload: dict[str, object]) -> TranscriptTopic:
    return TranscriptTopic(
        label=str(payload.get("label") or ""),
        start=float(payload.get("start") or 0.0),
        end=float(payload.get("end") or 0.0),
    )


def _speaker_stat_from_payload(payload: dict[str, object]) -> TranscriptSpeakerStat:
    return TranscriptSpeakerStat(
        speaker=str(payload.get("speaker") or "Speaker"),
        segment_count=int(payload.get("segment_count") or 0),
        speaking_seconds=float(payload.get("speaking_seconds") or 0.0),
        overlap_segments=int(payload.get("overlap_segments") or 0),
        first_start=float(payload.get("first_start") or 0.0),
        last_end=float(payload.get("last_end") or 0.0),
    )


def _analysis_segment_from_payload(payload: dict[str, object]) -> TranscriptAnalysisSegment:
    notes = payload.get("notes")
    return TranscriptAnalysisSegment(
        segment_id=str(payload.get("segment_id") or ""),
        start=float(payload.get("start") or 0.0),
        end=float(payload.get("end") or 0.0),
        speaker=str(payload.get("speaker") or "Speaker"),
        raw_text=str(payload.get("raw_text") or ""),
        corrected_text=str(payload.get("corrected_text") or ""),
        confidence=float(payload["confidence"]) if payload.get("confidence") is not None else None,
        speaker_confidence=(
            float(payload["speaker_confidence"]) if payload.get("speaker_confidence") is not None else None
        ),
        overlap=bool(payload.get("overlap") or False),
        notes=[str(item) for item in notes] if isinstance(notes, list) else [],
    )


def _quality_report_from_payload(payload: dict[str, object] | None) -> TranscriptQualityReport | None:
    if not payload:
        return None
    warnings = payload.get("warnings")
    return TranscriptQualityReport(
        segment_count=int(payload.get("segment_count") or 0),
        speaker_count=int(payload.get("speaker_count") or 0),
        unresolved_segments=int(payload.get("unresolved_segments") or 0),
        overlap_ratio=float(payload.get("overlap_ratio") or 0.0),
        avg_asr_confidence=float(payload["avg_asr_confidence"]) if payload.get("avg_asr_confidence") is not None else None,
        avg_speaker_confidence=(
            float(payload["avg_speaker_confidence"]) if payload.get("avg_speaker_confidence") is not None else None
        ),
        word_timing_coverage=float(payload.get("word_timing_coverage") or 0.0),
        corrected_change_ratio=float(payload.get("corrected_change_ratio") or 0.0),
        topic_count=int(payload.get("topic_count") or 0),
        action_item_count=int(payload.get("action_item_count") or 0),
        decision_count=int(payload.get("decision_count") or 0),
        question_count=int(payload.get("question_count") or 0),
        summary_present=bool(payload.get("summary_present") or False),
        warnings=[str(item) for item in warnings] if isinstance(warnings, list) else [],
    )


def _analysis_from_row(row: sqlite3.Row) -> TranscriptAnalysis:
    topics = json.loads(row["topics_json"])
    action_items = json.loads(row["action_items_json"])
    decisions = json.loads(row["decisions_json"])
    speaker_stats = json.loads(row["speaker_stats_json"])
    segments = json.loads(row["segments_json"])
    quality_payload = json.loads(row["quality_report_json"]) if row["quality_report_json"] else None
    return TranscriptAnalysis(
        transcript_id=row["transcript_id"],
        source_provider=row["source_provider"],
        backend_conversation_id=row["backend_conversation_id"],
        raw_text_output=row["raw_text_output"],
        corrected_text_output=row["corrected_text_output"],
        summary=row["summary"],
        topics=[_topic_from_payload(item) for item in topics],
        action_items=[str(item) for item in action_items],
        decisions=[str(item) for item in decisions],
        speaker_stats=[_speaker_stat_from_payload(item) for item in speaker_stats],
        segments=[_analysis_segment_from_payload(item) for item in segments],
        quality_report=_quality_report_from_payload(quality_payload),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _dump_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


class SessionRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, title: str, device_id: str, status: str, timestamp: str) -> Session:
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO sessions (title, device_id, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, device_id, status, timestamp, timestamp),
            )
            session_id = int(cursor.lastrowid)
            row = connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise RuntimeError("Failed to create session.")
        return _session_from_row(row)

    def get(self, session_id: int) -> Session | None:
        with self._database.connect() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return _session_from_row(row) if row else None

    def list(self, query: str = "") -> list[Session]:
        sql = "SELECT * FROM sessions"
        parameters: tuple[str, ...] = ()
        normalized = query.strip()
        if normalized:
            like_query = f"%{normalized}%"
            sql += " WHERE title LIKE ? OR device_id LIKE ?"
            parameters = (like_query, like_query)
        sql += " ORDER BY updated_at DESC, created_at DESC, id DESC"
        with self._database.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [_session_from_row(row) for row in rows]

    def delete(self, session_id: int) -> bool:
        with self._database.connect() as connection:
            cursor = connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0

    def touch(self, session_id: int, updated_at: str) -> Session | None:
        with self._database.connect() as connection:
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (updated_at, session_id),
            )
            row = connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return _session_from_row(row) if row else None

    def summary_counts(self) -> AppSummary:
        with self._database.connect() as connection:
            counts = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM sessions) AS total_sessions,
                    (SELECT COUNT(*) FROM sessions WHERE status = 'active') AS active_sessions,
                    (SELECT COUNT(*) FROM transcripts) AS total_transcripts,
                    (SELECT COUNT(*) FROM graph_nodes) AS total_nodes,
                    (SELECT COUNT(*) FROM snapshots) AS total_snapshots
                """
            ).fetchone()
        if counts is None:
            raise RuntimeError("Failed to load summary counts.")
        return AppSummary(
            total_sessions=counts["total_sessions"],
            active_sessions=counts["active_sessions"],
            total_transcripts=counts["total_transcripts"],
            total_nodes=counts["total_nodes"],
            total_snapshots=counts["total_snapshots"],
        )


class TranscriptRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create_many(self, session_id: int, drafts: list[TranscriptDraft]) -> list[Transcript]:
        created: list[Transcript] = []
        with self._database.connect() as connection:
            for draft in drafts:
                cursor = connection.execute(
                    """
                    INSERT INTO transcripts (session_id, text, confidence, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session_id, draft.text, draft.confidence, draft.created_at),
                )
                created.append(
                    Transcript(
                        id=int(cursor.lastrowid),
                        session_id=session_id,
                        text=draft.text,
                        confidence=draft.confidence,
                        created_at=draft.created_at,
                    )
                )
        return created

    def list_by_session(self, session_id: int) -> list[Transcript]:
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM transcripts WHERE session_id = ? ORDER BY created_at ASC, id ASC",
                (session_id,),
            ).fetchall()
        return [_transcript_from_row(row) for row in rows]

    def update_text(self, transcript_id: int, text: str, confidence: float | None = None) -> Transcript | None:
        with self._database.connect() as connection:
            if confidence is None:
                connection.execute(
                    "UPDATE transcripts SET text = ? WHERE id = ?",
                    (text, transcript_id),
                )
            else:
                connection.execute(
                    "UPDATE transcripts SET text = ?, confidence = ? WHERE id = ?",
                    (text, confidence, transcript_id),
                )
            row = connection.execute("SELECT * FROM transcripts WHERE id = ?", (transcript_id,)).fetchone()
        return _transcript_from_row(row) if row else None


class GraphNodeRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create_many(self, session_id: int, drafts: list[GraphNodeDraft]) -> list[GraphNode]:
        created: list[GraphNode] = []
        with self._database.connect() as connection:
            for draft in drafts:
                cursor = connection.execute(
                    """
                    INSERT INTO graph_nodes (
                        session_id,
                        transcript_id,
                        parent_node_id,
                        branch_type,
                        branch_slot,
                        node_text,
                        override_reason,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        draft.transcript_id,
                        draft.parent_node_id,
                        draft.branch_type,
                        draft.branch_slot,
                        draft.node_text,
                        draft.override_reason,
                        draft.created_at,
                    ),
                )
                created.append(
                    GraphNode(
                        id=int(cursor.lastrowid),
                        session_id=session_id,
                        transcript_id=draft.transcript_id,
                        parent_node_id=draft.parent_node_id,
                        branch_type=draft.branch_type,
                        branch_slot=draft.branch_slot,
                        node_text=draft.node_text,
                        override_reason=draft.override_reason,
                        created_at=draft.created_at,
                    )
                )
        return created

    def list_by_session(self, session_id: int) -> list[GraphNode]:
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM graph_nodes WHERE session_id = ? ORDER BY created_at ASC, id ASC",
                (session_id,),
            ).fetchall()
        return [_graph_node_from_row(row) for row in rows]

    def update_node_text_by_transcript(self, transcript_id: int, node_text: str) -> None:
        with self._database.connect() as connection:
            connection.execute(
                "UPDATE graph_nodes SET node_text = ? WHERE transcript_id = ?",
                (node_text, transcript_id),
            )


class SnapshotRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, session_id: int, node_count: int, hash_sha256: str, created_at: str) -> Snapshot:
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO snapshots (session_id, node_count, hash_sha256, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, node_count, hash_sha256, created_at),
            )
            snapshot_id = int(cursor.lastrowid)
            row = connection.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        if row is None:
            raise RuntimeError("Failed to create snapshot.")
        return _snapshot_from_row(row)

    def list_by_session(self, session_id: int) -> list[Snapshot]:
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM snapshots WHERE session_id = ? ORDER BY created_at DESC, id DESC",
                (session_id,),
            ).fetchall()
        return [_snapshot_from_row(row) for row in rows]

    def replace_for_session(
        self,
        session_id: int,
        node_count: int,
        hash_sha256: str,
        created_at: str,
    ) -> list[Snapshot]:
        with self._database.connect() as connection:
            connection.execute("DELETE FROM snapshots WHERE session_id = ?", (session_id,))
            connection.execute(
                """
                INSERT INTO snapshots (session_id, node_count, hash_sha256, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, node_count, hash_sha256, created_at),
            )
        return self.list_by_session(session_id)


class TranscriptAnalysisRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def upsert(self, transcript_id: int, draft: TranscriptAnalysisDraft) -> TranscriptAnalysis:
        topics_payload = [
            {
                "label": item.label,
                "start": item.start,
                "end": item.end,
            }
            for item in draft.topics
        ]
        speaker_stats_payload = [
            {
                "speaker": item.speaker,
                "segment_count": item.segment_count,
                "speaking_seconds": item.speaking_seconds,
                "overlap_segments": item.overlap_segments,
                "first_start": item.first_start,
                "last_end": item.last_end,
            }
            for item in draft.speaker_stats
        ]
        segments_payload = [
            {
                "segment_id": item.segment_id,
                "start": item.start,
                "end": item.end,
                "speaker": item.speaker,
                "raw_text": item.raw_text,
                "corrected_text": item.corrected_text,
                "confidence": item.confidence,
                "speaker_confidence": item.speaker_confidence,
                "overlap": item.overlap,
                "notes": item.notes,
            }
            for item in draft.segments
        ]
        quality_payload = (
            {
                "segment_count": draft.quality_report.segment_count,
                "speaker_count": draft.quality_report.speaker_count,
                "unresolved_segments": draft.quality_report.unresolved_segments,
                "overlap_ratio": draft.quality_report.overlap_ratio,
                "avg_asr_confidence": draft.quality_report.avg_asr_confidence,
                "avg_speaker_confidence": draft.quality_report.avg_speaker_confidence,
                "word_timing_coverage": draft.quality_report.word_timing_coverage,
                "corrected_change_ratio": draft.quality_report.corrected_change_ratio,
                "topic_count": draft.quality_report.topic_count,
                "action_item_count": draft.quality_report.action_item_count,
                "decision_count": draft.quality_report.decision_count,
                "question_count": draft.quality_report.question_count,
                "summary_present": draft.quality_report.summary_present,
                "warnings": draft.quality_report.warnings,
            }
            if draft.quality_report is not None
            else None
        )
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO transcript_analyses (
                    transcript_id,
                    source_provider,
                    backend_conversation_id,
                    raw_text_output,
                    corrected_text_output,
                    summary,
                    topics_json,
                    action_items_json,
                    decisions_json,
                    speaker_stats_json,
                    segments_json,
                    quality_report_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(transcript_id) DO UPDATE SET
                    source_provider = excluded.source_provider,
                    backend_conversation_id = excluded.backend_conversation_id,
                    raw_text_output = excluded.raw_text_output,
                    corrected_text_output = excluded.corrected_text_output,
                    summary = excluded.summary,
                    topics_json = excluded.topics_json,
                    action_items_json = excluded.action_items_json,
                    decisions_json = excluded.decisions_json,
                    speaker_stats_json = excluded.speaker_stats_json,
                    segments_json = excluded.segments_json,
                    quality_report_json = excluded.quality_report_json,
                    updated_at = excluded.updated_at
                """,
                (
                    transcript_id,
                    draft.source_provider,
                    draft.backend_conversation_id,
                    draft.raw_text_output,
                    draft.corrected_text_output,
                    draft.summary,
                    _dump_json(topics_payload),
                    _dump_json(draft.action_items),
                    _dump_json(draft.decisions),
                    _dump_json(speaker_stats_payload),
                    _dump_json(segments_payload),
                    _dump_json(quality_payload) if quality_payload is not None else None,
                    draft.created_at,
                    draft.updated_at,
                ),
            )
            row = connection.execute(
                "SELECT * FROM transcript_analyses WHERE transcript_id = ?",
                (transcript_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("Failed to store transcript analysis.")
        return _analysis_from_row(row)

    def list_by_session(self, session_id: int) -> dict[int, TranscriptAnalysis]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT analysis.*
                FROM transcript_analyses AS analysis
                INNER JOIN transcripts ON transcripts.id = analysis.transcript_id
                WHERE transcripts.session_id = ?
                ORDER BY transcripts.created_at ASC, transcripts.id ASC
                """,
                (session_id,),
            ).fetchall()
        analyses = [_analysis_from_row(row) for row in rows]
        return {item.transcript_id: item for item in analyses}

    def get(self, transcript_id: int) -> TranscriptAnalysis | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM transcript_analyses WHERE transcript_id = ?",
                (transcript_id,),
            ).fetchone()
        return _analysis_from_row(row) if row else None
