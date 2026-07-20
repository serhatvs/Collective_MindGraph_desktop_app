# FINAL STABLE FALLBACK STATUS

## Current Stable Default: Fallback-First Production Memory

Collective MindGraph is currently optimized for a **stable, 100% offline experience** without requiring a local Large Language Model (LLM) server to be running by default. All core organizational memory features remain operational via deterministic heuristic and graph-based reasoning.

### ✅ What works without Local LLM:
- **Knowledge Graph Persistence**: Full V2 schema support (Sessions, Segments, Tasks, Decisions, Topics, Entities, Risks, Open Questions, Follow-ups).
- **Hybrid Memory Query**: Multi-modal search using Keyword and Graph reasoning.
- **Human-in-the-loop Review**: Complete lifecycle for approving, editing, rejecting, and merging extracted knowledge items.
- **Evidence-only Ask Memory**: Accurate, template-based answers derived directly from the Knowledge Graph.
- **Reasoning Trace**: Full visibility into the evidence chains (Session -> Segment -> Insight) supporting every claim.
- **Export/Import**: Full session and graph context portability.
- **Semantic Retrieval**: Operational if a local embedding model is configured (otherwise falls back to keyword/graph).

### 🛠️ Optional Features (Require Local LLM):
- **High-Fidelity AI Extraction**: Structured JSON extraction via Llama 3.1 8B (LM Studio/Ollama).
- **LLM-assisted Ask Memory**: Natural language synthesis of answers with automated hallucination guarding.

### 📋 How to run the Demo (No LLM Required):
```bash
# 1. Start the backend (defaults to heuristic fallback)
./scripts/launch/dev_backend.sh

# 2. Start the Desktop UI
./scripts/launch/dev_desktop.sh

# 3. Use 'Global Search' and 'Ask Your Memory' (Evidence-only mode)
```

### 🚀 How to re-enable Local LLM:
1. Start **LM Studio** or **Ollama** on `http://127.0.0.1:1234/v1`.
2. Update `.env` or set environment variables:
   ```bash
   export CMG_LOCAL_LLM_PROVIDER=lmstudio
   export CMG_LOCAL_LLM_ENDPOINT=http://127.0.0.1:1234/v1
   export CMG_EXTRACTION_MODE=local_llm
   ```
3. Restart the backend.
4. Verify via `Diagnostics` page in the UI (should show **ACTIVE**).

---
*Note: Diarization (speaker identification) remains on the long-term roadmap.*
