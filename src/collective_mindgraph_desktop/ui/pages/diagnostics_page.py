"""Diagnostics page showing technical backend and pipeline status."""

from __future__ import annotations

from PySide6.QtCore import Qt
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
        
        # 1. Pipeline Status Card
        self.status_card = CardWidget("Technical Diagnostics")
        self.container_layout.addWidget(self.status_card)
        
        self.form = QFormLayout()
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form.setSpacing(12)
        
        self.labels = {
            "backend_url": QLabel("http://127.0.0.1:8081"),
            "asr_provider": QLabel("-"),
            "asr_backend_resolved": QLabel("-"),
            "asr_model": QLabel("-"),
            "asr_device": QLabel("-"),
            "asr_compute_type": QLabel("-"),
            "asr_language": QLabel("-"),
            "asr_runtime_profile": QLabel("-"),
            "gpu_enabled": QLabel("-"),
            "gpu_required": QLabel("-"),
            "cuda_available": QLabel("-"),
            "gpu_requested": QLabel("-"),
            "gpu_actual": QLabel("-"),
            "gpu_fallback": QLabel("-"),
            "gpu_fallback_reason": QLabel("-"),
            "vad_provider": QLabel("-"),
            "embedding_device": QLabel("-"),
            "local_llm_enabled": QLabel("-"),
            "llm_status": QLabel("WIRED BUT UNAVAILABLE"),
            "llm_endpoint": QLabel("-"),
            "extraction_mode": QLabel("HEURISTIC_FALLBACK"),
            "embedding_status": QLabel("MOCK_ONLY"),
            "embedding_path": QLabel("-"),
            "vector_count": QLabel("0"),
            "embedding_dim": QLabel("384"),
            "offline_mode": QLabel("ACTIVE (Strict Local-First)"),
            "processing_time": QLabel("-"),
            "raw_length": QLabel("-"),
            "clean_length": QLabel("-"),
        }
        for label in self.labels.values():
            label.setStyleSheet("font-family: 'Consolas', monospace; color: #264a7f;")
            
        self.form.addRow("Backend URL", self.labels["backend_url"])
        self.form.addRow("ASR Provider", self.labels["asr_provider"])
        self.form.addRow("ASR Backend Resolved", self.labels["asr_backend_resolved"])
        self.form.addRow("ASR Model", self.labels["asr_model"])
        self.form.addRow("ASR Device", self.labels["asr_device"])
        self.form.addRow("ASR Compute Type", self.labels["asr_compute_type"])
        self.form.addRow("ASR Language", self.labels["asr_language"])
        self.form.addRow("Runtime Profile", self.labels["asr_runtime_profile"])
        self.form.addRow("GPU Enabled", self.labels["gpu_enabled"])
        self.form.addRow("GPU Required", self.labels["gpu_required"])
        self.form.addRow("CUDA Available", self.labels["cuda_available"])
        self.form.addRow("GPU Requested By ASR", self.labels["gpu_requested"])
        self.form.addRow("GPU Actually Used By ASR", self.labels["gpu_actual"])
        self.form.addRow("ASR Fallback", self.labels["gpu_fallback"])
        self.form.addRow("Fallback Reason", self.labels["gpu_fallback_reason"])
        self.form.addRow("VAD Provider", self.labels["vad_provider"])
        self.form.addRow("Embedding Device", self.labels["embedding_device"])
        self.form.addRow("Security Mode", self.labels["offline_mode"])
        
        # Production Status rows
        self.labels["llm_status"].setStyleSheet("color: #9a3412; font-weight: bold;")
        self.form.addRow("Local AI Layer (LLM)", self.labels["llm_status"])
        self.form.addRow("Local LLM Enabled", self.labels["local_llm_enabled"])
        self.form.addRow("LLM Endpoint", self.labels["llm_endpoint"])

        self.labels["extraction_mode"].setStyleSheet("color: #ca8a04; font-weight: bold;")
        self.form.addRow("Extraction Mode", self.labels["extraction_mode"])
        
        self.labels["embedding_status"].setStyleSheet("color: #ca8a04; font-weight: bold;")
        self.form.addRow("Semantic Memory", self.labels["embedding_status"])
        self.form.addRow("Model Path", self.labels["embedding_path"])
        self.form.addRow("Vector Index Size", self.labels["vector_count"])
        self.form.addRow("Vector Dimension", self.labels["embedding_dim"])
        
        self.labels["graph_status"] = QLabel("ACTIVE (V2 Graph Nodes/Edges)")
        self.labels["graph_status"].setStyleSheet("color: #166534; font-weight: bold;")
        self.form.addRow("Graph Reasoning", self.labels["graph_status"])
        
        self.labels["ask_memory_evidence"] = QLabel("ACTIVE")
        self.labels["ask_memory_evidence"].setStyleSheet("color: #166534; font-weight: bold;")
        self.form.addRow("Ask Memory (Evidence-only)", self.labels["ask_memory_evidence"])

        self.labels["ask_memory_llm"] = QLabel("FALLBACK_TO_EVIDENCE_ONLY")
        self.labels["ask_memory_llm"].setStyleSheet("color: #ca8a04; font-weight: bold;")
        self.form.addRow("Ask Memory (LLM-assisted)", self.labels["ask_memory_llm"])

        self.labels["hybrid_status"] = QLabel("ACTIVE (Keyword + Graph)")
        self.labels["hybrid_status"].setStyleSheet("color: #166534; font-weight: bold;")
        self.form.addRow("Hybrid Query", self.labels["hybrid_status"])

        self.form.addRow("Diarization", QLabel("NOT ENABLED (Roadmap)"))
        self.form.addRow("Raw Audio Trace Count", self.labels["raw_length"])
        self.form.addRow("Memory Cache Size", self.labels["clean_length"])
        self.form.addRow("Analysis Duration", self.labels["processing_time"])
        
        self.status_card.body_layout.addLayout(self.form)
        
        # 2. Safety Card
        self.safety_card = CardWidget("Offline Safety Guards")
        self.container_layout.addWidget(self.safety_card)
        
        safety_text = QLabel(
            "✓ External cloud AI providers (Deepgram, Bedrock) are REMOVED.\n"
            "✓ Mandatory URL validation restricts API calls to local/private network ranges.\n"
            "✓ Local model verification prevents silent auto-downloads."
        )
        safety_text.setStyleSheet("color: #19693d; font-weight: 600;")
        self.safety_card.body_layout.addWidget(safety_text)
        
        self.container_layout.addStretch(1)

    def set_app_summary(self, vector_count: int, embedding_dim: int, provider_name: str, model_path: str = "") -> None:
        self.labels["vector_count"].setText(str(vector_count))
        self.labels["embedding_dim"].setText(str(embedding_dim))
        self.labels["embedding_path"].setText(model_path or "N/A (Mock)")
        
        if provider_name == "Mock":
            self.labels["embedding_status"].setText("MOCK_ONLY")
            self.labels["embedding_status"].setStyleSheet("color: #ca8a04; font-weight: bold;")
            self.labels["hybrid_status"].setText("ACTIVE (Keyword + Graph)")
        elif provider_name == "SentenceTransformer":
            self.labels["embedding_status"].setText("REAL_ACTIVE")
            self.labels["embedding_status"].setStyleSheet("color: #166534; font-weight: bold;")
            self.labels["hybrid_status"].setText("ACTIVE (Keyword + Vector + Graph)")
        else:
            self.labels["embedding_status"].setText("MISSING_MODEL")
            self.labels["embedding_status"].setStyleSheet("color: #9a3412; font-weight: bold;")
            self.labels["hybrid_status"].setText("ACTIVE (Keyword + Graph)")

    def set_backend_health(self, health: BackendHealthStatus | None) -> None:
        if health is None:
            self.labels["asr_provider"].setText("-")
            self.labels["asr_backend_resolved"].setText("-")
            self.labels["asr_model"].setText("-")
            self.labels["asr_device"].setText("-")
            self.labels["asr_compute_type"].setText("-")
            self.labels["asr_language"].setText("-")
            self.labels["asr_runtime_profile"].setText("-")
            self.labels["gpu_enabled"].setText("-")
            self.labels["gpu_required"].setText("-")
            self.labels["cuda_available"].setText("-")
            self.labels["gpu_requested"].setText("-")
            self.labels["gpu_actual"].setText("-")
            self.labels["gpu_fallback"].setText("-")
            self.labels["gpu_fallback_reason"].setText("-")
            self.labels["vad_provider"].setText("-")
            self.labels["embedding_device"].setText("-")
            self.labels["local_llm_enabled"].setText("-")
            return

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

    def set_detail(self, detail: SessionDetail | None) -> None:
        if not detail or not detail.transcripts:
            return

        last_id = detail.transcripts[-1].id
        analysis = detail.transcript_analyses.get(last_id)
        if not analysis:
            return

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


def _bool_text(value: bool | None) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unknown"
