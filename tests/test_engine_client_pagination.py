from __future__ import annotations

from collective_mindgraph.desktop.engine_client import EngineClient


def test_typed_client_consumes_and_forwards_list_cursors(monkeypatch):
    client = EngineClient()
    requests: list[tuple[str, dict[str, object]]] = []

    def request(
        method: str,
        path: str,
        *,
        query: dict[str, object] | None = None,
        **_kwargs: object,
    ) -> dict[str, object]:
        assert method == "GET"
        requests.append((path, query or {}))
        return {"items": [], "next_cursor": "next-page"}

    monkeypatch.setattr(client, "_request", request)

    assert client.list_insights(cursor="insight-page") == ((), "next-page")
    assert client.search_memory("roadmap", cursor="memory-page") == ((), "next-page")
    assert client.list_knowledge(cursor="node-page") == ((), "next-page")
    assert client.list_relationships(cursor="edge-page") == ((), "next-page")
    assert client.list_jobs(cursor="job-page") == ((), "next-page")

    assert [query["cursor"] for _path, query in requests] == [
        "insight-page",
        "memory-page",
        "node-page",
        "edge-page",
        "job-page",
    ]
