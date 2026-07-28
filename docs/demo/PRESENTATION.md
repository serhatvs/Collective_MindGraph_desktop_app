# Collective MindGraph Presentation Notes

## One-sentence description

Collective MindGraph turns local meeting audio into reviewable transcripts,
evidence-linked knowledge, and searchable organizational memory.

## Suggested story

1. Conversations contain decisions and actions that are hard to recover later.
2. Collective MindGraph processes the audio locally and keeps raw evidence.
3. People correct transcripts and accept or reject extracted insights.
4. Accepted knowledge becomes searchable and can support evidence-backed
   answers.
5. Every answer exposes its meeting/segment sources and reasoning trace.

## Live sequence

```powershell
python scripts/datasets/seed_demo_meeting.py
mindgraph
```

Show Home, open the seeded meeting, correct one transcript segment, review an
insight, then search and ask from Memory. Finish by switching the interface
between Turkish and English and opening Privacy/Diagnostics.

## Architecture slide

```text
PySide6 desktop
      ↓ typed localhost API
FastAPI engine
      ↓
use cases → local adapters → normalized SQLite
```

The domain/application layers do not depend on Qt, FastAPI, SQLite, or model
providers. The engine is the only persistent-data owner.

## Honest claim

The demonstrated capture-to-memory loop is locally implemented and covered by
automated tests. Speaker separation and real meeting-room accuracy are not yet
validated, and optional local models must be configured separately.
