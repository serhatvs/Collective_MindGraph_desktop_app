# Collective MindGraph V2 Roadmap

This roadmap outlines the transition from the current local software MVP to a production-validated hardware/software system with semantic intelligence.

## Phase 1: Stabilization & Validation (Short-term)
Focus on proving current software capabilities on real-world data.
- **Meeting Audio Validation**: Record project-specific technical meeting WAVs and run full quality benchmarks.
- **Diarization Audit**: Stress-test speaker identification with 3+ overlapping speakers in noisy environments.
- **UI Polish**: Improve session timeline visualization and global search result ranking.
- **Packaging**: Finalize single-file `.exe` installer with bundled lightweight models.

## Phase 2: Semantic Memory (Medium-term)
Transition from keyword-based search to similarity-based understanding.
- **Local Embeddings**: Integrate a strictly offline transformer model (e.g., Sentence-BERT) for text vectorization.
- **Vector Search**: Implement a local vector store (e.g., FAISS or simple numpy-based index) for semantic retrieval.
- **Semantic Query API**: Enable "ask a question" queries that find conceptually related results even without exact keyword matches.
- **Reranking**: Use semantic similarity to improve the relevance of search results.

## Phase 3: Graph Reasoning & Workspace (Long-term)
Expand the basic node hierarchy into a rich semantic network.
- **Arbitrary Graph Edges**: Implement non-hierarchical relationships (e.g., "Decision A relates to Task B from a different session").
- **Relationship Reasoning**: Heuristic detection of conceptual links between different meetings.
- **Multi-hop Queries**: Enable queries like "What were the decisions related to the FastAPI issue discussed last month?"
- **Organizational Workspace**: Add support for multi-user shared memory graphs with local synchronization.

## Phase 4: Hardware Integration (Future Direction)
Develop a dedicated physical device for seamless meeting intelligence.
- **Hardware Device Prototype**: A compact on-premise unit with local compute.
- **Microphone Array**: Integrated far-field microphone array for superior multi-speaker capture.
- **Status Display**: A small screen showing real-time transcription status, wake trigger readiness, and active speakers.
- **Local Inference Workflow**: Seamless push/pull of memory between the hardware device and the desktop application.

---
**Baseline**: The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It is not yet a production-validated meeting intelligence platform.
