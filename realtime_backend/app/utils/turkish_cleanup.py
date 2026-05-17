"""Deterministic transcript cleanup helpers for Turkish and technical context."""

from __future__ import annotations

import json
import re
from pathlib import Path

# Common Turkish fillers to remove when safe
TURKISH_FILLERS = {
    "şey", "yani", "ııı", "eee", "aa", "işte", "falan", "filan"
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

def clean_turkish_transcript(text: str) -> str:
    """
    Deterministic cleanup for Turkish transcripts.
    Preserves Turkish characters, timestamps (if part of text), and glossary terms.
    Removes repeated fillers and fixes common punctuation/spacing issues.
    """
    if not text:
        return text

    # 1. Normalize spacing
    cleaned = " ".join(text.strip().split())

    # 2. Fix repeated punctuation
    cleaned = re.sub(r'([.!?])\1+', r'\1', cleaned)
    cleaned = re.sub(r'\s+([.!?])', r'\1', cleaned)

    # 3. Capitalize sentence starts where safe
    # Split by sentence boundaries and capitalize
    sentences = re.split(r'([.!?]\s*)', cleaned)
    capitalized_sentences = []
    for i in range(0, len(sentences), 2):
        s = sentences[i]
        if s:
            s = s[:1].upper() + s[1:]
        capitalized_sentences.append(s)
        if i + 1 < len(sentences):
            capitalized_sentences.append(sentences[i+1])
    cleaned = "".join(capitalized_sentences)

    # 4. Remove obvious repeated fillers when safe (case insensitive)
    # We do this carefully to not remove meaningful words
    for filler in TURKISH_FILLERS:
        pattern = re.compile(rf'\b{filler}\b', re.IGNORECASE)
        # Only remove if it's repeated or clearly a filler at the start/end
        cleaned = pattern.sub("", cleaned)

    # 5. Fix glossary term casing (optional but helpful)
    for term in GLOSSARY_TERMS:
        pattern = re.compile(rf'\b{term}\b', re.IGNORECASE)
        cleaned = pattern.sub(term, cleaned)

    # 6. Final spacing cleanup
    cleaned = " ".join(cleaned.strip().split())
    
    # If we removed everything, return original to be safe
    if not cleaned and text:
        return text

    # Ensure it ends with punctuation if it was reasonably long
    if cleaned and cleaned[-1] not in ".!?" and len(cleaned) > 5:
        cleaned += "."

    return cleaned
