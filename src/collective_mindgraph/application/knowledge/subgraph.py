"""Bounded subgraph expansion for the knowledge canvas.

A canvas that tries to draw an entire graph stops being readable and stops
being fast. Expansion is therefore bounded twice: by depth, and by a hard cap
on visible nodes that the caller cannot raise.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

DEFAULT_NODE_LIMIT = 150
MAX_NODE_LIMIT = 500
MAX_DEPTH = 6


@dataclass(frozen=True, slots=True)
class SubgraphEdge:
    """One relationship between two nodes in the returned view."""

    source_id: str
    target_id: str
    kind: str

    def other(self, node_id: str) -> str | None:
        if node_id == self.source_id:
            return self.target_id
        if node_id == self.target_id:
            return self.source_id
        return None


@dataclass(frozen=True, slots=True)
class Subgraph:
    """What the canvas draws, plus what it deliberately left out."""

    root_id: str
    node_ids: tuple[str, ...] = field(default_factory=tuple)
    edges: tuple[SubgraphEdge, ...] = field(default_factory=tuple)
    depth_reached: int = 0
    truncated: bool = False
    omitted_neighbours: int = 0

    @property
    def node_count(self) -> int:
        return len(self.node_ids)


class SubgraphExpander:
    """Breadth-first expansion that stops at the declared bounds."""

    def __init__(self, neighbours: Callable[[Sequence[str]], Iterable[SubgraphEdge]]) -> None:
        self._neighbours = neighbours

    def expand(
        self,
        root_id: str,
        *,
        depth: int = 2,
        limit: int = DEFAULT_NODE_LIMIT,
    ) -> Subgraph:
        """Return the neighbourhood of one node within the bounds.

        Expansion is breadth-first so that truncation drops the most distant
        nodes rather than an arbitrary slice, and the result reports both that
        it truncated and how many neighbours it left out.
        """

        if not root_id.strip():
            raise ValueError("A subgraph needs a root node.")
        if not 0 <= depth <= MAX_DEPTH:
            raise ValueError(f"Depth must be between 0 and {MAX_DEPTH}.")
        if limit < 1:
            raise ValueError("A subgraph limit must be at least one.")
        # The cap is the product's, not the caller's.
        effective_limit = min(limit, MAX_NODE_LIMIT)

        visited: dict[str, int] = {root_id: 0}
        order: list[str] = [root_id]
        collected: dict[tuple[str, str, str], SubgraphEdge] = {}
        frontier: deque[str] = deque([root_id])
        truncated = False
        omitted = 0
        depth_reached = 0

        while frontier and not truncated:
            level = list(frontier)
            frontier.clear()
            level_depth = visited[level[0]]
            if level_depth >= depth:
                break
            for edge in self._neighbours(level):
                for node_id in (edge.source_id, edge.target_id):
                    if node_id in visited:
                        continue
                    if len(order) >= effective_limit:
                        truncated = True
                        omitted += 1
                        continue
                    visited[node_id] = level_depth + 1
                    order.append(node_id)
                    frontier.append(node_id)
                    depth_reached = max(depth_reached, level_depth + 1)
                if edge.source_id in visited and edge.target_id in visited:
                    collected[(edge.source_id, edge.target_id, edge.kind)] = edge

        return Subgraph(
            root_id=root_id,
            node_ids=tuple(order),
            edges=tuple(collected.values()),
            depth_reached=depth_reached,
            truncated=truncated,
            omitted_neighbours=omitted,
        )


__all__ = [
    "DEFAULT_NODE_LIMIT",
    "MAX_DEPTH",
    "MAX_NODE_LIMIT",
    "Subgraph",
    "SubgraphEdge",
    "SubgraphExpander",
]
