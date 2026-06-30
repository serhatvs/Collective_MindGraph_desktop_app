from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class SourceReference:
    """
    Provides strict traceability back to the origin of extracted knowledge.
    Ensures that every piece of information in the memory graph can be verified
    against the raw audio trace or original document.
    """
    session_id: str
    segment_id: Optional[str] = None
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None
    text_preview: Optional[str] = None
    confidence: float = 1.0
    extractor_model: str = "heuristic"
