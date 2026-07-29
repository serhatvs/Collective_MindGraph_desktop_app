"""Rollout flags, migration independence, and the release readiness decision."""

from __future__ import annotations

import statistics
import time
from pathlib import Path
from uuid import uuid4

import pytest

from collective_mindgraph.application.release.feature_flags import (
    ROLLOUT_ORDER,
    FeatureFlag,
    FeatureFlagSet,
    FlagOrderError,
    parse_flags,
)
from collective_mindgraph.application.release.readiness import (
    KEYWORD_SEARCH_P95_MS,
    MIN_CANVAS_FPS,
    ExternalInput,
    PerformanceBudget,
    build_readiness_report,
    format_readiness,
)
from collective_mindgraph.application.transcription.evaluation.release_gates import (
    MIN_AUDIO_HOURS,
    MIN_LABELLED_QUERIES,
    MIN_MEETINGS,
    AudioEvidence,
    RetrievalEvidence,
    build_report,
)

# Feature flags ------------------------------------------------------------


def test_the_rollout_order_is_the_one_the_programme_fixed():
    assert ROLLOUT_ORDER == (
        FeatureFlag.SCHEMA,
        FeatureFlag.CRYPTO,
        FeatureFlag.SYNC,
        FeatureFlag.COLLABORATION,
        FeatureFlag.GRAPH,
        FeatureFlag.TELEMETRY,
    )


def test_a_flag_cannot_skip_what_it_depends_on():
    flags = FeatureFlagSet.none()
    for flag in (FeatureFlag.CRYPTO, FeatureFlag.SYNC, FeatureFlag.COLLABORATION):
        with pytest.raises(FlagOrderError):
            flags.enable(flag)
    assert flags.enabled == frozenset()

    ordered = flags.enable_through(FeatureFlag.COLLABORATION)
    assert ordered.is_enabled(FeatureFlag.COLLABORATION)
    assert ordered.rollout_position == 4


def test_telemetry_and_graph_do_not_wait_on_the_cloud():
    """A local canvas and an opt-in metric must not require sync to ship."""

    flags = FeatureFlagSet.none().enable(FeatureFlag.TELEMETRY)
    assert flags.is_enabled(FeatureFlag.TELEMETRY)
    with_schema = flags.enable(FeatureFlag.SCHEMA).enable(FeatureFlag.GRAPH)
    assert with_schema.is_enabled(FeatureFlag.GRAPH)
    assert not with_schema.is_enabled(FeatureFlag.SYNC)


def test_rolling_back_takes_dependants_with_it():
    """Leaving a dependant on over a rolled-back dependency is untested ground."""

    full = FeatureFlagSet.none().enable_through(FeatureFlag.TELEMETRY)
    assert full.rollout_position == len(ROLLOUT_ORDER)

    without_sync = full.disable(FeatureFlag.SYNC)
    assert not without_sync.is_enabled(FeatureFlag.SYNC)
    assert not without_sync.is_enabled(FeatureFlag.COLLABORATION)
    # Independent features survive the rollback.
    assert without_sync.is_enabled(FeatureFlag.GRAPH)
    assert without_sync.is_enabled(FeatureFlag.TELEMETRY)


def test_every_flag_can_be_rolled_back_individually():
    full = FeatureFlagSet.none().enable_through(FeatureFlag.TELEMETRY)
    for flag in FeatureFlag:
        assert not full.disable(flag).is_enabled(flag)


def test_configuration_is_parsed_in_order_regardless_of_how_it_is_written():
    flags = parse_flags(["telemetry", "sync", "schema", " crypto "])
    assert flags.is_enabled(FeatureFlag.SYNC)
    assert flags.is_enabled(FeatureFlag.TELEMETRY)
    assert not flags.is_enabled(FeatureFlag.COLLABORATION)
    with pytest.raises(ValueError):
        parse_flags(["not-a-flag"])


def test_migration_runs_regardless_of_every_flag(tmp_path: Path):
    """Data must upgrade whether or not any feature is switched on.

    If migration waited on a flag, rolling that flag back would leave the
    database ahead of the code that reads it.
    """

    from collective_mindgraph.application.release import feature_flags
    from collective_mindgraph.infrastructure.persistence import (
        SCHEMA_VERSION,
        SqliteDatabase,
        initialize_schema,
    )

    assert (
        "feature"
        not in Path("src/collective_mindgraph/infrastructure/persistence/canonical_schema.py")
        .read_text(encoding="utf-8")
        .lower()
    )

    database = SqliteDatabase(tmp_path / "canonical.sqlite3")
    initialize_schema(database)
    with database.connect() as connection:
        version = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    assert int(version[0]) == SCHEMA_VERSION
    assert feature_flags.FeatureFlagSet.none().enabled == frozenset()


# Readiness ----------------------------------------------------------------


