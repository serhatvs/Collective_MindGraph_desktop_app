# Slide Outline: Collective MindGraph MVP

### Slide 1: Title
- **Title**: Collective MindGraph
- **Subtitle**: Local-First Organizational Memory for Technical Meetings
- **Visual**: Project logo or a stylized graph connecting a microphone to a technical tree.
- **Speaker Notes**: Welcome. Introducing a privacy-first way to capture and retrieve meeting intelligence.

### Slide 2: The Problem
- **Bullet Points**:
  - Information loss in technical discussions.
  - Privacy risks with cloud-based AI.
  - Language gap in local-first Turkish tools.
- **Visual**: Icons representing a leaking bucket (info loss) and a "cloud" with a warning sign (privacy).
- **Speaker Notes**: Decisions are forgotten, and proprietary data shouldn't leave the building.

### Slide 3: The Solution
- **Bullet Points**:
  - Strictly offline-capable processing.
  - Dual-transcript preservation (Raw + Cleaned).
  - Automated technical Turkish extraction.
- **Visual**: Diagram showing audio staying on-device and turning into structured nodes.
- **Speaker Notes**: We keep everything local, ensuring data sovereignty while automating meeting minutes.

### Slide 4: Current MVP Architecture
- **Bullet Points**:
  - Local STT: Optimized Faster-Whisper.
  - Heuristic Extraction: Technical Turkish linguistic patterns.
  - Hierarchical Storage: Basic graph-node persistence in SQLite.
- **Visual**: A pipeline flow diagram (Audio -> VAD -> ASR -> Cleanup -> SQLite).
- **Speaker Notes**: Our software MVP handles the end-to-end flow entirely on local hardware.

### Slide 5: Product Loop Demo
- **Bullet Points**:
  - Automated transcript cleaning.
  - Heuristic detection of tasks and decisions.
  - Traceable Global Search.
- **Visual**: Screenshot of the Search UI navigating back to a specific transcript line.
- **Speaker Notes**: We don't just search text; we find extracted insights and link them back to their source.

### Slide 6: Validation Status
- **Bullet Points**:
  - 91% Keyword Overlap on clean Turkish speech.
  - Strictly verified offline safety guards.
  - 170+ automated regression tests.
- **Visual**: A bar chart showing the Common Voice benchmark results.
- **Speaker Notes**: We've proven the core logic on clean speech; meeting-room validation is our next step.

### Slide 8: Project Status
- **Implemented**: Local pipeline, clean-speech regression, Global Search.
- **Claim Boundary**: The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It is not yet a production-validated meeting intelligence platform.
- **Next Step**: Real meeting-room audio validation.
- **Speaker Notes**: We are demo-ready and integration-ready, and we know exactly what's next.
