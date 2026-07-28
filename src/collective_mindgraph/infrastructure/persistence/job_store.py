"""SQLite processing-job reads used by engine and desktop."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from collective_mindgraph.application.pagination import Page, PageRequest
from collective_mindgraph.domain import (
    JobId,
    MeetingId,
    ProcessingJob,
    ProcessingStatus,
    RecordingId,
    TranscriptId,
)

from .row_mapping import dump_json, load_object, parse_timestamp
from .sqlite_database import SqliteDatabase
from .sqlite_pagination import decode_offset, encode_offset


class SqliteJobStore:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def create(self, job: ProcessingJob) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO processing_jobs (
                    id, meeting_id, recording_id, parent_job_id,
                    result_transcript_id, kind, status, progress, message, error,
                    retryable, attributes_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(job.id),
                    int(job.meeting_id) if job.meeting_id is not None else None,
                    str(job.recording_id) if job.recording_id is not None else None,
                    str(job.parent_job_id) if job.parent_job_id is not None else None,
                    (
                        int(job.result_transcript_id)
                        if job.result_transcript_id is not None
                        else None
                    ),
                    job.kind,
                    job.status.value,
                    job.progress,
                    job.message,
                    job.error,
                    int(job.retryable),
                    dump_json(job.attributes),
                    job.created_at.isoformat(),
                    job.updated_at.isoformat(),
                ),
            )

    def get(self, job_id: JobId) -> ProcessingJob | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM processing_jobs WHERE id = ?",
                (str(job_id),),
            ).fetchone()
        return self._map(row) if row is not None else None

    def list(self, request: PageRequest, *, active_only: bool = False) -> Page[ProcessingJob]:
        where = "WHERE status IN ('pending', 'running')" if active_only else ""
        offset = decode_offset(request.cursor)
        with self._database.connect() as connection:
            total = int(
                connection.execute(f"SELECT COUNT(*) FROM processing_jobs {where}").fetchone()[0]
            )
            rows = connection.execute(
                f"""
                SELECT * FROM processing_jobs
                {where}
                ORDER BY updated_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (request.limit, offset),
            ).fetchall()
        items = tuple(self._map(row) for row in rows)
        return Page(items, total, encode_offset(offset + len(items), total))

    def update(
        self,
        job_id: JobId,
        *,
        status: ProcessingStatus | None = None,
        progress: int | None = None,
        message: str | None = None,
        error: str | None = None,
        retryable: bool | None = None,
        result_transcript_id: TranscriptId | None = None,
        now: datetime,
    ) -> ProcessingJob | None:
        if progress is not None and not 0 <= progress <= 100:
            raise ValueError("Job progress must be between 0 and 100.")
        assignments = ["updated_at = ?"]
        parameters: list[object] = [now.isoformat()]
        for column, value in (
            ("status", status.value if status else None),
            ("progress", progress),
            ("message", message),
            ("error", error),
            ("retryable", int(retryable) if retryable is not None else None),
            (
                "result_transcript_id",
                int(result_transcript_id) if result_transcript_id is not None else None,
            ),
        ):
            if value is not None:
                assignments.append(f"{column} = ?")
                parameters.append(value)
        parameters.append(str(job_id))
        with self._database.connect() as connection:
            cursor = connection.execute(
                f"UPDATE processing_jobs SET {', '.join(assignments)} WHERE id = ?",
                tuple(parameters),
            )
        return self.get(job_id) if cursor.rowcount else None

    @staticmethod
    def _map(row: sqlite3.Row) -> ProcessingJob:
        return ProcessingJob(
            id=JobId(str(row["id"])),
            meeting_id=MeetingId(int(row["meeting_id"])) if row["meeting_id"] else None,
            recording_id=(RecordingId(str(row["recording_id"])) if row["recording_id"] else None),
            parent_job_id=(JobId(str(row["parent_job_id"])) if row["parent_job_id"] else None),
            result_transcript_id=(
                TranscriptId(int(row["result_transcript_id"]))
                if row["result_transcript_id"]
                else None
            ),
            kind=str(row["kind"]),
            status=ProcessingStatus(str(row["status"])),
            progress=int(row["progress"]),
            message=str(row["message"]),
            error=str(row["error"]) if row["error"] else None,
            retryable=bool(row["retryable"]),
            attributes=load_object(row["attributes_json"]),
            created_at=parse_timestamp(str(row["created_at"])),
            updated_at=parse_timestamp(str(row["updated_at"])),
        )
