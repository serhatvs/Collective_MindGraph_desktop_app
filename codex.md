# codex.md

## Project

- Name: Collective MindGraph
- Type: Native Windows-first desktop application
- Stack: Python 3.11+, PySide6, SQLite
- Entry command: `python -m collective_mindgraph_desktop`

## Current State

- The repo contains a working local-first desktop app scaffold under `src/collective_mindgraph_desktop`.
- The repo now also contains a separate end-user desktop subproject under `companion/`.
- The repo now also contains a separate backend subproject under `realtime_backend/` for near-real-time multi-speaker transcription, diarization, and transcript correction.
- The application includes a `QMainWindow`, session explorer, detail panels, demo seed flow, snapshot rebuild flow, and JSON export.
- The main desktop window now also includes a `Voice Command` panel with staged UI controls for `Start Recording`, `Stop`, `Transcribe`, and `Clear`, plus a transcript output area.
- The MVP UI now exposes direct empty-state actions for `New Session` and `Seed Demo Data`, and menu actions are enabled or disabled based on current selection/state.
- The desktop layout is now sidebar-first and more minimal: sessions stay in a persistent left column, the top summary bar has been removed, and the session-detail area stays fully hidden until the user explicitly selects a session.
- Persistence is handled locally with SQLite; there are no external services, browsers, webviews, or network dependencies in the app architecture.
- Early-stage product flow is now being defined from input to output using a rubber duck workflow; the first input is a spoken command that will be transcribed to text.
- Voice-command behavior now includes real microphone capture to local `.wav` files through QtMultimedia and a transcription stage that targets Amazon Nova.
- Voice-command transcription is now wired to an Amazon Nova adapter through AWS Bedrock `converse` requests with direct audio bytes upload, using `boto3` and the Nova audio-understanding path rather than the lower-level Nova Sonic streaming API.
- The current app can complete the `record audio -> send to Nova -> receive transcript text` path in code, but live AWS execution still depends on external AWS region, credentials, and Bedrock model access being configured.
- The MVP target environment is a laptop-first workflow that uses the built-in laptop microphone as the primary audio input device.
- Recorded voice-command clips are now stored in a root-level `recordings/` folder inside the project workspace instead of the user's AppData directory.
- Transcript settings are now editable from the voice-command UI and stored locally in a root-level `transcription_settings.json` file.
- Transcript completion is now wired into a local session flow: if no session is explicitly selected, the next transcript starts a new session automatically; if a session is selected, the transcript is appended to that session.
- The default transcription preset is now aligned to `Amazon Nova 2 Lite` with `us.amazon.nova-2-lite-v1:0` in `us-east-1` so project-gallery or judging flows that prefer named Nova 2 options match the implementation more closely.
- Based on the Devpost hackathon framing, the current project aligns better with `Amazon Nova 2 Lite` and the Multimodal Understanding style of submission than with `Nova 2 Sonic`, unless the app is later redesigned around real-time conversational voice interaction.
- Automated tests cover schema creation, session create/list/search, demo seeding, snapshot hash determinism, and export payload structure.
- Root-level repo memory is now defined through `AGENTS.md` plus this `codex.md` file.
- This workspace is now a git repository and has been pushed to `https://github.com/serhatvs/Collective_MindGraph_desktop_app.git`.
- A separate end-user application concept is now in scope as a sibling product to the current AI or reasoning-facing desktop app.
- The companion app is implemented as `Collective MindGraph Companion` with its own package, tests, local SQLite storage, notes autosave, main-category and sub-category hierarchy, and a generated workspace map that displays session templates inside that category tree.
- The realtime backend MVP is implemented as a FastAPI service with `/health`, `/transcribe/file`, `/transcript/{id}`, `/summary/{id}`, and `/transcribe/stream`, plus a pluggable pipeline for VAD, ASR, diarization, speaker mapping, transcript formatting, and LLM post-processing.
- The realtime backend now also includes practical ingest client scripts: `scripts/transcribe_file.py` for file upload and `scripts/stream_microphone.py` for live microphone streaming into the WebSocket endpoint.
- A dedicated LLM post-processing module now exists in the realtime backend and exposes provider abstraction for `mock`, `none`, `ollama`, and OpenAI-compatible HTTP APIs while preserving both raw and corrected transcript text.
- The realtime backend VAD layer now includes adaptive energy-threshold fallback logic plus post-processing that merges tiny gaps and splits overly long speech regions for safer long-form downstream processing.
- The realtime backend ASR layer now transcribes VAD-derived WAV regions chunk by chunk instead of running only a single full-file pass, then re-applies offsets and deduplicates padded boundary repeats.
- The realtime backend diarization layer now supports VAD-driven diarization windows with padding, bounded window sizes, duplicate-turn cleanup, adjacent-turn merging, and overlap marking before transcript alignment.
- The realtime backend speaker-mapping layer now resolves diarization labels chunk by chunk using overlap and recency voting against prior transcript segments, while maintaining stable `Speaker_n` IDs across chunk boundaries.
- `tests/README.md` now contains the original project README for comparison: the original product was a Docker-first distributed multi-agent reasoning demo with MQTT, Postgres, agents, and a browser dashboard.
- The companion UI has been realigned again so the selected session is the center of the experience, with a readable session flow and a session-centered mindgraph derived from notes, template choice, branch context, and related sessions.

