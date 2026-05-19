"""Qt application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .services import CollectiveMindGraphService
from .ui.main_window import MainWindow


APP_STYLESHEET = """
QMainWindow {
    background-color: #f5f7fa;
}

#Sidebar {
    background-color: #ffffff;
    border-right: 1px solid #d6dfe8;
}

#CardWidget {
    background-color: #ffffff;
    border: 1px solid #d6dfe8;
    border-radius: 10px;
}

#SectionTitle {
    font-size: 13pt;
    font-weight: 700;
    color: #102036;
}

#MetricPill {
    background-color: #f8fbff;
    border: 1px solid #e0eaff;
    border-radius: 8px;
}

#MetricValue {
    font-size: 16pt;
    font-weight: 700;
    color: #264a7f;
}

#VoiceStatusBadge {
    font-weight: 800;
    font-size: 10pt;
    border-radius: 6px;
    color: white;
    padding: 4px 12px;
}

#VoiceStatusBadge[stage="idle"] { background-color: #64748b; }
#VoiceStatusBadge[stage="recording"] { background-color: #ef4444; }
#VoiceStatusBadge[stage="processing"] { background-color: #f59e0b; }
#VoiceStatusBadge[stage="transcribing"] { background-color: #3b82f6; }
#VoiceStatusBadge[stage="completed"] { background-color: #10b981; }
#VoiceStatusBadge[stage="error"] { background-color: #7f1d1d; }

#MutedText {
    color: #66788a;
}

QPushButton {
    padding: 8px 16px;
    font-weight: 600;
    border-radius: 6px;
    background-color: #264a7f;
    color: white;
    border: none;
}

QPushButton:hover {
    background-color: #1d3a66;
}

QPushButton:disabled {
    background-color: #cbd5e1;
}

QPushButton[secondary="true"] {
    background-color: transparent;
    color: #264a7f;
    border: 1px solid #264a7f;
}

QPushButton[secondary="true"]:hover {
    background-color: #f1f5f9;
}
"""


def build_application() -> tuple[QApplication, MainWindow]:
    import os
    import collective_mindgraph_desktop
    print(f"Desktop startup:")
    print(f"  ui_mode=REBUILT_NATIVE_MVP_UI")
    print(f"  python={sys.executable}")
    print(f"  package_path={os.path.abspath(collective_mindgraph_desktop.__file__)}")
    print(f"  main_window_file={os.path.abspath(__file__)}")

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Collective MindGraph")
    app.setOrganizationName("Collective MindGraph")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    service = CollectiveMindGraphService()
    window = MainWindow(service)
    return app, window


def run() -> int:
    app, window = build_application()
    window.show()
    return app.exec()
