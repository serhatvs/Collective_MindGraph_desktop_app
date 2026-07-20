# Collective MindGraph Transcription System Analysis

Date: 2026-06-22

Scope: speech-to-text quality only. This report intentionally ignores graph persistence, Ask Memory, knowledge extraction, review workflow, LLM reasoning, UI improvements, and patent positioning.

Current implementation note: the first transcription quality-hardening pass has been applied. `auto` ASR fallback to mock is now explicit through `ASR_STATUS=MOCK_FALLBACK`, transcription responses include benchmark-ready metadata, quality profiles are explicit (`fast`, `balanced`, `max_quality`), `max_quality` is the default profile, Turkish cleanup defaults to `conservative`, and preprocessing diagnostics now report ffmpeg success plus inspected WAV facts when available.

## 1. Executive Summary

Current transcription architecture: a local FastAPI backend receives file uploads or PCM WebSocket streams, normalizes audio to WAV/PCM, runs VAD, chunks long audio, calls Faster-Whisper, aligns ASR segments with speaker turns, optionally applies local LLM post-processing, applies deterministic Turkish cleanup, then stores structured JSON transcripts.

Primary code path:

`realtime_backend/app/api/routes.py` or `realtime_backend/app/api/ws.py` -> `realtime_backend/app/services/transcription_service.py` or `realtime_backend/app/services/streaming.py` -> `realtime_backend/app/pipeline/orchestrator.py` -> `realtime_backend/app/pipeline/vad.py` -> `realtime_backend/app/pipeline/asr.py` -> `realtime_backend/app/pipeline/alignment.py` -> `realtime_backend/app/pipeline/llm_postprocess.py` -> `realtime_backend/app/utils/turkish_cleanup.py` -> `realtime_backend/app/services/conversation_store.py`.

Current transcription maturity: technically credible local MVP / quality-tuning prototype. It has real Faster-Whisper integration, local VAD, chunking, word timestamps, Turkish language forcing, and benchmark scaffolding. It is not yet production-validated for real-world Turkish meeting-room conversations.

Main strengths:

- Forces `language="tr"` by default through `Settings.default_language`, reducing language-detection risk.
- Uses `large-v3` by default after the quality-hardening pass, with CUDA/float16 default settings when available. `large-v3-turbo` remains a reasonable speed/quality candidate to benchmark locally.
- Enables word timestamps and uses them for segment alignment.
- Disables Faster-Whisper internal VAD by default and uses an explicit external VAD/chunking pipeline, making segmentation behavior inspectable.
- Preserves raw ASR text separately from cleaned text.
- Emits ASR/provider/profile/preprocessing metadata suitable for later benchmark comparisons.
- Includes Common Voice Turkish import/benchmark scripts and approximate WER/CER tooling.

Main weaknesses:

- Real-world Turkish meeting-room validation is not present in the checkout; the project-specific meeting WAV is absent.
- Default CUDA/float16 settings can fail or fall back depending on local hardware/runtime.
- `auto` ASR provider can still fall back to `MockASR` if Faster-Whisper cannot load, but this is no longer silent: diagnostics/API metadata expose `ASR_STATUS=MOCK_FALLBACK`, `mock_fallback_used=true`, and warning text.
- VAD/chunking may clip or over-split conversational Turkish if thresholds are not tuned against real meetings.
- Conservative cleanup is now default and no longer removes filler words globally. Aggressive cleanup can still alter transcript fidelity if enabled.
- LLM post-processing defaults are confusing: `Settings.llm_provider` defaults to `"disabled"`, but `build_llm_postprocessor` treats unknown values as LM Studio, which may fail and then return raw text.
- Benchmarking exists but is partial and should not be treated as scientific accuracy validation.

Estimated readiness for real-world Turkish conversations: partial. The architecture is suitable for local quality experiments and clean-speech regression. It is not yet validated for noisy, overlapping, multi-speaker Turkish meetings. Confidence: High.

## 2. Current Pipeline Mapping

### Audio Input

- File upload endpoint: `realtime_backend/app/api/routes.py`, `transcribe_file`.
- WebSocket stream endpoint: `realtime_backend/app/api/ws.py`, `transcribe_stream`.
- Desktop file worker: `src/collective_mindgraph_desktop/ui/workers.py`, `BackendTranscriptionWorker`.
- Desktop microphone recorder: `src/collective_mindgraph_desktop/audio_capture.py`, `AudioCaptureController`.
- Configuration source: `realtime_backend/app/config.py`, `src/collective_mindgraph_desktop/transcription.py`, and the ignored local runtime file `transcription_settings.json`.
- Dependencies: FastAPI, PySide6 multimedia, HTTP multipart, WebSocket, local filesystem.
- Failure points: backend URL mismatch, missing file, malformed upload, no microphone, recorder errors, stream format mismatch.
- Quality impact: input format and microphone selection strongly affect STT. Desktop recorder targets WAV, mono, 16 kHz, which is good. WebSocket expects PCM signed 16-bit little-endian, 16 kHz, mono.