## Architecture

- Source layout uses `src/collective_mindgraph_desktop`.
- Main layers are `models`, `database`, `repositories`, `services`, and `ui`.
- UI is built with native Qt widgets through PySide6.
- Repository classes own SQLite access; service layer owns higher-level workflows.
- The first planned upstream pipeline stage is `voice command -> transcription text`, now implemented with a local audio capture adapter plus an Amazon Nova transcription adapter.
- The desktop service layer now also owns a local `transcript -> session/transcript/node/snapshot` ingestion path so the UI can behave more like a chat app even when live API work is deferred.
- The main window now uses a horizontal split with a dedicated session sidebar and a separate content column for voice input plus an on-demand session-detail panel.
- A dedicated `voice_command.py` workflow module now owns the UI-facing voice state transitions, while `audio_capture.py` owns real microphone recording to local files through QtMultimedia.
- `transcription.py` now defaults to the `Amazon Nova 2 Lite` model ID `us.amazon.nova-2-lite-v1:0`, which fits the current Bedrock `converse` implementation better than Nova Sonic.
- The MVP audio-capture path should assume a single-user laptop setup and prefer the default built-in microphone unless a later settings surface adds device selection.
- The audio capture default output path is now `Path.cwd() / "recordings"`, so recordings stay alongside the project files during MVP development.
- The transcript settings surface currently edits region, model ID, max tokens, temperature, top-p, and the transcription prompt, then persists them through `AmazonNovaTranscriptionSettingsStore`.
- The sibling user-facing product lives in `companion/src/collective_mindgraph_user_app` with the same layered structure and its own `companion/pyproject.toml`.
- The sibling realtime backend lives in `realtime_backend/app` and is organized into `api`, `pipeline`, `services`, and `utils`, with separate tests and requirements.
- Realtime ingest is split cleanly by responsibility: the backend accepts file uploads and raw PCM WebSocket streams, while microphone capture lives in a separate client script instead of being embedded into the server process.
- VAD configuration now includes merge-gap, smoothing, adaptive-threshold, and max-region splitting controls to improve long-recording chunk boundaries before ASR and diarization.
- ASR configuration now includes region padding for chunk-based transcription, and the current pipeline keeps word timestamps aligned back to the original timeline after per-region decoding.
- Diarization configuration now includes region padding, merge-gap, and max-window controls so long recordings can be diarized in bounded windows instead of only full-file passes.
- Speaker stabilization now keeps a persistent speaker profile registry and avoids reusing the same stable speaker ID for multiple new raw labels inside the same chunk unless prior evidence supports it.
- The companion app now uses category-first data modeling: `main_categories`, `sub_categories`, `user_sessions`, and `note_entries`. Its workspace map is derived from categories plus sessions rather than stored as a separate editable graph table.
- The companion service now also derives `session_flow` and `session_graph` views from each session's notes and branch context so the UI can stay closer to the original product's session/graph semantics without introducing external services.

## User Preferences

