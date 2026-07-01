"""Graph-based multi-hop memory reasoning service."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .memory_graph import EdgeType, GraphEdge, GraphNode, NodeType

logger = logging.getLogger(__name__)

@dataclass
class EvidenceStep:
    node: GraphNode
    edge: Optional[GraphEdge] = None
    direction: str = "out" # "out" or "in"

@dataclass
class EvidenceChain:
    steps: List[EvidenceStep] = field(default_factory=list)
    explanation: str = ""

@dataclass
class ReasoningResult:
    answer_type: str = "graph_evidence"
    chains: List[EvidenceChain] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

class GraphReasoningService:
    def __init__(self, graph_repo: Any):
        """
        Args:
            graph_repo: An instance of ProductionGraphRepository or similar.
        """
        self.repo = graph_repo

    def find_paths(self, source_id: str, target_id: str, max_depth: int = 3) -> List[EvidenceChain]:
        """Finds all simple paths between two nodes up to max_depth."""
        visited = {source_id}
        paths = []
        self._dfs(source_id, target_id, max_depth, [EvidenceStep(self.repo.get_node(source_id))], visited, paths)
        return paths

    def _dfs(self, current_id: str, target_id: str, depth: int, current_path: List[EvidenceStep], visited: Set[str], paths: List[EvidenceChain]):
        if current_id == target_id:
            paths.append(EvidenceChain(steps=list(current_path)))
            return

        if depth <= 0:
            return

        neighbors = self.repo.get_neighbors(current_id, direction="both")
        for edge, neighbor in neighbors:
            if neighbor.id not in visited:
                direction = "out" if edge.source_node_id == current_id else "in"
                visited.add(neighbor.id)
                current_path.append(EvidenceStep(node=neighbor, edge=edge, direction=direction))
                self._dfs(neighbor.id, target_id, depth - 1, current_path, visited, paths)
                current_path.pop()
                visited.remove(neighbor.id)

    def explain_node(self, node_id: str) -> ReasoningResult:
        """Returns the immediate context of a node including its parents and children."""
        node = self.repo.get_node(node_id)
        if not node:
            return ReasoningResult(warnings=[f"Node {node_id} not found."])
        
        result = ReasoningResult()
        neighbors = self.repo.get_neighbors(node_id, direction="both")
        
        for edge, neighbor in neighbors:
            direction = "out" if edge.source_node_id == node_id else "in"
            chain = EvidenceChain(steps=[
                EvidenceStep(node=node),
                EvidenceStep(node=neighbor, edge=edge, direction=direction)
            ])
            result.chains.append(chain)
            
        return result

    def find_related_items(self, topic_text: str, item_type: NodeType) -> ReasoningResult:
        """
        Finds nodes of item_type related to a topic by text, supporting 2-hop traversal.
        """
        result = ReasoningResult()
        
        # 1. Find the topic node(s)
        topics = self.repo.find_nodes_by_type(NodeType.TOPIC)
        # Also check ENTITY nodes if they match the topic_text as they act similarly in technical discussions
        entities = self.repo.find_nodes_by_type(NodeType.ENTITY)
        
        matched_nodes = []
        for t in topics:
            if self._is_hidden_from_normal_results(t):
                continue
            if topic_text.lower() in (t.properties.get("title") or "").lower():
                matched_nodes.append(t)
        for e in entities:
            if self._is_hidden_from_normal_results(e):
                continue
            if topic_text.lower() in (e.properties.get("title") or "").lower():
                matched_nodes.append(e)
                
        # If user asks for general items like "Riskler neler?", topic_text might be generic.
        # So if topic_text is "risk" or "ilgili", we might want to just fetch all risks.
        # But this method is usually called with a specific topic.
        # Let's support global fetching if topic_text is empty or too generic.
        if topic_text in ["risk", "açık", "entity", "follow", "ilgili", "karar", "görev", "topic"]:
            all_items = self.repo.find_nodes_by_type(item_type)
            for item_node in all_items:
                status = item_node.properties.get("review_status", "pending")
                if item_node.properties.get("disabled") or status in {"rejected", "merged"}:
                    continue
                chain = EvidenceChain(steps=[EvidenceStep(node=item_node)])
                result.chains.append(chain)
            return result

        if not matched_nodes:
            # Fallback: if we didn't find a topic, let's just search all items of that type that contain the text
            all_items = self.repo.find_nodes_by_type(item_type)
            for item_node in all_items:
                if topic_text.lower() in (item_node.properties.get("title") or "").lower():
                    status = item_node.properties.get("review_status", "pending")
                    if item_node.properties.get("disabled") or status in {"rejected", "merged"}:
                        continue
                    chain = EvidenceChain(steps=[EvidenceStep(node=item_node)])
                    result.chains.append(chain)
            
            if not result.chains:
                result.warnings.append(f"No topic or item found matching '{topic_text}'.")
            return result

        for start_node in matched_nodes:
            # 2. Find neighbors (incoming from segments usually)
            # Edge: SEGMENT --(MENTIONS_TOPIC)--> TOPIC or SEGMENT --(MENTIONS_ENTITY)--> ENTITY
            topic_neighbors = self.repo.get_neighbors(start_node.id, direction="in")
            for edge, neighbor in topic_neighbors:
                if neighbor.type == NodeType.SEGMENT:
                    # 3. Find items from segment
                    # Edge: SEGMENT --(CREATES_TASK/SUPPORTS_DECISION/RAISES_RISK/etc)--> ITEM
                    seg_neighbors = self.repo.get_neighbors(neighbor.id, direction="out")
                    for seg_edge, item_node in seg_neighbors:
                        if item_node.type == item_type:
                            # Verify review status
                            status = item_node.properties.get("review_status", "pending")
                            if item_node.properties.get("disabled") or status in {"rejected", "merged"}:
                                continue
                            
                            chain = EvidenceChain(steps=[
                                EvidenceStep(node=start_node),
                                EvidenceStep(node=neighbor, edge=edge, direction="in"),
                                EvidenceStep(node=item_node, edge=seg_edge, direction="out")
                            ])
                            if status == "pending":
                                result.warnings.append(f"Note: Result '{item_node.properties.get('title')}' is a pending suggestion.")
                            
                            result.chains.append(chain)
        
        return result

    @staticmethod
    def _is_hidden_from_normal_results(node: GraphNode) -> bool:
        status = node.properties.get("review_status")
        return bool(node.properties.get("disabled") or status in {"rejected", "merged"})

    def get_intent_based_reasoning(self, query: str) -> ReasoningResult:
        """Parses simple intents and routes to specific graph methods."""
        q = query.lower()
        
        # Intent: Tasks related to topic
        if "görev" in q or "task" in q:
            # Heuristic extraction of topic name from query
            # e.g. "FastAPI ile ilgili görevler" -> topic = "FastAPI"
            topic = query.split(" ")[0] # Very naive fallback
            # Look for keywords
            for word in query.split():
                if len(word) > 3 and word not in ["görev", "task", "ilgili", "about", "nedir", "what"]:
                    topic = word
                    break
            return self.find_related_items(topic, NodeType.TASK)
            
        # Intent: Decisions related to topic
        if "karar" in q or "decision" in q or "kararlaştırıldı" in q:
            topic = query.split(" ")[0]
            for word in query.split():
                if len(word) > 3 and word not in ["karar", "decision", "ilgili", "about", "kararlaştırıldı", "hangi"]:
                    topic = word
                    break
            return self.find_related_items(topic, NodeType.DECISION)
            
        # Intent: Risks related to topic
        if "risk" in q or "tehlike" in q:
            topic = query.split(" ")[0]
            for word in query.split():
                if len(word) > 3 and word not in ["risk", "riskler", "tehlike", "ilgili", "hakkında", "neler"]:
                    topic = word
                    break
            return self.find_related_items(topic, NodeType.RISK)
            
        # Intent: Open Questions related to topic
        if "açık soru" in q or "soru" in q or "open question" in q:
            topic = query.split(" ")[0]
            for word in query.split():
                if len(word) > 3 and word not in ["açık", "soru", "sorular", "open", "question", "ilgili", "neler"]:
                    topic = word
                    break
            return self.find_related_items(topic, NodeType.OPEN_QUESTION)
            
        # Intent: Entities related to topic
        if "entity" in q or "tool" in q or "library" in q or "kütüphane" in q or "teknoloji" in q:
            topic = query.split(" ")[0]
            for word in query.split():
                if len(word) > 3 and word not in ["entity", "tool", "library", "kütüphane", "teknoloji", "hangi", "konuşuldu"]:
                    topic = word
                    break
            return self.find_related_items(topic, NodeType.ENTITY)
            
        # Intent: Follow-ups related to topic
        if "follow-up" in q or "takip" in q:
            topic = query.split(" ")[0]
            for word in query.split():
                if len(word) > 3 and word not in ["follow-up", "takip", "maddeleri", "neler", "hangi"]:
                    topic = word
                    break
            return self.find_related_items(topic, NodeType.FOLLOW_UP)

        # Intent: Unreviewed items in session
        if "onaylanmamış" in q or "pending" in q or "unreviewed" in q:
             # Find nodes with review_status == 'pending'
             # For a session if possible, otherwise global
             # This prototype will just return first few global pending
             result = ReasoningResult()
             all_tasks = self.repo.find_nodes_by_type(NodeType.TASK)
             all_decs = self.repo.find_nodes_by_type(NodeType.DECISION)
             for node in all_tasks + all_decs:
                 if node.properties.get("review_status") == "pending":
                     result.chains.append(EvidenceChain(steps=[EvidenceStep(node=node)]))
             return result

        # Default fallback
        return ReasoningResult(warnings=["Could not determine graph reasoning intent. Use specific keywords like 'task' or 'decision'."])
