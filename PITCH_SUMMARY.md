# Pitch Summary: Collective MindGraph

## One-Sentence Explanation
Collective MindGraph is a local-first, privacy-focused system that transcribes technical Turkish conversations and automatically extracts structured organizational memory like tasks and decisions.

## 30-Second Explanation
Most organizations lose critical context after technical meetings or risk privacy by sending data to cloud AI. Collective MindGraph solves this by running a complete intelligence pipeline—from speech-to-text to task extraction—entirely on local hardware. It specifically handles technical Turkish terminology and provides a traceable memory where every decision is linked back to the exact moment it was discussed.

## 2-Minute Explanation
Collective MindGraph is more than a transcription app; it is a prototype for an autonomous organizational memory. It uses a specialized local pipeline (Faster-Whisper + heuristic extraction) to process audio. It maintains a dual-transcript model: preserving the raw ASR for auditability while providing a cleaned, readable version for intelligence extraction. 

The current MVP demonstrates a full product loop: it captures speech, cleans it, identifies tasks and decisions using Turkish-specific linguistic patterns, and stores them in a hierarchical node structure. Users can then query this memory across multiple sessions. For example, asking about a "FastAPI endpoint" retrieves the specific task and allows the user to jump straight back to that segment in the original meeting.

## The Problem
- **Information Loss**: High-value technical decisions and action items are often lost or misremembered after meetings.
- **Privacy Risks**: Sensitive corporate data is frequently sent to external cloud providers (AWS, OpenAI) for processing.
- **Language Gap**: Most local-first tools are English-biased and fail to correctly process technical Turkish meeting contexts.

## The Solution
A strictly offline-capable platform that provides:
1. **Sovereign Transcription**: Local technical Turkish STT.
2. **Automated Memory**: Heuristic extraction of organizational "nodes" (Tasks, Decisions, Topics).
3. **Traceable Knowledge**: A search interface that links every insight back to its source session.

## Current MVP Capabilities
- **Local Pipeline**: Standardized audio normalization and offline transcription.
- **Turkish Optimization**: Glossary-aware STT and necessity/future-form task extraction.
- **Traceability**: Keyword-based search with direct source-segment navigation.
- **Offline Safety**: Mandatory guards ensuring zero data egress.

## Implemented vs. Pending
- **Implemented**: ASR pipeline, raw/clean separation, heuristic extraction, basic node storage, keyword query, desktop UI.
- **Pending**: Semantic/vector search, multi-hop reasoning, hardware integration, and large-scale meeting-room validation.

## Project Status
**The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It is not yet a production-validated meeting intelligence platform.**

## Why Local-First Matters
In technical and corporate environments, privacy is a functional requirement. By removing cloud dependencies, Collective MindGraph ensures that proprietary technical discussions, architectural decisions, and internal tasks remain within the organization’s secure perimeter.
