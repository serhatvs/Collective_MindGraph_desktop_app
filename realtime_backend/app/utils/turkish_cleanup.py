"""Deterministic transcript cleanup helpers for Turkish and technical context."""

from __future__ import annotations

import json
import re
from pathlib import Path

# Common Turkish fillers to remove only in aggressive cleanup mode.
TURKISH_FILLERS = {
    "\u015fey",
    "yani",
    "\u0131\u0131\u0131",
    "eee",
    "aa",
    "i\u015fte",
    "falan",
    "filan",
    # Mojibake variants kept so aggressive mode can still repair older outputs.
    "\u00c5\u0178ey",
    "\u00c4\u00b1\u00c4\u00b1\u00c4\u00b1",
    "i\u00c5\u0178te",
}


def load_glossary() -> list[str]:
    glossary_path = Path(__file__).parent.parent.parent / "config" / "transcription_glossary.tr.json"
    if not glossary_path.exists():
        return []
    try:
        data = json.loads(glossary_path.read_text(encoding="utf-8"))
        all_terms = []
        for category in data.values():
            all_terms.extend(category)
        return all_terms
    except Exception:
        return []


GLOSSARY_TERMS = load_glossary()


def clean_turkish_transcript(text: str, *, mode: str = "conservative") -> str:
    """
    Deterministic cleanup for Turkish transcripts.
    Preserves Turkish characters, timestamps (if part of text), and glossary terms.
    Conservative mode avoids filler deletion. Aggressive mode removes filler tokens.
    """
    if not text:
        return text

    cleanup_mode = (mode or "conservative").strip().lower()
    if cleanup_mode not in {"conservative", "aggressive"}:
        cleanup_mode = "conservative"

    cleaned = " ".join(text.strip().split())
    cleaned = re.sub(r"([.!?])\1+", r"\1", cleaned)
    cleaned = re.sub(r"\s+([.!?])", r"\1", cleaned)

    sentences = re.split(r"([.!?]\s*)", cleaned)
    capitalized_sentences = []
    for index in range(0, len(sentences), 2):
        sentence = sentences[index]
        if sentence:
            sentence = sentence[:1].upper() + sentence[1:]
        capitalized_sentences.append(sentence)
        if index + 1 < len(sentences):
            capitalized_sentences.append(sentences[index + 1])
    cleaned = "".join(capitalized_sentences)

    if cleanup_mode == "aggressive":
        cleaned = _remove_fillers(cleaned)

    for term in GLOSSARY_TERMS:
        pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
        cleaned = pattern.sub(lambda match: _preserve_leading_case(match.group(0), term), cleaned)

    cleaned = " ".join(cleaned.strip().split())
    if not cleaned and text:
        return text

    if cleaned and cleaned[-1] not in ".!?" and len(cleaned) > 5:
        cleaned += "."

    return cleaned


def _preserve_leading_case(matched: str, replacement: str) -> str:
    if matched[:1].isupper() and replacement:
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _remove_fillers(text: str) -> str:
    cleaned = text
    for filler in TURKISH_FILLERS:
        pattern = re.compile(rf"\b{re.escape(filler)}\b", re.IGNORECASE)
        cleaned = pattern.sub("", cleaned)
    return cleaned