- Build and maintain a real native desktop app, not a web app.
- Keep the product local-first, single-process, and SQLite-backed.
- Prefer clean layering, connected runnable code, and practical implementations over over-abstraction.
- While the project is still at the beginning stage, work in a rubber duck style: reason step by step from input toward output in sequence.
- For the initial input stage, assume spoken commands are the primary interaction and Amazon Nova is the temporary/default transcription provider.
- For early feature work, prefer building the UI shell first and then wiring button functionality incrementally instead of starting with low-level capture code in isolation.
- Keep this `codex.md` updated after user prompts so future work starts with current repo context.
- Prefer the simpler Nova audio-understanding + Bedrock `converse` route for recorded-file transcription before considering Nova Sonic streaming.
- For the MVP, optimize around laptop usage and the built-in laptop microphone rather than external studio or headset hardware.
- Keep transcript settings local and file-based for MVP; do not store AWS secrets in the project settings file.
- If external evaluators or project-gallery forms ask which Nova model was used, answer with `Amazon Nova 2 Lite` for the current implementation.
- For the hackathon context, using paid AWS cloud services is acceptable if it reduces implementation risk and keeps the demo aligned with Amazon Nova.
- For the immediate next phase, defer live API or Bedrock integration work and prioritize local product wiring, UX flow, and transcript-to-session behavior.
- For transcript UX, follow a ChatGPT-like rule: no explicit session selection means start a new session; explicit selection means continue that session.
- The user is now exploring a higher-bar voice product direction: multi-speaker conversational tracking with speaker continuity, tone/context awareness, and reliable long-recording handling rather than a simple one-shot `record -> transcribe` flow.
- This direction should not assume only two speakers; the architecture needs dynamic speaker handling for 3+ participants, including uncertainty and correction paths.
- For LLM correction, keep provider abstraction clean so local and API-backed models can be swapped without changing transcript pipeline orchestration.
- A local LM Studio GGUF model is available for experimentation: `Qwen3-VL-8B-Instruct-Q4_K_M.gguf` under `C:\Users\VICTUS\.lmstudio\models\lmstudio-community\Qwen3-VL-8B-Instruct-GGUF`.
- For the realtime backend, LLM post-processing should stay last in the implementation order; first priority is getting the raw conversation pipeline solid end to end with capture, VAD, ASR, diarization, speaker stability, and structured transcript output.
- The desktop UI is expected to represent the AI or reasoning-facing part of the product, not generic admin tooling.
- The separate end-user app should not feel like a generic CRUD manager; it needs a clearer consumer-facing product shape.
- The companion app should prioritize easy idea capture, visible category hierarchy, and session-template visualization over abstract `insight` or `action item` features.
- When comparing against the original project README, preserve more of the original product DNA around sessions, reasoning structure, and "mindgraph" semantics instead of drifting into a generic personal organizer.
- For the companion UI specifically, categories are context, not the center; the selected session, its flow, and its generated graph should lead the screen.

## Open Decisions / Risks

- Repo memory is enforced through `AGENTS.md`; there is no visible global Codex hook for automatic runtime-wide updates.
- `codex.md` must stay compact and rewritten in place, not turn into an append-only log.
- Amazon Nova as the initial speech-to-text provider introduces an external network dependency that partially conflicts with the local-first app direction; transcription should stay behind a replaceable adapter boundary.
- Live Nova transcription has not yet been verified against a real AWS account from this workspace because the current local environment has neither `AWS_REGION` nor AWS credentials configured.
- Direct Bedrock `converse` audio upload has a 25 MB limit in the current implementation; larger audio would need an S3-backed path if that becomes necessary.
- `Amazon Nova 2 Sonic` remains a possible future option, but it is not the current default because the app is built around recorded-file transcription via `converse`, not Sonic's lower-latency voice streaming path.
- The new realtime backend is production-style at the module boundary, but true live diarization quality still depends on heavy external dependencies (`faster-whisper`, `pyannote.audio`, `silero-vad`, ffmpeg, CUDA-ready PyTorch) being installed and validated on the target machine.

## Next Likely Tasks

