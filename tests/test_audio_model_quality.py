"""Signed catalogue verification, consent-gated installs, and release gates."""

from __future__ import annotations

import hashlib
import json
from base64 import b64encode
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from collective_mindgraph.application.transcription.evaluation.release_gates import (
    MAX_CLEAN_WER,
    MIN_AUDIO_HOURS,
    MIN_LABELLED_QUERIES,
    MIN_MEETINGS,
    AudioEvidence,
    GateOutcome,
    RetrievalEvidence,
    build_report,
    evaluate_audio,
    evaluate_retrieval,
    format_report,
)
from collective_mindgraph.domain.model_catalog import (
    InstalledModel,
    ModelConsentError,
    ModelEntry,
    ModelVerificationError,
)
from collective_mindgraph.infrastructure.models.catalog import (
    CATALOG_FORMAT,
    CATALOG_FORMAT_VERSION,
    canonical_payload,
    load_catalog,
)
from collective_mindgraph.infrastructure.models.installer import (
    ModelConsent,
    ModelInstaller,
)

NOW = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
PAYLOAD = b"model-weights" * 500
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


def _entry(**overrides: object) -> ModelEntry:
    fields: dict[str, object] = {
        "model_id": "whisper-tr",
        "version": "1.2.0",
        "provider": "openai",
        "size_bytes": len(PAYLOAD),
        "license": "MIT",
        "url": "https://models.example.test/whisper-tr-1.2.0.bin",
        "sha256": DIGEST,
        "min_engine": "0.3",
    }
    fields.update(overrides)
    return ModelEntry(**fields)  # type: ignore[arg-type]


def _sign(document: dict[str, object], key: Ed25519PrivateKey) -> str:
    signed = dict(document)
    signed["signature"] = b64encode(key.sign(canonical_payload(signed))).decode("ascii")
    return json.dumps(signed)


def _document(entries: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "format": CATALOG_FORMAT,
        "format_version": CATALOG_FORMAT_VERSION,
        "issued_at": "2026-06-01T00:00:00+00:00",
        "models": entries
        if entries is not None
        else [
            {
                "model_id": "whisper-tr",
                "version": "1.2.0",
                "provider": "openai",
                "size_bytes": len(PAYLOAD),
                "license": "MIT",
                "url": "https://models.example.test/whisper-tr-1.2.0.bin",
                "sha256": DIGEST,
                "min_engine": "0.3",
            }
        ],
    }


@pytest.fixture(scope="module")
def signing_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


@pytest.fixture(scope="module")
def public_key(signing_key: Ed25519PrivateKey) -> bytes:
    return signing_key.public_key().public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    )


# Catalogue entries --------------------------------------------------------


def test_entries_reject_unusable_declarations():
    for override in (
        {"model_id": " "},
        {"provider": ""},
        {"license": "  "},
        {"version": "not-a-version"},
        {"min_engine": "latest"},
        {"size_bytes": 0},
        {"sha256": "not-a-digest"},
        {"url": "http://models.example.test/x.bin"},
    ):
        with pytest.raises(ValueError):
            _entry(**override)


def test_digests_are_normalised_rather_than_merely_accepted():
    """An uppercase entry must not fail verification for a correct file."""

    assert _entry(sha256=DIGEST.upper()).sha256 == DIGEST
    assert _entry(sha256=f"  {DIGEST}  ").sha256 == DIGEST
    installed = InstalledModel(
        model_id="whisper-tr",
        version="1.2.0",
        path="/models/whisper-tr/1.2.0/model.bin",
        sha256=DIGEST.upper(),
        size_bytes=len(PAYLOAD),
        installed_at=NOW,
    )
    assert installed.sha256 == DIGEST
    with pytest.raises(ValueError):
        InstalledModel(
            model_id="m",
            version="1",
            path="/p",
            sha256="nope",
            size_bytes=1,
            installed_at=NOW,
        )
    with pytest.raises(ValueError):
        InstalledModel(
            model_id="m",
            version="1",
            path=" ",
            sha256=DIGEST,
            size_bytes=1,
            installed_at=NOW,
        )
    with pytest.raises(ValueError):
        InstalledModel(
            model_id="m",
            version="1",
            path="/p",
            sha256=DIGEST,
            size_bytes=1,
            installed_at=datetime(2026, 1, 1),
        )


def test_entries_declare_the_engine_they_need():
    entry = _entry(min_engine="0.4.1")
    assert entry.supports_engine("0.4.1") is True
    assert entry.supports_engine("1.0") is True
    assert entry.supports_engine("0.4") is False
    assert entry.supports_engine("0.3.9") is False


