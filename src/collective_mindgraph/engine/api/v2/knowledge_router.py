"""Bounded subgraph and hybrid search for the knowledge canvas."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from collective_mindgraph.application.knowledge.layout import compute_layout
from collective_mindgraph.application.knowledge.subgraph import (
    DEFAULT_NODE_LIMIT,
    MAX_DEPTH,
    MAX_NODE_LIMIT,
    SubgraphEdge,
    SubgraphExpander,
)
from collective_mindgraph.application.memory.rank_fusion import RankedList, fuse

router = APIRouter(prefix="/api/v2/knowledge", tags=["knowledge"])


class SubgraphNode(BaseModel):
    id: str
    title: str
    kind: str
    x: float
    y: float


class SubgraphEdgeResponse(BaseModel):
    source_id: str
    target_id: str
    kind: str


class SubgraphResponse(BaseModel):
    root_id: str
    depth_reached: int
    truncated: bool
    omitted_neighbours: int
    node_limit: int
    nodes: list[SubgraphNode] = Field(default_factory=list)
    edges: list[SubgraphEdgeResponse] = Field(default_factory=list)


class FusedHit(BaseModel):
    id: str
    title: str
    score: float
    sources: list[str] = Field(default_factory=list)
    corroborated: bool = False


@router.get("/subgraph/{root_id}", response_model=SubgraphResponse)
async def subgraph(
    request: Request,
    root_id: str,
    depth: int = Query(default=2, ge=0, le=MAX_DEPTH),
    limit: int = Query(default=DEFAULT_NODE_LIMIT, ge=1, le=MAX_NODE_LIMIT),
    kind: str | None = Query(default=None),
) -> SubgraphResponse:
    """Return a bounded neighbourhood with reproducible positions."""

    database = request.app.state.engine_context.database
    with database.connect() as connection:
        if (
            connection.execute("SELECT 1 FROM knowledge_nodes WHERE id = ?", (root_id,)).fetchone()
            is None
        ):
            raise HTTPException(status_code=404, detail="The node does not exist.")

        def _neighbours(node_ids: Sequence[str]) -> list[SubgraphEdge]:
            placeholders = ",".join("?" for _ in node_ids)
            rows = connection.execute(
                f"""
                SELECT source_id, target_id, kind FROM knowledge_edges
                WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders})
                ORDER BY created_at, id
                """,
                (*node_ids, *node_ids),
            ).fetchall()
            return [
                SubgraphEdge(
                    source_id=str(row["source_id"]),
                    target_id=str(row["target_id"]),
                    kind=str(row["kind"]),
                )
                for row in rows
            ]

        result = SubgraphExpander(_neighbours).expand(root_id, depth=depth, limit=limit)
        placeholders = ",".join("?" for _ in result.node_ids)
        clause = f"SELECT id, title, kind FROM knowledge_nodes WHERE id IN ({placeholders})"
        parameters: list[object] = list(result.node_ids)
        if kind is not None:
            clause += " AND kind = ?"
            parameters.append(kind)
        detail = {
            str(row["id"]): (str(row["title"]), str(row["kind"]))
            for row in connection.execute(clause, parameters).fetchall()
        }

    visible = [node_id for node_id in result.node_ids if node_id in detail]
    positions = {
        position.node_id: position
        for position in compute_layout(
            visible,
            [(edge.source_id, edge.target_id) for edge in result.edges],
        )
    }
    return SubgraphResponse(
        root_id=result.root_id,
        depth_reached=result.depth_reached,
        truncated=result.truncated,
        omitted_neighbours=result.omitted_neighbours,
        node_limit=min(limit, MAX_NODE_LIMIT),
        nodes=[
            SubgraphNode(
                id=node_id,
                title=detail[node_id][0],
                kind=detail[node_id][1],
                x=positions[node_id].x,
                y=positions[node_id].y,
            )
            for node_id in visible
            if node_id in positions
        ],
        edges=[
            SubgraphEdgeResponse(
                source_id=edge.source_id,
                target_id=edge.target_id,
                kind=edge.kind,
            )
            for edge in result.edges
            if edge.source_id in detail and edge.target_id in detail
        ],
    )


@router.get("/search", response_model=list[FusedHit])
async def hybrid_search(
    request: Request,
    query: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[FusedHit]:
    """Fuse keyword and semantic results by rank, not by score.

    When embeddings are unavailable the keyword list is fused alone, so the
    endpoint degrades to keyword search rather than failing or silently
    returning semantic-only results it does not have.
    """

    context = request.app.state.engine_context
    keyword_ids, titles = _keyword_hits(context, query, limit)
    lists = [RankedList(source="keyword", identifiers=keyword_ids)]
    semantic_ids = _semantic_hits(context, query, limit)
    if semantic_ids:
        lists.append(RankedList(source="semantic", identifiers=semantic_ids))

    return [
        FusedHit(
            id=result.identifier,
            title=titles.get(result.identifier, ""),
            score=round(result.score, 6),
            sources=list(result.sources),
            corroborated=result.is_corroborated,
        )
        for result in fuse(lists, limit=limit)
    ]


def _keyword_hits(
    context: object, query: str, limit: int
) -> tuple[tuple[str, ...], dict[str, str]]:
    from collective_mindgraph.infrastructure.persistence.search_schema import (
        SEARCH_TABLE,
        build_match_expression,
        has_searchable_terms,
    )

    if not has_searchable_terms(query):
        return (), {}
    database = getattr(context, "database")
    with database.connect() as connection:
        rows = connection.execute(
            f"""
            SELECT s.node_id AS id, n.title AS title
            FROM {SEARCH_TABLE} AS s
            JOIN knowledge_nodes AS n ON n.id = s.node_id
            WHERE {SEARCH_TABLE} MATCH ?
            ORDER BY bm25({SEARCH_TABLE}), s.node_id
            LIMIT ?
            """,
            (build_match_expression(query), limit),
        ).fetchall()
    return tuple(str(row["id"]) for row in rows), {
        str(row["id"]): str(row["title"]) for row in rows
    }


def _semantic_hits(context: object, query: str, limit: int) -> tuple[str, ...]:
    search = getattr(context, "search_memory", None)
    if search is None:
        return ()
    try:
        matches = search.semantic_node_ids(query, limit=limit)
    except (AttributeError, NotImplementedError, RuntimeError):
        # Semantic search is optional. Failing honestly to keyword-only beats
        # reporting an error for a capability the install may not have.
        return ()
    return tuple(str(entry) for entry in matches)[:limit]


__all__ = ["router"]
