# Real Transcript Fixture Validation Report

## Branch

`test/real-transcript-fixture-validation`

## Fixture Used

- Text fixture: `tests/fixtures/realistic_turkish_memory_session.txt`
- Content: anonymized Turkish meeting-style transcript covering payment flow, PostgreSQL indexing, mobile release timing, Redis follow-up, risk, open question, ambiguity, and a social sentence that should not become a task or decision.

## What Was Validated

- Fixture transcript was loaded with Turkish characters preserved.
- Raw transcript and cleaned transcript were kept separate.
- Segments were created from the cleaned transcript and persisted in transcript analysis.
- Structured extraction path was exercised with a deterministic local mocked LLM response for repeatable validation.
- TASK, DECISION, TOPIC, ENTITY, RISK, OPEN_QUESTION, and FOLLOW_UP graph nodes were persisted.
- Graph edges and source references were created.
- Human review state was updated for selected nodes.
- Evidence-only Ask Memory returned source-linked evidence for a supported PostgreSQL task query.
- Evidence-only Ask Memory returned no evidence for an unsupported Docker task query.
- The social/irrelevant sentence about coffee was not persisted as a task or decision.
- Lightweight offscreen UI smoke rendered a selected session, Diagnostics, memory search results, and Ask Memory evidence without crashing.
- Diagnostics continued to show diarization as `NOT IMPLEMENTED / ROADMAP`.

## Tests Run

The literal `pytest` executable was blocked by Windows application policy in this environment, so validation used `python -m pytest`.

```powershell
$env:PYTHONPATH='src;.'; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_realistic_turkish_fixture_validation.py
```

Result:

```text
1 passed in 1.10s
```

```powershell
$env:PYTHONPATH='src;.'; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest
```

Result:

```text
181 passed, 3 skipped, 1 warning in 24.07s
```

## Pass/Fail Result

Passed for the text-fixture product loop.

Skipped optional environment checks:

- Local LLM endpoint not reachable at `http://127.0.0.1:1234/v1`.
- Real local semantic embedding model not configured.

## Audio Fixture Validation

Not run. No real Turkish meeting-room audio fixture exists in the repo under `tests/` or `realtime_backend/tests/`.

No fake audio fixture was added.

## WER / Accuracy

Not measured. There is no real audio plus human reference transcript pair in this branch, so no WER/CER or ASR accuracy claim is made.

## Known Gaps

- The test validates realistic Turkish text input and downstream memory behavior, not live ASR quality.
- Structured extraction is deterministic in the test through a mocked local LLM response; it does not claim live LLM extraction quality.
- Semantic/vector retrieval remains optional and configuration-dependent.
- Diarization and speaker separation remain not implemented.
- UI validation is smoke-level only and does not test visual layout quality.

## Recommended Next Validation

- Add a cleared Turkish meeting-room audio fixture plus human reference transcript.
- Run ASR fixture validation without claiming diarization.
- Compare raw ASR output to the human reference only when the fixture is available and consent-cleared.
