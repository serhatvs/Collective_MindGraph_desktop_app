"""Deterministic, human-reference-based transcription metrics.

The default normalization is Turkish-aware: it preserves Turkish letters,
normalizes apostrophe variants, lowercases dotted/dotless I correctly, removes
punctuation, and collapses whitespace. Metrics are never produced when the
reference is missing, empty, or explicitly excluded by the caller.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
import unicodedata
from typing import Any, Iterable, Sequence, TypeVar


_T = TypeVar("_T")
_APOSTROPHES = "\u2018\u2019\u02bc\u0060\u00b4\u2032"
_INTEGER_RE = re.compile(r"(?<![\w])\d+(?![\w])", flags=re.UNICODE)


@dataclass(frozen=True, slots=True)
class NormalizationPolicy:
    language: str = "tr"
    lowercase: bool = True
    remove_punctuation: bool = True
    normalize_whitespace: bool = True
    normalize_apostrophes: bool = True
    normalize_numbers: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "NormalizationPolicy":
        if not value:
            return cls()
        allowed = {field_name for field_name in cls.__dataclass_fields__}
        return cls(**{key: value[key] for key in allowed if key in value})


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
        return self.word_distance / self.reference_word_count if self.reference_word_count else None

    @property
    def cer(self) -> float | None:
        return (
            self.character_distance / self.reference_character_count
            if self.reference_character_count
            else None
        )

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


@dataclass(frozen=True, slots=True)
class TextEvaluation:
    raw: MetricResult
    normalized: MetricResult
    normalization_policy: NormalizationPolicy

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw.to_dict(),
            "normalized": self.normalized.to_dict(),
            "normalization_policy": self.normalization_policy.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class DomainTermEvaluation:
    total_reference_occurrences: int
    correctly_recognized_occurrences: int
    missing_occurrences: int
    substitution_occurrences: int
    per_term: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def accuracy(self) -> float | None:
        if not self.total_reference_occurrences:
            return None
        return self.correctly_recognized_occurrences / self.total_reference_occurrences

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_reference_term_occurrences": self.total_reference_occurrences,
            "correctly_recognized_occurrences": self.correctly_recognized_occurrences,
            "missing_occurrences": self.missing_occurrences,
            "substitution_occurrences": self.substitution_occurrences,
            "domain_term_accuracy": self.accuracy,
            "per_term": self.per_term,
        }


def normalize_text(text: str, policy: NormalizationPolicy | None = None) -> str:
    """Normalize text deterministically without transliterating Turkish letters."""

    selected = policy or NormalizationPolicy()
    value = unicodedata.normalize("NFC", str(text))
    if selected.normalize_apostrophes:
        value = value.translate(str.maketrans({char: "'" for char in _APOSTROPHES}))
    if selected.lowercase:
        value = _language_aware_lower(value, selected.language)
    if selected.normalize_numbers:
        value = _INTEGER_RE.sub(lambda match: _normalize_integer(match.group(0), selected.language), value)
    if selected.remove_punctuation:
        value = "".join(" " if unicodedata.category(char).startswith("P") else char for char in value)
    if selected.normalize_whitespace:
        value = " ".join(value.split())
    return unicodedata.normalize("NFC", value.strip())


def evaluate_transcription(
    reference: str | None,
    hypothesis: str,
    *,
    policy: NormalizationPolicy | None = None,
    excluded: bool = False,
) -> TextEvaluation | None:
    """Return raw and normalized metrics, or ``None`` without a usable reference."""

    if excluded or reference is None or not str(reference).strip():
        return None
    selected = policy or NormalizationPolicy()
    raw_reference = str(reference)
    raw_hypothesis = str(hypothesis)
    normalized_reference = normalize_text(raw_reference, selected)
    normalized_hypothesis = normalize_text(raw_hypothesis, selected)
    return TextEvaluation(
        raw=_metric_result(raw_reference, raw_hypothesis, exact=True),
        normalized=_metric_result(normalized_reference, normalized_hypothesis, exact=False),
        normalization_policy=selected,
    )


def word_error_rate(
    reference: str | None,
    hypothesis: str,
    *,
    policy: NormalizationPolicy | None = None,
) -> float | None:
    result = evaluate_transcription(reference, hypothesis, policy=policy)
    return result.normalized.wer if result else None


def character_error_rate(
    reference: str | None,
    hypothesis: str,
    *,
    policy: NormalizationPolicy | None = None,
) -> float | None:
    result = evaluate_transcription(reference, hypothesis, policy=policy)
    return result.normalized.cer if result else None


def compare_to_reference(
    reference: str | None,
    hypothesis: str,
    *,
    policy: NormalizationPolicy | None = None,
) -> dict[str, Any] | None:
    """Compatibility-shaped comparison for the existing benchmark scripts."""

    evaluation = evaluate_transcription(reference, hypothesis, policy=policy)
    if evaluation is None:
        return None
    normalized = evaluation.normalized
    return {
        "wer": normalized.wer,
        "cer": normalized.cer,
        "reference_word_count": normalized.reference_word_count,
        "hypothesis_word_count": normalized.hypothesis_word_count,
        "substitution_count": len(normalized.substitutions),
        "deletion_count": len(normalized.deletions),
        "insertion_count": len(normalized.insertions),
        "notable_substitutions": [
            {"reference": item.reference, "actual": item.hypothesis}
            for item in normalized.substitutions[:15]
        ],
        "notable_deletions": [item.reference for item in normalized.deletions[:15]],
        "notable_insertions": [item.hypothesis for item in normalized.insertions[:15]],
        "raw": evaluation.raw.to_dict(),
        "normalized": normalized.to_dict(),
        "normalization_policy": evaluation.normalization_policy.to_dict(),
    }


def aggregate_metric_results(results: Iterable[MetricResult]) -> dict[str, Any] | None:
    items = list(results)
    if not items:
        return None
    reference_words = sum(item.reference_word_count for item in items)
    hypothesis_words = sum(item.hypothesis_word_count for item in items)
    reference_characters = sum(item.reference_character_count for item in items)
    hypothesis_characters = sum(item.hypothesis_character_count for item in items)
    word_distance = sum(item.word_distance for item in items)
    character_distance = sum(item.character_distance for item in items)
    return {
        "recording_count": len(items),
        "reference_word_count": reference_words,
        "hypothesis_word_count": hypothesis_words,
        "reference_character_count": reference_characters,
        "hypothesis_character_count": hypothesis_characters,
        "word_distance": word_distance,
        "character_distance": character_distance,
        "wer": word_distance / reference_words if reference_words else None,
        "cer": character_distance / reference_characters if reference_characters else None,
        "substitution_count": sum(len(item.substitutions) for item in items),
        "deletion_count": sum(len(item.deletions) for item in items),
        "insertion_count": sum(len(item.insertions) for item in items),
    }


def edit_distance_with_operations(
    reference: Sequence[str],
    hypothesis: Sequence[str],
) -> tuple[int, dict[str, list[Any]]]:
    """Return Levenshtein distance and compatibility-shaped edit details."""

    alignment = _align(reference, hypothesis)
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


def evaluate_domain_terms(
    reference: str | None,
    hypothesis: str,
    terms: Iterable[str],
    *,
    policy: NormalizationPolicy | None = None,
    excluded: bool = False,
) -> DomainTermEvaluation | None:
    """Evaluate glossary occurrences through word alignment.

    Credit is tied to the aligned hypothesis position of each reference
    occurrence, so a term appearing elsewhere in the hypothesis is not counted.
    """

    if excluded or reference is None or not str(reference).strip():
        return None
    selected = policy or NormalizationPolicy()
    reference_tokens = _normalized_words(reference, selected)
    hypothesis_tokens = _normalized_words(hypothesis, selected)
    alignment = _align(reference_tokens, hypothesis_tokens)
    reference_to_hypothesis = {
        step.reference_index: step.hypothesis_index
        for step in alignment
        if step.reference_index is not None and step.hypothesis_index is not None
    }

    per_term: dict[str, dict[str, Any]] = {}
    seen_terms: set[str] = set()
    total = correct = missing = substitutions = 0
    for display_term in terms:
        clean_display = " ".join(str(display_term).split())
        normalized_term = normalize_text(clean_display, selected)
        if not normalized_term or normalized_term in seen_terms:
            continue
        seen_terms.add(normalized_term)
        term_tokens = normalized_term.split()
        occurrences = _find_occurrences(reference_tokens, term_tokens)
        if not occurrences:
            continue
        details: list[dict[str, Any]] = []
        term_correct = term_missing = term_substitutions = 0
        for start_index in occurrences:
            expected_indices = list(range(start_index, start_index + len(term_tokens)))
            mapped = [reference_to_hypothesis.get(index) for index in expected_indices]
            is_contiguous = all(index is not None for index in mapped) and mapped == list(
                range(mapped[0], mapped[0] + len(mapped))
            )
            recognized = bool(
                is_contiguous
                and [hypothesis_tokens[index] for index in mapped if index is not None] == term_tokens
            )
            if recognized:
                status = "correct"
                actual = clean_display
                term_correct += 1
            else:
                available = [index for index in mapped if index is not None]
                if not available:
                    status = "missing"
                    actual = ""
                    term_missing += 1
                else:
                    status = "substitution"
                    lower = min(available)
                    upper = max(available)
                    actual = " ".join(hypothesis_tokens[lower : upper + 1])
                    term_substitutions += 1
            details.append(
                {
                    "reference_start_word": start_index,
                    "status": status,
                    "reference": clean_display,
                    "hypothesis": actual,
                }
            )
        count = len(occurrences)
        total += count
        correct += term_correct
        missing += term_missing
        substitutions += term_substitutions
        per_term[clean_display] = {
            "reference_occurrences": count,
            "correct_occurrences": term_correct,
            "missing_occurrences": term_missing,
            "substitution_occurrences": term_substitutions,
            "accuracy": term_correct / count,
            "occurrences": details,
        }
    return DomainTermEvaluation(
        total_reference_occurrences=total,
        correctly_recognized_occurrences=correct,
        missing_occurrences=missing,
        substitution_occurrences=substitutions,
        per_term=per_term,
    )


def _metric_result(reference: str, hypothesis: str, *, exact: bool) -> MetricResult:
    reference_words = reference.split() if exact else _metric_words(reference)
    hypothesis_words = hypothesis.split() if exact else _metric_words(hypothesis)
    word_alignment = _align(reference_words, hypothesis_words)
    substitutions = tuple(step for step in word_alignment if step.operation == "substitution")
    deletions = tuple(step for step in word_alignment if step.operation == "deletion")
    insertions = tuple(step for step in word_alignment if step.operation == "insertion")
    reference_characters = list(reference)
    hypothesis_characters = list(hypothesis)
    character_alignment = _align(reference_characters, hypothesis_characters)
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


def _align(reference: Sequence[_T], hypothesis: Sequence[_T]) -> list[AlignmentOperation]:
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


def _normalized_words(text: str, policy: NormalizationPolicy) -> list[str]:
    normalized = normalize_text(text, policy)
    return normalized.split() if normalized else []


def _find_occurrences(tokens: list[str], term_tokens: list[str]) -> list[int]:
    if not term_tokens or len(term_tokens) > len(tokens):
        return []
    starts: list[int] = []
    cursor = 0
    while cursor <= len(tokens) - len(term_tokens):
        if tokens[cursor : cursor + len(term_tokens)] == term_tokens:
            starts.append(cursor)
            cursor += len(term_tokens)
        else:
            cursor += 1
    return starts


def _language_aware_lower(text: str, language: str) -> str:
    if language.casefold().startswith("tr"):
        return text.translate(str.maketrans({"I": "ı", "İ": "i"})).lower()
    return text.casefold()


def _normalize_integer(value: str, language: str) -> str:
    if not language.casefold().startswith("tr"):
        return str(int(value))
    number = int(value)
    if number > 999_999_999:
        return str(number)
    return _turkish_integer_words(number)


def _turkish_integer_words(number: int) -> str:
    ones = ("sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz")
    tens = ("", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan")

    def under_thousand(value: int) -> list[str]:
        parts: list[str] = []
        hundreds, remainder = divmod(value, 100)
        if hundreds:
            if hundreds > 1:
                parts.append(ones[hundreds])
            parts.append("yüz")
        ten, one = divmod(remainder, 10)
        if ten:
            parts.append(tens[ten])
        if one:
            parts.append(ones[one])
        return parts

    if number == 0:
        return ones[0]
    parts: list[str] = []
    millions, remainder = divmod(number, 1_000_000)
    thousands, units = divmod(remainder, 1_000)
    if millions:
        parts.extend(under_thousand(millions))
        parts.append("milyon")
    if thousands:
        if thousands != 1:
            parts.extend(under_thousand(thousands))
        parts.append("bin")
    parts.extend(under_thousand(units))
    return " ".join(parts)
