# Collective MindGraph

> [!IMPORTANT]
> Collective MindGraph currently uses separate development tracks:
>
> - `feature/transcription-quality-pipeline` - Transcription Track  
>   For ASR/STT, Turkish transcription quality, Faster-Whisper settings, VAD/audio preprocessing, and transcription benchmarks.
>
> - `feature/transcript-to-memory-pipeline` - Memory Track  
>   For transcript/session ingestion, structured memory extraction, review lifecycle, graph memory, source traceability, hybrid search, Ask Memory, and export/import.
>
> Do not mix Transcription Track and Memory Track work in the same branch.

## Branch Scope

Collective MindGraph development is currently split into two scoped tracks:

- **Transcription Track** (`feature/transcription-quality-pipeline`): keeps the ASR/STT and Turkish transcription pipeline stable, benchmarked, and safely maintainable.
- **Memory Track** (`feature/transcript-to-memory-pipeline`): turns transcript/session data into reviewable, source-linked graph memory that can be queried through hybrid search and evidence-only Ask Memory.

Keep branch work aligned with its track. Transcription quality changes such as ASR tuning, Faster-Whisper settings, VAD tuning, audio preprocessing, or transcription benchmarking should stay separate from Memory Track changes such as graph persistence, review lifecycle, source tracing, hybrid memory search, Ask Memory, and export/import.

Collective MindGraph is a local-first, privacy-focused organizational memory system for technical teams. It captures, transcribes, and extracts structured knowledge from technical conversations—entirely on local hardware.

## Current Status: Stable Fallback-First

Collective MindGraph is stable in **fallback-first production memory mode**. This means the system is fully operational for core organizational memory tasks without requiring a local Large Language Model (LLM) server to be running.

### ✅ What works now (Stable/Offline)
- **Knowledge Graph Persistence**: Full session and insight lifecycle (Sessions, Tasks, Decisions, Topics, Entities).
- **GPU-routed Local ASR**: Validated through the real backend transcription pipeline with Faster-Whisper CUDA/float16 on a local Turkish WAV. This confirms GPU execution and routing only; it does not claim meeting-room robustness, diarization, Silero VAD validation, or measured WER/CER accuracy.
- **Hybrid Memory Query**: Combined Keyword and Graph-based reasoning.
- **Human-in-the-loop Review**: Complete UI for approving, editing, and merging extracted knowledge.
- **Evidence-only Ask Memory**: Accurate, template-based answers derived directly from the Knowledge Graph.
- **Reasoning Trace**: Full visibility into the evidence chains supporting every claim.
- **Semantic Retrieval**: Operational with local embedding models (e.g., `sentence-transformers`).
- **Source Traceability**: Every extracted item is linked back to the exact temporal segment in the transcript.
- **Export/Import**: Full session and graph context portability via JSON.
- **Job Tracking**: Real-time monitoring of background processing tasks.

### 🛠️ Optional / Manual Activation
- **Local LLM Extraction**: High-fidelity structured JSON extraction via Llama 3.1 (requires LM Studio/Ollama).
- **LLM-assisted Ask Memory**: Natural language synthesis of answers with automated hallucination guarding.

### 📋 Roadmap
- **Diarization**: Automatic speaker separation is currently not implemented or validated for production.
- **Semantic Reranking**: Improved relevance for complex multi-session queries.
- **Enhanced Graph Edges**: Transition from hierarchical trees to rich semantic networks.

## Getting Started

### 1. Run the Backend
The backend service handles audio processing, transcription, and memory extraction.
```bash
./scripts/dev_backend.sh
```

### 2. Run the Desktop App
The native PySide6 application is the primary interface for managing sessions and searching memory.
```bash
./scripts/dev_desktop.sh
```

## Main Workflows

1.  **Ingest**: Capture live audio via the Voice Panel or transcribe local technical WAV files.
2.  **Review**: Open a session to compare **Raw ASR** vs. **Cleaned Transcripts** and validate extracted insights.
3.  **Graph**: Explore the hierarchical knowledge structure where tasks and decisions are linked to transcript segments.
4.  **Search**: Use **Global Search** to find technical terms across all sessions with direct navigation to sources.
5.  **Ask Memory**: Ask questions about your organization's history and receive evidence-backed answers.
6.  **Export/Import**: Backup or share your organizational memory as portable JSON packages.

## Tests
Collective MindGraph maintains a rigorous test suite covering core logic and product loops.
```bash
PYTHONPATH=src:. python3 -m pytest
```

## Documentation
- **[Product Status](docs/product/STATUS.md)**: Capability matrix and current implementation details.
- **[Roadmap](docs/product/ROADMAP.md)**: Future development phases.
- **[Demo Guide](docs/demo/DEMO_FLOW.md)**: Instructions for running the technical demonstration loop.
- **[Developer Setup](docs/dev/SETUP.md)**: Configuration for local models and environment.
- **[Architecture](docs/dev/ARCHITECTURE.md)**: Technical overview of the system design.
- **[Reports Archive](docs/reports/README.md)**: Dated benchmark, validation, and simulation report archive.
- **[Patent-Safe Claims](docs/patent/PATENT_SAFE_CLAIMS.md)**: Formal terminology for IP filings.
