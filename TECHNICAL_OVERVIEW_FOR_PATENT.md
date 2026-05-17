# Technical Overview for Patent Reference: Collective MindGraph

## 1. System Purpose
Collective MindGraph is a privacy-focused organizational memory system designed to capture, process, and structure information from technical conversations. The system aims to provide a local-first alternative to cloud-based transcription and intelligence services, ensuring that sensitive organizational data never leaves the local environment.

## 2. Hardware/Software Direction
While the current implementation is a software MVP (Minimum Viable Product), the conceptual design may include a dedicated hardware component. This hardware can be configured to integrate a high-fidelity microphone array and a local inference module, enabling real-time, on-premise transcription and memory extraction independent of external internet connectivity.

## 3. Local-First Privacy Model
The system architecture prioritizes data sovereignty. All processing stages—including audio normalization, voice activity detection (VAD), speech-to-text (STT), speaker diarization, and heuristic extraction—are performed locally. The system can be configured to run in a strictly offline mode, with mandatory URL and path validation guards to prevent unintentional network egress.

## 4. Current Software MVP Implementation
The current software implementation provides a foundational data processing pipeline:

### 4.1 Transcription Pipeline
- **Audio Preprocessing**: Automatic normalization of diverse audio inputs to a standardized format (e.g., 16kHz mono PCM).
- **Speech-to-Text (STT)**: A local inference engine (such as Faster-Whisper) provides multi-language support, with specific optimizations for technical Turkish terminology.
- **Dual-Transcript Model**: The system concurrently maintains a "Raw Transcript" (exact ASR output) and a "Cleaned Transcript" (processed for readability and filler removal).

### 4.2 Structured Extraction Heuristics
The system identifies and extracts high-level organizational entities from the cleaned transcript text:
- **Tasks**: Identification of necessity or future-action verb forms and responsible parties.
- **Decisions**: Detection of explicit agreement markers or passive-voice state changes.
- **Topics**: Heuristic categorization based on keyword density and technical glossary matching.

### 4.3 Memory Persistence and Search
- **Hierarchical Node Persistence**: Knowledge is stored in a basic graph-node structure (e.g., SQLite adjacency list) where extracted entities are linked to their parent conversation nodes.
- **Keyword Memory Query**: A retrieval layer that enables cross-session search over transcripts and structured entities.
- **Source Traceability**: Every extracted entity can be navigated back to its original session, timestamp, and transcript segment.

## 5. Implementation vs. Roadmap
- **Implemented**: Local ASR, raw/clean separation, heuristic technical Turkish extraction, keyword query, and source-linked desktop UI.
- **Roadmap (Potential Future Capabilities)**: Semantic vector retrieval, multi-hop reasoning, arbitrary graph edge relationships, and hardware-specific status displays.

## 6. Project Status
The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It is not yet a production-validated meeting intelligence platform.

*Note: This document describes a prototype/MVP implementation. Actual performance in non-controlled environments or meeting-room conditions is pending further validation.*
