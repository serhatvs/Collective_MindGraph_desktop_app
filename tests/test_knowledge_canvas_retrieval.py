"""FTS5 search, rank fusion, bounded subgraphs, and deterministic layout."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from collective_mindgraph.application.knowledge.layout import (
    NodePosition,
    compute_layout,
    initial_position,
)
from collective_mindgraph.application.knowledge.subgraph import (
    DEFAULT_NODE_LIMIT,
    MAX_DEPTH,
    MAX_NODE_LIMIT,
    SubgraphEdge,
    SubgraphExpander,
)
from collective_mindgraph.application.memory.rank_fusion import (
    DEFAULT_RANK_CONSTANT,
    RankedList,
    fuse,
)
from collective_mindgraph.infrastructure.persistence.search_schema import (
    SEARCH_TABLE,
    build_match_expression,
    fold_turkish,
    has_searchable_terms,
    rebuild_search_index,
)

# Rank fusion --------------------------------------------------------------


def test_fusion_uses_rank_not_score():
    """An engine with huge scores must not dominate one with small scores."""

    keyword = RankedList(source="keyword", identifiers=("a", "b", "c"))
    semantic = RankedList(source="semantic", identifiers=("c", "b", "a"))
    fused = {entry.identifier: entry.score for entry in fuse([keyword, semantic])}
    # Mirrored input gives the outer pair identical scores: only rank matters,
    # and each of them placed first once and last once.
    assert fused["a"] == pytest.approx(fused["c"])
    # The middle element is not tied with them; 1/62 + 1/62 is very slightly
    # below 1/61 + 1/63, which is exactly the damping the constant provides.
    assert fused["b"] < fused["a"]
    assert [entry.identifier for entry in fuse([keyword, semantic])] == ["a", "c", "b"]


def test_agreement_between_engines_outranks_a_single_top_hit():
    keyword = RankedList(source="keyword", identifiers=("solo", "shared"))
    semantic = RankedList(source="semantic", identifiers=("shared", "other"))
    fused = fuse([keyword, semantic])
    assert fused[0].identifier == "shared"
    assert fused[0].is_corroborated is True
    assert fused[0].sources == ("keyword", "semantic")
    assert all(not entry.is_corroborated for entry in fused[1:])


def test_fusion_is_deterministic_and_breaks_ties_on_identity():
    lists = [RankedList(source="one", identifiers=("b", "a"))]
    first = fuse(lists)
    second = fuse(lists)
    assert [entry.identifier for entry in first] == [entry.identifier for entry in second]
    tied = fuse(
        [RankedList(source="x", identifiers=("z",)), RankedList(source="y", identifiers=("a",))]
    )
    assert [entry.identifier for entry in tied] == ["a", "z"]


def test_fusion_honours_weights_and_limits():
    weighted = fuse(
        [
            RankedList(source="keyword", identifiers=("k",), weight=2.0),
            RankedList(source="semantic", identifiers=("s",), weight=1.0),
        ]
    )
    assert weighted[0].identifier == "k"
    assert len(fuse([RankedList(source="k", identifiers=("a", "b", "c"))], limit=2)) == 2


def test_a_single_list_fuses_to_itself():
    """Degrading to keyword-only must not reorder the keyword results."""

    identifiers = ("first", "second", "third")
    fused = fuse([RankedList(source="keyword", identifiers=identifiers)])
    assert tuple(entry.identifier for entry in fused) == identifiers


def test_fusion_rejects_unusable_input():
    with pytest.raises(ValueError):
        RankedList(source=" ", identifiers=("a",))
    with pytest.raises(ValueError):
        RankedList(source="k", identifiers=("a",), weight=0)
    with pytest.raises(ValueError):
        RankedList(source="k", identifiers=("a", "a"))
    with pytest.raises(ValueError):
        fuse([], limit=0)
    with pytest.raises(ValueError):
        fuse([], rank_constant=0)
    assert fuse([]) == ()
    assert DEFAULT_RANK_CONSTANT == 60


# Full-text search ---------------------------------------------------------


@pytest.fixture()
def indexed() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE knowledge_nodes (id TEXT PRIMARY KEY, title TEXT, body TEXT);
        CREATE VIRTUAL TABLE knowledge_search USING fts5(
            node_id UNINDEXED, title, body,
            tokenize = "unicode61 remove_diacritics 2"
        );
        """
    )
    rows = [
        ("1", "Bütçe kararı", "Ekip bütçeyi onayladı"),
        ("2", "İstanbul toplantısı", "Ofis taşınması görüşüldü"),
        ("3", "Release plan", "Ship the signed installer"),
    ]
    connection.executemany("INSERT INTO knowledge_nodes VALUES (?, ?, ?)", rows)
    rebuild_search_index(connection)
    return connection