Confidence: High.

### Preprocessing

- Main pipeline preprocessing: `realtime_backend/app/utils/audio_process.py`, `normalize_audio`.
- Separate normalizer class: `realtime_backend/app/services/media.py`, `FFmpegAudioNormalizer`.
- Configuration source: `Settings.sample_rate=16000`, `Settings.channels=1`, `Settings.sample_width_bytes=2`, optional `CMG_RT_FFMPEG_PATH` or `CMG_FFMPEG_EXE`.
- Dependencies: ffmpeg, Python `wave`.
- Current ffmpeg command in `normalize_audio`: `ffmpeg -y -i <source> -ar 16000 -ac 1 -sample_fmt s16 <target>`.
- Failure points: ffmpeg missing, unsupported codec, bad audio, subprocess failure. If normalization fails, `TranscriptionPipeline` uses the original file; VAD then expects a readable WAV and may fail.
- Quality impact: resampling and mono conversion improve model compatibility. No loudness normalization, denoise, high-pass filtering, DC offset correction, clipping detection, or automatic gain handling is currently applied.

Confidence: High.

### VAD

- File path: `realtime_backend/app/pipeline/vad.py`.
- Classes/functions: `SileroVAD`, `EnergyVAD`, `build_vad`, `_postprocess_regions`, `_merge_regions`, `_split_long_regions`.
- Configuration source: `Settings.vad_provider`, frame/min speech/min silence/padding/merge/split fields.
- Default provider: `silero`.
- Fallback provider: `EnergyVAD`.
- Dependencies: `silero_vad`, `torch`, `torchaudio` compatibility shim, `numpy`, `wave`.
- Failure points: missing torch/silero, WAV read errors, wrong sample rate assumptions, overly aggressive thresholds, long-region splitting at poor low-energy points.
- Quality impact: VAD decides what audio reaches ASR. Conservative padding helps avoid clipped phonemes; over-splitting hurts context; under-segmentation increases long-window hallucination/repetition risk.

Confidence: High.

### Chunking

- File path: `realtime_backend/app/pipeline/orchestrator.py`.
- Functions: `_build_processing_windows`, `_split_full_duration`, `_clip_regions_to_window`, `_replace_timeline_tail`.
- Configuration source: `Settings.pipeline_max_window_seconds=90.0`, `Settings.pipeline_window_overlap_seconds=2.0`, VAD region limits.
- Dependencies: VAD regions and WAV slicing in `realtime_backend/app/utils/audio.py`.
- Failure points: VAD empty output, bad duration, overlap replacement dropping tails, context loss across windows.
- Quality impact: 90-second maximum windows preserve more context than very short chunks. Two-second overlap reduces boundary loss, but deduplication and tail replacement must be validated on real long conversations.

Confidence: Medium-High.

### ASR

- File path: `realtime_backend/app/pipeline/asr.py`.
- Classes/functions: `FasterWhisperASR`, `MockASR`, `build_asr`, `_regions_for_asr`, `_dedupe_segments`.
- Configuration source: `Settings.asr_provider`, `asr_model_name`, `asr_device`, `asr_compute_type`, `asr_beam_size`, `asr_region_padding_seconds`, `transcription_quality_mode`.
- Dependencies: `faster_whisper`, CTranslate2 runtime, model files/download behavior, GPU/CPU runtime.
- Failure points: missing dependency/model/GPU, unsupported compute type, model load failure, mock fallback in `auto`, too little context after VAD slicing.
- Quality impact: model size, forced Turkish, beam size, no internal VAD, and no previous-text conditioning are major quality levers.

Confidence: High.

### Transcript Cleanup

- LLM postprocess: `realtime_backend/app/pipeline/llm_postprocess.py`.
- Deterministic Turkish cleanup: `realtime_backend/app/utils/turkish_cleanup.py`.
- Configuration source: `Settings.llm_provider`, `llm_endpoint`, `llm_batch_size`, `llm_context_segments`, `default_language`.
- Dependencies: optional local HTTP LLM endpoint, `httpx`, Turkish glossary JSON.
- Failure points: unavailable LLM endpoint, invalid JSON response, cleanup removing meaningful fillers, glossary casing regex altering text.
- Quality impact: cleanup improves readability but can reduce verbatim fidelity. Raw text remains available for quality analysis.

Confidence: High.

### Storage

- File path: `realtime_backend/app/services/conversation_store.py`.
- Classes/functions: `ConversationStore.save`, `ConversationStore.get`.
- Configuration source: `Settings.data_dir / "transcripts"`.
- Dependencies: JSON, Pydantic serialization, filesystem.
- Failure points: disk permissions, duplicate conversation IDs, incompatible model schema changes.
- Quality impact: storage does not affect ASR generation but preserves raw/cleaned outputs and diagnostics for audit.

Confidence: High.

## 3. ASR Engine Analysis

### Faster-Whisper Integration

`FasterWhisperASR.__init__` dynamically imports `faster_whisper.WhisperModel` and constructs it with:

