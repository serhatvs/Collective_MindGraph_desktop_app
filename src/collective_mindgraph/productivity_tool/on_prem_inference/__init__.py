"""On-prem inference provider submodule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    task_name: str
    prompt: str
    max_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class InferenceResult:
    text: str
    model_name: str
    confidence: float | None = None


class InferenceProvider(Protocol):
    """Boundary for local, on-prem, or private-cloud model inference."""

    def complete(self, request: InferenceRequest) -> InferenceResult:
        """Run an inference request inside the approved deployment boundary."""
