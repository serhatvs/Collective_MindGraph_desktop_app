"""Evidence-based memory answer service using graph relationships."""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Set, Tuple

from ..api.memory_models import MemoryAskResponse
from ..models import EvidenceChain, EvidenceStep
from .graph_reasoning import GraphReasoningService, ReasoningResult
from .memory_graph import NodeType

logger = logging.getLogger(__name__)

class EvidenceAnswerService:
    def __init__(self, reasoning_service: GraphReasoningService):
        self.reasoning_service = reasoning_service

    def ask(
        self, 
        query: str, 
        session_id: Optional[str] = None, 
        include_pending: bool = False,
        mode: str = "evidence_only"
    ) -> MemoryAskResponse:
        # 1. Get graph reasoning results
        result = self.reasoning_service.get_intent_based_reasoning(query)
        
        # 2. Filter by session_id if provided
        filtered_chains = []
        source_session_ids = set()
        source_segment_ids = set()
        
        for chain in result.chains:
            # Check session affinity
            in_session = True
            if session_id:
                session_match = False
                for step in chain.steps:
                    if step.node.source and step.node.source.session_id == session_id:
                        session_match = True
                        break
                if not session_match:
                    in_session = False
            
            if not in_session:
                continue

            # Check review status and disabled flag
            # Note: GraphReasoningService.find_related_items already filters some of these, 
            # but we ensure consistency here.
            is_valid = True
            has_pending = False
            for step in chain.steps:
                props = step.node.properties
                if props.get("disabled"):
                    is_valid = False
                    break
                status = props.get("review_status", "pending")
                if status == "rejected":
                    is_valid = False
                    break
                if status == "pending":
                    has_pending = True
            
            if not is_valid:
                continue
            
            if has_pending and not include_pending:
                continue
                
            filtered_chains.append(chain)
            
            # Extract source IDs
            for step in chain.steps:
                if step.node.source:
                    if step.node.source.session_id:
                        source_session_ids.add(step.node.source.session_id)
                    if step.node.source.segment_id:
                        source_segment_ids.add(step.node.source.segment_id)

        # 3. Generate template-based answer
        short_answer, confidence = self._generate_template_answer(query, filtered_chains)
        
        # 4. Map to response model
        api_chains = []
        for chain in filtered_chains:
            steps = []
            for step in chain.steps:
                steps.append(
                    EvidenceStep(
                        node_id=step.node.id,
                        node_type=step.node.type.value,
                        text=step.node.properties.get("title") or step.node.properties.get("text") or step.node.properties.get("decision") or "",
                        edge_type=step.edge.type.value if step.edge else None,
                        direction=step.direction
                    )
                )
            api_chains.append(EvidenceChain(steps=steps, explanation=chain.explanation))

        return MemoryAskResponse(
            query=query,
            mode=mode,
            mode_requested=mode,
            mode_used="evidence_only",
            answer_type="evidence_only",
            answer_validation_status="accepted",
            short_answer=short_answer,
            evidence_chains=api_chains,
            warnings=result.warnings,
            confidence_level=confidence,
            evidence_coverage_score=1.0 if filtered_chains else 0.0,
            source_session_ids=list(source_session_ids),
            source_segment_ids=list(source_segment_ids),
            used_sources=[],
            rejected_sources=[],
            sentence_validations=[]
        )

    def _generate_template_answer(self, query: str, chains: List[Any]) -> Tuple[str, str]:
        if not chains:
            return "Üzgünüm, bu konuyla ilgili herhangi bir kanıt bulamadım.", "insufficient"
        
        q = query.lower()
        count = len(chains)
        
        # Detect intent type from chains
        node_types = set()
        for chain in chains:
            for step in chain.steps:
                node_types.add(step.node.type)
        
        if "görev" in q or "task" in q or "yapması" in q:
            topic = self._extract_topic_from_query(query)
            return f"{topic} ile ilgili {count} adet görev bulundu.", "high"
            
        if "karar" in q or "decision" in q or "kararlaştırıldı" in q:
            topic = self._extract_topic_from_query(query)
            return f"{topic} hakkında {count} adet karar tespit edildi.", "high"
            
        if "risk" in q or "tehlike" in q:
            topic = self._extract_topic_from_query(query)
            return f"{topic} ile ilgili {count} adet risk bulundu.", "high"
            
        if "açık soru" in q or "soru" in q or "open question" in q:
            topic = self._extract_topic_from_query(query)
            return f"{topic} konusunda {count} adet açık soru tespit edildi.", "high"
            
        if "entity" in q or "tool" in q or "library" in q or "kütüphane" in q or "teknoloji" in q:
            topic = self._extract_topic_from_query(query)
            return f"{topic} alanında {count} adet entity (teknoloji/kavram) konuşuldu.", "high"
            
        if "follow-up" in q or "takip" in q:
            topic = self._extract_topic_from_query(query)
            return f"{topic} hakkında {count} adet follow-up maddesi var.", "high"
            
        if "onaylanmamış" in q or "pending" in q:
            return f"Sistemde onaylanmamış {count} adet bilgi bulunuyor.", "high"

        if "ayrımı" in q or "neden" in q or "source" in q or "nasıl" in q or "niye" in q:
             # Look for decision or segment text
             evidence_texts = []
             for chain in chains:
                 for step in chain.steps:
                     if step.node.type in {NodeType.DECISION, NodeType.SEGMENT}:
                         text = step.node.properties.get("decision") or step.node.properties.get("text") or step.node.properties.get("title")
                         if text: evidence_texts.append(text)
             
             if evidence_texts:
                 preview = evidence_texts[0]
                 if len(preview) > 100: preview = preview[:97] + "..."
                 return f"Bu konuyla ilgili şu kayıt bulundu: {preview}", "medium"

        return f"Konuyla ilgili {count} adet kanıt zinciri bulundu.", "medium"

    def _extract_topic_from_query(self, query: str) -> str:
        # Simple heuristic to extract the main subject
        words = query.split()
        ignore = ["görev", "task", "ilgili", "karar", "decision", "nedir", "neler", "risk", "riskler", "açık", "soru", "sorular", "entity", "tool", "library", "follow-up", "takip", "hangi", "var", "mı", "kimin", "ne", "yapması", "gerekiyor"]
        for word in words:
            if len(word) > 3 and word.lower() not in ignore:
                return word
        return "İlgili konu"
