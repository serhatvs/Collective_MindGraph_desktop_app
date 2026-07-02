# Technical Q&A: Collective MindGraph MVP

## 1. Is this just a transcription app?
No. While it includes a transcription pipeline, the core value is the **structured memory extraction**. It doesn't just produce text; it identifies organizational entities (Tasks, Decisions, Topics) and preserves them in a searchable, traceable database linked back to source segments.

## 2. Is meeting-room accuracy proven?
No. The current **91% keyword overlap** benchmark is based on the **Mozilla Common Voice** Turkish dataset (clean, scripted speech). While the infrastructure is ready for technical meetings, real meeting-room production accuracy (with noise and overlap) is pending manual validation with specific meeting fixtures.

## 3. Is this a full graph database?
No. The current implementation uses **basic graph-node persistence**. It stores knowledge in a hierarchical SQLite structure (tree-style adjacency list). Arbitrary graph edges and complex relationship reasoning are planned for the V2 roadmap.

## 4. Does it use cloud AI (OpenAI, Bedrock)?
No. All cloud AI logic (Amazon Bedrock, Deepgram) has been **completely removed**. The system is strictly local-first and offline-capable by default.

## 5. What is "local-first" in this context?
It means all audio normalization, VAD, ASR, and extraction happen on the user's machine. The system includes **offline safety guards** that prevent it from making unintentional network calls to public APIs. The **frontend** is a native desktop application that communicates with this local service.

## 6. Where is the user interface?
The user interface is a **native PySide6 desktop application**. The FastAPI backend at `127.0.0.1:8080` is a background service and is not the intended user interface. Use `/docs` only for developer debugging.

## 7. What is the difference between raw_transcript and cleaned_transcript?
- **Raw Transcript**: The exact, unfiltered output from the ASR model, preserved for auditability and debugging.
- **Cleaned Transcript**: Metatdata-aware text processed to remove Turkish filler words (*şey, yani, ııı*) and normalize technical casing (*FastAPI, SQLite*).

## 8. What is the difference between keyword search and semantic search?
- **Keyword Search (Implemented)**: Finds exact token matches in the database.
- **Semantic Search (Planned)**: Uses vector embeddings to find conceptually related results (e.g., searching "database" finds "SQLite").

## 9. What is the strongest technical novelty angle?
The **dual-transcript auditable pipeline** combined with **deterministic technical Turkish heuristic extraction** running in a strictly **privacy-preserved offline environment**.

## 10. How is privacy handled?
By design, the system has no code paths to cloud AI providers. All endpoints are validated against local/private IP ranges. Audio files and transcripts never leave the local storage directories.

## 11. What happens to raw audio?
Audio is normalized locally and temporarily stored in a `temp/` directory for processing. Users can configure retention or permanent storage settings.

## 12. What is the current official status?
The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It is not yet a production-validated meeting intelligence platform.
