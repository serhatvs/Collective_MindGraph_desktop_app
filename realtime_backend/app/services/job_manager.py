"""Persistent job repository and manager for background tasks."""

import json
import uuid
import sqlite3
from enum import Enum
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobManager:
    """Manages background jobs persisted in SQLite."""

    def __init__(self, database_proxy):
        self.db = database_proxy
        self._initialize_schema()

    def _initialize_schema(self):
        schema = """
        CREATE TABLE IF NOT EXISTS v2_jobs (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            status TEXT NOT NULL,
            progress INTEGER NOT NULL DEFAULT 0,
            message TEXT,
            error TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
        with self.db.connect() as conn:
            conn.executescript(schema)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_job(self, job_type: str, message: str = "Starting...", metadata: Dict[str, Any] = None) -> str:
        job_id = str(uuid.uuid4())
        now = self._now()
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO v2_jobs (id, type, status, progress, message, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, job_type, JobStatus.PENDING.value, 0, message, json.dumps(metadata or {}), now, now)
            )
        return job_id

    def update_job(self, job_id: str, status: Optional[JobStatus] = None, progress: Optional[int] = None, message: Optional[str] = None, error: Optional[str] = None):
        now = self._now()
        updates = ["updated_at = ?"]
        params = [now]
        
        if status:
            updates.append("status = ?")
            params.append(status.value)
        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)
        if message:
            updates.append("message = ?")
            params.append(message)
        if error:
            updates.append("error = ?")
            params.append(error)
            
        params.append(job_id)
        query = f"UPDATE v2_jobs SET {', '.join(updates)} WHERE id = ?"
        
        with self.db.connect() as conn:
            conn.execute(query, params)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM v2_jobs WHERE id = ?", (job_id,)).fetchone()
            return dict(row) if row else None

    def list_jobs(self, active_only: bool = False) -> List[Dict[str, Any]]:
        query = "SELECT * FROM v2_jobs"
        if active_only:
            query += f" WHERE status IN ('{JobStatus.PENDING.value}', '{JobStatus.RUNNING.value}')"
        query += " ORDER BY created_at DESC"
        
        with self.db.connect() as conn:
            rows = conn.execute(query).fetchall()
            return [dict(r) for r in rows]