- `settings.asr_model_name`
- `device=settings.asr_device`
- `compute_type=settings.asr_compute_type`

Default configuration in `realtime_backend/app/config.py`:

- `CMG_RT_ASR_PROVIDER`: `auto`
- `CMG_RT_ASR_MODEL`: `large-v3`
- `CMG_RT_ASR_DEVICE`: `cuda`
- `CMG_RT_ASR_COMPUTE_TYPE`: `float16`
- `CMG_RT_ASR_BEAM_SIZE`: `5`
- `CMG_RT_ASR_MAX_QUALITY_BEAM_SIZE`: `8`
- `CMG_RT_ASR_WORD_TIMESTAMPS`: `true`
- `CMG_RT_ASR_INTERNAL_VAD`: `false`
- `CMG_RT_ASR_CONDITION_ON_PREVIOUS_TEXT`: `false`
- `CMG_RT_LANGUAGE`: `tr`
- `CMG_RT_TRANSCRIPTION_QUALITY_MODE`: `max_quality`

Confidence: High.

### Model Currently Used

Default model: `large-v3`.

Evidence:

- `Settings.asr_model_name` default in `realtime_backend/app/config.py`.
- `benchmark_results.json` records `"model": "large-v3-turbo"` for a prior local run, so `large-v3-turbo` has repository-adjacent regression evidence but is no longer the code default.
- No new benchmark has yet been run comparing `large-v3` and `large-v3-turbo` after the default change.

Confidence: High.

### Model Selection Logic

- If `settings.asr_provider == "mock"`, returns `MockASR`.
- If `settings.asr_provider == "auto"`, tries `FasterWhisperASR`; on any exception, logs warning and returns `MockASR` with `ASR_STATUS=MOCK_FALLBACK`, `mock_fallback_used=True`, and fallback reason metadata.
- Any other provider string returns `FasterWhisperASR(settings)`.

Risk: `CMG_RT_ASR_PROVIDER=auto` can still use mock output if local ASR cannot load, but API/diagnostics now expose the failure. Callers must treat `ASR_STATUS=MOCK_FALLBACK` as non-transcription.

Confidence: High.

### Inference Settings

In `FasterWhisperASR._transcribe_window`, current call:

```python
self._model.transcribe(
    str(audio_path),
    language=resolved_language,
    beam_size=profile.beam_size,
    word_timestamps=profile.word_timestamps,
    vad_filter=profile.vad_filter,
    condition_on_previous_text=profile.condition_on_previous_text,
    task="transcribe",
    initial_prompt=initial_prompt,
    no_speech_threshold=profile.no_speech_threshold,
)
```

Configured:

- `language`: `language` argument or `Settings.default_language`.
- `beam_size`: resolved by `resolve_asr_quality_profile`.
- `word_timestamps`: enabled by default through `CMG_RT_ASR_WORD_TIMESTAMPS=true`.
- `vad_filter`: disabled by default through `CMG_RT_ASR_INTERNAL_VAD=false`.
- `condition_on_previous_text`: disabled by default through `CMG_RT_ASR_CONDITION_ON_PREVIOUS_TEXT=false`.
- `task`: always `"transcribe"`.
- `initial_prompt`: glossary when language is Turkish.
- `no_speech_threshold`: quality-mode mapping.

Uses Faster-Whisper defaults:

- `temperature`: not set in code.
- compression/logprob thresholds: not set in code.
- patience, length penalty, repetition penalties: not set in code.
- suppress tokens and hotword-specific options: not set in code.

Unclear without runtime inspection:

- Whether model path is fully local or downloaded/cached by Faster-Whisper.
- Exact CTranslate2 behavior for `large-v3-turbo` on each machine.
- Whether CUDA/float16 is actually available in the runtime used for demos.

Confidence: High.

### Quality Profiles

`fast`:

- `beam_size = 1`
- `no_speech_threshold = 0.5`

`balanced`:

- `beam_size = max(3, Settings.asr_beam_size)`, default `5`
- `no_speech_threshold = 0.6`

`max_quality`:

- `beam_size = max(5, Settings.asr_max_quality_beam_size, Settings.asr_beam_size)`, default `8`
- `no_speech_threshold = 0.7`

Compatibility alias: `accurate` maps to `max_quality` for older tests/callers.

Observation: the three named profiles are now explicit. No temperature, best-of, or patience differences are configured yet.

Confidence: High.

### Language Handling

Default language is `tr`, so auto-language detection is usually bypassed. If caller passes `language=None` and `CMG_RT_LANGUAGE` is unset/empty, Faster-Whisper may use its default detection behavior, but the repo default is Turkish.

Confidence: High.

### VAD Integration

Faster-Whisper internal VAD is disabled (`vad_filter=False`). External VAD controls regions. When regions exist, `_regions_for_asr` pads each by `Settings.asr_region_padding_seconds` default `0.10` and merges overlaps before slicing to temporary WAVs.

Quality implication: external VAD makes behavior auditable, but 100 ms ASR region padding may be too small for conversational Turkish starts/ends if Silero or EnergyVAD cuts tightly.

