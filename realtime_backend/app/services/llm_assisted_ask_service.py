"""LLM-assisted memory answer generation."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from ..api.memory_models import MemoryAskResponse
from ..pipeline.local_llm_provider import LocalLLMEndpointProvider

logger = logging.getLogger(__name__)

class LLMAssistedAskService:
    def __init__(self, llm_provider: LocalLLMEndpointProvider):
        self.llm_provider = llm_provider

    async def generate_answer(self, query: str, evidence_response: MemoryAskResponse) -> MemoryAskResponse:
        """
        Takes an evidence-only response and uses LLM to synthesize a natural language answer.
        """
        if self.llm_provider.base_url == "disabled" or not self.llm_provider.is_available():
            status = "disabled" if self.llm_provider.base_url == "disabled" else "unavailable"
            evidence_response.warnings.append(f"Local LLM {status}. Falling back to evidence-only.")
            evidence_response.answer_type = "fallback_to_evidence_only"
            evidence_response.mode_used = "evidence_only_fallback"
            evidence_response.answer_validation_status = "fallback_to_evidence_only"
            return evidence_response

        # 1. Prepare evidence context
        evidence_context = self._format_evidence_for_llm(evidence_response)
        
        # 2. Build Prompt
        prompt = self._build_prompt(query, evidence_context)
        
        # 3. Request LLM completion
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "used_sources": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "string", "enum": ["high", "medium", "low", "insufficient"]},
                "missing_evidence_note": {"type": "string"}
            },
            "required": ["answer", "used_sources", "confidence"]
        }
        
        import asyncio
        try:
            llm_result = await asyncio.to_thread(self.llm_provider.generate_structured_json, prompt, schema)
            answer = llm_result.get("answer", "")
            reported_sources = llm_result.get("used_sources", [])
            
            # 4. Audit & Validation
            
            # 4.1 Validate used sources
            valid_source_ids = set(evidence_response.source_session_ids + [s for s in evidence_response.source_segment_ids if s])
            for i in range(len(evidence_response.evidence_chains)):
                valid_source_ids.add(str(i+1))
                valid_source_ids.add(f"Evidence {i+1}")
            
            used_sources = []
            rejected_sources = []
            for rs in reported_sources:
                if rs in valid_source_ids:
                    used_sources.append(rs)
                else:
                    rejected_sources.append(rs)

            if not used_sources:
                evidence_response.warnings.append("LLM failed to cite any valid sources.")
                evidence_response.answer_validation_status = "rejected_missing_sources"
                evidence_response.answer_type = "fallback_to_evidence_only"
                evidence_response.mode_used = "evidence_only_fallback"
                return evidence_response

            if rejected_sources:
                evidence_response.warnings.append(f"LLM cited unknown sources: {rejected_sources}")

            # 4.2 Per-sentence validation
            import re
            sentences = [s.strip() for s in re.split(r'[.!?]+', answer) if s.strip()]
            sentence_validations = []
            all_unsupported_terms = set()
            
            for sentence in sentences:
                unsupported = self._find_unsupported_terms(sentence, evidence_context)
                all_unsupported_terms.update(unsupported)
                
                # Heuristic: LLM usually cites in text or in json
                # For this prototype, if sentence is valid and overall sources exist, we mark as supported
                # but in production we'd want per-sentence source tags.
                sentence_validations.append({
                    "sentence": sentence,
                    "supported": len(unsupported) == 0,
                    "sources": used_sources if len(unsupported) == 0 else [],
                    "unsupported_terms": unsupported
                })

            evidence_response.sentence_validations = sentence_validations
            evidence_response.rejected_terms = list(all_unsupported_terms)
            evidence_response.used_sources = used_sources
            evidence_response.rejected_sources = rejected_sources

            # 4.3 Hallucination rejection
            if all_unsupported_terms:
                logger.warning(f"LLM answer rejected due to unsupported terms: {all_unsupported_terms}")
                evidence_response.warnings.append("LLM answer contained unsupported information and was rejected.")
                evidence_response.answer_validation_status = "rejected_unsupported_terms"
                evidence_response.answer_type = "fallback_to_evidence_only"
                evidence_response.mode_used = "evidence_only_fallback"
                evidence_response.evidence_coverage_score = 0.0
                return evidence_response

            # 4.4 Coverage Score calculation
            valid_sentences = sum(1 for sv in sentence_validations if sv["supported"])
            coverage_score = valid_sentences / len(sentences) if sentences else 0.0
            evidence_response.evidence_coverage_score = coverage_score

            # 5. Final Update
            evidence_response.short_answer = answer
            evidence_response.confidence_level = llm_result.get("confidence", "low")
            evidence_response.missing_evidence_note = llm_result.get("missing_evidence_note")
            evidence_response.answer_type = "llm_assisted"
            evidence_response.mode_used = "llm_assisted"
            evidence_response.answer_validation_status = "accepted"
            
        except Exception as e:
            logger.error(f"LLM assisted ask failed: {e}")
            evidence_response.warnings.append(f"LLM assisted generation failed: {str(e)}")
            evidence_response.answer_type = "fallback_to_evidence_only"
            evidence_response.mode_used = "evidence_only_fallback"
            evidence_response.answer_validation_status = "fallback_to_evidence_only"
            
        return evidence_response

    def _find_unsupported_terms(self, answer: str, evidence: str) -> List[str]:
        """
        Simple technical term extractor and comparator.
        Rejects if answer contains technical terms (capitalized or specific patterns) 
        not found in evidence.
        """
        import re
        # Look for technical-looking words (starting with capital, or specific extensions/tech names)
        # This is a heuristic and can be refined.
        pattern = re.compile(r'\b[A-Z][a-zA-Z0-9]{2,}\b|\b(?:[a-z]{2,}\.[a-z]{2,})\b')
        answer_terms = set(pattern.findall(answer))
        evidence_terms = set(pattern.findall(evidence))
        
        # Case-insensitive technical match for common terms
        common_tech = {"fastapi", "sqlite", "vad", "whisper", "python", "docker", "pytest", "npm", "react", "git"}
        for word in re.findall(r'\b[a-z]{3,}\b', answer.lower()):
            if word in common_tech:
                answer_terms.add(word)
        for word in re.findall(r'\b[a-z]{3,}\b', evidence.lower()):
            if word in common_tech:
                evidence_terms.add(word)

        unsupported = []
        for term in answer_terms:
            if term.lower() not in [et.lower() for et in evidence_terms]:
                unsupported.append(term)
        
        return unsupported

    def _format_evidence_for_llm(self, response: MemoryAskResponse) -> str:
        lines = []
        for i, chain in enumerate(response.evidence_chains):
            chain_text = " -> ".join([f"[{step.node_type}] {step.text}" for step in chain.steps])
            source_info = ""
            # Simple heuristic: find segment ID in steps or use response global
            seg_ids = []
            for step in chain.steps:
                # We don't have node_source in api models easily, 
                # but we have node_id which we could look up if needed.
                # For now use the response global source IDs.
                pass
            lines.append(f"Evidence {i+1}: {chain_text}")
        
        return "\n".join(lines)

    def _build_prompt(self, query: str, evidence: str) -> str:
        return (
            "You are a specialized memory retrieval assistant for 'Collective MindGraph'.\n"
            "Your task is to answer a user question based ONLY on the provided evidence retrieved from a knowledge graph.\n\n"
            "STRICT RULES:\n"
            "1. You must answer only using the provided evidence. Do not add advice, tools, methods, assumptions, or outside knowledge.\n"
            "2. If the evidence does not mention a detail, do not include it. For example, if a tool like 'Pytest' or 'Docker' is not in the evidence, you MUST NOT suggest it.\n"
            "3. If the user asks what should be done, report only recorded tasks/decisions explicitly found in the evidence.\n"
            "4. If the evidence is insufficient to answer the question, state it clearly and set confidence to 'insufficient'.\n"
            "5. Cite the evidence used in your answer (e.g., 'According to Evidence 1...').\n"
            "6. Language: Answer in the same language as the question (likely Turkish).\n\n"
            f"USER QUESTION: {query}\n\n"
            f"RETRIEVED EVIDENCE:\n{evidence if evidence else 'No evidence found.'}\n\n"
            "Required JSON format:\n"
            "{\n"
            "  \"answer\": \"...\",\n"
            "  \"used_sources\": [\"list of session or segment IDs if known, or Evidence index numbers\"],\n"
            "  \"confidence\": \"high|medium|low|insufficient\",\n"
            "  \"missing_evidence_note\": \"...\"\n"
            "}"
        )