def _search(connection: sqlite3.Connection, query: str) -> list[str]:
    rows = connection.execute(
        f"SELECT node_id FROM {SEARCH_TABLE} WHERE {SEARCH_TABLE} MATCH ? "
        f"ORDER BY bm25({SEARCH_TABLE}), node_id",
        (build_match_expression(query),),
    ).fetchall()
    return [str(row["node_id"]) for row in rows]


def test_search_matches_turkish_prefixes_and_folds_diacritics(indexed: sqlite3.Connection):
    # A LIKE scan for "karar" would miss "kararı"; the index does not.
    assert _search(indexed, "karar") == ["1"]
    assert _search(indexed, "butce") == ["1"]
    assert _search(indexed, "istanbul") == ["2"]
    assert _search(indexed, "İSTANBUL") == ["2"]


def test_dotless_and_dotted_i_are_folded_together(indexed: sqlite3.Connection):
    """unicode61 alone does not do this: ı and İ are letters, not accents."""

    assert fold_turkish("farklı") == "farkli"
    assert fold_turkish("İstanbul") == "istanbul"
    assert fold_turkish("IRMAK") == "iRMAK"
    assert _search(indexed, "toplantisi") == ["2"]
    assert _search(indexed, "toplantısı") == ["2"]


def test_multiple_words_must_all_match(indexed: sqlite3.Connection):
    assert _search(indexed, "signed installer") == ["3"]
    assert _search(indexed, "signed toplantı") == []


def test_punctuation_cannot_become_query_syntax(indexed: sqlite3.Connection):
    # A stray quote or a bare OR would otherwise be FTS5 syntax. Quoting every
    # token turns them into ordinary required words instead, so the query stays
    # parseable and does not silently widen to an OR across the corpus.
    assert build_match_expression('karar" OR "x') == '"karar"* AND "OR"* AND "x"*'
    assert _search(indexed, 'karar" OR "x') == []
    assert _search(indexed, "karar*") == ["1"]
    for query in ("", "   ", "!!!", "-"):
        assert has_searchable_terms(query) is False
        with pytest.raises(ValueError):
            build_match_expression(query)


def test_the_index_is_rebuildable_from_the_table(indexed: sqlite3.Connection):
    indexed.execute(f"DELETE FROM {SEARCH_TABLE}")
    assert _search(indexed, "karar") == []
    assert rebuild_search_index(indexed) == 3
    assert _search(indexed, "karar") == ["1"]


def test_triggers_keep_the_index_current(tmp_path: Path):
    from collective_mindgraph.infrastructure.persistence import (
        SqliteDatabase,
        initialize_schema,
    )

    database = SqliteDatabase(tmp_path / "canonical.sqlite3")
    initialize_schema(database)
    node_id = str(uuid4())
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO knowledge_nodes(id, kind, title, body, created_at, updated_at) "
            "VALUES (?, 'note', 'Bütçe kararı', 'onaylandı', '2026-01-01', '2026-01-01')",
            (node_id,),
        )
    with database.connect() as connection:
        assert _search(connection, "karar") == [node_id]
        connection.execute(
            "UPDATE knowledge_nodes SET title = 'Tamamen farklı' WHERE id = ?",
            (node_id,),
        )
    with database.connect() as connection:
        assert _search(connection, "karar") == []
        assert _search(connection, "farkli") == [node_id]
        connection.execute("DELETE FROM knowledge_nodes WHERE id = ?", (node_id,))
    with database.connect() as connection:
        assert _search(connection, "farkli") == []


# Subgraph -----------------------------------------------------------------


def _chain(length: int) -> list[SubgraphEdge]:
    return [
        SubgraphEdge(source_id=f"n{index}", target_id=f"n{index + 1}", kind="related_to")
        for index in range(length)
    ]


