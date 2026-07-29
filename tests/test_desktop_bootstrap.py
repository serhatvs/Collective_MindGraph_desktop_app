from collective_mindgraph.desktop import app as desktop_app
from collective_mindgraph.desktop import launcher as desktop_launcher
from collective_mindgraph.desktop.ui.theme import DARK, LIGHT, ThemeMode, stylesheet


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
        # The default mode follows the desktop, so assert against whichever
        # palette that resolves to rather than pinning one environment.
        expected = desktop_app.resolve(
            ThemeMode.SYSTEM,
            system_prefers_dark=desktop_app.system_prefers_dark(application),
        )
        assert application.styleSheet() == stylesheet(expected)
        assert expected.primary in application.styleSheet()
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


def test_an_explicit_theme_mode_repaints_the_application(qapp, monkeypatch):
    monkeypatch.setattr(desktop_app, "MainWindow", lambda: object())
    original_stylesheet = qapp.styleSheet()
    try:
        assert desktop_app.apply_theme(qapp, ThemeMode.DARK) is DARK
        assert qapp.styleSheet() == stylesheet(DARK)
        assert desktop_app.apply_theme(qapp, ThemeMode.LIGHT) is LIGHT
        assert qapp.styleSheet() == stylesheet(LIGHT)
        # Switching at runtime leaves no colour from the previous palette.
        assert DARK.canvas not in qapp.styleSheet()
    finally:
        qapp.setStyleSheet(original_stylesheet)