Confidence: Medium-High.

### Word Timestamps

Always enabled. Used by `realtime_backend/app/pipeline/alignment.py` to split ASR segments by speaker turns when diarization turns are available.

Quality implication: word timestamps are helpful for alignment and source timing, but they may increase compute cost. They do not guarantee better text accuracy.

Confidence: High.

## 4. Turkish Language Quality Analysis

### language="tr" Usage

Default Turkish configuration is strong:

- `Settings.default_language` defaults to `tr`.
- File API accepts `language` form override.
- WebSocket accepts `?language=tr`.
- The local desktop `transcription_settings.json` may override language and device choices; it is runtime state and is not tracked.
- Benchmark scripts pass `language="tr"`.

Conclusion: the active code is designed to force Turkish rather than rely on auto-detection. Confidence: High.

### Auto-Language Detection Behavior

The repo does not explicitly evaluate auto-language detection. Because default language is `tr`, auto-detection is usually avoided. If users override the language to empty/None through environment or request, behavior depends on Faster-Whisper defaults.

Conclusion: auto-detection should not be part of the recommended Turkish configuration until tested. Confidence: Medium.

### Turkish Character Preservation

Runtime cleanup source and glossary files contain valid Turkish Unicode when read as UTF-8:

- `realtime_backend/app/utils/turkish_cleanup.py` includes `şey`, `ııı`, `işte`.
- `realtime_backend/config/transcription_glossary.tr.json` includes `toplantı`, `konuşmacı`, `görev`, `karar`, `özet`.
- `realtime_backend/app/pipeline/llm_postprocess.py` prompt includes Turkish character examples `ç, ğ, ı, İ, ö, ş, ü`.

The Windows shell displayed mojibake in several command outputs, but escaped file reads show the main runtime files are UTF-8-correct. Some test/log/doc strings display as mojibake in raw tool output; the known critical benchmark files checked with escaped output appear correct.

Conclusion: no direct evidence that active runtime cleanup corrupts Turkish characters, but console/display encoding can mislead audits and should be guarded by tests. Confidence: Medium-High.

### Punctuation Behavior

Sources:

- Faster-Whisper generates raw segment text.
- Optional LLM postprocessor can add punctuation.
- `clean_turkish_transcript` normalizes repeated punctuation, removes spaces before punctuation, capitalizes sentence starts, and appends punctuation if text is longer than five characters.

Risk: appending a period and normalizing punctuation can make cleaned transcripts less verbatim. Raw transcript remains preserved.

Confidence: High.

### Casing Behavior

`clean_turkish_transcript` capitalizes sentence starts using Python `.upper()`. In Python Unicode, `i`.upper() returns `I`, not Turkish dotted `İ`. This can produce Turkish casing errors for sentences beginning with lowercase `i`.

Glossary replacement uses case-insensitive regex and substitutes configured glossary casing, helping technical terms such as `FastAPI` and `SQLite`.

Conclusion: casing is readability-oriented, not Turkish-locale-perfect. Confidence: High.

### Normalization Behavior

Before the first hardening pass, cleanup normalized whitespace and removed fillers globally. Current behavior is safer:

- Configuration: `Settings.transcript_cleanup_mode`, environment `CMG_RT_TRANSCRIPT_CLEANUP_MODE`.
- Default: `conservative`.
- Conservative mode: spacing, repeated punctuation cleanup, sentence-start capitalization, glossary term casing, final punctuation.
- Aggressive mode: conservative cleanup plus common filler token removal.

Historical filler-removal behavior:

- Fillers: `şey`, `yani`, `ııı`, `eee`, `aa`, `işte`, `falan`, `filan`.
- Aggressive-mode removal is global with word-boundary regex; conservative mode does not remove these tokens.

Quality risk: `yani`, `işte`, and `şey` can be meaningful discourse markers. Removing all occurrences may improve readability but hurt faithful transcription.

Confidence: High.

### Tokenization Issues

Quality metrics in `realtime_backend/app/services/quality.py` use `_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9'-]{1,}")`, which excludes Turkish-specific letters. This affects internal text-overlap quality comparisons, not ASR itself.

Benchmark scripts use whitespace tokenization and lowercasing; this is better for Turkish than ASCII regex but still approximate.

Conclusion: ASR tokenization is handled by Whisper; repo-side evaluation tokenization is partial. Confidence: High.

## 5. Audio Preprocessing Analysis

### ffmpeg Usage

Two code paths:

- `realtime_backend/app/utils/audio_process.py`: used by `TranscriptionPipeline.process_audio_path`.
- `realtime_backend/app/services/media.py`: used by API construction and stream PCM-to-WAV conversion.

Main pipeline command:

```text
ffmpeg -y -i <source> -ar 16000 -ac 1 -sample_fmt s16 <target>
```

It resamples, downmixes to mono, and writes signed 16-bit WAV.

Confidence: High.

### Steps That Help Quality

