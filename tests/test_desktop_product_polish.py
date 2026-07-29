"""Theme tokens, the WCAG contrast gate, and telemetry consent."""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest

from collective_mindgraph.desktop.telemetry import (
    ALLOWED_FIELDS,
    MAX_VALUE_LENGTH,
    TelemetryConsent,
    TelemetryEvent,
    TelemetryEventKind,
    TelemetryReporter,
    redact,
)
from collective_mindgraph.desktop.ui.theme import (
    AA_NON_TEXT_RATIO,
    AA_NORMAL_TEXT_RATIO,
    DARK,
    LIGHT,
    NON_TEXT_PAIRS,
    TEXT_PAIRS,
    Palette,
    ThemeMode,
    contrast_failures,
    contrast_ratio,
    relative_luminance,
    resolve,
    stylesheet,
)

NOW = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)
HEX = re.compile(r"#[0-9A-Fa-f]{6}")


# Contrast -----------------------------------------------------------------


def test_contrast_ratio_matches_the_wcag_reference_points():
    # Black on white is the defined maximum; identical colours are the minimum.
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0, abs=0.01)
    assert contrast_ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1.0, abs=0.001)
    assert contrast_ratio("#FFFFFF", "#000000") == pytest.approx(21.0, abs=0.01)
    assert relative_luminance("#FFFFFF") == pytest.approx(1.0, abs=0.001)
    assert relative_luminance("#000000") == pytest.approx(0.0, abs=0.001)
    # sRGB luminance is not a linear average; mid grey sits well below 0.5.
    assert relative_luminance("#808080") == pytest.approx(0.2159, abs=0.001)


@pytest.mark.parametrize("palette", [LIGHT, DARK], ids=["light", "dark"])
def test_every_declared_pair_meets_wcag_2_2_aa(palette: Palette):
    """This is a release gate: a palette change that fails is a failure."""

    assert contrast_failures(palette) == ()


@pytest.mark.parametrize("palette", [LIGHT, DARK], ids=["light", "dark"])
def test_body_text_and_focus_clear_their_thresholds_with_margin(palette: Palette):
    assert contrast_ratio(palette.text, palette.surface) >= AA_NORMAL_TEXT_RATIO
    assert contrast_ratio(palette.text, palette.canvas) >= AA_NORMAL_TEXT_RATIO
    assert contrast_ratio(palette.focus, palette.surface) >= AA_NON_TEXT_RATIO


def test_the_contrast_gate_actually_rejects_an_unreadable_palette():
    """A gate that cannot fail proves nothing."""

    unreadable = Palette(**{**{name: "#F2F2F2" for name in LIGHT.role_names()}})
    failures = contrast_failures(unreadable)
    assert failures
    assert any("text on surface" in entry for entry in failures)


def test_colour_parsing_rejects_anything_that_is_not_a_hex_triplet():
    for value in ("red", "#FFF", "#GGGGGG", "", "#1234567"):
        with pytest.raises(ValueError):
            relative_luminance(value)


# Tokens -------------------------------------------------------------------


def test_both_palettes_define_the_same_roles():
    assert LIGHT.role_names() == DARK.role_names()
    assert set(LIGHT.role_names()) >= {name for pair in TEXT_PAIRS for name in pair[:2]} | {
        name for pair in NON_TEXT_PAIRS for name in pair
    }


def test_the_light_and_dark_palettes_are_actually_different():
    assert LIGHT != DARK
    assert relative_luminance(LIGHT.canvas) > relative_luminance(DARK.canvas)
    assert relative_luminance(LIGHT.text) < relative_luminance(DARK.text)


def test_system_mode_follows_the_operating_system():
    assert resolve(ThemeMode.SYSTEM, system_prefers_dark=True) is DARK
    assert resolve(ThemeMode.SYSTEM, system_prefers_dark=False) is LIGHT
    # An explicit choice overrides the system in both directions.
    assert resolve(ThemeMode.DARK, system_prefers_dark=False) is DARK
    assert resolve(ThemeMode.LIGHT, system_prefers_dark=True) is LIGHT


@pytest.mark.parametrize("palette", [LIGHT, DARK], ids=["light", "dark"])
def test_the_stylesheet_paints_only_palette_colours(palette: Palette):
    """No hardcoded hex may survive in the rendered stylesheet."""

    declared = {getattr(palette, name).upper() for name in palette.role_names()}
    used = {value.upper() for value in HEX.findall(stylesheet(palette))}
    assert used <= declared
    assert "WHITE" not in stylesheet(palette).upper().replace("QWIDGET", "")


