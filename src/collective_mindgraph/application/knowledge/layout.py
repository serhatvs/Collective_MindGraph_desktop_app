"""Deterministic force-directed layout for the knowledge canvas.

The same graph must always produce the same picture: a canvas that reshuffles
on every open is disorienting, and a layout that depends on dictionary order or
an unseeded generator cannot be reproduced in a bug report. Positions here are
a pure function of the node identifiers and the edges.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass

DEFAULT_ITERATIONS = 120
DEFAULT_CANVAS = 1000.0
MIN_SEPARATION = 1e-4


@dataclass(frozen=True, slots=True)
class NodePosition:
    """Where one node sits on the canvas."""

    node_id: str
    x: float
    y: float


def initial_position(node_id: str, *, canvas: float = DEFAULT_CANVAS) -> tuple[float, float]:
    """Place a node on a circle at an angle derived from its identifier.

    Seeding from the identifier rather than a random generator is what makes
    the whole layout reproducible without carrying a seed around.
    """

    digest = hashlib.sha256(node_id.encode("utf-8")).digest()
    angle = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF * 2 * math.pi
    radius = (0.25 + int.from_bytes(digest[4:6], "big") / 0xFFFF * 0.25) * canvas
    return (canvas / 2 + radius * math.cos(angle), canvas / 2 + radius * math.sin(angle))


def compute_layout(
    node_ids: Sequence[str],
    edges: Sequence[tuple[str, str]],
    *,
    iterations: int = DEFAULT_ITERATIONS,
    canvas: float = DEFAULT_CANVAS,
    pinned: dict[str, tuple[float, float]] | None = None,
) -> tuple[NodePosition, ...]:
    """Lay out a graph, honouring pinned nodes.

    Returns positions in the order the nodes were given, so a caller can zip
    them against its own list without re-matching by identifier.
    """

    if iterations < 1:
        raise ValueError("Layout needs at least one iteration.")
    if canvas <= 0:
        raise ValueError("The canvas must have a positive size.")
    unique = list(dict.fromkeys(node_ids))
    if not unique:
        return ()
    fixed = dict(pinned or {})

    positions = {node_id: initial_position(node_id, canvas=canvas) for node_id in unique}
    positions.update({node_id: point for node_id, point in fixed.items() if node_id in positions})

    adjacency = [
        (source, target)
        for source, target in edges
        if source in positions and target in positions and source != target
    ]
    ideal = canvas / math.sqrt(len(unique)) if len(unique) > 1 else canvas
    temperature = canvas / 10

    for _ in range(iterations):
        displacement = {node_id: [0.0, 0.0] for node_id in unique}
        for index, first in enumerate(unique):
            for second in unique[index + 1 :]:
                dx, dy, distance = _delta(positions[first], positions[second])
                repulsion = ideal * ideal / distance
                displacement[first][0] += dx / distance * repulsion
                displacement[first][1] += dy / distance * repulsion
                displacement[second][0] -= dx / distance * repulsion
                displacement[second][1] -= dy / distance * repulsion
        for source, target in adjacency:
            dx, dy, distance = _delta(positions[source], positions[target])
            attraction = distance * distance / ideal
            displacement[source][0] -= dx / distance * attraction
            displacement[source][1] -= dy / distance * attraction
            displacement[target][0] += dx / distance * attraction
            displacement[target][1] += dy / distance * attraction

        for node_id in unique:
            if node_id in fixed:
                continue
            dx, dy = displacement[node_id]
            magnitude = max(math.hypot(dx, dy), MIN_SEPARATION)
            step = min(magnitude, temperature)
            x = positions[node_id][0] + dx / magnitude * step
            y = positions[node_id][1] + dy / magnitude * step
            positions[node_id] = (_clamp(x, canvas), _clamp(y, canvas))
        temperature = max(temperature * 0.92, canvas / 1000)

    return tuple(
        NodePosition(node_id=node_id, x=positions[node_id][0], y=positions[node_id][1])
        for node_id in node_ids
        if node_id in positions
    )


def _delta(
    first: tuple[float, float],
    second: tuple[float, float],
) -> tuple[float, float, float]:
    dx = first[0] - second[0]
    dy = first[1] - second[1]
    return dx, dy, max(math.hypot(dx, dy), MIN_SEPARATION)


def _clamp(value: float, canvas: float) -> float:
    return min(max(value, 0.0), canvas)


__all__ = [
    "DEFAULT_CANVAS",
    "DEFAULT_ITERATIONS",
    "NodePosition",
    "compute_layout",
    "initial_position",
]
