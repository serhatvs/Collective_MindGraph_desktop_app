from pathlib import Path
import sys

from collective_mindgraph_desktop.backend_runtime import build_local_backend_launch_spec


def test_build_local_backend_launch_spec_targets_local_backend(tmp_path):
    backend_dir = tmp_path / "realtime_backend"
    (backend_dir / "app").mkdir(parents=True)
    (backend_dir / "app" / "main.py").write_text("app = object()\n", encoding="utf-8")
    (backend_dir / ".venv" / "Scripts").mkdir(parents=True)
    python_path = backend_dir / ".venv" / "Scripts" / "python.exe"
    python_path.write_text("", encoding="utf-8")

    spec = build_local_backend_launch_spec("http://127.0.0.1:9090", repo_root=tmp_path)

    assert spec is not None
    assert Path(spec.program) == python_path
    assert spec.arguments[-1] == "9090"
    assert spec.working_directory == str(backend_dir)


def test_build_local_backend_launch_spec_skips_non_loopback_urls(tmp_path):
    assert build_local_backend_launch_spec("https://example.com:8080", repo_root=tmp_path) is None


def test_build_local_backend_launch_spec_uses_embedded_backend_when_frozen(tmp_path, monkeypatch):
    executable_path = tmp_path / "CollectiveMindGraph.exe"
    executable_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable_path))

    spec = build_local_backend_launch_spec("http://127.0.0.1:8080", repo_root=tmp_path)

    assert spec is not None
    assert Path(spec.program) == executable_path
    assert spec.arguments == ["--backend", "--host", "127.0.0.1", "--port", "8080"]
    assert spec.working_directory == str(executable_path.parent)
    assert spec.environment["CMG_RT_DATA_DIR"].endswith("CollectiveMindGraph\\realtime_backend_data")
    assert spec.environment["CMG_RT_TEMP_DIR"].endswith("CollectiveMindGraph\\realtime_backend_temp")
