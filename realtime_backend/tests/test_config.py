from pathlib import Path

from app import config
from app.pipeline.asr_runtime_config import resolve_asr_runtime_config


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


def test_asr_runtime_config_gpu_profile_and_direct_env_overrides():
    resolved = resolve_asr_runtime_config(
        {
            "CMG_RUNTIME_PROFILE": "gpu_asr",
            "CMG_GPU_ENABLED": "1",
            "CMG_REQUIRE_GPU": "1",
            "CMG_ASR_MODEL": "large-v3",
            "CMG_ASR_DEVICE": "cuda",
            "CMG_ASR_COMPUTE_TYPE": "float16",
            "CMG_ASR_LANGUAGE": "tr",
            "CMG_EMBEDDING_DEVICE": "cpu",
        }
    )

    assert resolved.runtime_profile == "gpu_asr"
    assert resolved.gpu_enabled is True
    assert resolved.gpu_required is True
    assert resolved.asr_model == "large-v3"
    assert resolved.asr_device == "cuda"
    assert resolved.asr_compute_type == "float16"
    assert resolved.asr_language == "tr"
    assert resolved.embedding_device == "cpu"
    assert resolved.cuda_requested is True


def test_asr_runtime_config_cpu_profile_defaults():
    resolved = resolve_asr_runtime_config({})

    assert resolved.runtime_profile == "cpu"
    assert resolved.asr_model == "small"
    assert resolved.asr_device == "cpu"
    assert resolved.asr_compute_type == "int8"
    assert resolved.asr_language == "tr"
