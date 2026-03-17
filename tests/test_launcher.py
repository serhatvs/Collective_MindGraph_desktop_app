from collective_mindgraph_desktop import embedded_backend, launcher


def test_launcher_runs_desktop_by_default(monkeypatch):
    captured = {}

    def fake_run_desktop():
        captured["called"] = True
        return 11

    monkeypatch.setattr(launcher, "run_desktop", fake_run_desktop)

    assert launcher.run([]) == 11
    assert captured["called"] is True


def test_launcher_runs_embedded_backend_when_requested(monkeypatch):
    captured = {}

    def fake_run_embedded_backend(arguments):
        captured["arguments"] = list(arguments)
        return 17

    monkeypatch.setattr(embedded_backend, "run_embedded_backend", fake_run_embedded_backend)

    assert launcher.run(["--backend", "--host", "127.0.0.1"]) == 17
    assert captured["arguments"] == ["--host", "127.0.0.1"]
