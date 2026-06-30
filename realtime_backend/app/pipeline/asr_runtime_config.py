"""ASR runtime configuration and diagnostics.

This module is intentionally independent from ``Settings`` so scripts and the
backend can resolve the same environment contract without constructing the full
application.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
import importlib
import os
from pathlib import Path
import site
import sys
from typing import Any


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
_DLL_DIRECTORY_HANDLES: list[Any] = []


@dataclass(frozen=True, slots=True)
class TorchCudaProbe:
    available: bool | None
    status: str
    version: str | None = None
    cuda_version: str | None = None
    device_count: int | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ASRRuntimeConfig:
    runtime_profile: str
    gpu_enabled: bool
    gpu_required: bool
    asr_backend: str
    asr_model: str
    asr_device: str
    asr_compute_type: str
    asr_language: str | None
    embedding_device: str
    direct_overrides: dict[str, str] = field(default_factory=dict)

    @property
    def cuda_requested(self) -> bool:
        return self.asr_device.strip().lower().startswith("cuda")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_asr_runtime_config(environ: Mapping[str, str] | None = None) -> ASRRuntimeConfig:
    env = environ if environ is not None else os.environ
    runtime_profile = _env_first(env, ("CMG_RUNTIME_PROFILE", "CMG_RT_RUNTIME_PROFILE"), "cpu").strip().lower()
    if runtime_profile not in {"cpu", "gpu_asr"}:
        runtime_profile = "cpu"

    gpu_enabled = _env_bool_first(env, ("CMG_GPU_ENABLED", "CMG_RT_GPU_ENABLED"), False)
    gpu_required = _env_bool_first(env, ("CMG_REQUIRE_GPU", "CMG_RT_REQUIRE_GPU"), False)

    profile_defaults = {
        "asr_model": "small",
        "asr_device": "cpu",
        "asr_compute_type": "int8",
        "asr_language": "tr",
    }
    if runtime_profile == "gpu_asr":
        profile_defaults.update(
            {
                "asr_device": "cuda",
                "asr_compute_type": "float16",
                "asr_language": "tr",
            }
        )

    logical_envs = {
        "asr_backend": ("CMG_ASR_BACKEND", "CMG_ASR_PROVIDER", "CMG_RT_ASR_PROVIDER"),
        "asr_model": ("CMG_ASR_MODEL", "CMG_RT_ASR_MODEL"),
        "asr_device": ("CMG_ASR_DEVICE", "CMG_RT_ASR_DEVICE"),
        "asr_compute_type": ("CMG_ASR_COMPUTE_TYPE", "CMG_RT_ASR_COMPUTE_TYPE"),
        "asr_language": ("CMG_ASR_LANGUAGE", "CMG_RT_LANGUAGE"),
        "embedding_device": ("CMG_EMBEDDING_DEVICE", "CMG_RT_EMBEDDING_DEVICE"),
    }
    overrides = _collect_overrides(env, logical_envs)

    return ASRRuntimeConfig(
        runtime_profile=runtime_profile,
        gpu_enabled=gpu_enabled,
        gpu_required=gpu_required,
        asr_backend=_env_first(env, logical_envs["asr_backend"], "auto").strip() or "auto",
        asr_model=_env_first(env, logical_envs["asr_model"], profile_defaults["asr_model"]).strip()
        or profile_defaults["asr_model"],
        asr_device=_env_first(env, logical_envs["asr_device"], profile_defaults["asr_device"]).strip()
        or profile_defaults["asr_device"],
        asr_compute_type=_env_first(
            env,
            logical_envs["asr_compute_type"],
            profile_defaults["asr_compute_type"],
        ).strip()
        or profile_defaults["asr_compute_type"],
        asr_language=_optional_env_first(env, logical_envs["asr_language"], profile_defaults["asr_language"]),
        embedding_device=_env_first(env, logical_envs["embedding_device"], "cpu").strip() or "cpu",
        direct_overrides=overrides,
    )


def probe_torch_cuda() -> TorchCudaProbe:
    try:
        torch = importlib.import_module("torch")
    except Exception as exc:  # pragma: no cover - environment dependent
        return TorchCudaProbe(
            available=None,
            status="torch_unavailable",
            error=f"{type(exc).__name__}: {exc}",
        )

    try:
        available = bool(torch.cuda.is_available())
        device_count = int(torch.cuda.device_count()) if hasattr(torch.cuda, "device_count") else None
        return TorchCudaProbe(
            available=available,
            status="cuda_available" if available else "cuda_not_available",
            version=str(getattr(torch, "__version__", "")) or None,
            cuda_version=str(getattr(torch.version, "cuda", "")) or None,
            device_count=device_count,
        )
    except Exception as exc:  # pragma: no cover - environment dependent
        return TorchCudaProbe(
            available=None,
            status="cuda_probe_failed",
            version=str(getattr(torch, "__version__", "")) or None,
            cuda_version=str(getattr(torch.version, "cuda", "")) or None,
            error=f"{type(exc).__name__}: {exc}",
        )


def add_cuda_dll_directories() -> list[str]:
    """Register venv-local CUDA DLL directories on Windows.

    CTranslate2 may need cuBLAS/cuDNN DLLs at inference time even when model
    construction succeeds. PyPI NVIDIA wheels place those DLLs under
    ``site-packages/nvidia/*/bin``; those folders are not always on PATH.
    """

    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return []

    candidates = _cuda_dll_directory_candidates()
    added: list[str] = []
    for candidate in candidates:
        if not candidate.exists() or not candidate.is_dir():
            continue
        path = str(candidate)
        try:
            handle = os.add_dll_directory(path)
        except OSError:
            continue
        _DLL_DIRECTORY_HANDLES.append(handle)
        added.append(path)
    if added:
        current_path = os.environ.get("PATH", "")
        missing = [path for path in added if path not in current_path.split(os.pathsep)]
        if missing:
            os.environ["PATH"] = os.pathsep.join([*missing, current_path]) if current_path else os.pathsep.join(missing)
    return added


def _cuda_dll_directory_candidates() -> list[Path]:
    roots: list[Path] = []
    try:
        roots.extend(Path(item) for item in site.getsitepackages())
    except Exception:
        roots.append(Path(sys.prefix) / "Lib" / "site-packages")
    roots.append(Path(sys.prefix) / "Lib" / "site-packages")

    candidates: list[Path] = []
    for root in _dedupe_paths(roots):
        candidates.extend(
            [
                root / "nvidia" / "cublas" / "bin",
                root / "nvidia" / "cuda_runtime" / "bin",
                root / "nvidia" / "cuda_nvrtc" / "bin",
                root / "nvidia" / "cudnn" / "bin",
                root / "torch" / "lib",
                root / "ctranslate2",
            ]
        )

    cuda_path = os.getenv("CUDA_PATH")
    if cuda_path:
        candidates.append(Path(cuda_path) / "bin")
    return _dedupe_paths(candidates)


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    deduped: list[Path] = []
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def build_asr_diagnostics(settings: Any, asr_provider: Any, *, llm_provider: Any | None = None) -> dict[str, Any]:
    cuda_probe = probe_torch_cuda()
    local_llm_enabled = str(getattr(settings, "llm_provider", "")).lower() not in {"", "none", "disabled"}
    return {
        "ASR runtime profile": getattr(settings, "asr_runtime_profile", None),
        "ASR backend": getattr(settings, "asr_provider", None),
        "ASR backend resolved": getattr(asr_provider, "provider_name", None),
        "ASR model": getattr(settings, "asr_model_name", None),
        "ASR device": getattr(settings, "asr_device", None),
        "ASR compute type": getattr(settings, "asr_compute_type", None),
        "ASR language": getattr(settings, "default_language", None),
        "CMG_GPU_ENABLED": getattr(settings, "gpu_enabled", None),
        "CMG_REQUIRE_GPU": getattr(settings, "gpu_required", None),
        "CUDA available through torch": cuda_probe.available,
        "Torch CUDA probe status": cuda_probe.status,
        "Torch version": cuda_probe.version,
        "Torch CUDA version": cuda_probe.cuda_version,
        "Faster-Whisper CUDA load status": getattr(asr_provider, "cuda_load_status", None),
        "GPU requested by ASR": bool(getattr(asr_provider, "gpu_requested", False)),
        "GPU actually loaded by ASR": bool(getattr(asr_provider, "gpu_loaded", False)),
        "Fallback happened": bool(getattr(asr_provider, "gpu_fallback_happened", False)),
        "Fallback reason": getattr(asr_provider, "gpu_fallback_reason", None),
        "CUDA DLL directories": getattr(asr_provider, "cuda_dll_directories", []),
        "Embedding device": getattr(settings, "embedding_device", "cpu"),
        "Local LLM enabled": local_llm_enabled,
        "LLM provider resolved": getattr(llm_provider, "provider_name", None) if llm_provider is not None else None,
    }


def format_asr_diagnostics(diagnostics: Mapping[str, Any]) -> str:
    return "\n".join(f"{key}: {value}" for key, value in diagnostics.items())


def _env_first(env: Mapping[str, str], names: tuple[str, ...], default: str) -> str:
    for name in names:
        value = env.get(name)
        if value is not None and value.strip() != "":
            return value
    return default


def _optional_env_first(env: Mapping[str, str], names: tuple[str, ...], default: str | None) -> str | None:
    value = _env_first(env, names, default or "")
    return value.strip() or None


def _env_bool_first(env: Mapping[str, str], names: tuple[str, ...], default: bool) -> bool:
    for name in names:
        value = env.get(name)
        if value is None:
            continue
        normalized = value.strip().lower()
        if normalized in TRUE_VALUES:
            return True
        if normalized in FALSE_VALUES:
            return False
    return default


def _collect_overrides(env: Mapping[str, str], logical_envs: Mapping[str, tuple[str, ...]]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for logical_name, names in logical_envs.items():
        for name in names:
            value = env.get(name)
            if value is not None and value.strip() != "":
                overrides[logical_name] = name
                break
    return overrides
