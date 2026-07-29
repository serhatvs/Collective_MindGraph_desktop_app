"""Reciprocal rank fusion for hybrid retrieval.

Keyword relevance and vector similarity are not on the same scale, so their
scores cannot be added. Fusion uses each result's *rank* instead, which is why
a keyword hit at position one and a semantic hit at position one contribute
equally regardless of how the two engines happen to score.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

# The constant from the original formulation. It damps the influence of the
# very top ranks so that one engine cannot dominate a fused list on its own.
DEFAULT_RANK_CONSTANT = 60


@dataclass(frozen=True, slots=True)
class RankedList:
    """One engine's results, best first."""

    source: str
    identifiers: tuple[str, ...]
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("A ranked list needs a source name.")
        if self.weight <= 0:
            raise ValueError("A ranked list weight must be positive.")
        if len(set(self.identifiers)) != len(self.identifiers):
            raise ValueError("A ranked list cannot repeat an identifier.")


@dataclass(frozen=True, slots=True)
class FusedResult:
    """One identifier and the evidence for where it placed."""

    identifier: str
    score: float
    ranks: dict[str, int] = field(default_factory=dict)

    @property
    def sources(self) -> tuple[str, ...]:
        return tuple(sorted(self.ranks))

    @property
    def is_corroborated(self) -> bool:
        """Whether more than one engine surfaced this result."""

        return len(self.ranks) > 1


def fuse(
    lists: Sequence[RankedList],
    *,
    limit: int | None = None,
    rank_constant: int = DEFAULT_RANK_CONSTANT,
) -> tuple[FusedResult, ...]:
    """Combine ranked lists into one ordering.

    Ties break on the identifier so the same inputs always produce the same
    output; a retrieval order that shifts between runs is not reproducible and
    cannot be evaluated.
    """

    if rank_constant < 1:
        raise ValueError("The rank constant must be at least one.")
    if limit is not None and limit < 1:
        raise ValueError("A fusion limit must be at least one.")

    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    for ranked in lists:
        for position, identifier in enumerate(ranked.identifiers, start=1):
            scores[identifier] = scores.get(identifier, 0.0) + ranked.weight / (
                rank_constant + position
            )
            ranks.setdefault(identifier, {})[ranked.source] = position

    ordered = sorted(scores.items(), key=lambda entry: (-entry[1], entry[0]))
    results = tuple(
        FusedResult(identifier=identifier, score=score, ranks=dict(ranks[identifier]))
        for identifier, score in ordered
    )
    return results[:limit] if limit is not None else results


__all__ = ["DEFAULT_RANK_CONSTANT", "FusedResult", "RankedList", "fuse"]