def test_an_empty_report_blocks_and_names_every_reason():
    report = build_readiness_report(security_scanners_available=False)
    assert report.may_release is False
    areas = {blocker.area for blocker in report.blockers}
    assert {"quality", "performance", "security", "packaging"} <= areas
    lines = format_readiness(report)
    assert lines[0] == report.summary()
    assert len(lines) == len(report.blockers) + 1


def test_the_report_separates_what_can_be_fixed_here():
    report = build_readiness_report(
        external_inputs=[ExternalInput(name="code-signing certificate")],
        security_scanners_available=False,
    )
    external = {blocker.reason for blocker in report.external_blockers}
    assert any("certificate" in reason for reason in external)
    assert any("not signed" in reason for reason in external)
    assert any("cannot run" in reason for reason in external)
    assert report.internal_blockers
    assert "needs an external input" in str(report.external_blockers[0])


def test_open_defects_and_findings_each_block():
    for kwargs in (
        {"open_defects": 1},
        {"unresolved_security_findings": 1},
        {"high_severity_vulnerabilities": 1},
    ):
        report = build_readiness_report(**kwargs)  # type: ignore[arg-type]
        assert report.may_release is False
        assert any(blocker.area in {"defects", "security"} for blocker in report.blockers)


def test_unmeasured_performance_blocks_just_as_a_missed_budget_does():
    unmeasured = PerformanceBudget().blockers()
    assert len(unmeasured) == 5
    assert all("not measured" in blocker.reason for blocker in unmeasured)

    missed = PerformanceBudget(
        keyword_p95_ms=KEYWORD_SEARCH_P95_MS + 1,
        semantic_p95_ms=10,
        sync_round_trip_p95_ms=10,
        visible_change_ms=10,
        canvas_fps=MIN_CANVAS_FPS - 1,
    ).blockers()
    reasons = " ".join(blocker.reason for blocker in missed)
    assert "keyword search p95" in reasons
    assert "FPS" in reasons


def test_a_fully_satisfied_release_is_allowed():
    """The gate must be able to say yes, or saying no proves nothing."""

    quality = build_report(
        AudioEvidence(
            meetings=MIN_MEETINGS,
            audio_hours=MIN_AUDIO_HOURS,
            clean_wer=0.15,
            noisy_wer=0.30,
            domain_term_recall=0.90,
            diarization_error=0.20,
            consent_documented=True,
        ),
        RetrievalEvidence(
            labelled_queries=MIN_LABELLED_QUERIES,
            recall_at_10=0.90,
            citation_precision=1.0,
            unsupported_claims=0,
        ),
    )
    report = build_readiness_report(
        quality=quality,
        performance=PerformanceBudget(
            keyword_p95_ms=40,
            semantic_p95_ms=200,
            sync_round_trip_p95_ms=180,
            visible_change_ms=1200,
            canvas_fps=60,
        ),
        external_inputs=[ExternalInput(name="code-signing certificate", available=True)],
        artifacts_signed=True,
    )
    assert report.may_release is True
    assert report.blockers == ()
    assert "may ship" in report.summary()


def test_the_report_reflects_this_repositorys_actual_state():
    """Today the honest answer is no, for reasons that are named."""

    report = build_readiness_report(security_scanners_available=False)
    assert report.may_release is False
    reasons = [str(blocker) for blocker in report.blockers]
    assert any("not signed" in reason for reason in reasons)
    assert any("unevaluated" in reason for reason in reasons)


# Measured performance -----------------------------------------------------


def test_keyword_search_meets_its_latency_budget(tmp_path: Path):
    """Measure the one budget this repository can actually measure."""

    from collective_mindgraph.infrastructure.persistence import (
        SqliteDatabase,
        initialize_schema,
    )
    from collective_mindgraph.infrastructure.persistence.search_schema import (
        SEARCH_TABLE,
        build_match_expression,
    )

    database = SqliteDatabase(tmp_path / "canonical.sqlite3")
    initialize_schema(database)
    with database.connect() as connection:
        connection.executemany(
            "INSERT INTO knowledge_nodes(id, kind, title, body, created_at, updated_at) "
            "VALUES (?, 'note', ?, ?, '2026-01-01', '2026-01-01')",
            [
                (
                    str(uuid4()),
                    f"Bütçe kararı {index}",
                    f"Ekip {index} bütçeyi onayladı ve toplantıyı kapattı",
                )
                for index in range(2000)
            ],
        )

    samples: list[float] = []
    with database.connect() as connection:
        for _ in range(60):
            started = time.perf_counter()
            connection.execute(
                f"SELECT node_id FROM {SEARCH_TABLE} WHERE {SEARCH_TABLE} MATCH ? "
                f"ORDER BY bm25({SEARCH_TABLE}) LIMIT 20",
                (build_match_expression("karar"),),
            ).fetchall()
            samples.append((time.perf_counter() - started) * 1000)

    p95 = statistics.quantiles(samples, n=20)[-1]
    assert p95 < KEYWORD_SEARCH_P95_MS, f"keyword p95 was {p95:.1f} ms"
