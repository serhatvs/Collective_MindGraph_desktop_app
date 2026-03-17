"""Voice-command workflow primitives for the desktop UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

VoiceCommandStage = Literal["idle", "recording", "audio_ready", "transcribing", "transcript_ready", "error"]


@dataclass(frozen=True, slots=True)
class VoiceCommandState:
    stage: VoiceCommandStage
    status_label: str
    guidance_text: str
    transcript_text: str
    audio_path: str | None
    start_enabled: bool
    stop_enabled: bool
    transcribe_enabled: bool
    clear_enabled: bool


class VoiceCommandWorkflow:
    """Small state machine so the UI can be wired before audio capture exists."""

    def __init__(self) -> None:
        self._state = self._build_idle_state()

    @property
    def state(self) -> VoiceCommandState:
        return self._state

    def start_recording(self) -> VoiceCommandState:
        self._state = VoiceCommandState(
            stage="recording",
            status_label="Recording",
            guidance_text=(
                "Listening for a spoken command through the active microphone. You can stop manually, "
                "or just pause and let the recorder auto-stop after a short silence."
            ),
            transcript_text="",
            audio_path=None,
            start_enabled=False,
            stop_enabled=True,
            transcribe_enabled=False,
            clear_enabled=True,
        )
        return self._state

    def stop_recording(self, audio_path: str | None = None) -> VoiceCommandState:
        if self._state.stage != "recording" or not audio_path:
            return self._state

        return self.load_audio_file(
            audio_path,
            guidance_text=(
                "Recording is saved locally. The next step is sending this audio clip to the local "
                "transcription backend."
            ),
        )

    def load_audio_file(
        self,
        audio_path: str | None,
        *,
        guidance_text: str | None = None,
    ) -> VoiceCommandState:
        if not audio_path:
            return self._state

        self._state = VoiceCommandState(
            stage="audio_ready",
            status_label="Audio Ready",
            guidance_text=guidance_text
            or (
                "Recording is saved locally. The next step is sending this audio clip to the local "
                "transcription backend."
            ),
            transcript_text="",
            audio_path=audio_path,
            start_enabled=True,
            stop_enabled=False,
            transcribe_enabled=True,
            clear_enabled=True,
        )
        return self._state

    def transcribe(self) -> VoiceCommandState:
        if self._state.stage != "audio_ready":
            return self._state

        self._state = VoiceCommandState(
            stage="transcribing",
            status_label="Transcribing",
            guidance_text="Sending the recorded audio to the local transcription backend.",
            transcript_text="",
            audio_path=self._state.audio_path,
            start_enabled=False,
            stop_enabled=False,
            transcribe_enabled=False,
            clear_enabled=False,
        )
        return self._state

    def complete_transcription(self, transcript_text: str) -> VoiceCommandState:
        if self._state.stage not in {"transcribing", "audio_ready"}:
            return self._state

        cleaned_text = transcript_text.strip()
        self._state = VoiceCommandState(
            stage="transcript_ready",
            status_label="Transcript Ready",
            guidance_text="The local transcription backend returned transcript text for the recorded audio.",
            transcript_text=cleaned_text,
            audio_path=self._state.audio_path,
            start_enabled=True,
            stop_enabled=False,
            transcribe_enabled=False,
            clear_enabled=True,
        )
        return self._state

    def set_error(self, message: str, audio_path: str | None = None) -> VoiceCommandState:
        self._state = VoiceCommandState(
            stage="error",
            status_label="Capture Error",
            guidance_text=message,
            transcript_text="",
            audio_path=audio_path,
            start_enabled=True,
            stop_enabled=False,
            transcribe_enabled=audio_path is not None,
            clear_enabled=True,
        )
        return self._state

    def clear(self) -> VoiceCommandState:
        self._state = self._build_idle_state()
        return self._state

    @staticmethod
    def _build_idle_state() -> VoiceCommandState:
        return VoiceCommandState(
            stage="idle",
            status_label="Idle",
            guidance_text=(
                "Input starts as a spoken command. Say 'command wake' for hands-free capture, "
                "then pause briefly to auto-stop and launch local-backend transcription."
            ),
            transcript_text="",
            audio_path=None,
            start_enabled=True,
            stop_enabled=False,
            transcribe_enabled=False,
            clear_enabled=False,
        )
