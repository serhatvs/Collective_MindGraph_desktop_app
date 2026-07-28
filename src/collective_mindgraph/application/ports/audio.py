"""Audio adapter boundaries."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class PcmAudioNormalizer(Protocol):
    def pcm_to_wav(
        self,
        pcm_bytes: bytes,
        target_path: Path,
        sample_width_bytes: int,
    ) -> object: ...
