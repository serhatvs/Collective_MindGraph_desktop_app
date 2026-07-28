"""SQLite transcript persistence and correction handling."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from collective_mindgraph.domain import (
    MeetingId,
    SegmentId,
    Transcript,
    TranscriptId,
    TranscriptSegment,
)

from .row_mapping import dump_json, load_object, load_string_tuple, parse_timestamp
from .sqlite_database import SqliteDatabase


class SqliteTranscriptStore:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def save(self, transcript: Transcript) -> Transcript:
        """Persist a complete transcript while keeping raw and corrected text separate."""

        with self._database.connect() as connection:
            existing = None
            if transcript.conversation_id:
                existing = connection.execute(
                    "SELECT id FROM transcripts WHERE conversation_id = ?",
                    (transcript.conversation_id,),
                ).fetchone()
            if existing is None:
                cursor = connection.execute(
                    """
                    INSERT INTO transcripts (
                        meeting_id, conversation_id, provider, language,
                        raw_text, corrected_text, confidence, diagnostics_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(transcript.meeting_id),
                        transcript.conversation_id,
                        transcript.provider,
                        transcript.language,
                        transcript.raw_text,
                        transcript.corrected_text,
                        transcript.confidence,
                        dump_json(transcript.diagnostics),
                        transcript.created_at.isoformat(),
                        transcript.updated_at.isoformat(),
                    ),
                )
                transcript_id = int(cursor.lastrowid)
            else:
                transcript_id = int(existing["id"])
                connection.execute(
                    """
                    UPDATE transcripts SET
                        meeting_id = ?, provider = ?, language = ?,
                        raw_text = ?, corrected_text = ?, confidence = ?,
                        diagnostics_json = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        int(transcript.meeting_id),
                        transcript.provider,
                        transcript.language,
                        transcript.raw_text,
                        transcript.corrected_text,
                        transcript.confidence,
                        dump_json(transcript.diagnostics),
                        transcript.updated_at.isoformat(),
                        transcript_id,
                    ),
                )
                connection.execute(
                    "DELETE FROM transcript_segments WHERE transcript_id = ?",
                    (transcript_id,),
                )
            for segment in transcript.segments:
                connection.execute(
                    """
                    INSERT INTO transcript_segments (
                        id, transcript_id, position, start_seconds, end_seconds,
                        speaker_label, raw_text, corrected_text, confidence,
                        speaker_confidence, overlaps_speech, notes_json, diagnostics_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(segment.id),
                        transcript_id,
                        segment.position,
                        segment.start_seconds,
                        segment.end_seconds,
                        segment.speaker_label,
                        segment.raw_text,
                        segment.corrected_text,
                        segment.confidence,
                        segment.speaker_confidence,
                        int(segment.overlaps_speech),
                        dump_json(segment.notes),
                        dump_json(segment.diagnostics),
                    ),
                )
        saved = self.latest_for_meeting(transcript.meeting_id)
        if saved is None:
            raise RuntimeError("Persisted transcript could not be loaded.")
        return saved

    def get_by_conversation_id(self, conversation_id: str) -> Transcript | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM transcripts WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            if row is None:
                return None
            segments = connection.execute(
                """
                SELECT * FROM transcript_segments
                WHERE transcript_id = ?
                ORDER BY position
                """,
                (int(row["id"]),),
            ).fetchall()
        return self._map_transcript(row, segments)

    def latest_for_meeting(self, meeting_id: MeetingId) -> Transcript | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM transcripts
                WHERE meeting_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (int(meeting_id),),
            ).fetchone()
            if row is None:
                return None
            segments = connection.execute(
                """
                SELECT * FROM transcript_segments
                WHERE transcript_id = ?
                ORDER BY position
                """,
                (int(row["id"]),),
            ).fetchall()
        return self._map_transcript(row, segments)

    def meeting_id_for_segment(self, segment_id: SegmentId) -> MeetingId | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT transcripts.meeting_id
                FROM transcript_segments
                INNER JOIN transcripts ON transcripts.id = transcript_segments.transcript_id
                WHERE transcript_segments.id = ?
                """,
                (str(segment_id),),
            ).fetchone()
        return MeetingId(int(row["meeting_id"])) if row is not None else None

    def update_segment_text(
        self,
        segment_id: SegmentId,
        *,
        corrected_text: str,
        now: datetime,
    ) -> TranscriptSegment | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT transcript_id FROM transcript_segments WHERE id = ?",
                (str(segment_id),),
            ).fetchone()
            if row is None:
                return None
            transcript_id = int(row["transcript_id"])
            connection.execute(
                "UPDATE transcript_segments SET corrected_text = ? WHERE id = ?",
                (corrected_text, str(segment_id)),
            )
            corrected_rows = connection.execute(
                """
                SELECT corrected_text FROM transcript_segments
                WHERE transcript_id = ?
                ORDER BY position
                """,
                (transcript_id,),
            ).fetchall()
            corrected_output = "\n".join(
                str(item["corrected_text"]).strip()
                for item in corrected_rows
                if str(item["corrected_text"]).strip()
            )
            connection.execute(
                "UPDATE transcripts SET corrected_text = ?, updated_at = ? WHERE id = ?",
                (corrected_output, now.isoformat(), transcript_id),
            )
            updated = connection.execute(
                "SELECT * FROM transcript_segments WHERE id = ?",
                (str(segment_id),),
            ).fetchone()
        return self._map_segment(updated) if updated is not None else None

    def count(self) -> int:
        with self._database.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0])

    @classmethod
    def _map_transcript(
        cls,
        row: sqlite3.Row,
        segments: list[sqlite3.Row],
    ) -> Transcript:
        return Transcript(
            id=TranscriptId(int(row["id"])),
            meeting_id=MeetingId(int(row["meeting_id"])),
            conversation_id=str(row["conversation_id"]) if row["conversation_id"] else None,
            provider=str(row["provider"]),
            language=str(row["language"]) if row["language"] else None,
            raw_text=str(row["raw_text"]),
            corrected_text=str(row["corrected_text"]),
            confidence=float(row["confidence"]) if row["confidence"] is not None else None,
            diagnostics=load_object(row["diagnostics_json"]),
            created_at=parse_timestamp(str(row["created_at"])),
            updated_at=parse_timestamp(str(row["updated_at"])),
            segments=tuple(cls._map_segment(segment) for segment in segments),
        )

    @staticmethod
    def _map_segment(row: sqlite3.Row) -> TranscriptSegment:
        return TranscriptSegment(
            id=SegmentId(str(row["id"])),
            transcript_id=TranscriptId(int(row["transcript_id"])),
            position=int(row["position"]),
            start_seconds=float(row["start_seconds"]),
            end_seconds=float(row["end_seconds"]),
            speaker_label=str(row["speaker_label"]) if row["speaker_label"] else None,
            raw_text=str(row["raw_text"]),
            corrected_text=str(row["corrected_text"]),
            confidence=float(row["confidence"]) if row["confidence"] is not None else None,
            speaker_confidence=(
                float(row["speaker_confidence"]) if row["speaker_confidence"] is not None else None
            ),
            overlaps_speech=bool(row["overlaps_speech"]),
            notes=load_string_tuple(row["notes_json"]),
            diagnostics=load_object(row["diagnostics_json"]),
        )
