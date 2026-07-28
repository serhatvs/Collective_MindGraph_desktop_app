"""Reusable timeline and cancellation helpers for recording processing."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from collective_mindgraph.application.ports import TranscriptionConfiguration
from collective_mindgraph.application.transcription.contracts import (
    ASRSegment,
    DiarizationTurn,
    SpeechRegion,
    TranscriptSegment,
)
from collective_mindgraph.infrastructure.audio.wav_files import extract_wav_region

from .asr import resolve_asr_quality_profile

_TimelineItem = TypeVar("_TimelineItem", ASRSegment, DiarizationTurn, TranscriptSegment)


def build_processing_windows(
    total_duration: float,
    regions: list[SpeechRegion],
    max_window_seconds: float,
    overlap_seconds: float,
) -> list[SpeechRegion]:
    if total_duration <= 0:
        return []

    safe_max_window = max(max_window_seconds, 1.0)
    safe_overlap = max(overlap_seconds, 0.0)
    if total_duration <= safe_max_window:
        return [SpeechRegion(start=0.0, end=total_duration)]

    if not regions:
        return _split_full_duration(total_duration, safe_max_window, safe_overlap)

    windows: list[SpeechRegion] = []
    current_start = max(0.0, regions[0].start - safe_overlap)
    current_end = min(total_duration, regions[0].end + safe_overlap)
    for region in regions[1:]:
        proposed_end = min(total_duration, region.end + safe_overlap)
        if proposed_end - current_start <= safe_max_window:
            current_end = max(current_end, proposed_end)
            continue
        windows.append(SpeechRegion(start=current_start, end=current_end))
        current_start = max(0.0, region.start - safe_overlap)
        current_end = proposed_end
    windows.append(SpeechRegion(start=current_start, end=current_end))
    return windows


def _split_full_duration(
    total_duration: float,
    max_window_seconds: float,
    overlap_seconds: float,
) -> list[SpeechRegion]:
    windows: list[SpeechRegion] = []
    start = 0.0
    while start < total_duration:
        end = min(total_duration, start + max_window_seconds)
        windows.append(SpeechRegion(start=start, end=end))
        if end >= total_duration:
            break
        start = max(0.0, end - overlap_seconds)
    return windows


def clip_regions_to_window(
    regions: list[SpeechRegion],
    window_start: float,
    window_end: float,
) -> list[SpeechRegion]:
    clipped: list[SpeechRegion] = []
    for region in regions:
        overlap_start = max(region.start, window_start)
        overlap_end = min(region.end, window_end)
        if overlap_end <= overlap_start:
            continue
        clipped.append(
            SpeechRegion(
                start=overlap_start - window_start,
                end=overlap_end - window_start,
                confidence=region.confidence,
            )
        )
    return clipped


def replace_timeline_tail(
    existing: list[_TimelineItem],
    incoming: list[_TimelineItem],
    from_second: float,
) -> list[_TimelineItem]:
    preserved = [item for item in existing if item.end <= from_second]
    return preserved + incoming


def offset_diarization_turns(
    items: list[DiarizationTurn],
    offset_seconds: float,
) -> list[DiarizationTurn]:
    if not offset_seconds:
        return list(items)
    return [
        item.model_copy(
            update={
                "start": item.start + offset_seconds,
                "end": item.end + offset_seconds,
            }
        )
        for item in items
    ]


def is_full_audio_window(window: SpeechRegion, total_duration: float) -> bool:
    return window.start <= 0.0 and window.end >= total_duration


async def extract_wav_region_owned(
    source_path: Path,
    start_seconds: float,
    end_seconds: float,
    target_dir: Path,
) -> Path:
    return await to_thread_cancellation_safe(
        extract_wav_region,
        source_path,
        start_seconds,
        end_seconds,
        target_dir,
        cancelled_result_cleanup=lambda path: path.unlink(missing_ok=True),
    )


async def to_thread_cancellation_safe(
    function: Callable[..., Any],
    /,
    *args: Any,
    cancelled_result_cleanup: Callable[[Any], None] | None = None,
    **kwargs: Any,
) -> Any:
    worker_task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(worker_task)
    except asyncio.CancelledError:
        while not worker_task.done():
            try:
                await asyncio.shield(worker_task)
            except asyncio.CancelledError:
                continue
            except BaseException:
                break
        if cancelled_result_cleanup is not None and not worker_task.cancelled():
            try:
                abandoned_result = worker_task.result()
            except BaseException:
                pass
            else:
                cancelled_result_cleanup(abandoned_result)
        raise


def audio_inspection_metadata(inspection: object | None) -> dict[str, object] | None:
    if inspection is None:
        return None
    return {
        "sample_rate": getattr(inspection, "sample_rate", None),
        "channels": getattr(inspection, "channels", None),
        "sample_width_bytes": getattr(inspection, "sample_width_bytes", None),
        "frame_count": getattr(inspection, "frame_count", None),
        "duration_seconds": getattr(inspection, "duration_seconds", None),
        "format": getattr(inspection, "format", None),
    }


def unique_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def initial_selective_metadata(
    settings: TranscriptionConfiguration,
) -> dict[str, object]:
    profile = resolve_asr_quality_profile(
        settings,
        settings.selective_retranscription_profile,
    )
    return {
        "enabled": bool(settings.selective_retranscription_enabled),
        "number_of_first_pass_segments": 0,
        "number_of_flagged_segments": 0,
        "number_of_second_pass_regions": 0,
        "number_of_replaced_segments": 0,
        "number_of_retained_first_pass_segments": 0,
        "number_of_selected_segments": 0,
        "second_pass_profile": profile.name,
        "second_pass_model": profile.model_name,
        "fallback_reason": None,
        "first_pass_processing_time_seconds": 0.0,
        "second_pass_processing_time_seconds": 0.0,
        "total_additional_processing_time_seconds": 0.0,
        "retranscribed_audio_seconds": 0.0,
        "percentage_of_audio_retranscribed": 0.0,
        "triggers": [],
        "regions": [],
        "first_pass_segments": [],
        "interpretation": "Candidate scores are estimates, not accuracy or WER/CER.",
    }


def report_progress(
    callback: Callable[[str, int], None] | None,
    stage: str,
    progress: int,
) -> None:
    if callback is not None:
        callback(stage, progress)


def merge_selective_metadata(
    target: dict[str, object],
    incoming: dict[str, object],
) -> None:
    for key in (
        "number_of_flagged_segments",
        "number_of_second_pass_regions",
        "number_of_replaced_segments",
        "second_pass_processing_time_seconds",
        "retranscribed_audio_seconds",
    ):
        target[key] = float(target[key]) + float(incoming.get(key, 0.0))
    for key in ("triggers", "regions"):
        target_items = target.get(key)
        incoming_items = incoming.get(key)
        if isinstance(target_items, list) and isinstance(incoming_items, list):
            target_items.extend(incoming_items)
    if incoming.get("fallback_reason") and not target.get("fallback_reason"):
        target["fallback_reason"] = incoming["fallback_reason"]
