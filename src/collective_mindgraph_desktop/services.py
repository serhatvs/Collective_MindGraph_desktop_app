"""Service layer for application workflows."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .database import Database
from .models import AppSummary, GraphNode, GraphNodeDraft, Session, SessionDetail, Snapshot, TranscriptDraft
from .repositories import GraphNodeRepository, SessionRepository, SnapshotRepository, TranscriptRepository


def current_timestamp() -> str:
    return datetime.now(tz=UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S")


class SnapshotHasher:
    @staticmethod
    def compute(nodes: list[GraphNode]) -> str:
        canonical_nodes = [
            {
                "id": node.id,
                "session_id": node.session_id,
                "transcript_id": node.transcript_id,
                "parent_node_id": node.parent_node_id,
                "branch_type": node.branch_type,
                "branch_slot": node.branch_slot,
                "node_text": node.node_text,
                "override_reason": node.override_reason,
                "created_at": node.created_at,
            }
            for node in sorted(nodes, key=lambda item: item.id)
        ]
        payload = json.dumps(canonical_nodes, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CollectiveMindGraphService:
    def __init__(self, database: Database | None = None) -> None:
        self._database = database or Database()
        self._database.initialize()
        self.sessions = SessionRepository(self._database)
        self.transcripts = TranscriptRepository(self._database)
        self.graph_nodes = GraphNodeRepository(self._database)
        self.snapshots = SnapshotRepository(self._database)

    def create_session(self, title: str, device_id: str, status: str = "active") -> Session:
        cleaned_title = title.strip()
        cleaned_device_id = device_id.strip()
        cleaned_status = status.strip().lower() or "active"
        if not cleaned_title:
            raise ValueError("Session title is required.")
        if not cleaned_device_id:
            raise ValueError("Device ID is required.")
        return self.sessions.create(cleaned_title, cleaned_device_id, cleaned_status, current_timestamp())

    def list_sessions(self, query: str = "") -> list[Session]:
        return self.sessions.list(query)

    def get_session_detail(self, session_id: int) -> SessionDetail | None:
        session = self.sessions.get(session_id)
        if session is None:
            return None
        return SessionDetail(
            session=session,
            transcripts=self.transcripts.list_by_session(session_id),
            graph_nodes=self.graph_nodes.list_by_session(session_id),
            snapshots=self.snapshots.list_by_session(session_id),
        )

    def delete_session(self, session_id: int) -> bool:
        return self.sessions.delete(session_id)

    def seed_demo_data(self) -> list[Session]:
        existing = self.sessions.list()
        if existing:
            return existing

        now = datetime.now().replace(microsecond=0)
        dataset = [
            {
                "title": "Emergency Routing Analysis",
                "device_id": "WS-ENG-01",
                "status": "active",
                "transcripts": [
                    ("Incoming signals suggest a corridor blockage on the north route.", 0.98, now - timedelta(minutes=55)),
                    ("Primary path reroute is feasible if power load remains under threshold.", 0.91, now - timedelta(minutes=48)),
                    ("Side branch explores manual override in case of relay drift.", 0.88, now - timedelta(minutes=40)),
                ],
                "nodes": [
                    {"key": "root", "branch_type": "root", "parent_key": None, "branch_slot": None, "transcript_index": 0, "node_text": "Route blockage detected at corridor north.", "override_reason": None, "created_at": now - timedelta(minutes=54)},
                    {"key": "main_primary", "branch_type": "main", "parent_key": "root", "branch_slot": None, "transcript_index": 1, "node_text": "Recommend primary reroute with monitored load balancing.", "override_reason": None, "created_at": now - timedelta(minutes=46)},
                    {"key": "side_override", "branch_type": "side", "parent_key": "main_primary", "branch_slot": 1, "transcript_index": 2, "node_text": "Fallback: manual relay override if automated handoff fails.", "override_reason": "Operator confidence dip on relay telemetry.", "created_at": now - timedelta(minutes=38)},
                ],
            },
            {
                "title": "Assembly Line Consistency Review",
                "device_id": "MFG-LINE-07",
                "status": "paused",
                "transcripts": [
                    ("Observed mismatch between expected torque pattern and actual readings.", 0.95, now - timedelta(minutes=33)),
                    ("Main interpretation points to calibration drift after shift handoff.", 0.89, now - timedelta(minutes=28)),
                    ("Secondary interpretation keeps sensor heat bloom as an alternative.", 0.83, now - timedelta(minutes=22)),
                    ("Operator notes suggest both paths should remain visible for review.", 0.87, now - timedelta(minutes=16)),
                ],
                "nodes": [
                    {"key": "root", "branch_type": "root", "parent_key": None, "branch_slot": None, "transcript_index": 0, "node_text": "Torque pattern mismatch flagged on line seven.", "override_reason": None, "created_at": now - timedelta(minutes=32)},
                    {"key": "main_primary", "branch_type": "main", "parent_key": "root", "branch_slot": None, "transcript_index": 1, "node_text": "Likely calibration drift introduced during handoff window.", "override_reason": None, "created_at": now - timedelta(minutes=27)},
                    {"key": "side_thermal", "branch_type": "side", "parent_key": "main_primary", "branch_slot": 1, "transcript_index": 2, "node_text": "Alternative branch: thermal bloom may be distorting readings.", "override_reason": "Ambient line temperature rose above expected baseline.", "created_at": now - timedelta(minutes=21)},
                    {"key": "side_review", "branch_type": "side", "parent_key": "main_primary", "branch_slot": 2, "transcript_index": 3, "node_text": "Keep both interpretations active pending next maintenance sample.", "override_reason": "Supervisor requested dual-path review.", "created_at": now - timedelta(minutes=15)},
                ],
            },
            {
                "title": "Field Diagnostics Session",
                "device_id": "FIELD-NODE-22",
                "status": "active",
                "transcripts": [
                    ("Portable scanner reports intermittent packet loss from the edge cluster.", 0.97, now - timedelta(minutes=12)),
                    ("Main branch attributes loss to power cycling during battery swap.", 0.93, now - timedelta(minutes=10)),
                    ("Side branch tracks potential antenna obstruction from new casing.", 0.84, now - timedelta(minutes=8)),
                ],
                "nodes": [
                    {"key": "root", "branch_type": "root", "parent_key": None, "branch_slot": None, "transcript_index": 0, "node_text": "Edge cluster packet loss detected during field scan.", "override_reason": None, "created_at": now - timedelta(minutes=11)},
                    {"key": "main_primary", "branch_type": "main", "parent_key": "root", "branch_slot": None, "transcript_index": 1, "node_text": "Battery swap power cycling likely caused transient disconnects.", "override_reason": None, "created_at": now - timedelta(minutes=9)},
                    {"key": "side_antenna", "branch_type": "side", "parent_key": "main_primary", "branch_slot": 1, "transcript_index": 2, "node_text": "Check antenna clearance on new protective casing.", "override_reason": "Signal degradation remains directional, not random.", "created_at": now - timedelta(minutes=7)},
                ],
            },
        ]

        created_sessions: list[Session] = []
        for item in dataset:
            created_sessions.append(
                self._seed_single_session(
                    title=item["title"],
                    device_id=item["device_id"],
                    status=item["status"],
                    transcript_rows=item["transcripts"],
                    node_rows=item["nodes"],
                )
            )
        return created_sessions

    def rebuild_snapshots(self, session_id: int | None = None) -> list[Snapshot]:
        target_ids = [session_id] if session_id is not None else [session.id for session in self.sessions.list()]
        rebuilt: list[Snapshot] = []
        for current_session_id in target_ids:
            detail = self.get_session_detail(current_session_id)
            if detail is None:
                continue
            refreshed_at = current_timestamp()
            rebuilt.extend(
                self.snapshots.replace_for_session(
                    current_session_id,
                    node_count=len(detail.graph_nodes),
                    hash_sha256=SnapshotHasher.compute(detail.graph_nodes),
                    created_at=refreshed_at,
                )
            )
            self.sessions.touch(current_session_id, refreshed_at)
        return rebuilt

    def export_session(self, session_id: int, target_path: str | Path) -> dict[str, object]:
        detail = self.get_session_detail(session_id)
        if detail is None:
            raise ValueError("Selected session was not found.")
        payload = {
            "session": asdict(detail.session),
            "transcripts": [asdict(item) for item in detail.transcripts],
            "graph_nodes": [asdict(item) for item in detail.graph_nodes],
            "snapshots": [asdict(item) for item in detail.snapshots],
        }
        path = Path(target_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return payload

    def get_app_summary(self) -> AppSummary:
        return self.sessions.summary_counts()

    def _seed_single_session(
        self,
        title: str,
        device_id: str,
        status: str,
        transcript_rows: list[tuple[str, float, datetime]],
        node_rows: list[dict[str, object]],
    ) -> Session:
        created_at = transcript_rows[0][2].strftime("%Y-%m-%d %H:%M:%S")
        session = self.sessions.create(title, device_id, status, created_at)

        transcripts = self.transcripts.create_many(
            session.id,
            [
                TranscriptDraft(
                    text=text,
                    confidence=confidence,
                    created_at=timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                )
                for text, confidence, timestamp in transcript_rows
            ],
        )

        node_key_to_id: dict[str, int] = {}
        created_nodes: list[GraphNode] = []
        for row in node_rows:
            parent_key = row["parent_key"]
            created_node = self.graph_nodes.create_many(
                session.id,
                [
                    GraphNodeDraft(
                        transcript_id=transcripts[int(row["transcript_index"])].id,
                        parent_node_id=node_key_to_id.get(str(parent_key)) if parent_key else None,
                        branch_type=row["branch_type"],
                        branch_slot=row["branch_slot"],
                        node_text=row["node_text"],
                        override_reason=row["override_reason"],
                        created_at=row["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
                    )
                ],
            )[0]
            created_nodes.append(created_node)
            node_key_to_id[str(row["key"])] = created_node.id

        snapshot_history = [
            (created_nodes[: max(1, len(created_nodes) - 1)], created_nodes[max(0, len(created_nodes) - 2)].created_at),
            (created_nodes, created_nodes[-1].created_at),
        ]
        for snapshot_nodes, created_snapshot_at in snapshot_history:
            self.snapshots.create(
                session.id,
                node_count=len(snapshot_nodes),
                hash_sha256=SnapshotHasher.compute(snapshot_nodes),
                created_at=created_snapshot_at,
            )
        updated_session = self.sessions.touch(session.id, created_nodes[-1].created_at)
        return updated_session or session
