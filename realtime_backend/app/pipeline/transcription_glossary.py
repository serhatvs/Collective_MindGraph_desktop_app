"""Deterministic glossary resolution for ASR prompts and hotwords."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


GLOBAL_GLOSSARY_PATH = Path(__file__).resolve().parents[2] / "config" / "transcription_glossary.tr.json"


@dataclass(slots=True)
class ResolvedGlossary:
    terms: tuple[str, ...]
    initial_prompt: str | None
    hotwords: str | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        return {
            **self.metadata,
            "terms": list(self.terms),
            "final_prompt_count": len(self.terms),
            "final_prompt_length": len(self.initial_prompt or ""),
        }


def resolve_transcription_glossary(
    settings: Any,
    *,
    session_terms: Iterable[str] | None = None,
    user_hotwords: Iterable[str] | None = None,
) -> ResolvedGlossary:
    """Resolve terms in deterministic user/session/project/global precedence order."""

    source_terms: list[tuple[str, list[str]]] = [
        ("user_hotwords", _coerce_terms(user_hotwords)),
        ("session", _coerce_terms(session_terms)),
    ]
    project_path = getattr(settings, "transcription_project_glossary_path", None)
    project_terms, project_error = load_glossary_file(project_path)
    global_terms, global_error = load_glossary_file(GLOBAL_GLOSSARY_PATH)
    source_terms.extend(
        [
            ("project", project_terms),
            ("global", global_terms),
        ]
    )

    max_terms = max(0, int(getattr(settings, "transcription_glossary_max_terms", 120)))
    max_prompt_chars = max(0, int(getattr(settings, "transcription_glossary_max_prompt_chars", 1500)))
    max_term_length = max(1, int(getattr(settings, "transcription_glossary_max_term_length", 80)))
    supplied_by_source = {name: len(items) for name, items in source_terms}
    accepted_by_source = {name: 0 for name, _items in source_terms}
    accepted: list[str] = []
    seen: set[str] = set()
    removed_duplicates = 0
    omitted_empty = 0
    omitted_too_long = 0
    omitted_by_term_limit = 0
    omitted_by_prompt_limit = 0
    current_prompt_length = 0

    for source_name, values in source_terms:
        for raw_term in values:
            term = _normalize_term(raw_term)
            if not term:
                omitted_empty += 1
                continue
            if len(term) > max_term_length:
                omitted_too_long += 1
                continue
            key = term.casefold()
            if key in seen:
                removed_duplicates += 1
                continue
            if len(accepted) >= max_terms:
                omitted_by_term_limit += 1
                continue
            added_length = len(term) + (2 if accepted else 0)
            if current_prompt_length + added_length > max_prompt_chars:
                omitted_by_prompt_limit += 1
                continue
            accepted.append(term)
            seen.add(key)
            accepted_by_source[source_name] += 1
            current_prompt_length += added_length

    prompt = ", ".join(accepted) or None
    omitted_count = omitted_empty + omitted_too_long + omitted_by_term_limit + omitted_by_prompt_limit
    metadata = {
        "precedence": ["user_hotwords", "session", "project", "global"],
        "supplied_by_source": supplied_by_source,
        "accepted_by_source": accepted_by_source,
        "supplied_count": sum(supplied_by_source.values()),
        "accepted_count": len(accepted),
        "removed_duplicates": removed_duplicates,
        "omitted_count": omitted_count,
        "omitted_empty": omitted_empty,
        "omitted_too_long": omitted_too_long,
        "omitted_by_term_limit": omitted_by_term_limit,
        "omitted_by_prompt_limit": omitted_by_prompt_limit,
        "max_terms": max_terms,
        "max_prompt_length": max_prompt_chars,
        "max_term_length": max_term_length,
        "project_glossary_path": str(project_path) if project_path else None,
        "project_glossary_error": project_error,
        "global_glossary_path": str(GLOBAL_GLOSSARY_PATH),
        "global_glossary_error": global_error,
    }
    return ResolvedGlossary(
        terms=tuple(accepted),
        initial_prompt=prompt,
        hotwords=prompt,
        metadata=metadata,
    )


def parse_term_input(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, str):
        return _coerce_terms(value)
    stripped = value.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, list):
            return [str(item) for item in decoded]
    normalized = stripped.replace("\r\n", "\n").replace(";", "\n").replace(",", "\n")
    return [item.strip() for item in normalized.split("\n") if item.strip()]


def load_glossary_file(path: Path | str | None) -> tuple[list[str], str | None]:
    """Load glossary terms and return a non-fatal diagnostic on failure."""

    if path is None:
        return [], None
    resolved = Path(path).expanduser()
    if not resolved.exists():
        return [], f"glossary file not found: {resolved}"
    try:
        text = resolved.read_text(encoding="utf-8")
        if resolved.suffix.lower() == ".json":
            payload = json.loads(text)
            return _terms_from_json(payload), None
        return parse_term_input(text), None
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return [], f"{type(exc).__name__}: {exc}"


def _terms_from_json(payload: Any) -> list[str]:
    if isinstance(payload, list):
        return [str(item) for item in payload]
    if isinstance(payload, dict):
        terms: list[str] = []
        for value in payload.values():
            if isinstance(value, list):
                terms.extend(str(item) for item in value)
            elif isinstance(value, str):
                terms.append(value)
        return terms
    if isinstance(payload, str):
        return parse_term_input(payload)
    return []


def _coerce_terms(values: Iterable[str] | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return parse_term_input(values)
    return [str(item) for item in values]


def _normalize_term(value: str) -> str:
    return " ".join(str(value).strip().split())
