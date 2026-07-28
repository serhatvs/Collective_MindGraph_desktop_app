"""Boundary between transcription use cases and audio-processing adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .contracts import ConversationTranscript


@dataclass(frozen=True, slots=True)
class ProcessingRuntimeSnapshot:
    vad_provider: str | None
    asr_provider_resolved: str | None
    asr_fallback_provider: str | None
    asr_status: str | None
    asr_mock_fallback_used: bool
    cuda_available_through_torch: bool | None
    gpu_requested: bool
    gpu_loaded: bool
    faster_whisper_cuda_load_status: str | None
    gpu_fallback_happened: bool
    gpu_fallback_reason: str | None
    local_llm_enabled: bool
    llm_provider_resolved: str | None
    llm_fallback_provider: str | None
    _diagnostic_items: tuple[tuple[str, Any], ...] = field(repr=False)

    def diagnostics(self) -> dict[str, Any]:
        return dict(self._diagnostic_items)


class RecordingProcessorPort(Protocol):
    async def process_audio_path(
        self,
        audio_path: Path,
        **options: Any,
    ) -> ConversationTranscript: ...

    def runtime_status(self) -> ProcessingRuntimeSnapshot: ...
