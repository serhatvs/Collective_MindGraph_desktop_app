# Turkish Transcription Reference Data Guide

## Reviewer Goal

Write a faithful transcript of what is audibly spoken. The reference is evidence for measuring transcription errors and may later become training data. It is not a meeting summary and must not be “improved” beyond the audio.

## Core Rules

1. **Write exactly what was spoken.** Preserve the speaker’s words, including grammatical mistakes and unfinished phrases when intelligible.
2. **Do not summarize.** Never replace a long statement with its meaning.
3. **Do not add missing meaning.** If the audio does not contain a word, do not infer it from context, slides, or project knowledge.
4. **Preserve Turkish characters.** Use `ç, ğ, ı, İ, ö, ş, ü` correctly. Do not transliterate them to ASCII.
5. **Use consistent punctuation.** Punctuation may reflect clear sentence/question boundaries, but do not change the words.
6. **Write known technical terms correctly only when that pronunciation is audible.** Use consistent spellings such as `Collective MindGraph`, `FastAPI`, `SQLite`, `PySide6`, or project glossary terms. Do not insert glossary terms merely because they seem plausible.
7. **Keep raw ASR separate.** Correct only the human-reference field. Never rewrite original raw, selected, or cleaned ASR fields.
8. **Never approve unchecked ASR output.** A prefilled reference is still `pending` until a person listens to the segment.

## Pending, Reviewed, Unclear, and Excluded

- `pending`: not yet listened to and verified.
- `reviewed`: listened to, boundaries are valid, and the reference faithfully represents intelligible speech.
- `unclear`: speech exists but part of the wording remains uncertain. Keep reviewer notes; do not use it for metrics or training export yet.
- `excluded`: the region should not be evaluated or trained on—for example genuinely unintelligible speech, unusable corruption, non-consensual content, or an invalid segment. Record the reason.

Do not mark difficult but intelligible audio as excluded simply because ASR performed poorly; those examples are valuable once correctly annotated.

## Boundaries

- Include the complete spoken phrase without cutting initial or final phonemes.
- Remove large unrelated silence when practical.
- Do not create negative or zero-length regions.
- Resolve unintended overlap warnings when possible.
- Overlapping speech can remain tagged `overlapping_speech`, but exclude the segment if a single faithful transcript cannot be established for the intended task.
- Boundary edits change only reviewed boundaries. Original ASR boundaries remain audit evidence.

## Uncertain Words and Non-Speech

Replay at normal speed and, when helpful, `0.75×`. If a word remains uncertain, use `unclear` rather than guessing. Do not add descriptions such as `[noise]` or `[inaudible]` unless the dataset adopts one documented convention consistently; excluded or unclear status is preferred for this pilot.

## Names, Numbers, and Abbreviations

- Use the audible and conventionally written form for known names and technical terms.
- Preserve spoken numbers as words when that is what the reference policy requires; stay consistent across the dataset.
- Keep acronyms consistent (`VAD`, `API`, `GPU`) when clearly spoken.
- Never identify a person from voice. `speaker_id` stays `unknown` unless a human-provided, consented label exists.

## Recording Conditions

Tag observable conditions such as `bad_mic`, `far_field`, `noisy_room`, `low_volume`, `clipping`, `echo`, device type, and `technical_meeting`. Add short microphone/room notes when known. Do not guess equipment details.

## Quality Check Before Marking Reviewed

- Listen to the full segment at least once.
- Compare every word against the audio, not the ASR suggestion.
- Confirm Turkish characters and technical-term spelling.
- Confirm reviewed start/end contain the full speech.
- Confirm the reference is non-empty.
- Confirm no private annotation note was accidentally placed in the reference field.

## Training and Evaluation Separation

Keep held-out evaluation meetings separate from future training data by `meeting_id`, not merely by segment. Audio from the same meeting, speaker session, or near-duplicate recording must not appear in both training and evaluation sets. Do not tune thresholds or choose models on the final held-out meetings.

Only export segments that are human-reviewed, non-empty, valid, and not excluded. Never train on pending or merely cleaned ASR output. Maintain consent, privacy, licensing, and retention records outside the transcript text.
