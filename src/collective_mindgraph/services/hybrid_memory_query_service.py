"""Hybrid Memory Query Service integrating Keyword, Graph, and Vector search."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
import logging

from collective_mindgraph.core.hybrid_query import HybridQueryInterface, HybridQueryResult
from collective_mindgraph.infrastructure.database.graph_repository import ProductionGraphRepository
from collective_mindgraph.infrastructure.database.vector_repository import VectorRepository
from collective_mindgraph.core.ai_provider import LocalEmbeddingProvider
from collective_mindgraph.core.memory_graph import GraphNode, GraphEdge, NodeType, EdgeType

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
                keyword_hits = self.graph_repo.database.connect().execute(
                    "SELECT id FROM v2_graph_nodes WHERE text_content LIKE ? OR title LIKE ?",
                    (f"%{text_query}%", f"%{text_query}%")
                ).fetchall()
                for row in keyword_hits:
                    node_id = row["id"]
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

        # 2. Graph Expansion
        if use_graph:
            initial_ids = list(enhanced_results.keys())
            for node_id in initial_ids:
                source_res = enhanced_results[node_id]
                # Expand from SEGMENT to related items
                if source_res.node.type == NodeType.SEGMENT:
                    edges = self.graph_repo.get_edges_by_node(node_id, as_source=True)
                    for edge in edges:
                        if edge.type in {EdgeType.SEGMENT_CREATES_TASK, EdgeType.SEGMENT_SUPPORTS_DECISION, EdgeType.SEGMENT_MENTIONS_TOPIC}:
                            self._add_graph_hit(enhanced_results, edge.target_node_id, source_res, edge.type.value)
                
                # Expand from TASK/DECISION/TOPIC back to SEGMENT
                elif source_res.node.type in {NodeType.TASK, NodeType.DECISION, NodeType.TOPIC}:
                    edges = self.graph_repo.get_edges_by_node(node_id, as_source=False)
                    for edge in edges:
                        if edge.type in {EdgeType.SEGMENT_CREATES_TASK, EdgeType.SEGMENT_SUPPORTS_DECISION, EdgeType.SEGMENT_MENTIONS_TOPIC}:
                            self._add_graph_hit(enhanced_results, edge.source_node_id, source_res, edge.type.value)

        # 3. Final Ranking and Assembly
        final_list = list(enhanced_results.values())
        final_list.sort(key=lambda x: x.score, reverse=True)

        result = HybridQueryResult()
        for res in final_list:
            # Enrich node properties with metadata for UI
            matched_set = res.matched_by
            res.node.properties["matched_by"] = ", ".join(sorted(list(matched_set)))
            res.node.properties["score"] = res.score
            res.node.properties["score_breakdown"] = {
                "keyword": res.keyword_score,
                "vector": res.vector_score,
                "graph": res.graph_score
            }
            res.node.properties["edge_path"] = " -> ".join(res.edge_path)
            
            result.nodes.append(res.node)
            
        return result

    def _add_graph_hit(self, results: Dict[str, EnhancedQueryResult], target_id: str, source_res: EnhancedQueryResult, edge_type: str):
        if target_id not in results:
            node = self.graph_repo.get_node(target_id)
            if node:
                results[target_id] = EnhancedQueryResult(node=node)
        
        if target_id in results:
            res = results[target_id]
            # Don't downgrade matched_by if already matched by something else
            res.matched_by.add("graph")
            # Graph hits inherit a portion of the source score
            res.graph_score = max(res.graph_score, source_res.score * 0.8)
            res.score = max(res.score, res.graph_score)
            if not res.edge_path:
                res.edge_path = [f"{source_res.node.type.value} --({edge_type})--> {res.node.type.value}"]
