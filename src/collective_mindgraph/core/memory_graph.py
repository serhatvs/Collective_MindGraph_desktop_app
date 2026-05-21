from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from .source_reference import SourceReference

class NodeType(Enum):
    SESSION = "SESSION"
    SEGMENT = "SEGMENT"
    TASK = "TASK"
    DECISION = "DECISION"
    TOPIC = "TOPIC"
    PERSON = "PERSON"
    DOCUMENT = "DOCUMENT"
    PROJECT = "PROJECT"
    ENTITY = "ENTITY"

class EdgeType(Enum):
    SESSION_HAS_SEGMENT = "SESSION_HAS_SEGMENT"
    SEGMENT_MENTIONS_TOPIC = "SEGMENT_MENTIONS_TOPIC"
    SEGMENT_CREATES_TASK = "SEGMENT_CREATES_TASK"
    SEGMENT_SUPPORTS_DECISION = "SEGMENT_SUPPORTS_DECISION"
    TASK_ASSIGNED_TO_PERSON = "TASK_ASSIGNED_TO_PERSON"
    DECISION_RELATED_TO_TOPIC = "DECISION_RELATED_TO_TOPIC"
    TOPIC_RELATED_TO_TOPIC = "TOPIC_RELATED_TO_TOPIC"
    ENTITY_MENTIONED_IN_SEGMENT = "ENTITY_MENTIONED_IN_SEGMENT"
    NODE_MERGED_INTO = "NODE_MERGED_INTO" # For duplicate handling

@dataclass
class GraphNode:
    """
    Represents a discrete unit of knowledge in the semantic memory graph.
    Supports a full review lifecycle: pending -> approved/rejected/edited.
    
    Metadata properties convention:
    - review_status: pending | approved | rejected | edited
    - original_text: raw extraction before human edit
    - disabled: bool
    - disabled_reason: string
    - edited_by_user: bool
    - edited_at: ISO timestamp
    """
    id: str
    type: NodeType
    properties: Dict[str, Any] = field(default_factory=dict)
    source: Optional[SourceReference] = None

@dataclass
class GraphEdge:
    """
    Represents a relationship between two units of knowledge.
    Enables multi-hop reasoning across sessions and documents.
    """
    id: str
    source_node_id: str
    target_node_id: str
    type: EdgeType
    properties: Dict[str, Any] = field(default_factory=dict)
    source: Optional[SourceReference] = None
