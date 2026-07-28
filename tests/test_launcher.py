import sys
from types import SimpleNamespace

import pytest

from collective_mindgraph import launcher
from collective_mindgraph.desktop import launcher as desktop_launcher
from collective_mindgraph.engine import embedded_runner


def test_launcher_runs_desktop_by_default(monkeypatch):
    monkeypatch.setattr(desktop_launcher, "run_desktop", lambda _arguments: 11)
    assert launcher.run([]) == 11


def test_launcher_runs_embedded_engine_when_requested(monkeypatch):
    captured: dict[str, list[str]] = {}

    def fake_run(arguments):
        captured["arguments"] = list(arguments)
        return 17

    monkeypatch.setattr(embedded_runner, "run_embedded_engine", fake_run)

    assert launcher.run(["--engine", "--host", "127.0.0.1"]) == 17
    assert captured["arguments"] == ["--host", "127.0.0.1"]


def test_embedded_engine_uses_windowless_safe_logging(monkeypatch):
    captured: dict[str, object] = {}

    class FakeConfig:
        def __init__(self, **options):
            captured["config"] = options

    class FakeServer:
        def __init__(self, config):
            captured["server_config"] = config

        def run(self):
            captured["ran"] = True

    fake_uvicorn = SimpleNamespace(Config=FakeConfig, Server=FakeServer)
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    monkeypatch.setattr(
        "collective_mindgraph.engine.main.create_app",
        lambda: "application",
    )

    assert (
        embedded_runner.run_embedded_engine(
            ["--host", "127.0.0.1", "--port", "8765", "--log-level", "warning"]
        )
        == 0
    )
    assert captured["config"] == {
        "app": "application",
        "host": "127.0.0.1",
        "port": 8765,
        "log_level": "warning",
        "log_config": None,
        "access_log": False,
        "reload": False,
    }
    assert captured["ran"] is True


def test_embedded_engine_rejects_non_local_bind_address():
    with pytest.raises(ValueError, match="only bind to localhost"):
        embedded_runner.run_embedded_engine(["--host", "0.0.0.0"])