# Catalogue signature ------------------------------------------------------


def test_a_signed_catalogue_parses(signing_key: Ed25519PrivateKey, public_key: bytes):
    catalog = load_catalog(_sign(_document(), signing_key), public_key=public_key)
    assert len(catalog.entries) == 1
    assert catalog.entry("whisper-tr", "1.2.0") is not None
    assert catalog.entry("whisper-tr", "9.9.9") is None
    assert catalog.for_engine("0.3") == catalog.entries
    assert catalog.for_engine("0.1") == ()


def test_signing_covers_content_not_formatting(
    signing_key: Ed25519PrivateKey,
    public_key: bytes,
):
    """Reformatting must still verify; changing a field must not."""

    document = _document()
    signature = json.loads(_sign(document, signing_key))["signature"]

    reordered = {"signature": signature, **{k: document[k] for k in reversed(list(document))}}
    assert load_catalog(json.dumps(reordered, indent=4), public_key=public_key).entries

    tampered = json.loads(_sign(document, signing_key))
    tampered["models"][0]["url"] = "https://attacker.example.test/payload.bin"
    with pytest.raises(ModelVerificationError, match="signature"):
        load_catalog(json.dumps(tampered), public_key=public_key)

    digest_swap = json.loads(_sign(document, signing_key))
    digest_swap["models"][0]["sha256"] = "0" * 64
    with pytest.raises(ModelVerificationError, match="signature"):
        load_catalog(json.dumps(digest_swap), public_key=public_key)


def test_unsigned_and_foreign_catalogues_are_refused(
    signing_key: Ed25519PrivateKey,
    public_key: bytes,
):
    with pytest.raises(ModelVerificationError, match="not signed"):
        load_catalog(json.dumps(_document()), public_key=public_key)

    foreign = Ed25519PrivateKey.generate()
    with pytest.raises(ModelVerificationError, match="signature"):
        load_catalog(_sign(_document(), foreign), public_key=public_key)


def test_malformed_catalogues_are_refused(signing_key: Ed25519PrivateKey, public_key: bytes):
    with pytest.raises(ModelVerificationError, match="valid JSON"):
        load_catalog("not json", public_key=public_key)
    with pytest.raises(ModelVerificationError, match="JSON object"):
        load_catalog("[]", public_key=public_key)

    wrong_format = _document()
    wrong_format["format"] = "something-else"
    with pytest.raises(ModelVerificationError, match="format"):
        load_catalog(_sign(wrong_format, signing_key), public_key=public_key)

    empty = _document(entries=[])
    with pytest.raises(ModelVerificationError, match="no models"):
        load_catalog(_sign(empty, signing_key), public_key=public_key)

    entry = _document()["models"][0]
    duplicated = _document(entries=[dict(entry), dict(entry)])
    with pytest.raises(ModelVerificationError, match="repeats"):
        load_catalog(_sign(duplicated, signing_key), public_key=public_key)

    broken = dict(entry)
    broken.pop("sha256")
    with pytest.raises(ModelVerificationError, match="Unusable catalogue entry"):
        load_catalog(_sign(_document(entries=[broken]), signing_key), public_key=public_key)


# Installation -------------------------------------------------------------


def _source(payload: bytes = PAYLOAD, *, chunk: int = 4096):
    calls: list[int] = []

    def _read(url: str, offset: int) -> Iterator[bytes]:
        calls.append(offset)
        remaining = payload[offset:]
        for index in range(0, len(remaining), chunk):
            yield remaining[index : index + chunk]

    return _read, calls


def _consent(entry: ModelEntry) -> ModelConsent:
    return ModelConsent(
        model_id=entry.model_id,
        version=entry.version,
        license=entry.license,
        accepted_at=NOW,
    )


def test_installing_requires_consent_for_that_exact_version(tmp_path: Path):
    read, _ = _source()
    installer = ModelInstaller(tmp_path / "models", source=read, clock=lambda: NOW)
    entry = _entry()

    with pytest.raises(ModelConsentError):
        installer.install(entry, consent=None, engine_version="1.0")

    for mismatched in (
        ModelConsent(model_id="other", version="1.2.0", license="MIT", accepted_at=NOW),
        ModelConsent(model_id="whisper-tr", version="1.1.0", license="MIT", accepted_at=NOW),
        # A new version may carry different terms, so the licence is part of it.
        ModelConsent(model_id="whisper-tr", version="1.2.0", license="GPL", accepted_at=NOW),
    ):
        with pytest.raises(ModelConsentError):
            installer.install(entry, consent=mismatched, engine_version="1.0")

    assert not list((tmp_path / "models").rglob("*.bin"))


