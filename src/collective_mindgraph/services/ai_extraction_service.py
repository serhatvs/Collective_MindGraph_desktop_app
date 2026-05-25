"""AI Extraction Service with LLM and Heuristic modes."""

from typing import List, Dict, Any, Optional
from collective_mindgraph.core.ai_provider import LocalLLMProvider

class AIExtractionService:
    def __init__(self, llm_provider: Optional[LocalLLMProvider] = None, mode: str = "auto"):
        self.llm_provider = llm_provider
        self.mode = mode

    def extract_from_transcript(self, transcript_text: str) -> Dict[str, Any]:
        """
        Extracts summary, tasks, decisions, and topics from a transcript.
        Tries local LLM first if in 'auto' or 'local_llm' mode.
        Falls back to heuristics if LLM fails or is unavailable.
        """
        use_llm = False
        if self.mode == "local_llm":
            if not self.llm_provider:
                raise ValueError("local_llm mode requires a LocalLLMProvider")
            use_llm = True
        elif self.mode == "auto":
            if self.llm_provider and self.llm_provider.is_available():
                use_llm = True

        if use_llm:
            try:
                return self._extract_via_llm(transcript_text)
            except Exception as e:
                # Log error here in production
                pass

        # Fallback to heuristic
        return self._extract_via_heuristic(transcript_text)

    def _extract_via_llm(self, text: str) -> Dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "tasks": {"type": "array", "items": {"type": "string"}},
                "decisions": {"type": "array", "items": {"type": "string"}},
                "topics": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["summary", "tasks", "decisions", "topics"]
        }
        prompt = f"Analyze the following technical meeting transcript and extract the key information.\n\nTranscript:\n{text}"
        
        result = self.llm_provider.generate_structured_json(prompt, schema)
        result["extraction_source"] = "local_llm"
        return result

    def _extract_via_heuristic(self, text: str) -> Dict[str, Any]:
        """Basic heuristic extraction fallback."""
        # In a real integration, this would call the existing summary.py logic.
        return {
            "summary": "Heuristic summary generated.",
            "tasks": [],
            "decisions": [],
            "topics": ["General Discussion"],
            "extraction_source": "heuristic_fallback"
        }
