"""Hybrid Memory Query Service integrating Keyword, Graph, and Vector search."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
import logging
import json

from .hybrid_query import HybridQueryInterface, HybridQueryResult
from .graph_repository import ProductionGraphRepository
from .vector_repository import VectorRepository
from .ai_provider import LocalEmbeddingProvider
from .memory_graph import GraphNode, GraphEdge, NodeType, EdgeType

logger = logging.getLogger(__name__)

@dataclass
class EnhancedQueryResult:
    node: GraphNode
    matched_by: Set[str] = field(default_factory=set)
    score: float = 0.0
    keyword_score: float = 0.0
    vector_score: float = 0.0
    graph_score: float = 0.0
    edge_path: List[str] = field(default_factory=list)

class HybridMemoryQueryService(HybridQueryInterface):
    def __init__(
        self, 
        graph_repo: ProductionGraphRepository, 
        vector_repo: Optional[VectorRepository] = None,
        embedding_provider: Optional[LocalEmbeddingProvider] = None
    ):
        self.graph_repo = graph_repo
        self.vector_repo = vector_repo
        self.embedding_provider = embedding_provider

    def execute_query(
        self, 
        text_query: str, 
        use_keyword: bool = True,
        use_vector: bool = True, 
        use_graph: bool = True,
        threshold: float = 0.3
    ) -> HybridQueryResult:
        
        # 1. Gather intermediate results
        enhanced_results: Dict[str, EnhancedQueryResult] = {}

        # 1.1 Vector Search
        if use_vector and self.vector_repo and self.embedding_provider and self.embedding_provider.is_available():
            try:
                q_vec = self.embedding_provider.embed_text(text_query)
                vec_hits = self.vector_repo.search_similar(q_vec, top_k=10, threshold=threshold)
                for hit in vec_hits:
                    node_id = hit["node_id"]
                    if node_id not in enhanced_results:
                        node = self.graph_repo.get_node(node_id)
                        if node:
                            # Filter by review status and disabled flag
                            meta = node.properties
                            if meta.get("disabled") or meta.get("review_status") == "rejected":
                                continue
                            enhanced_results[node_id] = EnhancedQueryResult(node=node)
                    
                    if node_id in enhanced_results:
                        res = enhanced_results[node_id]
                        res.matched_by.add("vector")
                        res.vector_score = hit["score"]
                        res.score = max(res.score, hit["score"])
            except Exception as e:
                logger.error(f"Vector search failed: {e}")

        # 1.2 Keyword Search
        if use_keyword:
            try:
                # Filter out disabled nodes in the query itself if possible, 
                # but since they are in metadata_json, we check in Python for now.
                with self.graph_repo.database.connect() as connection:
                    keyword_hits = connection.execute(
                        "SELECT id, type, title, text_content, metadata_json FROM v2_graph_nodes WHERE text_content LIKE ? OR title LIKE ?",
                        (f"%{text_query}%", f"%{text_query}%")
                    ).fetchall()
                for row in keyword_hits:
                    node_id = row["id"]
                    meta = json.loads(row["metadata_json"]) if isinstance(row["metadata_json"], str) else row["metadata_json"]
                    # Filter by review status and disabled flag
                    if meta.get("disabled") or meta.get("review_status") == "rejected":
                        continue
                        
                    if node_id not in enhanced_results:
                        node = self.graph_repo.get_node(node_id)
                        if node:
                            enhanced_results[node_id] = EnhancedQueryResult(node=node)
                    
                    if node_id in enhanced_results:
                        res = enhanced_results[node_id]
                        res.matched_by.add("keyword")
                        res.keyword_score = 1.0 
                        res.score = max(res.score, 0.5)
            except Exception as e:
                logger.error(f"Keyword search failed: {e}")

        # 1.3 Graph Traversal (Expansion)
        if use_graph and enhanced_results:
            try:
                # Simple 1-hop expansion for now
                pass
            except Exception as e:
                logger.error(f"Graph expansion failed: {e}")

        # 2. Finalize and Rank
        final_nodes = []
        for res in enhanced_results.values():
            # Update node properties with ranking info for the UI
            res.node.properties["matched_by"] = list(res.matched_by)
            res.node.properties["score"] = res.score
            res.node.properties["score_breakdown"] = {
                "keyword": res.keyword_score,
                "vector": res.vector_score,
                "graph": res.graph_score
            }
            if res.edge_path:
                res.node.properties["edge_path"] = " -> ".join(res.edge_path)
            
            final_nodes.append(res.node)

        # Sort by score descending
        final_nodes.sort(key=lambda x: x.properties.get("score", 0.0), reverse=True)

        return HybridQueryResult(
            nodes=final_nodes,
            confidence=max([n.properties.get("score", 0.0) for n in final_nodes]) if final_nodes else 0.0
        )
