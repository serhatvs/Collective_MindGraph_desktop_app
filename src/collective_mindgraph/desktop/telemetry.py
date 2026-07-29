"""Content-free, opt-in telemetry.

Telemetry is off until the user turns it on. When it is on, only the fields
declared here leave the machine: no transcript, no audio, no meeting title, no
query, no evidence, and no file path. The redactor drops anything else rather
than trying to sanitise it, so a new field cannot leak by being forgotten.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

MAX_VALUE_LENGTH = 120


class TelemetryEventKind(StrEnum):
    """The only events the product may report."""

    APP_STARTED = "app.started"
    APP_CRASHED = "app.crashed"
    ENGINE_UNAVAILABLE = "engine.unavailable"
    TRANSCRIPTION_COMPLETED = "transcription.completed"
    SYNC_PASS_COMPLETED = "sync.pass_completed"


# Every field a payload may carry, with the type it must have. A key that is
# not here is dropped, which is why adding a field is a deliberate act.
ALLOWED_FIELDS: Mapping[str, type] = {
    "app_version": str,
    "os_release": str,
    "duration_ms": int,
    "audio_seconds": int,
    "segment_count": int,
    "queue_depth": int,
    "operation_count": int,
    "conflict_count": int,
    "provider": str,
    "outcome": str,
    "error_type": str,
}


@dataclass(frozen=True, slots=True)
class TelemetryConsent:
    """What the user actually agreed to, and when."""

    enabled: bool = False
    decided_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.decided_at is not None and self.decided_at.tzinfo is None:
            raise ValueError("The consent timestamp must be timezone-aware.")
        if self.enabled and self.decided_at is None:
            raise ValueError("Telemetry cannot be enabled without a recorded decision.")

    @property
    def is_undecided(self) -> bool:
        """Whether the user has never been asked, which is not consent."""

        return self.decided_at is None


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    """One redacted event ready to send."""

    kind: TelemetryEventKind
    occurred_at: datetime
    fields: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError("Event timestamps must be timezone-aware.")
        unexpected = set(self.fields) - set(ALLOWED_FIELDS)
        if unexpected:
            raise ValueError(f"Unexpected telemetry fields: {sorted(unexpected)}.")


def redact(payload: Mapping[str, object]) -> dict[str, object]:
    """Keep only declared fields with the declared type.

    Unknown keys are dropped rather than sanitised: a value that was never
    meant to be reported cannot be made safe by trimming it.
    """

    kept: dict[str, object] = {}
    for name, expected in ALLOWED_FIELDS.items():
        if name not in payload:
            continue
        value = payload[name]
        if expected is int:
            if isinstance(value, bool) or not isinstance(value, int):
                continue
            kept[name] = value
        elif isinstance(value, str):
            trimmed = value.strip()
            if trimmed:
                kept[name] = trimmed[:MAX_VALUE_LENGTH]
    return kept


class TelemetryReporter:
    """Drops every event until the user has opted in."""

    def __init__(
        self,
        consent: TelemetryConsent | None = None,
        *,
        sink: object = None,
    ) -> None:
        self._consent = consent or TelemetryConsent()
        self._sink = sink
        self.dropped = 0

    @property
    def consent(self) -> TelemetryConsent:
        return self._consent

    @property
    def is_enabled(self) -> bool:
        return self._consent.enabled

    def update_consent(self, consent: TelemetryConsent) -> None:
        """Record a new decision, including withdrawal."""

        self._consent = consent

    def report(
        self,
        kind: TelemetryEventKind,
        *,
        occurred_at: datetime,
        payload: Mapping[str, object] | None = None,
    ) -> TelemetryEvent | None:
        """Redact and send one event, or drop it when consent is absent."""

        if not self._consent.enabled:
            self.dropped += 1
            return None
        event = TelemetryEvent(
            kind=kind,
            occurred_at=occurred_at,
            fields=redact(payload or {}),
        )
        if self._sink is not None and callable(self._sink):
            self._sink(event)
        return event


__all__ = [
    "ALLOWED_FIELDS",
    "MAX_VALUE_LENGTH",
    "TelemetryConsent",
    "TelemetryEvent",
    "TelemetryEventKind",
    "TelemetryReporter",
    "redact",
]
