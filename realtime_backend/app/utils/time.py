"""Time and overlap utilities."""

from __future__ import annotations


def format_timestamp(seconds: float) -> str:
    total_milliseconds = int(round(max(seconds, 0.0) * 1000))
    minutes, milliseconds = divmod(total_milliseconds, 60_000)
    secs, millis = divmod(milliseconds, 1_000)
    return f"{minutes:02d}:{secs:02d}.{millis:03d}"


def overlap_duration(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def overlap_ratio(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    overlap = overlap_duration(start_a, end_a, start_b, end_b)
    base = max(end_a - start_a, 1e-6)
    return overlap / base
