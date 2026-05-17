# Demo Presentation Notes: Collective MindGraph MVP

These notes guide you through presenting the current local-first software MVP. 

## Preparation
1.  **Check Readiness**: Run `./scripts/check_demo_readiness.sh`.
2.  **Seed Data**: Run `PYTHONPATH=. python realtime_backend/scripts/seed_demo_session.py`.
3.  **Start Services**: Launch `./scripts/dev_backend.sh` and `./scripts/dev_desktop.sh`.

---

## 2-Minute Demo: The Knowledge Loop
1.  **Open Seeded Session**: Select `demo_technical_turkish` in the Session Explorer.
2.  **Highlight Cleaned Transcript**: Show how technical terms like *FastAPI* and *MindGraph* are correctly capitalized and readable.
3.  **Show Extracted Insights**: Point to the "Decision" and "Action" nodes in the right panel.
4.  **Quick Search**: Open **Global Search**, type `FastAPI endpoint`, and double-click the result to show immediate navigation back to the source.

## 5-Minute Technical Demo: Architecture & Privacy
1.  **Offline Proof**: Explain that no internet connection is active.
2.  **Audio Audit**: Open the **Analysis** tab. Compare **Raw ASR** (with fillers like *şey, ııı*) vs. **Corrected Text**.
3.  **Heuristic Extraction**: Explain how the system uses local regex/glossaries to find tasks and decisions without cloud LLMs.
4.  **Cross-Session Retrieval**: Perform multiple searches:
    - `raw transcript`: Shows how the system remembers architectural decisions across meetings.
    - `VAD ayarları`: Shows extracted technical tasks.
    - `Collective MindGraph`: Shows topic-level indexing.
5.  **Source Traceability**: Explain the score logic and how every result is pinned to a session ID and segment UUID.

---

## Demonstration Query Guide
| Query | Expected Result | Proves |
| :--- | :--- | :--- |
| `FastAPI endpoint` | Task | Heuristic future-action extraction. |
| `raw transcript` | Decision | Passive-voice decision detection. |
| `VAD ayarları` | Task / Topic | Technical term recognition. |
| `kararlar` | Decision | Turkish agreement marker detection. |
| `Collective MindGraph`| Session / Topic | Multi-type keyword relevance. |

---

## Important Caveats (What NOT to claim)
- **Production-Ready**: Do not claim it is ready for critical production meeting rooms without further audio validation.
- **Full Semantic AI**: The current search is keyword-based. Do not claim it "understands" concepts semantically yet.
- **Full Graph Reasoning**: The system uses hierarchical nodes, not a multi-hop graph reasoning engine.
- **Perfect Diarization**: State that diarization is optimized for local environments but can be model-limited in high noise.

---
**Status**: Local MVP Demo Ready. Product-integration ready for keyword-based memory exploration.
