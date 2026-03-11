"""Speaker diarization providers."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path

from ..config import Settings
from ..models import DiarizationTurn, SpeechRegion
from ..utils.audio import extract_wav_region, wav_duration_seconds
from ..utils.time import overlap_ratio

LOGGER = logging.getLogger(__name__)


class BaseDiarizer(ABC):
    @abstractmethod
    def diarize(
        self,
        audio_path: Path,
        regions: list[SpeechRegion] | None = None,
    ) -> list[DiarizationTurn]:
        raise NotImplementedError


class PyAnnoteDiarizer(BaseDiarizer):
    def __init__(self, settings: Settings) -> None:
        try:
            import torch
            from pyannote.audio import Pipeline
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("pyannote.audio is not installed.") from exc

        self._torch = torch
        _enable_pyannote_checkpoint_compat(torch)
        self._pipeline = Pipeline.from_pretrained(
            settings.diarizer_model_name,
            use_auth_token=settings.diarizer_auth_token,
        )
        device = torch.device(settings.diarizer_device)
        self._pipeline.to(device)
        self._settings = settings

    def diarize(
        self,
        audio_path: Path,
        regions: list[SpeechRegion] | None = None,
    ) -> list[DiarizationTurn]:
        if not regions:
            turns = self._run_window(audio_path, offset_seconds=0.0)
            return _postprocess_turns(turns, self._settings.diarizer_overlap_threshold)

        turns: list[DiarizationTurn] = []
        for window in _regions_for_diarization(
            regions,
            padding_seconds=self._settings.diarizer_region_padding_seconds,
            merge_gap_seconds=self._settings.diarizer_merge_gap_seconds,
            max_window_seconds=self._settings.diarizer_max_window_seconds,
        ):
            region_path = extract_wav_region(
                source_path=audio_path,
                start_seconds=window.start,
                end_seconds=window.end,
                target_dir=self._settings.temp_dir,
            )
            try:
                turns.extend(self._run_window(region_path, offset_seconds=window.start))
            finally:
                region_path.unlink(missing_ok=True)
        return _postprocess_turns(turns, self._settings.diarizer_overlap_threshold)

    def _run_window(self, audio_path: Path, offset_seconds: float) -> list[DiarizationTurn]:
        annotation = self._pipeline(str(audio_path))
        turns: list[DiarizationTurn] = []
        for speech_turn, _track, speaker_label in annotation.itertracks(yield_label=True):
            turns.append(
                DiarizationTurn(
                    start=float(speech_turn.start) + offset_seconds,
                    end=float(speech_turn.end) + offset_seconds,
                    speaker=str(speaker_label),
                    confidence=1.0,
                )
            )
        return turns


class SingleSpeakerFallbackDiarizer(BaseDiarizer):
    """Clear fallback when pyannote is unavailable; not true diarization."""

    def diarize(
        self,
        audio_path: Path,
        regions: list[SpeechRegion] | None = None,
    ) -> list[DiarizationTurn]:
        if regions:
            return [
                DiarizationTurn(
                    start=region.start,
                    end=region.end,
                    speaker="UNRESOLVED_0",
                    confidence=0.0,
                )
                for region in regions
            ]
        duration = wav_duration_seconds(audio_path)
        return [DiarizationTurn(start=0.0, end=duration, speaker="UNRESOLVED_0", confidence=0.0)]


def build_diarizer(settings: Settings) -> BaseDiarizer:
    if settings.diarizer_provider == "fallback":
        return SingleSpeakerFallbackDiarizer()
    try:
        return PyAnnoteDiarizer(settings)
    except Exception as exc:
        LOGGER.warning("Falling back to SingleSpeakerFallbackDiarizer because pyannote failed: %s", exc)
        return SingleSpeakerFallbackDiarizer()


def _enable_pyannote_checkpoint_compat(torch_module) -> None:
    """Allow pyannote checkpoints to load on newer PyTorch defaults."""

    # pyannote 3.x still relies on checkpoint objects that PyTorch 2.6+
    # blocks behind weights_only=True by default.
    os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")

    add_safe_globals = getattr(torch_module.serialization, "add_safe_globals", None)
    if add_safe_globals is None:
        return
    torch_version_cls = getattr(torch_module.torch_version, "TorchVersion", None)
    specifications_cls = None
    try:
        from pyannote.audio.core.task import Specifications

        specifications_cls = Specifications
    except Exception:  # pragma: no cover - best effort compatibility
        specifications_cls = None

    safe_globals = [item for item in (torch_version_cls, specifications_cls) if item is not None]
    if not safe_globals:
        return
    add_safe_globals(safe_globals)


def _regions_for_diarization(
    regions: list[SpeechRegion],
    padding_seconds: float,
    merge_gap_seconds: float,
    max_window_seconds: float,
) -> list[SpeechRegion]:
    windows: list[SpeechRegion] = []
    for region in sorted(regions, key=lambda item: item.start):
        padded = SpeechRegion(
            start=max(0.0, region.start - padding_seconds),
            end=region.end + padding_seconds,
            confidence=region.confidence,
        )
        _append_or_split_window(
            windows=windows,
            region=padded,
            merge_gap_seconds=merge_gap_seconds,
            max_window_seconds=max_window_seconds,
        )
    return windows


def _append_or_split_window(
    windows: list[SpeechRegion],
    region: SpeechRegion,
    merge_gap_seconds: float,
    max_window_seconds: float,
) -> None:
    if not windows:
        _append_split_region(windows, region, max_window_seconds)
        return

    previous = windows[-1]
    should_merge = (
        region.start - previous.end <= merge_gap_seconds
        and (region.end - previous.start) <= max_window_seconds
    )
    if should_merge:
        windows[-1] = SpeechRegion(
            start=previous.start,
            end=max(previous.end, region.end),
            confidence=_merge_confidence(previous.confidence, region.confidence),
        )
        return

    _append_split_region(windows, region, max_window_seconds)


def _append_split_region(
    windows: list[SpeechRegion],
    region: SpeechRegion,
    max_window_seconds: float,
) -> None:
    if max_window_seconds <= 0 or (region.end - region.start) <= max_window_seconds:
        windows.append(region)
        return

    start = region.start
    while start < region.end:
        end = min(region.end, start + max_window_seconds)
        windows.append(
            SpeechRegion(
                start=start,
                end=end,
                confidence=region.confidence,
            )
        )
        start = end


def _postprocess_turns(
    turns: list[DiarizationTurn],
    overlap_threshold: float,
) -> list[DiarizationTurn]:
    ordered = sorted(
        [turn for turn in turns if turn.end > turn.start],
        key=lambda item: (item.start, item.end, item.speaker),
    )
    compact: list[DiarizationTurn] = []
    for turn in ordered:
        if compact and _looks_duplicate(compact[-1], turn):
            compact[-1] = _prefer_turn(compact[-1], turn)
            continue
        if compact and _can_merge_turns(compact[-1], turn):
            compact[-1] = DiarizationTurn(
                start=compact[-1].start,
                end=max(compact[-1].end, turn.end),
                speaker=compact[-1].speaker,
                confidence=_merge_confidence(compact[-1].confidence, turn.confidence),
                overlap=compact[-1].overlap or turn.overlap,
            )
            continue
        compact.append(turn)

    marked: list[DiarizationTurn] = []
    for index, turn in enumerate(compact):
        overlap = any(
            other.speaker != turn.speaker
            and overlap_ratio(turn.start, turn.end, other.start, other.end) >= overlap_threshold
            for other_index, other in enumerate(compact)
            if other_index != index
        )
        marked.append(turn.model_copy(update={"overlap": overlap}))
    return marked


def _can_merge_turns(left: DiarizationTurn, right: DiarizationTurn) -> bool:
    return (
        left.speaker == right.speaker
        and right.start <= left.end + 0.20
        and not left.overlap
        and not right.overlap
    )


def _looks_duplicate(left: DiarizationTurn, right: DiarizationTurn) -> bool:
    return left.speaker == right.speaker and overlap_ratio(left.start, left.end, right.start, right.end) >= 0.85


def _prefer_turn(left: DiarizationTurn, right: DiarizationTurn) -> DiarizationTurn:
    left_confidence = left.confidence or 0.0
    right_confidence = right.confidence or 0.0
    return right if right_confidence > left_confidence else left


def _merge_confidence(left: float | None, right: float | None) -> float | None:
    values = [item for item in (left, right) if item is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 3)