def test_a_consented_install_verifies_and_lands_outside_the_app_version(tmp_path: Path):
    read, _ = _source()
    installer = ModelInstaller(tmp_path / "models", source=read, clock=lambda: NOW)
    entry = _entry()
    progress: list[float] = []

    installed = installer.install(
        entry,
        consent=_consent(entry),
        engine_version="1.0",
        on_progress=lambda update: progress.append(update.fraction),
    )
    assert isinstance(installed, InstalledModel)
    assert installed.sha256 == DIGEST
    assert Path(installed.path).read_bytes() == PAYLOAD
    # The path carries the model version, not the application version.
    assert Path(installed.path).parts[-3:] == ("whisper-tr", "1.2.0", "model.bin")
    assert progress and progress[-1] == pytest.approx(1.0)
    assert installer.installed_versions("whisper-tr") == ("1.2.0",)


def test_an_install_refuses_an_engine_that_is_too_old(tmp_path: Path):
    read, _ = _source()
    installer = ModelInstaller(tmp_path / "models", source=read, clock=lambda: NOW)
    entry = _entry(min_engine="2.0")
    with pytest.raises(ModelVerificationError, match="requires engine"):
        installer.install(entry, consent=_consent(entry), engine_version="1.9")


def test_a_download_resumes_instead_of_restarting(tmp_path: Path):
    entry = _entry()
    read, offsets = _source()
    installer = ModelInstaller(tmp_path / "models", source=read, clock=lambda: NOW)
    partial = installer.partial_path(entry)
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_bytes(PAYLOAD[:5000])

    installed = installer.install(entry, consent=_consent(entry), engine_version="1.0")
    assert offsets == [5000]
    assert Path(installed.path).read_bytes() == PAYLOAD


def test_a_corrupt_download_is_discarded_rather_than_installed(tmp_path: Path):
    entry = _entry()
    read, _ = _source(b"x" * len(PAYLOAD))
    installer = ModelInstaller(tmp_path / "models", source=read, clock=lambda: NOW)

    with pytest.raises(ModelVerificationError, match="failed verification"):
        installer.install(entry, consent=_consent(entry), engine_version="1.0")
    assert not installer.target_path(entry).exists()
    assert not installer.partial_path(entry).exists()
    assert installer.installed_versions("whisper-tr") == ()


def test_a_truncated_download_is_discarded(tmp_path: Path):
    entry = _entry()
    read, _ = _source(PAYLOAD[:-10])
    installer = ModelInstaller(tmp_path / "models", source=read, clock=lambda: NOW)
    with pytest.raises(ModelVerificationError):
        installer.install(entry, consent=_consent(entry), engine_version="1.0")


def test_an_oversized_partial_is_not_resumed_from(tmp_path: Path):
    entry = _entry()
    read, offsets = _source()
    installer = ModelInstaller(tmp_path / "models", source=read, clock=lambda: NOW)
    partial = installer.partial_path(entry)
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_bytes(b"junk" * len(PAYLOAD))

    installer.install(entry, consent=_consent(entry), engine_version="1.0")
    assert offsets == [0]


def test_removal_respects_a_pin(tmp_path: Path):
    entry = _entry()
    read, _ = _source()
    installer = ModelInstaller(tmp_path / "models", source=read, clock=lambda: NOW)
    installer.install(entry, consent=_consent(entry), engine_version="1.0")

    with pytest.raises(ModelVerificationError, match="pinned"):
        installer.remove("whisper-tr", "1.2.0", pinned=True)
    assert installer.remove("whisper-tr", "1.2.0") is True
    assert installer.installed_versions("whisper-tr") == ()
    assert installer.remove("whisper-tr", "1.2.0") is False


def test_two_versions_coexist_so_rollback_is_possible(tmp_path: Path):
    read, _ = _source()
    installer = ModelInstaller(tmp_path / "models", source=read, clock=lambda: NOW)
    for version in ("1.2.0", "1.3.0"):
        entry = _entry(version=version)
        installer.install(entry, consent=_consent(entry), engine_version="1.0")
    assert installer.installed_versions("whisper-tr") == ("1.2.0", "1.3.0")


# Release gates ------------------------------------------------------------