def _expander(edges: list[SubgraphEdge]) -> SubgraphExpander:
    def _neighbours(node_ids):
        wanted = set(node_ids)
        return [edge for edge in edges if edge.source_id in wanted or edge.target_id in wanted]

    return SubgraphExpander(_neighbours)


def test_expansion_stops_at_the_requested_depth():
    result = _expander(_chain(5)).expand("n0", depth=2)
    assert set(result.node_ids) == {"n0", "n1", "n2"}
    assert result.depth_reached == 2
    assert result.truncated is False


def test_depth_zero_returns_only_the_root():
    result = _expander(_chain(3)).expand("n0", depth=0)
    assert result.node_ids == ("n0",)
    assert result.edges == ()


def test_the_visible_node_cap_is_the_products_not_the_callers():
    star = [
        SubgraphEdge(source_id="root", target_id=f"leaf{index}", kind="related_to")
        for index in range(MAX_NODE_LIMIT + 50)
    ]
    result = _expander(star).expand("root", depth=1, limit=MAX_NODE_LIMIT + 50)
    assert result.node_count == MAX_NODE_LIMIT
    assert result.truncated is True
    assert result.omitted_neighbours > 0


def test_truncation_is_reported_rather_than_hidden():
    star = [
        SubgraphEdge(source_id="root", target_id=f"leaf{index}", kind="related_to")
        for index in range(10)
    ]
    result = _expander(star).expand("root", depth=1, limit=4)
    assert result.node_count == 4
    assert result.truncated is True
    assert result.omitted_neighbours == 7
    # Every returned edge connects two returned nodes.
    for edge in result.edges:
        assert edge.source_id in result.node_ids
        assert edge.target_id in result.node_ids


def test_expansion_rejects_unusable_bounds():
    expander = _expander(_chain(2))
    for kwargs in ({"depth": -1}, {"depth": MAX_DEPTH + 1}, {"limit": 0}):
        with pytest.raises(ValueError):
            expander.expand("n0", **kwargs)
    with pytest.raises(ValueError):
        expander.expand("  ")
    assert DEFAULT_NODE_LIMIT <= MAX_NODE_LIMIT


def test_edges_carry_their_kind_and_helper_resolves_the_other_end():
    edge = SubgraphEdge(source_id="a", target_id="b", kind="mentions")
    assert edge.other("a") == "b"
    assert edge.other("b") == "a"
    assert edge.other("c") is None


# Layout -------------------------------------------------------------------


def test_layout_is_reproducible_for_the_same_graph():
    nodes = [f"n{index}" for index in range(12)]
    edges = [(f"n{index}", f"n{index + 1}") for index in range(11)]
    first = compute_layout(nodes, edges, iterations=30)
    second = compute_layout(nodes, edges, iterations=30)
    assert first == second
    assert [position.node_id for position in first] == nodes


def test_initial_positions_depend_only_on_the_identifier():
    assert initial_position("stable") == initial_position("stable")
    assert initial_position("stable") != initial_position("other")


def test_pinned_nodes_do_not_move():
    nodes = ["a", "b", "c"]
    pinned = {"a": (10.0, 20.0)}
    positions = {
        entry.node_id: entry
        for entry in compute_layout(nodes, [("a", "b")], iterations=40, pinned=pinned)
    }
    assert (positions["a"].x, positions["a"].y) == (10.0, 20.0)
    assert (positions["b"].x, positions["b"].y) != (10.0, 20.0)


def test_layout_keeps_every_node_inside_the_canvas():
    nodes = [f"n{index}" for index in range(20)]
    edges = [("n0", f"n{index}") for index in range(1, 20)]
    for position in compute_layout(nodes, edges, iterations=50, canvas=500.0):
        assert 0.0 <= position.x <= 500.0
        assert 0.0 <= position.y <= 500.0


def test_connected_nodes_end_closer_than_unconnected_ones():
    nodes = ["a", "b", "far"]
    positions = {
        entry.node_id: entry for entry in compute_layout(nodes, [("a", "b")], iterations=200)
    }
    linked = _distance(positions["a"], positions["b"])
    unlinked = min(
        _distance(positions["a"], positions["far"]), _distance(positions["b"], positions["far"])
    )
    assert linked < unlinked


