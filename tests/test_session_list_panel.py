import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from collective_mindgraph_desktop.models import Session
from collective_mindgraph_desktop.ui.session_list_panel import SessionListPanel


def test_session_list_panel_keeps_selection_empty_without_explicit_target():
    app = QApplication.instance() or QApplication([])
    panel = SessionListPanel()
    selected_ids: list[int] = []
    panel.session_selected.connect(selected_ids.append)

    panel.set_sessions(
        [
            Session(
                id=2,
                title="Second Session",
                device_id="VOICE-MIC",
                status="active",
                created_at="2026-03-10 10:00:00",
                updated_at="2026-03-10 10:05:00",
            ),
            Session(
                id=1,
                title="First Session",
                device_id="VOICE-MIC",
                status="active",
                created_at="2026-03-10 09:00:00",
                updated_at="2026-03-10 09:05:00",
            ),
        ]
    )

    assert app is not None
    assert panel.current_session_id() is None
    assert selected_ids == []