def test_switching_palettes_changes_the_rendered_stylesheet():
    assert stylesheet(LIGHT) != stylesheet(DARK)
    assert LIGHT.canvas in stylesheet(LIGHT)
    assert LIGHT.canvas not in stylesheet(DARK)


# Telemetry ----------------------------------------------------------------


def test_telemetry_is_off_until_the_user_decides():
    reporter = TelemetryReporter()
    assert reporter.is_enabled is False
    assert reporter.consent.is_undecided is True
    assert reporter.report(TelemetryEventKind.APP_STARTED, occurred_at=NOW) is None
    assert reporter.dropped == 1


def test_enabling_telemetry_requires_a_recorded_decision():
    with pytest.raises(ValueError):
        TelemetryConsent(enabled=True)
    with pytest.raises(ValueError):
        TelemetryConsent(enabled=True, decided_at=datetime(2026, 1, 1))
    granted = TelemetryConsent(enabled=True, decided_at=NOW)
    assert granted.is_undecided is False


def test_declining_is_a_decision_and_still_reports_nothing():
    reporter = TelemetryReporter(TelemetryConsent(enabled=False, decided_at=NOW))
    assert reporter.consent.is_undecided is False
    assert reporter.report(TelemetryEventKind.APP_STARTED, occurred_at=NOW) is None


def test_consent_can_be_withdrawn_and_stops_reporting_immediately():
    sent: list[TelemetryEvent] = []
    reporter = TelemetryReporter(
        TelemetryConsent(enabled=True, decided_at=NOW),
        sink=sent.append,
    )
    assert reporter.report(TelemetryEventKind.APP_STARTED, occurred_at=NOW) is not None
    reporter.update_consent(TelemetryConsent(enabled=False, decided_at=NOW))
    assert reporter.report(TelemetryEventKind.APP_STARTED, occurred_at=NOW) is None
    assert len(sent) == 1


def test_redaction_drops_everything_that_was_not_declared():
    payload = {
        "app_version": "1.0.0",
        "duration_ms": 1200,
        # None of the following may ever leave the machine.
        "transcript": "we agreed to ship on Friday",
        "meeting_title": "Board review",
        "query": "what did we decide",
        "evidence": "segment 12",
        "file_path": r"C:\Users\person\recording.wav",
        "audio": b"\x00\x01",
        "subject": "person@example.test",
    }
    redacted = redact(payload)
    assert redacted == {"app_version": "1.0.0", "duration_ms": 1200}
    for forbidden in ("transcript", "meeting_title", "query", "evidence", "file_path"):
        assert forbidden not in redacted
    assert "recording.wav" not in str(redacted)


def test_redaction_enforces_declared_types_and_bounds():
    assert redact({"duration_ms": "1200"}) == {}
    assert redact({"duration_ms": True}) == {}
    assert redact({"app_version": "   "}) == {}
    assert redact({"app_version": 5}) == {}
    long_value = "x" * (MAX_VALUE_LENGTH + 50)
    assert len(redact({"provider": long_value})["provider"]) == MAX_VALUE_LENGTH


def test_reported_events_carry_only_declared_fields():
    sent: list[TelemetryEvent] = []
    reporter = TelemetryReporter(
        TelemetryConsent(enabled=True, decided_at=NOW),
        sink=sent.append,
    )
    event = reporter.report(
        TelemetryEventKind.TRANSCRIPTION_COMPLETED,
        occurred_at=NOW,
        payload={"audio_seconds": 90, "transcript": "secret"},
    )
    assert event is not None
    assert event.fields == {"audio_seconds": 90}
    assert sent == [event]
    assert set(event.fields) <= set(ALLOWED_FIELDS)

    with pytest.raises(ValueError):
        TelemetryEvent(
            kind=TelemetryEventKind.APP_STARTED,
            occurred_at=NOW,
            fields={"transcript": "secret"},
        )
    with pytest.raises(ValueError):
        TelemetryEvent(kind=TelemetryEventKind.APP_STARTED, occurred_at=datetime(2026, 1, 1))


def test_the_declared_field_list_holds_no_content_bearing_name():
    """A guard against a future field quietly widening what is reported."""

    forbidden = ("transcript", "title", "body", "query", "evidence", "path", "text", "name")
    assert not [name for name in ALLOWED_FIELDS if any(word in name for word in forbidden)]