- Keep this file aligned with any durable changes to architecture, workflow, or user preferences.
- During early-stage work, structure implementation discussions and changes sequentially from input to output instead of jumping ahead to later layers.
- Configure real AWS region, credentials, and Bedrock model access so the current Nova transcription path can be exercised end to end.
- If transcription quality or latency becomes a problem, compare the current recorded-file `converse` approach with a future Nova Sonic streaming path.
- Once live transcription is verified, decide how transcript text should feed into session creation, transcript history, and graph generation inside the desktop app.
- Decide whether transcript settings should later move from `transcription_settings.json` into a richer app settings surface or remain repo-local for development.
- Keep the current audio capture boundary replaceable so transcription providers can change without reworking the UI panel.
- If the product shifts further toward multi-speaker conversation analysis, the likely next architecture step is speaker diarization plus rolling context memory for long recordings instead of single-file transcription only.
- Supporting more than two speakers is an explicit product risk: speaker drift, overlapping speech, and identity continuity will need confidence scoring plus a manual correction path in the UI.
- Validate the realtime backend against real GPU-backed local runs, long recordings, and 3+ speaker conversations before connecting it to any UI layer.
- After ingest plumbing, the next backend priority remains VAD/ASR/diarization quality on real audio rather than LLM cleanup.
- Do not spend the next iteration on transcript cleanup models before the base pipeline is verified on real audio, long files, and multi-speaker sessions.
- If the backend matures, decide whether it remains a sibling service or becomes the speech/conversation engine behind the desktop product.
- If the desktop app gains or loses major features, update the `Current State` and `Architecture` sections.
- If UI polish continues, focus next on transcript/node creation flows and richer session editing, not web-style scaffolding.
- If work splits by audience, keep the current app AI-facing and design the normal-user app as a separate product with its own package and UX.
- Further work can evolve the companion app independently from inside `companion/` using its own install, run, and test commands.
- Companion work should keep strengthening the category-first workspace map UX rather than reintroducing schema-driven CRUD panels.
- If new repo-level working rules are added, record them here only if they remain useful across prompts.

## Last Updated

- 2026-03-06: Added repo-scoped Codex memory workflow and initialized the living project summary.
- 2026-03-06: Refined the desktop UI MVP with actionable empty-state controls and state-aware menu actions.
- 2026-03-06: Clarified that the desktop UI should be treated as the AI or reasoning-facing surface of the product.
- 2026-03-06: Added the idea of a separate normal-user application as a sibling to the AI-facing desktop app.
- 2026-03-06: Implemented the separate `companion/` subproject for the end-user desktop app.
- 2026-03-06: User clarified that the companion UI should be more product-shaped and less like schema-driven CRUD.
- 2026-03-06: Refactored the companion app into a category-first product with main categories, sub categories, quick idea capture, and a generated workspace map instead of insights, action items, and standalone mind map CRUD.
- 2026-03-06: Added the original project README under `tests/README.md` as a comparison source for keeping future UX closer to the repo's original product DNA.
- 2026-03-06: Reworked the companion UI again around session-first flow and a generated mindgraph, keeping category management only as supporting workspace context.
- 2026-03-06: Initialized git for this workspace and pushed the current history to `serhatvs/Collective_MindGraph_desktop_app` with several small history commits plus a final full project commit.
- 2026-03-10: Restored the temporary voice-command UI and stub workflow after a mistaken removal so the feature can continue from the current UI-first stage.
- 2026-03-10: Wired the voice-command panel to real microphone capture via QtMultimedia, saving local `.wav` clips while leaving transcription itself as a placeholder step.
- 2026-03-10: Replaced the placeholder transcription step with an Amazon Nova Bedrock `converse` adapter based on official Nova audio-understanding docs and added environment-aware error handling plus unit tests.
- 2026-03-10: Added a transcript settings dialog plus local `transcription_settings.json` persistence for Nova region/model/prompt and inference settings.
- 2026-03-10: Shifted the default transcription preset from Nova Pro to Amazon Nova 2 Lite so the implementation better matches common project-gallery and judging option lists while staying compatible with the current `converse` architecture.
- 2026-03-10: User decided to defer live API work temporarily and focus next on local transcript-to-session product flow and UI wiring.
- 2026-03-10: Implemented ChatGPT-like session continuation so transcript completion starts a new session only when no session is explicitly selected, otherwise it continues the selected session and persists transcript, graph, and snapshot data locally.
- 2026-03-10: Added a new `realtime_backend/` sibling FastAPI project for multi-speaker transcription with VAD, ASR, diarization, stable speaker mapping, streaming support, summary extraction, and a dedicated pluggable LLM post-processing module.
