from collective_mindgraph.desktop import app as desktop_app
from collective_mindgraph.desktop import launcher as desktop_launcher
from collective_mindgraph.desktop.ui.design_tokens import application_stylesheet


def test_build_application_applies_product_identity_and_styles(qapp, monkeypatch):
    window = object()
    monkeypatch.setattr(desktop_app, "MainWindow", lambda: window)
    original_name = qapp.applicationName()
    original_organization = qapp.organizationName()
    original_style = qapp.style().objectName()
    original_stylesheet = qapp.styleSheet()

    try:
        application, created_window = desktop_app.build_application()

        assert application is qapp
        assert created_window is window
        assert application.applicationName() == "Collective MindGraph"
        assert application.organizationName() == "CollectiveMindGraph"
        assert application.styleSheet() == application_stylesheet()
        assert "#3157D5" in application.styleSheet()
    finally:
        qapp.setApplicationName(original_name)
        qapp.setOrganizationName(original_organization)
        qapp.setStyle(original_style)
        qapp.setStyleSheet(original_stylesheet)


def test_desktop_run_shows_window_and_returns_event_loop_status(monkeypatch):
    events: list[str] = []

    class FakeApplication:
        def exec(self):
            events.append("exec")
            return 23

    class FakeWindow:
        def show(self):
            events.append("show")

    monkeypatch.setattr(
        desktop_app,
        "build_application",
        lambda: (FakeApplication(), FakeWindow()),
    )

    assert desktop_app.run() == 23
    assert events == ["show", "exec"]


def test_desktop_launcher_parses_arguments_and_runs_app(monkeypatch):
    monkeypatch.setattr(desktop_app, "run", lambda: 29)

    assert desktop_launcher.run_desktop([]) == 29
    assert desktop_launcher.run([]) == 29