- 16 kHz sample rate is appropriate for Whisper-family ASR.
- Mono conversion reduces channel complexity.
- PCM s16 is compatible with `wave` readers and Silero/Energy VAD.
- ffmpeg handles many source codecs for file ingest.

Confidence: High.

### Steps That May Hurt Quality

- Downmixing stereo to mono can hurt if channels contain different speakers or phase issues.
- No loudness normalization means quiet recordings may remain quiet.
- No clipping detection means distorted recordings are not flagged.
- No denoise/high-pass filter means HVAC/room noise can leak into VAD and ASR.
- If ffmpeg fails, pipeline falls back to original source and records warning metadata. VAD and WAV duration helpers may still fail if the original is not WAV.

Confidence: Medium-High.

### Missing Preprocessing Opportunities

- Loudness normalization or gain analysis.
- Clipping detection and warning.
- DC offset removal.
- Optional high-pass filter for rumble.
- Optional denoise/noise suppression profile for meeting-room audio.
- RMS before/after remains missing.
- Clipping detection and loudness reporting remain missing.
- `TranscriptionPipeline` now populates inspected input/output sample rate, channel count, duration, and format when the file can be opened as WAV.
- `TranscriptionPipeline` now records `preprocessing_status`, `ffmpeg_normalization_succeeded`, and warning metadata if ffmpeg fails and original audio is used.

Confidence: High.

## 6. VAD Analysis

### Provider Used

Default provider: `silero`.

If Silero import/model load fails, `build_vad` logs a warning and returns `EnergyVAD`.

Confidence: High.

### Thresholds and Chunk Sizes

Defaults in `Settings`:

- `vad_frame_ms=30`
- `vad_min_speech_ms=250`
- `vad_min_silence_ms=300`
- `vad_padding_ms=120`
- `vad_merge_gap_ms=120`
- `vad_smoothing_frames=5`
- `vad_max_region_seconds=24.0`
- `vad_target_region_seconds=12.0`
- `vad_split_search_seconds=1.5`
- `vad_adaptive_multiplier=2.2`
- `vad_energy_threshold=0.015`
- `pipeline_max_window_seconds=90.0`
- `pipeline_window_overlap_seconds=2.0`
- `asr_region_padding_seconds=0.10`

Confidence: High.

### Silence Detection Behavior

Silero path:

- `get_speech_timestamps` uses min speech duration, min silence duration, and speech padding.
- Regions are post-processed by merge/split logic.

Energy fallback:

- Computes frame RMS.
- Smooths energy with a moving average.
- Builds adaptive threshold from percentiles and multiplier.
- Requires minimum speech and silence durations.
- Adds padding and post-processes regions.

Confidence: High.

### Effect on Turkish Speech

There is no Turkish-specific VAD tuning. Turkish suffixes and low-energy word endings can be clipped if VAD boundaries are too tight. Current 120 ms VAD padding plus 100 ms ASR region padding helps, but may still be too small for soft starts/endings or fast speech.

Confidence: Medium.

### Risks

Risk of clipping words: Medium. VAD padding exists, but not validated on Turkish meeting audio.

Risk of over-segmentation: Medium. `vad_max_region_seconds=24` and target split at 12 seconds may break conversational context. Over-segmentation can hurt punctuation and phrase continuity.

Risk of under-segmentation: Low-Medium. Merge gap is only 120 ms, but long speech regions are split. Noisy rooms could keep VAD active too long.

Confidence: Medium.

## 7. Benchmark Readiness

| Capability | Status | Evidence | Notes |
| --- | --- | --- | --- |
| Common Voice support | Implemented | `realtime_backend/scripts/import_common_voice_tr_sample.py`, `realtime_backend/tests/fixtures/expected/common_voice_tr_manifest.json` | 20 local WAV fixture files are present under `realtime_backend/tests/fixtures/audio/common_voice_tr/`. |
| Benchmark script | Implemented | `realtime_backend/scripts/benchmark_common_voice_tr.py` | Produces JSON report with raw/cleaned metrics. |
| WER calculation | Partial | `benchmark_common_voice_tr.py`, `test_project_turkish_meeting_asr_quality.py` | Levenshtein-based approximate WER, not a standard library such as jiwer. |
| CER calculation | Partial | `benchmark_common_voice_tr.py` | Levenshtein-based approximate CER. |
| Transcript comparison tooling | Partial | `TranscriptQualityService`, benchmark scripts | Intrinsic quality report and reference comparison exist, but tokenization is not Turkish-safe in all paths. |
| Quality reports | Implemented | `realtime_backend/app/services/quality.py`, `/quality/{conversation_id}` | Reports segment count, unresolved speakers, confidence averages, word timing coverage, cleanup change ratio, warnings. |
| Real meeting benchmark | Missing/optional | `test_project_turkish_meeting_asr_quality.py` | Skips unless `turkish_meeting_sample.wav` exists. It is absent in this checkout. |
| Benchmark readiness script | Implemented | `realtime_backend/scripts/check_transcription_test_readiness.py` | Checks ffmpeg, Common Voice fixtures, optional meeting WAV. |

