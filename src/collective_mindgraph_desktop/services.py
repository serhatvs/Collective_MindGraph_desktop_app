"""Service layer for application workflows."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .database import Database
from .models import (
    AppSummary,
    GraphNode,
    GraphNodeDraft,
    Session,
    SessionDetail,
    Snapshot,
    Transcript,
    TranscriptAnalysisDraft,
    TranscriptAnalysisSegment,
    TranscriptDraft,
    TranscriptQualityReport,
    TranscriptSpeakerStat,
    TranscriptTopic,
)
from .repositories import (
    GraphNodeRepository,
    SessionRepository,
    SnapshotRepository,
    TranscriptAnalysisRepository,
    TranscriptRepository,
)
from .transcription import TranscriptionResult


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
        self.transcript_analyses = TranscriptAnalysisRepository(self._database)

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
            transcript_analyses=self.transcript_analyses.list_by_session(session_id),
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
            "transcript_analyses": [asdict(item) for item in detail.transcript_analyses.values()],
        }
        path = Path(target_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return payload

    def get_app_summary(self) -> AppSummary:
        return self.sessions.summary_counts()

    def ingest_transcript(
        self,
        transcript_text: str,
        session_id: int | None = None,
        device_id: str = "VOICE-MIC",
    ) -> Session:
        cleaned_text = " ".join(transcript_text.split())
        if not cleaned_text:
            raise ValueError("Transcript text is required.")

        timestamp = current_timestamp()
        session, _transcript, _primary_node = self._create_transcript_with_primary_node(
            cleaned_text=cleaned_text,
            session_id=session_id,
            device_id=device_id,
            timestamp=timestamp,
        )

        rebuilt = self.rebuild_snapshots(session.id)
        if rebuilt:
            refreshed_session = self.sessions.get(session.id)
            if refreshed_session is not None:
                return refreshed_session
        return session

    def ingest_transcription_result(
        self,
        result: TranscriptionResult,
        session_id: int | None = None,
        device_id: str = "VOICE-MIC",
    ) -> Session:
        transcript_text = self._preferred_transcript_text(result)
        timestamp = current_timestamp()
        session, transcript, primary_node = self._create_transcript_with_primary_node(
            cleaned_text=transcript_text,
            session_id=session_id,
            device_id=device_id,
            timestamp=timestamp,
        )
        analysis_side_nodes = self._build_analysis_side_nodes(
            session_id=session.id,
            parent_node=primary_node,
            result=result,
            created_at=timestamp,
        )
        if analysis_side_nodes:
            self.graph_nodes.create_many(session.id, analysis_side_nodes)
        self.transcript_analyses.upsert(
            transcript.id,
            TranscriptAnalysisDraft(
                source_provider=result.model_id,
                backend_conversation_id=result.conversation_id,
                raw_text_output=result.raw_text_output or transcript_text,
                corrected_text_output=result.corrected_text_output or transcript_text,
                summary=result.summary,
                topics=self._build_topics(result.topics),
                action_items=list(result.action_items),
                decisions=list(result.decisions),
                speaker_stats=self._build_speaker_stats(result.speaker_stats),
                segments=self._build_segments(result.segments, transcript_text),
                quality_report=self._build_quality_report(result.quality_report),
                created_at=timestamp,
                updated_at=timestamp,
            ),
        )
        self.rebuild_snapshots(session.id)
        refreshed_session = self.sessions.get(session.id)
        return refreshed_session or session

    def save_transcript_analysis_corrections(
        self,
        transcript_id: int,
        edited_segments: list[TranscriptAnalysisSegment],
    ) -> None:
        analysis = self.transcript_analyses.get(transcript_id)
        if analysis is None:
            raise ValueError("Transcript analysis was not found.")

        corrected_text_output = self._render_corrected_text_output(edited_segments)
        flat_transcript_text = self._flatten_segments_to_transcript_text(edited_segments)
        updated_at = current_timestamp()
        refreshed_speaker_stats = self._compute_speaker_stats(edited_segments)
        quality_report = analysis.quality_report
        if quality_report is not None:
            quality_report = TranscriptQualityReport(
                segment_count=len(edited_segments),
                speaker_count=len({item.speaker for item in edited_segments}),
                unresolved_segments=sum(1 for item in edited_segments if item.speaker.lower().startswith("unknown")),
                overlap_ratio=quality_report.overlap_ratio,
                avg_asr_confidence=quality_report.avg_asr_confidence,
                avg_speaker_confidence=quality_report.avg_speaker_confidence,
                word_timing_coverage=quality_report.word_timing_coverage,
                corrected_change_ratio=quality_report.corrected_change_ratio,
                topic_count=quality_report.topic_count,
                action_item_count=quality_report.action_item_count,
                decision_count=quality_report.decision_count,
                question_count=quality_report.question_count,
                summary_present=quality_report.summary_present,
                warnings=list(quality_report.warnings),
            )

        self.transcript_analyses.upsert(
            transcript_id,
            TranscriptAnalysisDraft(
                source_provider=analysis.source_provider,
                backend_conversation_id=analysis.backend_conversation_id,
                raw_text_output=analysis.raw_text_output,
                corrected_text_output=corrected_text_output,
                summary=analysis.summary,
                topics=analysis.topics,
                action_items=analysis.action_items,
                decisions=analysis.decisions,
                speaker_stats=refreshed_speaker_stats,
                segments=edited_segments,
                quality_report=quality_report,
                created_at=analysis.created_at,
                updated_at=updated_at,
            ),
        )
        self.transcripts.update_text(transcript_id, flat_transcript_text)
        self.graph_nodes.update_node_text_by_transcript(transcript_id, self._build_node_text(flat_transcript_text))
        transcript = self._find_transcript(transcript_id)
        if transcript is None:
            raise ValueError("Transcript was not found.")
        self.rebuild_snapshots(transcript.session_id)
        self.sessions.touch(transcript.session_id, updated_at)

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

    def _create_transcript_with_primary_node(
        self,
        cleaned_text: str,
        session_id: int | None,
        device_id: str,
        timestamp: str,
    ) -> tuple[Session, Transcript, GraphNode]:
        session = self.sessions.get(session_id) if session_id is not None else None
        if session is None:
            session = self.sessions.create(
                self._build_session_title(cleaned_text),
                device_id.strip() or "VOICE-MIC",
                "active",
                timestamp,
            )

        transcript = self.transcripts.create_many(
            session.id,
            [TranscriptDraft(text=cleaned_text, confidence=1.0, created_at=timestamp)],
        )[0]

        existing_nodes = self.graph_nodes.list_by_session(session.id)
        parent_node_id = existing_nodes[-1].id if existing_nodes else None
        branch_type = "main" if existing_nodes else "root"

        primary_node = self.graph_nodes.create_many(
            session.id,
            [
                GraphNodeDraft(
                    transcript_id=transcript.id,
                    parent_node_id=parent_node_id,
                    branch_type=branch_type,
                    branch_slot=None,
                    node_text=self._build_node_text(cleaned_text),
                    override_reason=None,
                    created_at=timestamp,
                )
            ],
        )[0]
        return session, transcript, primary_node

    def _find_transcript(self, transcript_id: int):
        for session in self.sessions.list():
            for transcript in self.transcripts.list_by_session(session.id):
                if transcript.id == transcript_id:
                    return transcript
        return None

    def _build_analysis_side_nodes(
        self,
        session_id: int,
        parent_node: GraphNode,
        result: TranscriptionResult,
        created_at: str,
    ) -> list[GraphNodeDraft]:
        drafts: list[GraphNodeDraft] = []

        summary_bits: list[str] = []
        if result.summary:
            summary_bits.append(f"Summary: {result.summary.strip()}")
        if result.topics:
            topic_labels = [str(item.get('label') or '').strip() for item in result.topics if str(item.get("label") or "").strip()]
            if topic_labels:
                summary_bits.append(f"Topics: {', '.join(topic_labels[:4])}")
        if summary_bits:
            drafts.append(
                GraphNodeDraft(
                    transcript_id=None,
                    parent_node_id=parent_node.id,
                    branch_type="side",
                    branch_slot=1,
                    node_text=self._build_node_text(" | ".join(summary_bits)),
                    override_reason="Derived from backend conversation analysis.",
                    created_at=created_at,
                )
            )

        insight_lines: list[str] = []
        if result.decisions:
            insight_lines.extend(f"Decision: {item}" for item in result.decisions[:3])
        if result.action_items:
            insight_lines.extend(f"Action: {item}" for item in result.action_items[:3])
        if insight_lines:
            drafts.append(
                GraphNodeDraft(
                    transcript_id=None,
                    parent_node_id=parent_node.id,
                    branch_type="side",
                    branch_slot=2,
                    node_text=self._build_node_text(" | ".join(insight_lines)),
                    override_reason="Derived from backend decisions and action items.",
                    created_at=created_at,
                )
            )

        return drafts

    @staticmethod
    def _build_session_title(transcript_text: str) -> str:
        title = transcript_text[:60].strip()
        if len(transcript_text) > 60:
            title = f"{title.rstrip('. ,;:!?')}..."
        return title or "New Voice Session"

    @staticmethod
    def _build_node_text(transcript_text: str) -> str:
        if len(transcript_text) <= 140:
            return transcript_text
        return f"{transcript_text[:137].rstrip()}..."

    @staticmethod
    def _preferred_transcript_text(result: TranscriptionResult) -> str:
        candidate = (result.text or result.corrected_text_output or "").strip()
        if candidate:
            return candidate
        return result.text.strip()

    @staticmethod
    def _build_topics(topics: list[dict[str, object]]) -> list[TranscriptTopic]:
        built: list[TranscriptTopic] = []
        for item in topics:
            built.append(
                TranscriptTopic(
                    label=str(item.get("label") or "Topic"),
                    start=float(item.get("start") or 0.0),
                    end=float(item.get("end") or 0.0),
                )
            )
        return built

    @staticmethod
    def _build_speaker_stats(speaker_stats: list[dict[str, object]]) -> list[TranscriptSpeakerStat]:
        built: list[TranscriptSpeakerStat] = []
        for item in speaker_stats:
            built.append(
                TranscriptSpeakerStat(
                    speaker=str(item.get("speaker") or "Speaker"),
                    segment_count=int(item.get("segment_count") or 0),
                    speaking_seconds=float(item.get("speaking_seconds") or 0.0),
                    overlap_segments=int(item.get("overlap_segments") or 0),
                    first_start=float(item.get("first_start") or 0.0),
                    last_end=float(item.get("last_end") or 0.0),
                )
            )
        return built

    @staticmethod
    def _build_segments(
        segments: list[dict[str, object]],
        fallback_text: str,
    ) -> list[TranscriptAnalysisSegment]:
        if not segments:
            return [
                TranscriptAnalysisSegment(
                    segment_id="segment_1",
                    start=0.0,
                    end=0.0,
                    speaker="Speaker_1",
                    raw_text=fallback_text,
                    corrected_text=fallback_text,
                    confidence=1.0,
                    speaker_confidence=1.0,
                    overlap=False,
                    notes=[],
                )
            ]
        built: list[TranscriptAnalysisSegment] = []
        for item in segments:
            notes = item.get("notes")
            built.append(
                TranscriptAnalysisSegment(
                    segment_id=str(item.get("segment_id") or f"segment_{len(built) + 1}"),
                    start=float(item.get("start") or 0.0),
                    end=float(item.get("end") or 0.0),
                    speaker=str(item.get("speaker") or "Speaker_1"),
                    raw_text=str(item.get("raw_text") or ""),
                    corrected_text=str(item.get("corrected_text") or item.get("raw_text") or ""),
                    confidence=float(item["confidence"]) if item.get("confidence") is not None else None,
                    speaker_confidence=(
                        float(item["speaker_confidence"]) if item.get("speaker_confidence") is not None else None
                    ),
                    overlap=bool(item.get("overlap") or False),
                    notes=[str(note) for note in notes] if isinstance(notes, list) else [],
                )
            )
        return built

    @staticmethod
    def _build_quality_report(payload: dict[str, object] | None) -> TranscriptQualityReport | None:
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

    @staticmethod
    def _render_corrected_text_output(segments: list[TranscriptAnalysisSegment]) -> str:
        lines: list[str] = []
        for segment in segments:
            lines.append(
                f"[{CollectiveMindGraphService._format_seconds(segment.start)} - "
                f"{CollectiveMindGraphService._format_seconds(segment.end)}] "
                f"{segment.speaker}: {segment.corrected_text}"
            )
        return "\n".join(lines)

    @staticmethod
    def _flatten_segments_to_transcript_text(segments: list[TranscriptAnalysisSegment]) -> str:
        lines = [f"{item.speaker}: {item.corrected_text}".strip() for item in segments if item.corrected_text.strip()]
        return "\n".join(lines)

    @staticmethod
    def _compute_speaker_stats(segments: list[TranscriptAnalysisSegment]) -> list[TranscriptSpeakerStat]:
        stats: dict[str, TranscriptSpeakerStat] = {}
        order: list[str] = []
        for segment in segments:
            if segment.speaker not in stats:
                stats[segment.speaker] = TranscriptSpeakerStat(
                    speaker=segment.speaker,
                    segment_count=0,
                    speaking_seconds=0.0,
                    overlap_segments=0,
                    first_start=segment.start,
                    last_end=segment.end,
                )
                order.append(segment.speaker)
            current = stats[segment.speaker]
            stats[segment.speaker] = TranscriptSpeakerStat(
                speaker=current.speaker,
                segment_count=current.segment_count + 1,
                speaking_seconds=round(current.speaking_seconds + max(0.0, segment.end - segment.start), 3),
                overlap_segments=current.overlap_segments + int(segment.overlap),
                first_start=min(current.first_start, segment.start),
                last_end=max(current.last_end, segment.end),
            )
        return [stats[speaker] for speaker in order]

    @staticmethod
    def _format_seconds(value: float) -> str:
        total_milliseconds = max(0, int(round(value * 1000)))
        minutes, remainder = divmod(total_milliseconds, 60_000)
        seconds, milliseconds = divmod(remainder, 1_000)
        return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
