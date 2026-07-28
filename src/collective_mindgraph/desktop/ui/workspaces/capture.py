"""Live and file-based recording workspace."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...contracts import MeetingSummary, MeetingTranscript, TranscriptionPreferences
from ...engine_client import EngineClient, EngineClientError, is_engine_offline_error
from ...language_catalog import LanguageCatalog
from ...live_capture_client import LiveCaptureClient
from ...preferences import DesktopPreferenceStore
from ..job_presenter import JobPresenter
from ..state_panel import StatePanel


class CaptureWorkspace(QWidget):
    meeting_ready = Signal(int)

    def __init__(
        self,
        client: EngineClient,
        catalog: LanguageCatalog,
        presenter: JobPresenter,
        preferences: DesktopPreferenceStore | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._catalog = catalog
        self._presenter = presenter
        self._preferences = preferences or DesktopPreferenceStore()
        self._selected_file: Path | None = None
        self._live = LiveCaptureClient(client.settings.base_url, self)
        self._live.partial_transcript.connect(self._partial_transcript)
        self._live.progress_changed.connect(self._live_progress)
        self._live.finalized.connect(self._live_finalized)
        self._live.fallback_ready.connect(self._live_fallback)
        self._live.error_occurred.connect(self._show_error)
        self._live.recording_changed.connect(lambda _active: self.retranslate())
        self._live_meeting_id: int | None = None
        self._last_failed_job_id: str | None = None
        self._last_failed_meeting_id: int | None = None
        self._last_failed_cleanup_path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        self._title = QLabel()
        self._title.setObjectName("WorkspaceTitle")
        layout.addWidget(self._title)

        form = QFormLayout()
        self._meeting_name = QLineEdit()
        form.addRow("", self._meeting_name)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self._record = QPushButton()
        self._record.setObjectName("Primary")
        self._record.clicked.connect(self._toggle_recording)
        self._choose_file = QPushButton()
        self._choose_file.clicked.connect(self.choose_file)
        self._process = QPushButton()
        self._process.clicked.connect(
            lambda: self.process_path(self._selected_file) if self._selected_file else None
        )
        actions.addWidget(self._record)
        actions.addWidget(self._choose_file)
        actions.addWidget(self._process)
        actions.addStretch()
        layout.addLayout(actions)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.hide()
        layout.addWidget(self._progress)

        self._advanced = QGroupBox()
        self._advanced.setCheckable(True)
        self._advanced.setChecked(False)
        advanced_form = QFormLayout(self._advanced)
        self._language = QComboBox()
        self._quality = QComboBox()
        self._glossary = QLineEdit()
        self._language_label = QLabel()
        self._quality_label = QLabel()
        self._glossary_label = QLabel()
        advanced_form.addRow(self._language_label, self._language)
        advanced_form.addRow(self._quality_label, self._quality)
        advanced_form.addRow(self._glossary_label, self._glossary)
        layout.addWidget(self._advanced)

        self._transcript_label = QLabel()
        self._transcript_label.setStyleSheet("font-weight: 700")
        self._transcript = QPlainTextEdit()
        self._transcript.setReadOnly(True)
        layout.addWidget(self._transcript_label)
        layout.addWidget(self._transcript, 1)
        self.state_panel = StatePanel(catalog)
        self.state_panel.retry_requested.connect(self._retry_last)
        layout.addWidget(self.state_panel)
        catalog.language_changed.connect(self.retranslate)
        self.retranslate()

    def choose_file(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            self._catalog.text("capture.choose_file"),
            "",
            self._catalog.text("capture.file_filter"),
        )
        if not selected:
            return
        self._selected_file = Path(selected)
        self._process.setText(self._selected_file.name)

    def process_path(
        self,
        source: Path | None,
        *,
        meeting_id: int | None = None,
        cleanup_source_on_success: bool = False,
    ) -> None:
        if source is None:
            return
        self._last_failed_job_id = None
        self._last_failed_meeting_id = meeting_id if cleanup_source_on_success else None
        self._last_failed_cleanup_path = source if cleanup_source_on_success else None
        title = self._meeting_name.text().strip() or source.stem
        preferences = TranscriptionPreferences(
            language=self._language.currentData(),
            quality_mode=self._quality.currentData(),
            glossary=tuple(
                part.strip() for part in self._glossary.text().split(",") if part.strip()
            ),
        )
        self._progress.show()
        self.state_panel.show_state("loading", self._catalog.text("capture.processing"))
        self._set_actions_enabled(False)

        def operation():
            selected_meeting_id = meeting_id
            if selected_meeting_id is None:
                selected_meeting_id = self._client.create_meeting(title).id
            queued = self._client.ingest_recording(
                selected_meeting_id,
                source,
                preferences,
            )
            completed = self._client.wait_for_job(queued.id)
            if completed.status != "succeeded":
                raise EngineClientError(
                    code="recording_processing_failed",
                    message=completed.error or completed.message,
                    retryable=completed.retryable,
                    details={
                        "job_id": completed.id,
                        "meeting_id": selected_meeting_id,
                    },
                )
            transcript = self._client.get_transcript(selected_meeting_id)
            cleanup_error = _remove_uploaded_spool(source) if cleanup_source_on_success else None
            return selected_meeting_id, transcript, cleanup_error

        self._presenter.submit(
            operation,
            succeeded=self._processed,
            failed=self._processing_failed,
        )

    def _toggle_recording(self) -> None:
        if self._live.is_recording:
            self._live.stop()
            return
        title = self._meeting_name.text().strip() or self._catalog.text("capture.untitled_meeting")
        self._set_actions_enabled(False)
        self._presenter.submit(
            lambda: self._client.create_meeting(
                title,
                self._preferences.audio_device_id,
            ),
            succeeded=self._start_live,
            failed=self._processing_failed,
        )

    def _start_live(self, value: object) -> None:
        assert isinstance(value, MeetingSummary)
        meeting_id = value.id
        self._live_meeting_id = meeting_id
        preferences = TranscriptionPreferences(
            language=self._language.currentData(),
            quality_mode=self._quality.currentData(),
            glossary=tuple(
                part.strip() for part in self._glossary.text().split(",") if part.strip()
            ),
        )
        try:
            self._live.start(
                meeting_id,
                device_id=self._preferences.audio_device_id,
                preferences=preferences,
            )
            self._set_actions_enabled(True)
        except Exception as exc:
            self._set_actions_enabled(True)
            self._show_error(str(exc))

    def _live_progress(self, progress: int, stage: str) -> None:
        self._progress.setRange(0, 100)
        self._progress.setValue(progress)
        self._progress.show()
        self.state_panel.show_state("loading", stage)

    def _partial_transcript(self, transcript: str) -> None:
        self._transcript.setPlainText(transcript)

    def _live_finalized(self, transcript: str) -> None:
        self._progress.hide()
        self._set_actions_enabled(True)
        self.state_panel.clear()
        self._transcript.setPlainText(transcript)
        if self._live_meeting_id is not None:
            self.meeting_ready.emit(self._live_meeting_id)

    def _live_fallback(self, path: str) -> None:
        if self._live_meeting_id is None:
            self._show_error("Live capture fallback has no meeting.")
            return
        self.process_path(
            Path(path),
            meeting_id=self._live_meeting_id,
            cleanup_source_on_success=True,
        )

    def _processed(self, value: object) -> None:
        meeting_id, transcript, cleanup_error = value
        assert isinstance(transcript, MeetingTranscript)
        self._progress.hide()
        self._set_actions_enabled(True)
        self._last_failed_job_id = None
        self._last_failed_meeting_id = None
        self._last_failed_cleanup_path = None
        if cleanup_error:
            self._show_error(str(cleanup_error))
        else:
            self.state_panel.clear()
        self._transcript.setPlainText(transcript.corrected_text or transcript.raw_text)
        self.meeting_ready.emit(int(meeting_id))

    def _processing_failed(self, error: Exception) -> None:
        self._progress.hide()
        self._set_actions_enabled(True)
        if isinstance(error, EngineClientError) and error.details:
            job_id = error.details.get("job_id")
            meeting_id = error.details.get("meeting_id")
            self._last_failed_job_id = str(job_id) if job_id else None
            self._last_failed_meeting_id = int(meeting_id) if meeting_id is not None else None
        self._show_error(str(error), offline=is_engine_offline_error(error))

    def _retry_last(self) -> None:
        if self._last_failed_job_id is None or self._last_failed_meeting_id is None:
            if (
                self._last_failed_cleanup_path is not None
                and self._last_failed_meeting_id is not None
            ):
                self.process_path(
                    self._last_failed_cleanup_path,
                    meeting_id=self._last_failed_meeting_id,
                    cleanup_source_on_success=True,
                )
                return
            if self._selected_file is not None:
                self.process_path(self._selected_file)
            return
        job_id = self._last_failed_job_id
        meeting_id = self._last_failed_meeting_id
        cleanup_path = self._last_failed_cleanup_path
        self._progress.show()
        self._set_actions_enabled(False)

        def operation():
            queued = self._client.retry_job(job_id)
            completed = self._client.wait_for_job(queued.id)
            if completed.status != "succeeded":
                raise EngineClientError(
                    "recording_retry_failed",
                    completed.error or completed.message,
                    retryable=completed.retryable,
                    details={"job_id": completed.id, "meeting_id": meeting_id},
                )
            cleanup_error = (
                _remove_uploaded_spool(cleanup_path) if cleanup_path is not None else None
            )
            return meeting_id, self._client.get_transcript(meeting_id), cleanup_error

        self._presenter.submit(
            operation,
            succeeded=self._processed,
            failed=self._processing_failed,
        )

    def _show_error(self, detail: str, *, offline: bool = False) -> None:
        self.state_panel.show_state("offline" if offline else "error", detail)

    def _set_actions_enabled(self, enabled: bool) -> None:
        self._record.setEnabled(enabled)
        self._choose_file.setEnabled(enabled)
        self._process.setEnabled(enabled)

    def retranslate(self) -> None:
        tr = self._catalog.text
        self._title.setText(tr("capture.title"))
        self._meeting_name.setPlaceholderText(tr("capture.meeting_name"))
        record_key = "capture.stop" if self._live.is_recording else "capture.start"
        self._record.setText(tr(record_key))
        self._choose_file.setText(tr("capture.choose_file"))
        if self._selected_file is None:
            self._process.setText(tr("capture.choose_file"))
        self._advanced.setTitle(tr("capture.advanced"))
        self._language_label.setText(tr("capture.language"))
        self._quality_label.setText(tr("capture.quality"))
        self._glossary_label.setText(tr("capture.glossary"))
        _replace_options(
            self._language,
            (
                (tr("language.auto"), None),
                (tr("language.turkish"), "tr"),
                (tr("language.english"), "en"),
            ),
        )
        _replace_options(
            self._quality,
            (
                (tr("quality.balanced"), "balanced"),
                (tr("quality.maximum"), "max_quality"),
            ),
        )
        self._transcript_label.setText(tr("capture.transcript"))


def _remove_uploaded_spool(path: Path) -> str | None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return "The recording was processed, but its temporary capture file could not be removed."
    return None


def _replace_options(
    combo: QComboBox,
    options: tuple[tuple[str, object], ...],
) -> None:
    current = combo.currentData()
    combo.clear()
    for label, value in options:
        combo.addItem(label, value)
    index = combo.findData(current)
    combo.setCurrentIndex(index if index >= 0 else 0)
