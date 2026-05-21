from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from .memory_graph import GraphNode, GraphEdge

@dataclass
class HybridQueryResult:
    """
    The output of a hybrid search (combining keyword, vector, and graph traversal).
    Optionally includes an LLM-generated answer supported by citations.
    """
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)
    generated_answer: Optional[str] = None
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)

class HybridQueryInterface(ABC):
    """
    Core reasoning abstraction. Allows the system to answer user questions
    by searching across multiple modalities.
    """
    
    @abstractmethod
    def execute_query(
        self, 
        text_query: str, 
        use_keyword: bool = True,
        use_vector: bool = True, 
        use_graph: bool = True
    ) -> HybridQueryResult:
        """
        Executes the query and ranks results from all available storage layers.
        """
        pass
