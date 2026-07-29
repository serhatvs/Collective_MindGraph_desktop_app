"""The `1.0.0` release decision, assembled from what is actually known.

This module exists to make one question answerable without optimism: may this
build be released? It refuses on anything unmeasured, unsigned, unreviewed, or
unavailable, and names each reason. A readiness report that could only say yes
would not be worth running.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from collective_mindgraph.application.transcription.evaluation.release_gates import (
    GateReport,
    build_report,
)

# Targets fixed by the production programme, in milliseconds.
KEYWORD_SEARCH_P95_MS = 200.0
SEMANTIC_SEARCH_P95_MS = 500.0
SYNC_ROUND_TRIP_P95_MS = 500.0
VISIBLE_CHANGE_MS = 5000.0
MIN_CANVAS_FPS = 30.0


@dataclass(frozen=True, slots=True)
class ReleaseBlocker:
    """One reason the release cannot proceed."""

    area: str
    reason: str
    resolvable_here: bool

    def __str__(self) -> str:
        origin = "" if self.resolvable_here else " (needs an external input)"
        return f"{self.area}: {self.reason}{origin}"


@dataclass(frozen=True, slots=True)
class PerformanceBudget:
    """Measured latencies against the published targets."""

    keyword_p95_ms: float | None = None
    semantic_p95_ms: float | None = None
    sync_round_trip_p95_ms: float | None = None
    visible_change_ms: float | None = None
    canvas_fps: float | None = None

    def blockers(self) -> tuple[ReleaseBlocker, ...]:
        checks: tuple[tuple[str, float | None, float, bool], ...] = (
            ("keyword search p95", self.keyword_p95_ms, KEYWORD_SEARCH_P95_MS, True),
            ("semantic search p95", self.semantic_p95_ms, SEMANTIC_SEARCH_P95_MS, True),
            ("sync round trip p95", self.sync_round_trip_p95_ms, SYNC_ROUND_TRIP_P95_MS, True),
            ("visible change", self.visible_change_ms, VISIBLE_CHANGE_MS, True),
        )
        found: list[ReleaseBlocker] = []
        for name, measured, budget, upper in checks:
            if measured is None:
                found.append(ReleaseBlocker("performance", f"{name} was not measured", True))
            elif upper and measured > budget:
                found.append(
                    ReleaseBlocker(
                        "performance",
                        f"{name} is {measured:g} ms against a {budget:g} ms budget",
                        True,
                    )
                )
        if self.canvas_fps is None:
            found.append(ReleaseBlocker("performance", "canvas frame rate was not measured", True))
        elif self.canvas_fps < MIN_CANVAS_FPS:
            found.append(
                ReleaseBlocker(
                    "performance",
                    f"canvas runs at {self.canvas_fps:g} FPS against a {MIN_CANVAS_FPS:g} floor",
                    True,
                )
            )
        return tuple(found)


@dataclass(frozen=True, slots=True)
class ExternalInput:
    """Something the release needs that this repository cannot produce."""

    name: str
    available: bool = False

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("An external input needs a name.")


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    """Every blocker, and the single verdict they add up to."""

    blockers: tuple[ReleaseBlocker, ...] = field(default_factory=tuple)
    quality: GateReport | None = None

    @property
    def may_release(self) -> bool:
        return not self.blockers

    @property
    def external_blockers(self) -> tuple[ReleaseBlocker, ...]:
        return tuple(entry for entry in self.blockers if not entry.resolvable_here)

    @property
    def internal_blockers(self) -> tuple[ReleaseBlocker, ...]:
        return tuple(entry for entry in self.blockers if entry.resolvable_here)

    def summary(self) -> str:
        if self.may_release:
            return "Every release gate is met; 1.0.0 may ship."
        return (
            f"{len(self.blockers)} blocker(s): "
            f"{len(self.internal_blockers)} to resolve here, "
            f"{len(self.external_blockers)} needing external inputs."
        )


def build_readiness_report(
    *,
    quality: GateReport | None = None,
    performance: PerformanceBudget | None = None,
    external_inputs: Sequence[ExternalInput] = (),
    open_defects: int = 0,
    unresolved_security_findings: int = 0,
    high_severity_vulnerabilities: int = 0,
    artifacts_signed: bool = False,
    security_scanners_available: bool = True,
) -> ReadinessReport:
    """Decide whether `1.0.0` may ship, and say why not when it may not."""

    gates = quality or build_report()
    blockers: list[ReleaseBlocker] = []

    for gate in gates.blocking:
        resolvable = gate.name not in {
            "clean_median_wer",
            "noisy_far_field_wer",
            "domain_term_recall",
            "diarization_error_rate",
        }
        blockers.append(
            ReleaseBlocker("quality", f"{gate.name} is {gate.outcome.value}", resolvable)
        )

    blockers.extend((performance or PerformanceBudget()).blockers())

    if open_defects > 0:
        blockers.append(ReleaseBlocker("defects", f"{open_defects} open P0/P1 defect(s)", True))
    if unresolved_security_findings > 0:
        blockers.append(
            ReleaseBlocker(
                "security",
                f"{unresolved_security_findings} unresolved security finding(s)",
                True,
            )
        )
    if high_severity_vulnerabilities > 0:
        blockers.append(
            ReleaseBlocker(
                "security",
                f"{high_severity_vulnerabilities} high or critical dependency vulnerability",
                True,
            )
        )
    if not security_scanners_available:
        # A scanner that cannot run has not found nothing.
        blockers.append(
            ReleaseBlocker(
                "security",
                "code scanning and dependency review cannot run on this plan",
                False,
            )
        )
    if not artifacts_signed:
        blockers.append(ReleaseBlocker("packaging", "release artefacts are not signed", False))
    for required in external_inputs:
        if not required.available:
            blockers.append(ReleaseBlocker("external", f"{required.name} is not available", False))

    return ReadinessReport(blockers=tuple(blockers), quality=gates)


def format_readiness(report: ReadinessReport) -> Sequence[str]:
    """Render the decision as lines an operator can act on."""

    lines = [report.summary()]
    for blocker in report.blockers:
        lines.append(f"  - {blocker}")
    return lines


__all__ = [
    "KEYWORD_SEARCH_P95_MS",
    "MIN_CANVAS_FPS",
    "SEMANTIC_SEARCH_P95_MS",
    "SYNC_ROUND_TRIP_P95_MS",
    "VISIBLE_CHANGE_MS",
    "ExternalInput",
    "PerformanceBudget",
    "ReadinessReport",
    "ReleaseBlocker",
    "build_readiness_report",
    "format_readiness",
]
