from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings, Qt

from collective_mindgraph.desktop.contracts import (
    DashboardSnapshot,
    EngineHealth,
    EnginePreferencesSnapshot,
    EngineSettings,
)
from collective_mindgraph.desktop.engine_client import EngineClientError
from collective_mindgraph.desktop.language_catalog import LanguageCatalog
from collective_mindgraph.desktop.ui.main_window import MainWindow


class _OfflineClient:
    settings = EngineSettings()

    def dashboard(self):
        raise EngineClientError("engine_offline", "offline", retryable=True)

    def health(self):
        raise EngineClientError("engine_offline", "offline", retryable=True)


class _ReadyClient:
    settings = EngineSettings()

    def dashboard(self):
        return DashboardSnapshot(0, 0, 0, 0, ())

    def health(self):
        return EngineHealth("ready", "ready", "disabled", "disabled", "")

    def get_preferences(self):
        return EnginePreferencesSnapshot(
            language=None,
            transcription_quality="balanced",
            asr_provider="auto",
            asr_model="small",
            embeddings_enabled=False,
            embedding_provider="mock",
            local_llm_provider="disabled",
            diarization_enabled=False,
        )

    def list_meetings(self, _query=""):
        return (), None

    def list_insights(self, **_filters):
        return (), None

    def list_knowledge(self, **_filters):
        return (), None

    def list_relationships(self, **_filters):
        return (), None

    def search_memory(self, _query, **_filters):
        return (), None


def _catalog(path, language: str) -> LanguageCatalog:
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    settings.setValue("ui/language", language)
    return LanguageCatalog(settings)


def test_six_workspace_shell_renders_offscreen(qtbot, tmp_path):
    window = MainWindow(
        client=_ReadyClient(),
        catalog=_catalog(tmp_path / "ui.ini", "en"),
        auto_start_engine=False,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.dashboard.state_panel.isHidden(), timeout=2_000)

    assert window._stack.count() == 6
    assert [button.text() for button in window._nav_buttons] == [
        "Home",
        "Capture",
        "Meetings",
        "Memory",
        "Knowledge",
        "Settings",
    ]


def test_language_switch_retranslates_without_restart(qtbot, tmp_path):
    catalog = _catalog(tmp_path / "ui.ini", "en")
    window = MainWindow(
        client=_OfflineClient(),
        catalog=catalog,
        auto_start_engine=False,
    )
    qtbot.addWidget(window)

    catalog.set_language("tr")

    assert window._nav_buttons[0].text() == "Ana Merkez"
    assert window._nav_buttons[1].text() == "Kayıt"
    assert window.meetings._meeting_table.horizontalHeaderItem(0).text() == "Toplantı"
    assert window.memory._results.horizontalHeaderItem(1).text() == "Sonuç"
    assert window.capture._quality.itemText(0) == "Dengeli"
    assert "yerel Collective MindGraph" in window.settings._privacy_text.text()
    assert window.windowTitle() == "Collective MindGraph"


def test_offline_state_does_not_spawn_engine_when_disabled(qtbot):
    window = MainWindow(client=_OfflineClient(), auto_start_engine=False)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.dashboard.state_panel.isVisible(), timeout=2_000)

    assert not window._startup_attempted


@pytest.mark.parametrize("language", ["en", "tr"])
def test_every_workspace_renders_at_minimum_window_size(qtbot, tmp_path, language):
    window = MainWindow(
        client=_ReadyClient(),
        catalog=_catalog(tmp_path / f"{language}.ini", language),
        auto_start_engine=False,
    )
    qtbot.addWidget(window)
    window.resize(window.minimumSize())
    window.show()
    qtbot.waitUntil(lambda: window.dashboard.state_panel.isHidden(), timeout=2_000)

    for index, workspace in enumerate(window._workspaces):
        window.show_workspace(index)
        qtbot.wait(20)
        hint = workspace.minimumSizeHint()
        assert hint.width() <= window._stack.width()
        assert hint.height() <= window._stack.height()
        rendered = window.grab()
        assert not rendered.isNull()
        assert rendered.devicePixelRatio() >= 1

    assert all(
        button.fontMetrics().horizontalAdvance(button.text()) <= button.contentsRect().width()
        for button in window._nav_buttons
    )


def test_keyboard_focus_moves_through_navigation(qtbot, tmp_path):
    window = MainWindow(
        client=_ReadyClient(),
        catalog=_catalog(tmp_path / "keyboard.ini", "en"),
        auto_start_engine=False,
    )
    qtbot.addWidget(window)
    window.show()
    first = window._nav_buttons[0]
    first.setFocus()

    qtbot.keyClick(first, Qt.Key.Key_Tab)

    assert window.focusWidget() is not first