Existing local artifact: `benchmark_results.json` records a 20-sample Common Voice Turkish run using `large-v3-turbo`, balanced mode, with approximate summary metrics. These should be treated as local regression evidence only, not broad accuracy claims.

Confidence: High.

## 8. Quality Bottleneck Analysis

### Critical

1. Missing real meeting-room Turkish validation.
   Evidence: `test_project_turkish_meeting_asr_quality.py` skips if `realtime_backend/tests/fixtures/audio/turkish_meeting_sample.wav` is missing; the file is absent. Clean Common Voice samples do not validate noisy, overlapping, far-field conversation.
   Confidence: High.

2. ASR runtime/model availability can degrade to mock in `auto`.
   Evidence: `build_asr` falls back to `MockASR` on any Faster-Whisper construction exception, but now marks the provider/result with `ASR_STATUS=MOCK_FALLBACK`, `mock_fallback_used=true`, warning metadata, and unmistakable mock placeholder text.
   Quality impact: catastrophic if a caller ignores the status, because mock output is not transcription. The silent-fallback risk has been mitigated.
   Confidence: High.

### High

1. Hardware/compute configuration.
   Evidence: defaults are `cuda` and `float16`; tests often force CPU/int8. If CUDA is unavailable, model loading can fail or require config changes.
   Confidence: High.

2. VAD boundary tuning.
   Evidence: external VAD controls ASR regions; region padding is 120 ms plus 100 ms ASR padding.
   Quality impact: clipping and context loss are likely bottlenecks for real meetings.
   Confidence: Medium.

3. Cleanup logic may alter faithful transcripts when aggressive mode is enabled.
   Evidence: `clean_turkish_transcript` now defaults to conservative mode and no longer removes fillers by default. Aggressive mode still removes filler tokens globally and both modes can append punctuation.
   Quality impact: conservative mode is safer for fidelity; aggressive mode improves readability with possible loss of verbatim meaning.
   Confidence: High.

4. Evaluation quality.
   Evidence: WER/CER are approximate local functions; `TranscriptQualityService` token regex is ASCII-centric.
   Quality impact: can misrepresent Turkish improvements/regressions.
   Confidence: High.

### Medium

1. Decoding profile tuning still lacks benchmark evidence.
   Evidence: `fast`, `balanced`, and `max_quality` are now explicit, but beam/no-speech choices have not been validated on real Turkish meeting audio.
   Confidence: High.

2. `condition_on_previous_text=False`.
   Evidence: hard-coded in `FasterWhisperASR`.
   Quality impact: reduces hallucination/repetition risk across chunks, but may reduce continuity for long Turkish utterances.
   Confidence: Medium.

3. No audio enhancement.
   Evidence: ffmpeg only resamples/downmixes/sample-format-converts.
   Quality impact: noisy and quiet recordings may underperform.
   Confidence: Medium-High.

### Low

1. Faster-Whisper itself as a quality bottleneck.
   Evidence: no repository benchmark compares Faster-Whisper vs OpenAI Whisper on identical audio/config.
   Quality impact: unknown; likely less important than model size, decoding, audio, and VAD until proven otherwise.
   Confidence: Medium.

## 9. Recommended Quality Profiles

### Fast

Intended use: quick notes, live-ish feedback, low-latency previews, CPU-constrained machines.

Recommended model: `small` or `medium` Faster-Whisper only after Turkish-specific benchmarks; if keeping current default model, use `large-v3` with `quality_mode=fast` only on adequate GPU.

Recommended settings:

- `quality_mode=fast`
- `beam_size=1`
- shorter stream windows only if latency matters
- keep `language=tr`
- keep `word_timestamps=True` only if timing is required

Expected tradeoffs: faster throughput, lower accuracy on names/technical terms, weaker punctuation, more missed soft speech.

Confidence: Medium.

### Balanced

Intended use: default desktop transcription for local Turkish technical conversations.

Recommended model: `large-v3` for current default quality posture, with `large-v3-turbo` retained as the main speed/quality comparison target.

Recommended settings:

- `CMG_RT_ASR_MODEL=large-v3`
- `CMG_RT_ASR_PROVIDER=auto` only if health checks fail closed on mock; otherwise use explicit `faster_whisper`
- `CMG_RT_ASR_DEVICE=cuda` and `CMG_RT_ASR_COMPUTE_TYPE=float16` when GPU supports it
- CPU fallback: `device=cpu`, `compute_type=int8`
- `quality_mode=balanced`
- `language=tr`
- keep external VAD and word timestamps

Expected tradeoffs: slower than turbo/smaller models, still unproven for real meeting rooms without validation.

Confidence: Medium-High.

### Maximum Quality

Intended use: final transcription of important Turkish meetings where latency is secondary.

Recommended model: benchmark `large-v3` and `large-v3-turbo` locally; do not assume one wins without repository evidence.

Decoding recommendations:

- Force `language=tr`.
- Use beam size at least 5; test 8 or 10.
- Consider exposing `temperature`, `patience`, and threshold settings for experiments.
- Test `condition_on_previous_text=True` vs `False` on long Turkish conversations.
- Increase ASR region padding and/or VAD padding for meeting-room speech.
- Preserve raw output and evaluate cleanup separately.

Hardware recommendations:

- NVIDIA GPU with enough VRAM for large Whisper-family models.
- If CPU-only, use int8 and expect slower processing.
- Keep ffmpeg installed and verify sample rate/channel diagnostics.

Expected tradeoffs: slower, more GPU memory, but better chance of preserving technical names and lower error rates after tuning.

Confidence: Medium.

## 10. Faster-Whisper vs OpenAI Whisper Assessment

Is the current implementation likely losing quality because it uses Faster-Whisper?

No repository evidence proves that. The current bottlenecks are more likely model/config/runtime validation, VAD/chunking, audio quality, and cleanup/evaluation. Confidence: Medium.

Would OpenAI Whisper likely improve quality?

Unclear. OpenAI Whisper and Faster-Whisper can differ because of implementation/runtime/decoding details, but the repository has no A/B benchmark on identical Turkish audio. Switching would not automatically solve VAD, preprocessing, meeting-room audio, or cleanup issues. Confidence: Medium.

Is the difference likely negligible?

It may be negligible if the same model family, language forcing, beam settings, and preprocessing are used, but this must be measured. Faster-Whisper is generally chosen for speed/deployment advantages; quality equivalence should not be assumed without local Turkish benchmarks. Confidence: Medium-Low.

What evidence is needed before switching?

- Same audio set, same references, same normalization, same language forcing.
- Compare Faster-Whisper `large-v3-turbo`, Faster-Whisper `large-v3`, and OpenAI Whisper `large-v3` if available.
- Measure raw WER, raw CER, technical-term recall, Turkish character preservation, punctuation, and latency.
- Include clean Common Voice samples and real meeting-room samples.
- Run with `condition_on_previous_text` and VAD/chunk settings controlled.

Conclusion: no technical justification to switch engines yet. First build a controlled benchmark. Confidence: High.

## 11. Final Recommendations

### Immediate Changes

- Treat `ASR_STATUS=MOCK_FALLBACK` as a failed quality state in demos and clients. The backend now reports this status; consumers must fail closed on it.
- Make `CMG_RT_ASR_PROVIDER=faster_whisper` the recommended quality configuration; use `auto` only for development.
- Run the new targeted unit tests in an environment with `pytest` installed.
- Add real Turkish character preservation tests against actual Faster-Whisper output once a real fixture is available.
- Add RMS/loudness/clipping diagnostics; sample rate/channel/duration/format diagnostics now exist.
- Benchmark the new default `max_quality` profile rather than assuming it improves Turkish meeting quality.

Confidence: High.

### Next Changes

- Record and add `turkish_meeting_sample.wav`, then run `test_project_turkish_meeting_asr_quality.py`.
- Replace approximate WER/CER code with a standard evaluation library or well-reviewed internal implementation.
- Make tokenization Turkish-aware in `TranscriptQualityService`.
- Add VAD boundary tests with Turkish speech fixtures, especially soft starts/endings.
- Expose ASR experimental settings in config: temperature, patience, compression/logprob thresholds, condition-on-previous-text.
- Benchmark `large-v3` against `large-v3-turbo`.

Confidence: High.

### Long-Term Improvements

- Build a real meeting-room ASR benchmark suite: near-field, far-field, noisy, overlapping speech, multiple speakers, technical terms.
- Add audio preprocessing profiles: raw, high-pass, loudness-normalized, denoised; benchmark each.
- Build technical glossary evaluation: recall of `FastAPI`, `SQLite`, `PySide6`, project names, Turkish terms.
- Evaluate diarization separately from ASR text quality; do not let speaker-label failures obscure text WER/CER.
- Add per-stage artifacts: normalized WAV, VAD regions, ASR regions, raw ASR JSON, cleaned transcript, metrics.

Confidence: Medium-High.

### Recommended Default Configuration

For Turkish transcription quality today:

```text
CMG_RT_ASR_PROVIDER=faster_whisper
CMG_RT_ASR_MODEL=large-v3
CMG_RT_ASR_DEVICE=cuda
CMG_RT_ASR_COMPUTE_TYPE=float16
CMG_RT_LANGUAGE=tr
CMG_RT_TRANSCRIPTION_QUALITY_MODE=max_quality
CMG_RT_ASR_BEAM_SIZE=5
CMG_RT_ASR_MAX_QUALITY_BEAM_SIZE=8
CMG_RT_ASR_WORD_TIMESTAMPS=true
CMG_RT_ASR_INTERNAL_VAD=false
CMG_RT_ASR_CONDITION_ON_PREVIOUS_TEXT=false
CMG_RT_TRANSCRIPT_CLEANUP_MODE=conservative
CMG_RT_VAD_PROVIDER=silero
CMG_RT_VAD_MIN_SPEECH_MS=250
CMG_RT_VAD_MIN_SILENCE_MS=300
CMG_RT_VAD_PADDING_MS=160
CMG_RT_ASR_REGION_PADDING_SECONDS=0.20
CMG_RT_PIPELINE_MAX_WINDOW_SECONDS=90
CMG_RT_PIPELINE_WINDOW_OVERLAP_SECONDS=2
CMG_RT_LLM_PROVIDER=none
```

