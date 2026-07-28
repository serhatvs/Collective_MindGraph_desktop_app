# Real Room Audio Validation Plan

Date: 2026-06-30

Status: `PLAN_ONLY_NOT_RUN`

This document is a future validation plan. No real meeting-room audio has been tested by this plan yet, so it must not be used to claim meeting-room readiness, diarization quality, or production audio robustness.

## Claim Boundary

- GPU-routed local ASR through the real CMG backend pipeline is validated separately.
- This plan is for future real-room validation only.
- Diarization and real speaker separation are not implemented or validated here.
- WER/CER require manually written reference transcripts.

## Test Matrix

| Case | Required Input | Expected Output | What To Measure | Known Risks | Pass/Fail Criteria |
|---|---|---|---|---|---|
| Single speaker close mic | 1-3 minute Turkish speech recorded close to a microphone, WAV preferred, plus human reference transcript | One coherent Turkish transcript with preserved raw and cleaned text | WER, CER, processing time, real-time factor, Turkish character preservation, punctuation drift | Over-clean reference text can inflate WER; clipping if mic too close | Pass only if ASR completes with `ASR_STATUS=OK`, no mock fallback, no GPU fallback when GPU is required, and WER/CER are computed from the real reference |
| Single speaker laptop mic | 1-3 minute Turkish speech from normal laptop distance, plus reference transcript | Transcript preserves most words despite room coloration | WER, CER, dropped words, low-volume sections, VAD clipping | Laptop noise suppression, fan noise, weak input level | Pass only if all speech regions are represented and no obvious beginning/end clipping appears in manual review |
| Two speakers same room | 3-5 minute two-person Turkish conversation, one room mic, plus reference transcript without diarization assumptions | Combined transcript captures both speakers as text; speaker labels may remain unresolved | WER, CER, turn-boundary losses, overlap errors, VAD segmentation | Overlap, interruptions, distance differences | Pass only for ASR text capture; do not pass/fail diarization because speaker separation is not validated |
| Multiple speakers same room | 5-10 minute meeting with 3+ Turkish speakers, plus reference transcript | Combined transcript captures major content across speakers | WER, CER, missed utterances, repeated phrases, processing time, memory use | Overlap, far speakers, cross-talk, echo | Pass only if ASR is usable as text capture and limitations are documented; no speaker attribution claim |
| Background noise | Turkish speech with HVAC, keyboard, hallway, or cafe noise, plus reference transcript | Transcript remains source-traceable and does not hallucinate noise as speech | WER, CER, false speech segments, no-speech handling, cleanup damage | VAD false positives/negatives, low SNR | Pass only if speech is captured without large hallucinated passages and warnings document noise impact |
| Reverberation / echo | Speech in a reflective room or conference room, plus reference transcript | Transcript captures main speech despite echo | WER, CER, duplicated phrases, late reverberation false positives | Echo can create repeated ASR text and VAD over-segmentation | Pass only if repeated text is limited and manually reviewed |
| Low volume speech | Quiet Turkish speech at realistic meeting volume, plus reference transcript | Transcript captures low-energy phrases or warns about failures | WER, CER, VAD misses, RMS/loudness diagnostics when available | VAD may drop quiet starts/ends; ASR confidence may fall | Pass only if low-volume phrases are present or failure is explicit and reproducible |
| Long meeting audio | 30-60 minute Turkish technical meeting, plus reference transcript or sampled references | Bounded-window transcription completes without mock fallback | Processing time, real-time factor, chunk count, memory use, tail replacement artifacts | Long-window drift, temp file cleanup, model memory pressure | Pass only if the run completes, metadata is complete, and any chunk artifacts are documented |
| Turkish technical meeting vocabulary | Turkish speech with terms like FastAPI, SQLite, PySide6, VAD, transcript, aksiyon, karar, sprint, deployment | Technical terms are preserved or errors are cataloged | Term preservation checklist, WER/CER, substitutions/deletions/insertions | English acronyms inside Turkish, casing, suffixes | Pass only if term errors are listed honestly; do not claim perfect technical vocabulary |

## Required Fixture Package

Each fixture should include:

- Raw audio file, preferably WAV.
- Human reference transcript in UTF-8.
- Short metadata file with recording device, room type, speaker count, distance, noise notes, and whether overlap exists.
- Optional manually annotated notes for VAD clipping, dropped words, and technical terms.

## Recommended Run Order

1. Run `scripts/validation/check_asr_gpu.py` with `CMG_REQUIRE_GPU=1`.
2. Run `scripts/validation/full_scale_gpu_transcription_test.py` on the fixture.
3. Run `scripts/benchmarks/benchmark_asr_accuracy.py --audio <audio> --reference <reference> --profile gpu_asr`.
4. Run `scripts/benchmarks/validate_silero_vad_asr.py` only after ASR GPU routing is already confirmed.
5. Compare CPU/GPU runtime with `scripts/benchmarks/benchmark_cpu_vs_gpu_asr.py` when speed matters.

## Completion Criteria

This plan can be marked complete only after real meeting-room audio and matching human references are tested and reports are saved. MediaSpeech TR or other clean media speech datasets cannot satisfy this plan.