def test_no_evidence_means_unevaluated_not_passed():
    """The whole point: an unmeasured gate must never look like a met one."""

    report = build_report()
    assert report.may_release is False
    assert len(report.unevaluated) == len(report.results)
    assert all(result.outcome is GateOutcome.UNEVALUATED for result in report.results)
    assert "unevaluated" in report.summary()
    assert all(result.blocks_release for result in report.results)


def test_measurements_without_a_sufficient_corpus_stay_unevaluated():
    """Good numbers from too little data are not evidence."""

    thin = AudioEvidence(
        meetings=3,
        audio_hours=1.0,
        clean_wer=0.05,
        noisy_wer=0.10,
        domain_term_recall=0.99,
        diarization_error=0.05,
        consent_documented=True,
    )
    results = evaluate_audio(thin)
    assert all(result.outcome is GateOutcome.UNEVALUATED for result in results)
    assert any("meetings" in result.detail for result in results)
    assert thin.is_sufficient is False


def test_a_sufficient_corpus_without_consent_stays_unevaluated():
    unconsented = AudioEvidence(
        meetings=MIN_MEETINGS,
        audio_hours=MIN_AUDIO_HOURS,
        clean_wer=0.10,
        consent_documented=False,
    )
    results = evaluate_audio(unconsented)
    assert all(result.outcome is GateOutcome.UNEVALUATED for result in results)
    assert all("consent" in result.detail for result in results)


def test_a_sufficient_corpus_is_judged_against_the_thresholds():
    good = AudioEvidence(
        meetings=MIN_MEETINGS,
        audio_hours=MIN_AUDIO_HOURS,
        clean_wer=0.18,
        noisy_wer=0.30,
        domain_term_recall=0.90,
        diarization_error=0.20,
        consent_documented=True,
    )
    assert all(result.outcome is GateOutcome.MET for result in evaluate_audio(good))

    bad = AudioEvidence(
        meetings=MIN_MEETINGS,
        audio_hours=MIN_AUDIO_HOURS,
        clean_wer=MAX_CLEAN_WER + 0.01,
        noisy_wer=0.30,
        domain_term_recall=0.90,
        diarization_error=0.20,
        consent_documented=True,
    )
    outcomes = {result.name: result.outcome for result in evaluate_audio(bad)}
    assert outcomes["clean_median_wer"] is GateOutcome.NOT_MET
    assert outcomes["noisy_far_field_wer"] is GateOutcome.MET


def test_retrieval_gates_require_a_labelled_set_and_perfect_citations():
    thin = RetrievalEvidence(labelled_queries=10, recall_at_10=0.99)
    assert all(result.outcome is GateOutcome.UNEVALUATED for result in evaluate_retrieval(thin))

    good = RetrievalEvidence(
        labelled_queries=MIN_LABELLED_QUERIES,
        recall_at_10=0.88,
        citation_precision=1.0,
        unsupported_claims=0,
    )
    assert all(result.outcome is GateOutcome.MET for result in evaluate_retrieval(good))

    # One unsupported claim is one too many, and citation precision is exact.
    for override in ({"unsupported_claims": 1}, {"citation_precision": 0.99}):
        fields: dict[str, object] = {
            "labelled_queries": MIN_LABELLED_QUERIES,
            "recall_at_10": 0.88,
            "citation_precision": 1.0,
            "unsupported_claims": 0,
        }
        fields.update(override)
        flawed = RetrievalEvidence(**fields)  # type: ignore[arg-type]
        assert any(result.outcome is GateOutcome.NOT_MET for result in evaluate_retrieval(flawed))


def test_a_full_report_only_releases_when_every_gate_is_met():
    audio = AudioEvidence(
        meetings=MIN_MEETINGS,
        audio_hours=MIN_AUDIO_HOURS,
        clean_wer=0.18,
        noisy_wer=0.30,
        domain_term_recall=0.90,
        diarization_error=0.20,
        consent_documented=True,
    )
    retrieval = RetrievalEvidence(
        labelled_queries=MIN_LABELLED_QUERIES,
        recall_at_10=0.88,
        citation_precision=1.0,
        unsupported_claims=0,
    )
    report = build_report(audio, retrieval)
    assert report.may_release is True
    assert report.blocking == ()
    assert "are met" in report.summary()

    # Losing any single gate blocks the release.
    partial = build_report(audio, RetrievalEvidence(labelled_queries=1))
    assert partial.may_release is False
    lines = format_report(partial)
    assert lines[0] == partial.summary()
    assert any("unevaluated" in line for line in lines)
