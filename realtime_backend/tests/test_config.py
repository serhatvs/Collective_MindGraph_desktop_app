from pathlib import Path

from app import config


def test_resolve_pyannote_token_prefers_env(monkeypatch, tmp_path):
    monkeypatch.delenv("CMG_RT_PYANNOTE_TOKEN", raising=False)
    monkeypatch.setenv("HF_TOKEN", "hf_env_token")
    monkeypatch.setenv("APPDATA", str(tmp_path))

    assert config._resolve_pyannote_token() == "hf_env_token"


def test_resolve_pyannote_token_falls_back_to_cached_file(monkeypatch, tmp_path):
    monkeypatch.delenv("CMG_RT_PYANNOTE_TOKEN", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    token_path = Path(tmp_path) / "huggingface" / "token"
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text("hf_cached_token\n", encoding="utf-8")

    assert config._resolve_pyannote_token() == "hf_cached_token"
