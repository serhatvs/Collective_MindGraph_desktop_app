"""Production memory graph repository."""

import json
import sqlite3
import uuid
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone

from collective_mindgraph.core.memory_graph import GraphNode, GraphEdge, NodeType, EdgeType
from collective_mindgraph.core.source_reference import SourceReference


class ProductionGraphRepository:
    """SQLite-backed repository for the semantic memory graph."""

    def __init__(self, database):
        self.database = database

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_source_reference(self, ref: SourceReference) -> str:
        ref_id = str(uuid.uuid4())
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO v2_source_references 
                (id, session_id, segment_id, timestamp_start, timestamp_end, text_preview, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ref_id,
                    ref.session_id,
                    ref.segment_id,
                    ref.timestamp_start,
                    ref.timestamp_end,
                    None,
                    self._now(),
                )
            )
        return ref_id

    def create_node(self, node: GraphNode) -> GraphNode:
        if not node.id:
            node.id = str(uuid.uuid4())

        source_id = None
        if node.source:
            source_id = self.create_source_reference(node.source)

        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO v2_graph_nodes
                (id, type, title, text_content, metadata_json, source_reference_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.id,
                    node.type.value,
                    node.properties.get("title"),
                    node.properties.get("text_content") or node.properties.get("text"),
                    json.dumps(node.properties),
                    source_id,
                    self._now(),
                    self._now(),
                )
            )
        return node

    def create_edge(self, edge: GraphEdge) -> GraphEdge:
        if not edge.id:
            edge.id = str(uuid.uuid4())

        source_id = None
        if edge.source:
            source_id = self.create_source_reference(edge.source)

        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO v2_graph_edges
                (id, source_node_id, target_node_id, edge_type, metadata_json, confidence, source_reference_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.id,
                    edge.source_node_id,
                    edge.target_node_id,
                    edge.type.value,
                    json.dumps(edge.properties),
                    edge.properties.get("confidence", 1.0),
                    source_id,
                    self._now(),
                )
            )
        return edge

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM v2_graph_nodes WHERE id = ?", (node_id,)
            ).fetchone()
        if not row:
            return None
            
        return self._map_node(row)

    def find_nodes_by_type(self, node_type: NodeType) -> List[GraphNode]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM v2_graph_nodes WHERE type = ?", (node_type.value,)
            ).fetchall()
        return [self._map_node(row) for row in rows]

    def get_edges_by_node(self, node_id: str, as_source: bool = True) -> List[GraphEdge]:
        col = "source_node_id" if as_source else "target_node_id"
        with self.database.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM v2_graph_edges WHERE {col} = ?", (node_id,)
            ).fetchall()
        return [self._map_edge(row) for row in rows]
        
    def _map_source_ref(self, ref_id: Optional[str]) -> Optional[SourceReference]:
        if not ref_id:
            return None
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM v2_source_references WHERE id = ?", (ref_id,)
            ).fetchone()
        if not row:
            return None
        return SourceReference(
            session_id=row["session_id"],
            segment_id=row["segment_id"],
            timestamp_start=row["timestamp_start"],
            timestamp_end=row["timestamp_end"],
        )

    def _map_node(self, row: sqlite3.Row) -> GraphNode:
        return GraphNode(
            id=row["id"],
            type=NodeType(row["type"]),
            properties=json.loads(row["metadata_json"]),
            source=self._map_source_ref(row["source_reference_id"])
        )

    def _map_edge(self, row: sqlite3.Row) -> GraphEdge:
        return GraphEdge(
            id=row["id"],
            source_node_id=row["source_node_id"],
            target_node_id=row["target_node_id"],
            type=EdgeType(row["edge_type"]),
            properties=json.loads(row["metadata_json"]),
            source=self._map_source_ref(row["source_reference_id"])
        )

    def update_node(self, node_id: str, properties: Dict[str, Any]) -> bool:
        with self.database.connect() as connection:
            # First fetch current metadata to preserve existing fields
            row = connection.execute("SELECT metadata_json FROM v2_graph_nodes WHERE id = ?", (node_id,)).fetchone()
            if not row:
                return False
            
            meta = json.loads(row["metadata_json"])
            meta.update(properties)
            
            connection.execute(
                "UPDATE v2_graph_nodes SET title = ?, text_content = ?, metadata_json = ?, updated_at = ? WHERE id = ?",
                (
                    meta.get("title"),
                    meta.get("text_content") or meta.get("text"),
                    json.dumps(meta),
                    self._now(),
                    node_id
                )
            )
            return True

    def get_neighbors(self, node_id: str, direction: str = "both") -> List[Tuple[GraphEdge, GraphNode]]:
        """Returns list of (Edge, NeighborNode) pairs."""
        results = []
        with self.database.connect() as connection:
            if direction in ("out", "both"):
                # Use subqueries or explicit aliases to avoid ID collision
                rows = connection.execute(
                    """
                    SELECT 
                        e.id as e_id, e.source_node_id, e.target_node_id, e.edge_type as e_type, e.metadata_json as e_meta, e.confidence as e_confidence, e.source_reference_id as e_ref, e.created_at as e_created,
                        n.id as n_id, n.type as n_type, n.title as n_title, n.text_content as n_text_content, n.metadata_json as n_meta, n.source_reference_id as n_ref, n.created_at as n_created, n.updated_at as n_updated
                    FROM v2_graph_edges e 
                    JOIN v2_graph_nodes n ON e.target_node_id = n.id 
                    WHERE e.source_node_id = ?
                    """, (node_id,)
                ).fetchall()
                for row in rows:
                    results.append((self._map_edge_aliased(row, "e_"), self._map_node_aliased(row, "n_")))
            
            if direction in ("in", "both"):
                rows = connection.execute(
                    """
                    SELECT 
                        e.id as e_id, e.source_node_id, e.target_node_id, e.edge_type as e_type, e.metadata_json as e_meta, e.confidence as e_confidence, e.source_reference_id as e_ref, e.created_at as e_created,
                        n.id as n_id, n.type as n_type, n.title as n_title, n.text_content as n_text_content, n.metadata_json as n_meta, n.source_reference_id as n_ref, n.created_at as n_created, n.updated_at as n_updated
                    FROM v2_graph_edges e 
                    JOIN v2_graph_nodes n ON e.source_node_id = n.id 
                    WHERE e.target_node_id = ?
                    """, (node_id,)
                ).fetchall()
                for row in rows:
                    results.append((self._map_edge_aliased(row, "e_"), self._map_node_aliased(row, "n_")))
        return results

    def _map_node_aliased(self, row: sqlite3.Row, prefix: str) -> GraphNode:
        return GraphNode(
            id=row[f"{prefix}id"],
            type=NodeType(row[f"{prefix}type"]),
            properties=json.loads(row[f"{prefix}meta"]),
            source=self._map_source_ref(row[f"{prefix}ref"])
        )

    def _map_edge_aliased(self, row: sqlite3.Row, prefix: str) -> GraphEdge:
        return GraphEdge(
            id=row[f"{prefix}id"],
            source_node_id=row["source_node_id"],
            target_node_id=row["target_node_id"],
            type=EdgeType(row[f"{prefix}type"]),
            properties=json.loads(row[f"{prefix}meta"]),
            source=self._map_source_ref(row[f"{prefix}ref"])
        )

    def get_subgraph(self, root_node_id: str, depth: int = 1) -> Tuple[List[GraphNode], List[GraphEdge]]:
        nodes = {}
        edges = []
        
        root = self.get_node(root_node_id)
        if not root:
            return [], []
            
        nodes[root.id] = root
        
        current_layer = [root_node_id]
        for _ in range(depth):
            next_layer = []
            for node_id in current_layer:
                neighbors = self.get_neighbors(node_id, direction="out")
                for edge, neighbor in neighbors:
                    if neighbor.id not in nodes:
                        nodes[neighbor.id] = neighbor
                        next_layer.append(neighbor.id)
                    edges.append(edge)
            current_layer = next_layer
            if not current_layer:
                break
                
        return list(nodes.values()), edges

    def delete_graph_data_for_session(self, session_id: str) -> None:
        """Removes all v2 graph data linked to a session_id via source_references."""
        with self.database.connect() as connection:
            # Find all nodes linked to this session
            connection.execute(
                """
                DELETE FROM v2_graph_nodes WHERE source_reference_id IN (
                    SELECT id FROM v2_source_references WHERE session_id = ?
                )
                """, (session_id,)
            )
            connection.execute(
                """
                DELETE FROM v2_graph_edges WHERE source_reference_id IN (
                    SELECT id FROM v2_source_references WHERE session_id = ?
                )
                """, (session_id,)
            )
            connection.execute(
                "DELETE FROM v2_source_references WHERE session_id = ?", (session_id,)
            )

