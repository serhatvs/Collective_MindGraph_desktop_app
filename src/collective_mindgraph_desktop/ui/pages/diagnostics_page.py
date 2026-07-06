"""Diagnostics page showing technical backend and pipeline status."""

from __future__ import annotations

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    QScrollArea,
)

from ...models import SessionDetail, TranscriptAnalysis
from ...transcription import BackendHealthStatus
from ..widgets import CardWidget


class DiagnosticsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        layout.addWidget(scroll)
        
        container = QWidget()
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setContentsMargins(24, 24, 24, 24)
        self.container_layout.setSpacing(24)
        scroll.setWidget(container)

        self.intro_card = CardWidget("How to Read Diagnostics")
        self.container_layout.addWidget(self.intro_card)
        self.intro_card.body_layout.addWidget(self._helper_label(
            "Diagnostics shows current runtime readiness for the local demo environment.\n\n"
            "Some values are live backend checks, while others are selected-session or local "
            "configuration indicators. A fallback status is not always an error; it often means "
            "the app is using the safe offline/evidence-only path. Empty or unavailable values "
            "usually mean a check has not run yet, the optional provider is unavailable, or no "
            "session-specific analysis is selected."
        ))
        
        # 1. Pipeline Status Card
        self.status_card = CardWidget("Technical Diagnostics")
        self.container_layout.addWidget(self.status_card)
        self.last_refreshed_label = self._source_hint_label("Last refreshed: not yet")
        self.status_card.body_layout.addWidget(self.last_refreshed_label)
        self.backend_state_label = self._helper_label(
            "Backend check: not yet checked. The local backend may be started separately for "
            "runtime diagnostics; stored memory data is not changed by this check."
        )
        self.status_card.body_layout.addWidget(self.backend_state_label)
        self.session_state_label = self._helper_label(
            "Selected session: no selected session. Select a session to see session-specific "
            "diagnostics; global runtime checks can still be useful without one."
        )
        self.status_card.body_layout.addWidget(self.session_state_label)
        self.status_card.body_layout.addWidget(self._helper_label(
            "Backend values show whether the local backend is reachable. ASR, GPU, and VAD "
            "rows are runtime capability checks only; they do not validate meeting-room "
            "transcription quality. Status values use ACTIVE, DISABLED, OPTIONAL, ROADMAP, and "
            "NOT IMPLEMENTED. Local LLM support is optional, and evidence-only Ask Memory can "
            "work without it. LLM-assisted Ask Memory is guarded by fallback behavior. "
            "Diarization is not implemented here, with no speaker separation claim."
        ))
        
        self.form = QFormLayout()
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form.setSpacing(12)
        
        self.labels = {
            "backend_url": QLabel("http://127.0.0.1:8081"),
            "asr_provider": QLabel("not yet checked"),
            "asr_backend_resolved": QLabel("not yet checked"),
            "asr_model": QLabel("not yet checked"),
            "asr_device": QLabel("not yet checked"),
            "asr_compute_type": QLabel("not yet checked"),
            "asr_language": QLabel("not yet checked"),
            "asr_runtime_profile": QLabel("not yet checked"),
            "gpu_enabled": QLabel("not yet checked"),
            "gpu_required": QLabel("not yet checked"),
            "cuda_available": QLabel("not yet checked"),
            "gpu_requested": QLabel("not yet checked"),
            "gpu_actual": QLabel("not yet checked"),
            "gpu_fallback": QLabel("not yet checked"),
            "gpu_fallback_reason": QLabel("not yet checked"),
            "vad_provider": QLabel("not yet checked"),
            "embedding_device": QLabel("not yet checked"),
            "local_llm_enabled": QLabel("not yet checked"),
            "llm_status": QLabel("OPTIONAL / DISABLED"),
            "llm_endpoint": QLabel("provider not configured"),
            "extraction_mode": QLabel("HEURISTIC_FALLBACK"),
            "embedding_status": QLabel("DISABLED (mock embeddings only)"),
            "embedding_path": QLabel("provider not configured"),
            "vector_count": QLabel("0"),
            "embedding_dim": QLabel("384"),
            "offline_mode": QLabel("ACTIVE (Strict Local-First)"),
            "processing_time": QLabel("no selected session"),
            "raw_length": QLabel("no selected session"),
            "clean_length": QLabel("no selected session"),
        }
        for label in self.labels.values():
            label.setStyleSheet("font-family: 'Consolas', monospace; color: #264a7f;")
            
        self._add_row("Backend URL", self.labels["backend_url"], "Local configuration indicator")
        self._add_row("ASR Provider", self.labels["asr_provider"], "Live backend check")
        self._add_row("ASR Backend Resolved", self.labels["asr_backend_resolved"], "Live backend check")
        self._add_row("ASR Model", self.labels["asr_model"], "Live backend check")
        self._add_row("ASR Device", self.labels["asr_device"], "Runtime capability check")
        self._add_row("ASR Compute Type", self.labels["asr_compute_type"], "Runtime capability check")
        self._add_row("ASR Language", self.labels["asr_language"], "Live backend check")
        self._add_row("Runtime Profile", self.labels["asr_runtime_profile"], "Local configuration indicator")
        self._add_row("GPU Enabled", self.labels["gpu_enabled"], "Local configuration indicator")
        self._add_row("GPU Required", self.labels["gpu_required"], "Local configuration indicator")
        self._add_row("CUDA Available", self.labels["cuda_available"], "Runtime capability check")
        self._add_row("GPU Requested By ASR", self.labels["gpu_requested"], "Runtime capability check")
        self._add_row("GPU Actually Used By ASR", self.labels["gpu_actual"], "Runtime capability check")
        self._add_row("ASR Fallback", self.labels["gpu_fallback"], "Runtime capability check")
        self._add_row("Fallback Reason", self.labels["gpu_fallback_reason"], "Runtime capability check")
        self._add_row("VAD Provider", self.labels["vad_provider"], "Runtime capability check")
        self._add_row("Embedding Device", self.labels["embedding_device"], "Live backend check")
        self._add_row("Security Mode", self.labels["offline_mode"], "Safety posture indicator")
        
        # Production Status rows
        self.labels["llm_status"].setStyleSheet("color: #9a3412; font-weight: bold;")
        self._add_row("Local AI Layer (LLM)", self.labels["llm_status"], "Optional provider status")
        self._add_row("Local LLM Enabled", self.labels["local_llm_enabled"], "Optional provider status")
        self._add_row("LLM Endpoint", self.labels["llm_endpoint"], "Local configuration indicator")

        self.labels["extraction_mode"].setStyleSheet("color: #ca8a04; font-weight: bold;")
        self._add_row("Extraction Mode", self.labels["extraction_mode"], "Selected-session indicator")
        
        self.labels["embedding_status"].setStyleSheet("color: #ca8a04; font-weight: bold;")
        self._add_row("Semantic Memory", self.labels["embedding_status"], "Local configuration indicator")
        self._add_row("Model Path", self.labels["embedding_path"], "Local configuration indicator")
        self._add_row("Vector Index Size", self.labels["vector_count"], "Local configuration indicator")
        self._add_row("Vector Dimension", self.labels["embedding_dim"], "Local configuration indicator")
        
        self.labels["graph_status"] = QLabel("ACTIVE (V2 graph persistence)")
        self.labels["graph_status"].setStyleSheet("color: #166534; font-weight: bold;")
        self._add_row("Graph Reasoning", self.labels["graph_status"], "Persistence-backed status")

        self.labels["ask_memory_evidence"] = QLabel("ACTIVE (evidence-only)")
        self.labels["ask_memory_evidence"].setStyleSheet("color: #166534; font-weight: bold;")
        self._add_row("Ask Memory (Evidence-only)", self.labels["ask_memory_evidence"], "Evidence path status")

        self.labels["ask_memory_llm"] = QLabel("FALLBACK_TO_EVIDENCE_ONLY")
        self.labels["ask_memory_llm"].setStyleSheet("color: #ca8a04; font-weight: bold;")
        self._add_row("Ask Memory (LLM-assisted)", self.labels["ask_memory_llm"], "Optional provider status")

        self.labels["hybrid_status"] = QLabel("ACTIVE (keyword + graph)")
        self.labels["hybrid_status"].setStyleSheet("color: #166534; font-weight: bold;")
        self._add_row("Hybrid Query", self.labels["hybrid_status"], "Configured retrieval status")

        self.labels["diarization_status"] = QLabel("NOT IMPLEMENTED / ROADMAP")
        self.labels["diarization_status"].setStyleSheet("color: #9a3412; font-weight: bold;")
        self._add_row("Diarization", self.labels["diarization_status"], "Roadmap/static status")
        self._add_row("Raw Audio Trace Count", self.labels["raw_length"], "Selected-session indicator")
        self._add_row("Memory Cache Size", self.labels["clean_length"], "Selected-session indicator")
        self._add_row("Analysis Duration", self.labels["processing_time"], "Selected-session indicator")
        
        self.status_card.body_layout.addLayout(self.form)
        
        # 2. Safety Card
        self.safety_card = CardWidget("Offline Safety Guards")
        self.container_layout.addWidget(self.safety_card)
        
        safety_text = QLabel(
            "OK - External cloud AI providers (Deepgram, Bedrock) are removed.\n"
            "OK - URL validation restricts API calls to local/private network ranges.\n"
            "OK - Local model verification prevents silent auto-downloads."
        )
        safety_text.setStyleSheet("color: #19693d; font-weight: 600;")
        self.safety_card.body_layout.addWidget(safety_text)
        self.safety_card.body_layout.addWidget(self._helper_label(
            "These guards describe the app's local-first, offline-ready safety posture for demo "
            "readiness. They are not a production security certification or installer readiness claim."
        ))
        
        self.container_layout.addStretch(1)

    def _add_row(self, title: str, value_label: QLabel, hint_text: str) -> None:
        self.form.addRow(title, self._field_with_hint(value_label, hint_text))

    def _field_with_hint(self, value_label: QLabel, hint_text: str) -> QWidget:
        field = QWidget()
        layout = QVBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(value_label)
        layout.addWidget(self._source_hint_label(hint_text))
        return field

    @staticmethod
    def _source_hint_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color: #66788a; font-size: 9pt;")
        return label

    @staticmethod
    def _helper_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("color: #66788a; line-height: 1.4;")
        return label

    def set_app_summary(self, vector_count: int, embedding_dim: int, provider_name: str, model_path: str = "") -> None:
        self.labels["vector_count"].setText(str(vector_count))
        self.labels["embedding_dim"].setText(str(embedding_dim))
        self.labels["embedding_path"].setText(model_path or "N/A (Mock)")
        
        if provider_name == "Mock":
            self.labels["embedding_status"].setText("DISABLED (mock embeddings only)")
            self.labels["embedding_status"].setStyleSheet("color: #ca8a04; font-weight: bold;")
            self.labels["hybrid_status"].setText("ACTIVE (keyword + graph)")
        elif provider_name == "SentenceTransformer":
            self.labels["embedding_status"].setText("ACTIVE (local embeddings)")
            self.labels["embedding_status"].setStyleSheet("color: #166534; font-weight: bold;")
            self.labels["hybrid_status"].setText("ACTIVE (keyword + vector + graph)")
        else:
            self.labels["embedding_status"].setText("DISABLED (embedding model unavailable)")
            self.labels["embedding_status"].setStyleSheet("color: #9a3412; font-weight: bold;")
            self.labels["hybrid_status"].setText("ACTIVE (keyword + graph)")

    def set_backend_health(self, health: BackendHealthStatus | None) -> None:
        self._mark_last_refreshed()
        if health is None:
            self.backend_state_label.setText(
                "Backend check: backend not reachable. The local backend may not be running. "
                "Start the backend and refresh Diagnostics. This does not change stored memory data."
            )
            self.labels["asr_provider"].setText("unavailable")
            self.labels["asr_backend_resolved"].setText("unavailable")
            self.labels["asr_model"].setText("unavailable")
            self.labels["asr_device"].setText("unavailable")
            self.labels["asr_compute_type"].setText("unavailable")
            self.labels["asr_language"].setText("unavailable")
            self.labels["asr_runtime_profile"].setText("unavailable")
            self.labels["gpu_enabled"].setText("unavailable")
            self.labels["gpu_required"].setText("unavailable")
            self.labels["cuda_available"].setText("unavailable")
            self.labels["gpu_requested"].setText("unavailable")
            self.labels["gpu_actual"].setText("unavailable")
            self.labels["gpu_fallback"].setText("unavailable")
            self.labels["gpu_fallback_reason"].setText("backend not reachable")
            self.labels["vad_provider"].setText("unavailable")
            self.labels["embedding_device"].setText("unavailable")
            self.labels["local_llm_enabled"].setText("optional provider unavailable")
            return

        self.backend_state_label.setText(
            "Backend check: live backend check completed. Unavailable optional providers can still "
            "use fallback paths for demo readiness."
        )
        self.labels["asr_provider"].setText(health.asr_provider)
        self.labels["asr_backend_resolved"].setText(health.asr_provider_resolved or "-")
        self.labels["asr_model"].setText(health.asr_model_name or "-")
        self.labels["asr_device"].setText(health.asr_device or "-")
        self.labels["asr_compute_type"].setText(health.asr_compute_type or "-")
        self.labels["asr_language"].setText(health.asr_language or "-")
        self.labels["asr_runtime_profile"].setText(health.asr_runtime_profile or "-")
        self.labels["gpu_enabled"].setText(_bool_text(health.gpu_enabled))
        self.labels["gpu_required"].setText(_bool_text(health.gpu_required))
        self.labels["cuda_available"].setText(_bool_text(health.cuda_available_through_torch))
        self.labels["gpu_requested"].setText(_bool_text(health.gpu_requested))
        self.labels["gpu_actual"].setText(_bool_text(health.gpu_actually_used_by_asr))
        fallback_parts = []
        if health.asr_fallback_provider:
            fallback_parts.append(f"provider={health.asr_fallback_provider}")
        if health.gpu_fallback_happened is not None:
            fallback_parts.append(f"gpu={_bool_text(health.gpu_fallback_happened)}")
        self.labels["gpu_fallback"].setText(", ".join(fallback_parts) or "none")
        self.labels["gpu_fallback_reason"].setText(health.gpu_fallback_reason or "-")
        self.labels["vad_provider"].setText(health.vad_provider)
        self.labels["embedding_device"].setText(health.embedding_device or "-")
        self.labels["local_llm_enabled"].setText(_bool_text(health.local_llm_enabled))

        if health.gpu_actually_used_by_asr:
            self.labels["gpu_actual"].setStyleSheet("color: #166534; font-weight: bold;")
        elif health.gpu_requested:
            self.labels["gpu_actual"].setStyleSheet("color: #9a3412; font-weight: bold;")
        else:
            self.labels["gpu_actual"].setStyleSheet("font-family: 'Consolas', monospace; color: #264a7f;")

    def _mark_last_refreshed(self) -> None:
        refreshed_at = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.last_refreshed_label.setText(f"Last refreshed: {refreshed_at}")

    def set_detail(self, detail: SessionDetail | None) -> None:
        if not detail or not detail.transcripts:
            self._clear_session_detail()
            return

        last_id = detail.transcripts[-1].id
        analysis = detail.transcript_analyses.get(last_id)
        if not analysis:
            self._clear_session_detail()
            return

        self.session_state_label.setText(
            "Selected session: session-specific diagnostics loaded from the selected transcript analysis."
        )
        self.labels["asr_provider"].setText(analysis.source_provider)
        self.labels["llm_endpoint"].setText(analysis.metadata.get("llm_endpoint", "-"))
        
        # LLM / Extraction Status from metadata
        source = analysis.metadata.get("extraction_source", "unknown").upper()
        self.labels["extraction_mode"].setText(source)
        if source == "LOCAL_LLM":
            self.labels["extraction_mode"].setStyleSheet("color: #166534; font-weight: bold;")
            self.labels["llm_status"].setText("ACTIVE")
            self.labels["llm_status"].setStyleSheet("color: #166534; font-weight: bold;")
            self.labels["ask_memory_llm"].setText("ACTIVE")
            self.labels["ask_memory_llm"].setStyleSheet("color: #166534; font-weight: bold;")
        else:
            status_text = "DISABLED / FALLBACK ONLY"
            self.labels["extraction_mode"].setText(source or "HEURISTIC_FALLBACK")
            self.labels["extraction_mode"].setStyleSheet("color: #ca8a04; font-weight: bold;")
            self.labels["llm_status"].setText(status_text)
            self.labels["llm_status"].setToolTip("Local LLM support is implemented, but currently disabled/unavailable. The system is running in stable evidence-only and heuristic fallback mode.")
            self.labels["llm_status"].setStyleSheet("color: #ca8a04; font-weight: bold;")
            self.labels["ask_memory_llm"].setText("FALLBACK_TO_EVIDENCE_ONLY")
            self.labels["ask_memory_llm"].setStyleSheet("color: #ca8a04; font-weight: bold;")

        self.labels["raw_length"].setText(str(len(analysis.raw_text_output)))
        self.labels["clean_length"].setText(str(len(analysis.corrected_text_output)))
        self.labels["processing_time"].setText(f"{analysis.metadata.get('processing_time_seconds', '-')}s")

    def _clear_session_detail(self) -> None:
        self.labels["llm_endpoint"].setText("-")
        self.labels["extraction_mode"].setText("NO_SESSION_ANALYSIS")
        self.labels["extraction_mode"].setStyleSheet("color: #64748b; font-weight: bold;")
        self.labels["llm_status"].setText("NO_SESSION_ANALYSIS")
        self.labels["llm_status"].setToolTip("")
        self.labels["llm_status"].setStyleSheet("color: #64748b; font-weight: bold;")
        self.labels["ask_memory_llm"].setText("FALLBACK_TO_EVIDENCE_ONLY")
        self.labels["ask_memory_llm"].setStyleSheet("color: #ca8a04; font-weight: bold;")
        self.labels["raw_length"].setText("-")
        self.labels["clean_length"].setText("-")
        self.labels["processing_time"].setText("-")


def _bool_text(value: bool | None) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unknown"
