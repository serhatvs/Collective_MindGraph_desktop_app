"""Deterministic Levenshtein alignment and metric result models."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any, TypeVar

_T = TypeVar("_T")


@dataclass(frozen=True, slots=True)
class AlignmentOperation:
    operation: str
    reference: str | None
    hypothesis: str | None
    reference_index: int | None
    hypothesis_index: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MetricResult:
    reference_text: str
    hypothesis_text: str
    reference_word_count: int
    hypothesis_word_count: int
    reference_character_count: int
    hypothesis_character_count: int
    word_distance: int
    character_distance: int
    substitutions: tuple[AlignmentOperation, ...] = ()
    deletions: tuple[AlignmentOperation, ...] = ()
    insertions: tuple[AlignmentOperation, ...] = ()

    @property
    def wer(self) -> float | None:
        if not self.reference_word_count:
            return None
        return self.word_distance / self.reference_word_count

    @property
    def cer(self) -> float | None:
        if not self.reference_character_count:
            return None
        return self.character_distance / self.reference_character_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_text": self.reference_text,
            "hypothesis_text": self.hypothesis_text,
            "reference_word_count": self.reference_word_count,
            "hypothesis_word_count": self.hypothesis_word_count,
            "reference_character_count": self.reference_character_count,
            "hypothesis_character_count": self.hypothesis_character_count,
            "word_distance": self.word_distance,
            "character_distance": self.character_distance,
            "wer": self.wer,
            "cer": self.cer,
            "substitution_count": len(self.substitutions),
            "deletion_count": len(self.deletions),
            "insertion_count": len(self.insertions),
            "substitutions": [item.to_dict() for item in self.substitutions],
            "deletions": [item.to_dict() for item in self.deletions],
            "insertions": [item.to_dict() for item in self.insertions],
        }


def metric_result(reference: str, hypothesis: str, *, exact: bool) -> MetricResult:
    reference_words = reference.split() if exact else _metric_words(reference)
    hypothesis_words = hypothesis.split() if exact else _metric_words(hypothesis)
    word_alignment = align(reference_words, hypothesis_words)
    substitutions = tuple(step for step in word_alignment if step.operation == "substitution")
    deletions = tuple(step for step in word_alignment if step.operation == "deletion")
    insertions = tuple(step for step in word_alignment if step.operation == "insertion")
    reference_characters = list(reference)
    hypothesis_characters = list(hypothesis)
    character_alignment = align(reference_characters, hypothesis_characters)
    return MetricResult(
        reference_text=reference,
        hypothesis_text=hypothesis,
        reference_word_count=len(reference_words),
        hypothesis_word_count=len(hypothesis_words),
        reference_character_count=len(reference_characters),
        hypothesis_character_count=len(hypothesis_characters),
        word_distance=len(substitutions) + len(deletions) + len(insertions),
        character_distance=sum(step.operation != "equal" for step in character_alignment),
        substitutions=substitutions,
        deletions=deletions,
        insertions=insertions,
    )


def edit_distance_with_operations(
    reference: Sequence[str],
    hypothesis: Sequence[str],
) -> tuple[int, dict[str, list[Any]]]:
    """Return Levenshtein distance and compatibility-shaped edit details."""

    alignment = align(reference, hypothesis)
    substitutions = [
        {"reference": item.reference, "actual": item.hypothesis}
        for item in alignment
        if item.operation == "substitution"
    ]
    deletions = [item.reference for item in alignment if item.operation == "deletion"]
    insertions = [item.hypothesis for item in alignment if item.operation == "insertion"]
    return len(substitutions) + len(deletions) + len(insertions), {
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
    }


def align(
    reference: Sequence[_T],
    hypothesis: Sequence[_T],
) -> list[AlignmentOperation]:
    rows = len(reference) + 1
    columns = len(hypothesis) + 1
    costs = [[0] * columns for _ in range(rows)]
    back = [[""] * columns for _ in range(rows)]
    for row in range(1, rows):
        costs[row][0] = row
        back[row][0] = "deletion"
    for column in range(1, columns):
        costs[0][column] = column
        back[0][column] = "insertion"
    for row in range(1, rows):
        for column in range(1, columns):
            if reference[row - 1] == hypothesis[column - 1]:
                costs[row][column] = costs[row - 1][column - 1]
                back[row][column] = "equal"
                continue
            choices = (
                (costs[row - 1][column - 1] + 1, 0, "substitution"),
                (costs[row - 1][column] + 1, 1, "deletion"),
                (costs[row][column - 1] + 1, 2, "insertion"),
            )
            cost, _priority, operation = min(choices)
            costs[row][column] = cost
            back[row][column] = operation

    steps: list[AlignmentOperation] = []
    row = len(reference)
    column = len(hypothesis)
    while row > 0 or column > 0:
        operation = back[row][column]
        if operation in {"equal", "substitution"}:
            steps.append(
                AlignmentOperation(
                    operation=operation,
                    reference=str(reference[row - 1]),
                    hypothesis=str(hypothesis[column - 1]),
                    reference_index=row - 1,
                    hypothesis_index=column - 1,
                )
            )
            row -= 1
            column -= 1
        elif operation == "deletion":
            steps.append(
                AlignmentOperation(
                    operation=operation,
                    reference=str(reference[row - 1]),
                    hypothesis=None,
                    reference_index=row - 1,
                    hypothesis_index=None,
                )
            )
            row -= 1
        elif operation == "insertion":
            steps.append(
                AlignmentOperation(
                    operation=operation,
                    reference=None,
                    hypothesis=str(hypothesis[column - 1]),
                    reference_index=None,
                    hypothesis_index=column - 1,
                )
            )
            column -= 1
        else:
            break
    steps.reverse()
    return steps


def _metric_words(text: str) -> list[str]:
    return text.split() if text else []
