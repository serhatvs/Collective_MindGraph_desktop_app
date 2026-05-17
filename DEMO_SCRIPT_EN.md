# Demo Script (English)

This script is designed for presenting Collective MindGraph to professors, reviewers, or technical partners.

## Opening
"Hello, today I will present Collective MindGraph—a local-first, privacy-focused organizational memory system."

## Problem & Solution
"During technical meetings, critical decisions and tasks are often lost or misrecorded. Relying on cloud AI services creates privacy risks for sensitive data. Our solution provides a strictly offline pipeline that transcribes technical Turkish conversations and automatically extracts structured memory."

## Current MVP Capabilities
"The current prototype handles standardized audio normalization, local STT optimized for Turkish technical terms (like FastAPI and SQLite), heuristic extraction of tasks and decisions, and traceable keyword-based retrieval."

## Demo Steps

1.  **Readiness**: "First, we verify that the local environment and models are correctly configured." (`./scripts/check_demo_readiness.sh`)
2.  **Seeding Data**: "We seed the system with a technical Turkish meeting sample to demonstrate the extraction logic without requiring live audio." (`PYTHONPATH=. python realtime_backend/scripts/seed_demo_session.py`)
3.  **Launch**: "We start the local backend service on port 8081 and launch the native PySide6 desktop UI, which is our primary user interface." (`./scripts/dev_backend.sh` and `./scripts/dev_desktop.sh`)
4.  **Session Review**: "We open the 'demo_technical_turkish' session from the explorer."
5.  **Cleaned Transcript**: "Note how the system handles technical casing and filters out filler words for better readability."
6.  **Structured Insights**: "Observe the automatically extracted Tasks and Decisions in the side panel, such as 'FastAPI testing' or 'SQLite storage decisions'."
7.  **Global Search**: "Let's perform a cross-session search. I'll query for 'FastAPI endpoint'."
8.  **Traceability**: "By double-clicking the search result, the system navigates directly back to the source session and highlights the exact segment where this was mentioned."

## Important Caveats
"Current retrieval is keyword-based. We have established placeholders for semantic vector search and complex graph reasoning as part of our future roadmap."

## Closing
"Collective MindGraph establishes a stable foundation for sovereign organizational memory. Thank you for your time."

---
**Status**: The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It is not yet a production-validated meeting intelligence platform.
