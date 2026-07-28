"""Desktop and engine settings workspace."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...audio_capture import list_audio_inputs
from ...contracts import EngineHealth, EnginePreferencesSnapshot
from ...engine_client import EngineClient, is_engine_offline_error
from ...language_catalog import LanguageCatalog
from ...preferences import DesktopPreferenceStore
from ..job_presenter import JobPresenter
from ..state_panel import StatePanel


class SettingsWorkspace(QWidget):
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
        self._health: EngineHealth | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        self._title = QLabel()
        self._title.setObjectName("WorkspaceTitle")
        layout.addWidget(self._title)
        self._tabs = QTabWidget()

        language_page = QWidget()
        language_form = QFormLayout(language_page)
        self._ui_language = QComboBox()
        self._ui_language.currentIndexChanged.connect(self._language_changed)
        self._language_note = QLabel()
        self._language_note.setObjectName("Muted")
        language_form.addRow("", self._ui_language)
        language_form.addRow("", self._language_note)
        self._tabs.addTab(language_page, "")

        audio_page = QWidget()
        audio_form = QFormLayout(audio_page)
        self._audio_device = QComboBox()
        self._audio_input_label = QLabel()
        audio_form.addRow(self._audio_input_label, self._audio_device)
        self._tabs.addTab(audio_page, "")

        transcription_page = QWidget()
        transcription_form = QFormLayout(transcription_page)
        self._quality = QComboBox()
        self._asr_provider = QComboBox()
        self._asr_model = QLineEdit()
        self._quality_label = QLabel()
        self._asr_label = QLabel()
        self._asr_model_label = QLabel()
        transcription_form.addRow(self._quality_label, self._quality)
        transcription_form.addRow(self._asr_label, self._asr_provider)
        transcription_form.addRow(self._asr_model_label, self._asr_model)
        self._tabs.addTab(transcription_page, "")

        ai_page = QWidget()
        ai_form = QFormLayout(ai_page)
        self._embedding = QComboBox()
        self._language_model = QComboBox()
        self._embedding_label = QLabel()
        self._language_model_label = QLabel()
        ai_form.addRow(self._embedding_label, self._embedding)
        ai_form.addRow(self._language_model_label, self._language_model)
        self._tabs.addTab(ai_page, "")

        privacy_page = QWidget()
        privacy_layout = QVBoxLayout(privacy_page)
        self._privacy_text = QLabel()
        self._privacy_text.setWordWrap(True)
        self._retain_audio = QCheckBox()
        privacy_layout.addWidget(self._privacy_text)
        privacy_layout.addWidget(self._retain_audio)
        privacy_layout.addStretch()
        self._tabs.addTab(privacy_page, "")

        diagnostics_page = QWidget()
        diagnostics_layout = QVBoxLayout(diagnostics_page)
        self._diagnostics = QLabel()
        self._diagnostics.setWordWrap(True)
        diagnostics_layout.addWidget(self._diagnostics)
        diagnostics_layout.addStretch()
        self._tabs.addTab(diagnostics_page, "")

        labs_page = QWidget()
        labs_layout = QVBoxLayout(labs_page)
        self._experimental = QLabel()
        self._experimental.setStyleSheet("color: #B26A00; font-weight: 700")
        self._wake_phrase = QCheckBox()
        self._diarization = QCheckBox()
        self._expert_asr = QCheckBox()
        labs_layout.addWidget(self._experimental)
        labs_layout.addWidget(self._wake_phrase)
        labs_layout.addWidget(self._diarization)
        labs_layout.addWidget(self._expert_asr)
        labs_layout.addStretch()
        self._tabs.addTab(labs_page, "")
        layout.addWidget(self._tabs, 1)
        self._save = QPushButton()
        self._save.setObjectName("Primary")
        self._save.clicked.connect(self.save)
        layout.addWidget(self._save)
        self.state_panel = StatePanel(catalog)
        self.state_panel.retry_requested.connect(self.refresh)
        layout.addWidget(self.state_panel)
        catalog.language_changed.connect(self.retranslate)
        self.retranslate()
        self.refresh()

    def refresh(self) -> None:
        self.state_panel.show_state("loading")
        self._presenter.submit(
            lambda: (self._client.get_preferences(), self._client.health()),
            succeeded=self._loaded,
            failed=self._failed,
        )

    def save(self) -> None:
        self._save.setEnabled(False)
        self._presenter.submit(
            lambda: self._client.update_preferences(
                transcription_quality=str(self._quality.currentData()),
                asr_provider=str(self._asr_provider.currentData()),
                asr_model=self._asr_model.text().strip() or None,
                embedding_provider=str(self._embedding.currentData()),
                local_llm_provider=str(self._language_model.currentData()),
                diarization_enabled=self._diarization.isChecked(),
                retain_raw_audio=self._retain_audio.isChecked(),
            ),
            succeeded=lambda value: self._saved(value),
            failed=self._failed,
        )

    def _loaded(self, value: object) -> None:
        preferences, health = value
        assert isinstance(preferences, EnginePreferencesSnapshot)
        assert isinstance(health, EngineHealth)
        self.state_panel.clear()
        _select(self._quality, preferences.transcription_quality)
        _select(self._asr_provider, preferences.asr_provider)
        self._asr_model.setText(preferences.asr_model)
        _select(self._embedding, preferences.embedding_provider)
        _select(self._language_model, preferences.local_llm_provider)
        self._diarization.setChecked(preferences.diarization_enabled)
        self._retain_audio.setChecked(preferences.retain_raw_audio)
        self._wake_phrase.setChecked(self._preferences.wake_phrase_enabled)
        self._expert_asr.setChecked(self._preferences.expert_asr_enabled)
        self._populate_audio_devices()
        self._health = health
        self._render_diagnostics()
        _select(self._ui_language, self._catalog.language)

    def _saved(self, value: object) -> None:
        self._preferences.audio_device_id = self._audio_device.currentData()
        self._preferences.wake_phrase_enabled = self._wake_phrase.isChecked()
        self._preferences.expert_asr_enabled = self._expert_asr.isChecked()
        self._save.setEnabled(True)
        self.state_panel.clear()

    def _failed(self, error: Exception) -> None:
        self._save.setEnabled(True)
        self.state_panel.show_state(
            "offline" if is_engine_offline_error(error) else "error",
            str(error),
        )

    def _language_changed(self) -> None:
        language = self._ui_language.currentData()
        if language:
            self._catalog.set_language(str(language))

    def retranslate(self) -> None:
        tr = self._catalog.text
        self._title.setText(tr("settings.title"))
        self._language_note.setText(tr("settings.restart_free"))
        _replace_options(
            self._ui_language,
            (
                (tr("language.turkish"), "tr"),
                (tr("language.english"), "en"),
            ),
        )
        _select(self._ui_language, self._catalog.language)
        self._populate_audio_devices()
        _replace_options(
            self._quality,
            (
                (tr("quality.balanced"), "balanced"),
                (tr("quality.maximum"), "max_quality"),
            ),
        )
        _replace_options(
            self._asr_provider,
            (
                (tr("settings.asr_auto"), "auto"),
                (tr("settings.asr_faster_whisper"), "faster_whisper"),
                (tr("settings.asr_mock"), "mock"),
            ),
        )
        _replace_options(
            self._embedding,
            (
                (tr("settings.embedding_disabled"), "disabled"),
                (
                    tr("settings.embedding_sentence_transformer"),
                    "sentence_transformer",
                ),
            ),
        )
        _replace_options(
            self._language_model,
            (
                (tr("settings.language_model_disabled"), "disabled"),
                (tr("settings.language_model_local"), "lmstudio"),
            ),
        )
        self._audio_input_label.setText(tr("settings.audio_input"))
        self._quality_label.setText(tr("settings.quality"))
        self._asr_label.setText(tr("settings.asr"))
        self._asr_model_label.setText(tr("settings.model"))
        self._embedding_label.setText(tr("settings.embeddings"))
        self._language_model_label.setText(tr("settings.language_model"))
        self._privacy_text.setText(tr("settings.privacy_text"))
        self._retain_audio.setText(tr("settings.retain_audio"))
        labels = (
            "settings.language",
            "settings.audio",
            "settings.transcription",
            "settings.local_ai",
            "settings.privacy",
            "settings.diagnostics",
            "settings.labs",
        )
        for index, key in enumerate(labels):
            self._tabs.setTabText(index, tr(key))
        self._experimental.setText(tr("settings.experimental"))
        self._wake_phrase.setText(tr("labs.wake_phrase"))
        self._diarization.setText(tr("labs.diarization"))
        self._expert_asr.setText(tr("labs.expert_asr"))
        self._save.setText(tr("common.save"))
        self._render_diagnostics()

    def _populate_audio_devices(self) -> None:
        selected = self._preferences.audio_device_id or self._audio_device.currentData()
        options: list[tuple[str, object]] = [(self._catalog.text("settings.system_default"), None)]
        options.extend((device.label, device.device_id) for device in list_audio_inputs())
        _replace_options(self._audio_device, tuple(options))
        _select(self._audio_device, selected)

    def _render_diagnostics(self) -> None:
        if self._health is None:
            return
        tr = self._catalog.text
        health = self._health
        self._diagnostics.setText(
            f"{tr('settings.engine')}: {tr(f'status.{health.status}')}\n"
            f"{tr('settings.transcription_health')}: "
            f"{tr(f'status.{health.transcription}')}\n"
            f"{tr('settings.embeddings_health')}: "
            f"{tr(f'status.{health.embeddings}')}\n"
            f"{tr('settings.local_ai_health')}: "
            f"{tr(f'status.{health.local_llm}')}\n\n{health.detail}"
        )


def _select(combo: QComboBox, value: object) -> None:
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)


def _replace_options(
    combo: QComboBox,
    options: tuple[tuple[str, object], ...],
) -> None:
    current = combo.currentData()
    blocked = combo.blockSignals(True)
    combo.clear()
    for label, value in options:
        combo.addItem(label, value)
    index = combo.findData(current)
    combo.setCurrentIndex(index if index >= 0 else 0)
    combo.blockSignals(blocked)