def test_layout_handles_degenerate_input():
    assert compute_layout([], []) == ()
    assert len(compute_layout(["only"], [])) == 1
    # A duplicate identifier and a self-edge must not break the computation.
    assert len(compute_layout(["a", "a", "b"], [("a", "a")], iterations=5)) == 3
    with pytest.raises(ValueError):
        compute_layout(["a"], [], iterations=0)
    with pytest.raises(ValueError):
        compute_layout(["a"], [], canvas=0)


def _distance(first: NodePosition, second: NodePosition) -> float:
    return ((first.x - second.x) ** 2 + (first.y - second.y) ** 2) ** 0.5


# Localhost surface --------------------------------------------------------


@pytest.fixture()
def engine(tmp_path: Path):
    from collective_mindgraph.engine.main import create_app
    from collective_mindgraph.engine.settings import EngineSettings

    root = tmp_path / "engine"
    application = create_app(
        EngineSettings(
            data_dir=root / "data",
            temp_dir=root / "temp",
            database_path=root / "collective_mindgraph.sqlite3",
            asr_provider="mock",
            vad_provider="energy",
            diarizer_provider="fallback",
            embedding_provider="mock",
        )
    )
    with TestClient(application) as client:
        yield client, application


def _seed(application, count: int = 4) -> list[str]:
    identifiers = [str(uuid4()) for _ in range(count)]
    with application.state.engine_context.database.connect() as connection:
        for index, node_id in enumerate(identifiers):
            connection.execute(
                "INSERT INTO knowledge_nodes(id, kind, title, body, created_at, updated_at) "
                "VALUES (?, 'note', ?, ?, '2026-01-01', '2026-01-01')",
                (node_id, f"Bütçe kararı {index}", "onaylandı"),
            )
        for index in range(count - 1):
            connection.execute(
                "INSERT INTO knowledge_edges(id, source_id, target_id, kind, created_at) "
                "VALUES (?, ?, ?, 'related_to', '2026-01-01')",
                (str(uuid4()), identifiers[index], identifiers[index + 1]),
            )
    return identifiers


def test_the_subgraph_endpoint_is_bounded_and_positioned(engine):
    client, application = engine
    identifiers = _seed(application)

    payload = client.get(f"/api/v2/knowledge/subgraph/{identifiers[0]}?depth=1").json()
    assert payload["root_id"] == identifiers[0]
    assert {node["id"] for node in payload["nodes"]} == {identifiers[0], identifiers[1]}
    assert payload["truncated"] is False
    assert all("x" in node and "y" in node for node in payload["nodes"])

    deeper = client.get(f"/api/v2/knowledge/subgraph/{identifiers[0]}?depth=3").json()
    assert len(deeper["nodes"]) == len(identifiers)
    # Positions are reproducible across requests.
    again = client.get(f"/api/v2/knowledge/subgraph/{identifiers[0]}?depth=3").json()
    assert deeper["nodes"] == again["nodes"]


def test_the_subgraph_endpoint_enforces_its_bounds(engine):
    client, application = engine
    identifiers = _seed(application)
    assert client.get(f"/api/v2/knowledge/subgraph/{uuid4()}").status_code == 404
    assert client.get(f"/api/v2/knowledge/subgraph/{identifiers[0]}?depth=99").status_code == 422
    capped = client.get(f"/api/v2/knowledge/subgraph/{identifiers[0]}?limit={MAX_NODE_LIMIT + 1}")
    assert capped.status_code == 422


def test_hybrid_search_degrades_to_keyword_when_embeddings_are_absent(engine):
    client, application = engine
    identifiers = _seed(application)
    hits = client.get("/api/v2/knowledge/search", params={"query": "karar"}).json()
    assert {hit["id"] for hit in hits} == set(identifiers)
    assert all(hit["sources"] == ["keyword"] for hit in hits)
    assert all(hit["corroborated"] is False for hit in hits)
    assert all(hit["title"] for hit in hits)


def test_hybrid_search_returns_nothing_for_a_termless_query(engine):
    client, application = engine
    _seed(application)
    assert client.get("/api/v2/knowledge/search", params={"query": "!!!"}).json() == []
    assert client.get("/api/v2/knowledge/search", params={"query": ""}).status_code == 422