Rationale:

- Explicit `faster_whisper` prevents mock fallback entirely; `auto` fallback is now visible but should not be used for quality demos.
- `language=tr` avoids language-detection mistakes.
- `large-v3` is the current quality-first default. `large-v3-turbo` should still be benchmarked because prior repository artifacts used it.
- `max_quality` uses beam size at least 5 and currently defaults to 8.
- Slightly larger VAD/ASR padding is safer for real Turkish conversations than the current tight 120 ms / 100 ms combination.
- `CMG_RT_TRANSCRIPT_CLEANUP_MODE=conservative` avoids default filler deletion.
- `LLM_PROVIDER=none` isolates raw ASR quality during evaluation; cleanup can be evaluated as a separate layer.

If CUDA is unavailable:

```text
CMG_RT_ASR_DEVICE=cpu
CMG_RT_ASR_COMPUTE_TYPE=int8
```

Do not claim the same speed or quality without benchmarking.

Confidence: Medium-High.

## Evidence Inspected

- `docs/dev/codex.md`
- `realtime_backend/app/config.py`
- `realtime_backend/app/main.py`
- `realtime_backend/app/api/routes.py`
- `realtime_backend/app/api/ws.py`
- `realtime_backend/app/services/transcription_service.py`
- `realtime_backend/app/services/streaming.py`
- `realtime_backend/app/services/media.py`
- `realtime_backend/app/services/conversation_store.py`
- `realtime_backend/app/services/quality.py`
- `realtime_backend/app/pipeline/orchestrator.py`
- `realtime_backend/app/pipeline/asr.py`
- `realtime_backend/app/pipeline/vad.py`
- `realtime_backend/app/pipeline/alignment.py`
- `realtime_backend/app/pipeline/llm_postprocess.py`
- `realtime_backend/app/utils/audio.py`
- `realtime_backend/app/utils/audio_process.py`
- `realtime_backend/app/utils/turkish_cleanup.py`
- `realtime_backend/config/transcription_glossary.tr.json`
- `realtime_backend/scripts/benchmark_common_voice_tr.py`
- `realtime_backend/scripts/import_common_voice_tr_sample.py`
- `realtime_backend/scripts/check_transcription_test_readiness.py`
- `realtime_backend/scripts/prepare_turkish_audio_fixture.py`
- `realtime_backend/scripts/transcribe_local_file.py`
- `realtime_backend/tests/test_asr.py`
- `realtime_backend/tests/test_vad.py`
- `realtime_backend/tests/test_common_voice_tr_asr_quality.py`
- `realtime_backend/tests/test_common_voice_tr_chunk_boundary.py`
- `realtime_backend/tests/test_project_turkish_meeting_asr_quality.py`
- `realtime_backend/tests/test_asr_quality_smoke.py`
- `realtime_backend/tests/test_transcript_quality.py`
- `realtime_backend/tests/fixtures/expected/common_voice_tr_manifest.json`
- `realtime_backend/tests/fixtures/expected/turkish_meeting_sample.expected.txt`
- `realtime_backend/tests/fixtures/audio/common_voice_tr/*.wav`
- `benchmark_results.json`
- `transcription_settings.json` (ignored local runtime state)
- `src/collective_mindgraph_desktop/audio_capture.py`
- `src/collective_mindgraph_desktop/ui/workers.py`
- `src/collective_mindgraph_desktop/transcription.py`

## Unresolved Questions

- Does the target demo/runtime machine have CUDA and a compatible CTranslate2/Faster-Whisper stack?
- Are Faster-Whisper models guaranteed local, or can model resolution trigger downloads in some environments?
- How does `large-v3` compare with `large-v3-turbo` on the project’s real Turkish meeting audio?
- What are the best VAD padding and silence thresholds for actual Turkish meeting-room recordings?
- Does `condition_on_previous_text=True` improve long Turkish meeting continuity enough to justify hallucination/repetition risk?
- How much does deterministic cleanup improve readability while reducing verbatim fidelity?
- What is the real WER/CER on noisy, multi-speaker, far-field Turkish conversations?
- Should file ingest fail hard when ffmpeg normalization fails instead of trying the original file?

## Bottom Line

The transcription subsystem is a serious local-first STT implementation, not a mock, when Faster-Whisper loads successfully. It is strongest on clean, single-speaker Turkish audio with forced language and local model availability. Its biggest current risks are unvalidated real meeting-room conditions, callers ignoring explicit mock fallback status, VAD boundary tuning, unbenchmarked profile/model choices, and partial benchmark rigor.

Overall conclusion confidence: High for architecture and code mapping; Medium for real-world quality readiness because the necessary meeting-room validation evidence is missing.
