"""Release gates for transcription and retrieval quality.

A gate can be met, not met, or **unevaluated**. The third state exists because
the alternative is worse: a suite with no reference data would otherwise report
green, and "no measurement" would be indistinguishable from "measured and
fine". Nothing here invents a number it did not measure.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

# Thresholds fixed by the production programme.
MAX_CLEAN_WER = 0.20
MAX_NOISY_WER = 0.35
MIN_DOMAIN_TERM_RECALL = 0.85
MAX_DIARIZATION_ERROR = 0.25
MIN_RETRIEVAL_RECALL_AT_10 = 0.85
REQUIRED_CITATION_PRECISION = 1.0
MAX_UNSUPPORTED_CLAIMS = 0

# Minimum evidence the programme requires before a number means anything.
MIN_MEETINGS = 30
MIN_AUDIO_HOURS = 20.0
MIN_LABELLED_QUERIES = 500


class GateOutcome(StrEnum):
    MET = "met"
    NOT_MET = "not_met"
    UNEVALUATED = "unevaluated"


@dataclass(frozen=True, slots=True)
class GateResult:
    """One gate, its threshold, and what was actually measured."""

    name: str
    outcome: GateOutcome
    threshold: float
    measured: float | None = None
    detail: str = ""

    @property
    def blocks_release(self) -> bool:
        """Anything not positively met blocks the release."""

        return self.outcome is not GateOutcome.MET


@dataclass(frozen=True, slots=True)
class AudioEvidence:
    """The corpus a transcription claim rests on."""

    meetings: int = 0
    audio_hours: float = 0.0
    clean_wer: float | None = None
    noisy_wer: float | None = None
    domain_term_recall: float | None = None
    diarization_error: float | None = None
    consent_documented: bool = False

    @property
    def is_sufficient(self) -> bool:
        """Whether the corpus is large enough and licensed to draw on."""

        return (
            self.meetings >= MIN_MEETINGS
            and self.audio_hours >= MIN_AUDIO_HOURS
            and self.consent_documented
        )


@dataclass(frozen=True, slots=True)
class RetrievalEvidence:
    """The labelled set a retrieval claim rests on."""

    labelled_queries: int = 0
    recall_at_10: float | None = None
    citation_precision: float | None = None
    unsupported_claims: int | None = None

    @property
    def is_sufficient(self) -> bool:
        return self.labelled_queries >= MIN_LABELLED_QUERIES


@dataclass(frozen=True, slots=True)
class GateReport:
    """Every gate, and whether the release may proceed."""

    results: tuple[GateResult, ...] = field(default_factory=tuple)

    @property
    def blocking(self) -> tuple[GateResult, ...]:
        return tuple(result for result in self.results if result.blocks_release)

    @property
    def unevaluated(self) -> tuple[GateResult, ...]:
        return tuple(result for result in self.results if result.outcome is GateOutcome.UNEVALUATED)

    @property
    def may_release(self) -> bool:
        """A release needs every gate positively met, not merely not-failed."""

        return bool(self.results) and not self.blocking

    def summary(self) -> str:
        if not self.results:
            return "No gates were evaluated."
        if self.may_release:
            return f"All {len(self.results)} quality gates are met."
        unevaluated = len(self.unevaluated)
        failed = len(self.blocking) - unevaluated
        return f"{failed} gate(s) not met and {unevaluated} unevaluated; the release is blocked."


def evaluate_audio(evidence: AudioEvidence) -> tuple[GateResult, ...]:
    """Evaluate the transcription gates against a corpus."""

    reason = _audio_shortfall(evidence)
    return (
        _at_most("clean_median_wer", evidence.clean_wer, MAX_CLEAN_WER, reason),
        _at_most("noisy_far_field_wer", evidence.noisy_wer, MAX_NOISY_WER, reason),
        _at_least(
            "domain_term_recall",
            evidence.domain_term_recall,
            MIN_DOMAIN_TERM_RECALL,
            reason,
        ),
        _at_most(
            "diarization_error_rate",
            evidence.diarization_error,
            MAX_DIARIZATION_ERROR,
            reason,
        ),
    )


def evaluate_retrieval(evidence: RetrievalEvidence) -> tuple[GateResult, ...]:
    """Evaluate the retrieval gates against a labelled set."""

    reason = "" if evidence.is_sufficient else f"fewer than {MIN_LABELLED_QUERIES} labelled queries"
    unsupported = (
        float(evidence.unsupported_claims) if evidence.unsupported_claims is not None else None
    )
    return (
        _at_least(
            "retrieval_recall_at_10", evidence.recall_at_10, MIN_RETRIEVAL_RECALL_AT_10, reason
        ),
        _at_least(
            "citation_precision",
            evidence.citation_precision,
            REQUIRED_CITATION_PRECISION,
            reason,
        ),
        _at_most("unsupported_claims", unsupported, float(MAX_UNSUPPORTED_CLAIMS), reason),
    )


def build_report(
    audio: AudioEvidence | None = None,
    retrieval: RetrievalEvidence | None = None,
) -> GateReport:
    """Combine every gate into one release decision."""

    results: list[GateResult] = []
    results.extend(evaluate_audio(audio or AudioEvidence()))
    results.extend(evaluate_retrieval(retrieval or RetrievalEvidence()))
    return GateReport(results=tuple(results))


def _audio_shortfall(evidence: AudioEvidence) -> str:
    if not evidence.consent_documented:
        return "recording consent and licensing are not documented"
    missing: list[str] = []
    if evidence.meetings < MIN_MEETINGS:
        missing.append(f"{evidence.meetings}/{MIN_MEETINGS} meetings")
    if evidence.audio_hours < MIN_AUDIO_HOURS:
        missing.append(f"{evidence.audio_hours:g}/{MIN_AUDIO_HOURS:g} hours")
    return ", ".join(missing)


def _at_most(name: str, measured: float | None, threshold: float, reason: str) -> GateResult:
    return _decide(name, measured, threshold, reason, lambda value: value <= threshold)


def _at_least(name: str, measured: float | None, threshold: float, reason: str) -> GateResult:
    return _decide(name, measured, threshold, reason, lambda value: value >= threshold)


def _decide(
    name: str,
    measured: float | None,
    threshold: float,
    reason: str,
    passes: object,
) -> GateResult:
    if reason or measured is None:
        return GateResult(
            name=name,
            outcome=GateOutcome.UNEVALUATED,
            threshold=threshold,
            measured=measured,
            detail=reason or "no measurement was supplied",
        )
    assert callable(passes)
    met = bool(passes(measured))
    return GateResult(
        name=name,
        outcome=GateOutcome.MET if met else GateOutcome.NOT_MET,
        threshold=threshold,
        measured=measured,
        detail="" if met else f"measured {measured:g} against {threshold:g}",
    )


def format_report(report: GateReport) -> Sequence[str]:
    """Render the report as lines an operator can read."""

    lines = [report.summary()]
    for result in report.results:
        measured = "—" if result.measured is None else f"{result.measured:g}"
        line = f"  {result.outcome.value:<12} {result.name} (measured {measured})"
        lines.append(f"{line} — {result.detail}" if result.detail else line)
    return lines


__all__ = [
    "MAX_CLEAN_WER",
    "MAX_DIARIZATION_ERROR",
    "MAX_NOISY_WER",
    "MIN_AUDIO_HOURS",
    "MIN_DOMAIN_TERM_RECALL",
    "MIN_LABELLED_QUERIES",
    "MIN_MEETINGS",
    "MIN_RETRIEVAL_RECALL_AT_10",
    "AudioEvidence",
    "GateOutcome",
    "GateReport",
    "GateResult",
    "RetrievalEvidence",
    "build_report",
    "evaluate_audio",
    "evaluate_retrieval",
    "format_report",
]
