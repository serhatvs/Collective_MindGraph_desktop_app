import json
import asyncio
import os
from typing import List, Dict, Any, Optional
from ..config import Settings
from .local_llm_provider import LocalLLMEndpointProvider
from ..models import ConversationTranscript, TaskItem, DecisionItem, TopicSegment

import logging

LOGGER = logging.getLogger(__name__)

class AIExtractionService:
    """
    Handles structured extraction from technical transcripts using local LLMs.
    Supports chunked processing for large sessions.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        # Initialize local LLM provider
        self.llm_provider = LocalLLMEndpointProvider(
            base_url=settings.llm_endpoint or "http://127.0.0.1:1234/v1",
            timeout=int(settings.llm_timeout_seconds),
            allow_remote=settings.allow_remote_access
        )
        self.mode = settings.extraction_mode

    async def extract_intelligence(self, transcript: ConversationTranscript) -> ConversationTranscript:
        """
        Processes a transcript and populates summary, topics, tasks, and decisions.
        """
        full_text = "\n".join([f"{s.speaker}: {s.corrected_text}" for s in transcript.segments])
        if not full_text:
            return transcript

        # 1. Choose extraction strategy
        use_llm = False
        fallback_reason = None
        
        # Fast exit if LLM is explicitly disabled in provider config
        if self.settings.llm_provider == "disabled":
            use_llm = False
            fallback_reason = "local_llm_disabled_in_config"
        elif self.mode == "local_llm":
            use_llm = True
        elif self.mode == "auto":
            try:
                # Use a very short timeout for auto probe to not block pipeline
                use_llm = await asyncio.to_thread(self.llm_provider.is_available)
                if not use_llm:
                    fallback_reason = "local_llm_server_not_reachable"
            except Exception as e:
                use_llm = False
                fallback_reason = f"availability_check_failed: {str(e)}"
        else:
            use_llm = False
            fallback_reason = "mode_set_to_heuristic_fallback"

        if use_llm:
            try:
                extraction = await self._extract_via_llm(full_text)
                self._apply_extraction(transcript, extraction)
                
                # Enrich metadata with detailed telemetry
                transcript.metadata["extraction_mode"] = "local_llm"
                transcript.metadata["extraction_source"] = "local_llm"
                transcript.metadata["llm_provider"] = self.llm_provider.provider_name
                transcript.metadata["llm_endpoint"] = self.llm_provider.base_url
                transcript.metadata["json_valid"] = True
                transcript.metadata["local_llm_used"] = True
                transcript.metadata["heuristic_used"] = False
                
                LOGGER.info("AI Extraction complete using local LLM.")
                return transcript
            except Exception as e:
                fallback_reason = f"LLM generation failed: {str(e)}"
                LOGGER.warning(f"LLM Extraction failed, falling back to heuristics: {e}")

        # Fallback to existing heuristic extraction (handled by summary_service in pipeline)
        transcript.metadata["extraction_mode"] = "heuristic_fallback"
        transcript.metadata["extraction_source"] = "heuristic_fallback"
        transcript.metadata["extraction_fallback_reason"] = fallback_reason
        transcript.metadata["local_llm_used"] = False
        transcript.metadata["heuristic_used"] = True
        transcript.metadata["json_valid"] = False
        LOGGER.info(f"AI Extraction using heuristic fallback. Reason: {fallback_reason}")
        return transcript

    async def _extract_via_llm(self, text: str) -> Dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "tasks": {
                    "type": "array", 
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "assignee": {"type": "string"},
                            "segment_id": {"type": "string"}
                        }
                    }
                },
                "decisions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "decision": {"type": "string"},
                            "reason": {"type": "string"},
                            "segment_id": {"type": "string"}
                        }
                    }
                },
                "topics": {"type": "array", "items": {"type": "string"}},
                "entities": {"type": "array", "items": {"type": "string"}},
                "risks": {"type": "array", "items": {"type": "string"}},
                "open_questions": {"type": "array", "items": {"type": "string"}},
                "follow_ups": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["summary", "tasks", "decisions", "topics"]
        }
        prompt = (
            "Analyze this technical meeting transcript and extract high-quality structured memory.\n"
            "Language: Turkish (mostly) or Multilingual.\n"
            "Task: Identify Action Items (tasks), Key Decisions, Main Topics, Entities (libraries/tools), Risks, and Follow-ups.\n\n"
            f"Transcript:\n{text}"
        )
        
        return await asyncio.to_thread(self.llm_provider.generate_structured_json, prompt, schema)

    def _apply_extraction(self, transcript: ConversationTranscript, data: Dict[str, Any]):
        transcript.summary = data.get("summary")
        
        # Deduplicate and Apply Topics
        seen_topics = set()
        topics = []
        for t in data.get("topics", []):
            if t.lower() not in seen_topics:
                topics.append(TopicSegment(label=t, start=0, end=0))
                seen_topics.add(t.lower())
        transcript.topics = topics
        
        # Apply Tasks
        seen_tasks = set()
        tasks = []
        for t in data.get("tasks", []):
            title = t.get("title", "").strip()
            if title and title.lower() not in seen_tasks:
                tasks.append(TaskItem(
                    title=title,
                    responsible_person=t.get("assignee"),
                    source_segment_id=t.get("segment_id")
                ))
                seen_tasks.add(title.lower())
        transcript.action_items = tasks
        
        # Apply Decisions
        seen_decisions = set()
        decisions = []
        for d in data.get("decisions", []):
            text = d.get("decision", "").strip()
            if text and text.lower() not in seen_decisions:
                decisions.append(DecisionItem(
                    decision=text,
                    reason_context=d.get("reason"),
                    source_segment_id=d.get("segment_id")
                ))
                seen_decisions.add(text.lower())
        transcript.decisions = decisions
        
        # Additional metadata for V2 Graph
        transcript.metadata["entities"] = data.get("entities", [])
        transcript.metadata["risks"] = data.get("risks", [])
        transcript.metadata["open_questions"] = data.get("open_questions", [])
        transcript.metadata["follow_ups"] = data.get("follow_ups", [])
