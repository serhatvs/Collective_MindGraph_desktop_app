"""MSIX and App Installer manifest generation, and release checksums."""

from __future__ import annotations

import hashlib
from pathlib import Path
from xml.etree import ElementTree

import pytest

from collective_mindgraph.tooling.packaging.manifests import (
    APPINSTALLER_NAMESPACE,
    ArtifactDigest,
    PackageIdentity,
    PackagingError,
    ReleaseChannel,
    build_app_installer,
    build_appx_manifest,
    digest_artifacts,
    msix_version,
    parse_appinstaller_version,
    render_checksums,
)

IDENTITY = PackageIdentity(
    name="CollectiveMindGraph",
    publisher="CN=Example Ltd",
    publisher_display_name="Example Ltd",
    display_name="Collective MindGraph",
    description="Local-first meeting capture.",
)


# Versions -----------------------------------------------------------------


def test_project_versions_become_the_four_part_form_msix_requires():
    assert msix_version("0.3.0") == "0.3.0.0"
    assert msix_version("1.0") == "1.0.0.0"
    assert msix_version("2") == "2.0.0.0"
    # Pre-release and build metadata are not expressible in an MSIX version.
    assert msix_version("1.2.3-rc.1") == "1.2.3.0"
    assert msix_version("1.2.3+build9") == "1.2.3.0"


def test_unusable_versions_are_refused():
    for value in ("", "latest", "1.2.3.4", "a.b.c", "1..2"):
        with pytest.raises(PackagingError):
            msix_version(value)


def test_the_publisher_must_be_a_certificate_subject():
    """Windows refuses to install if this does not match the certificate."""

    with pytest.raises(PackagingError, match="certificate subject"):
        PackageIdentity(
            name="X",
            publisher="Example Ltd",
            publisher_display_name="Example Ltd",
            display_name="X",
            description="d",
        )
    for field in ("name", "publisher_display_name", "display_name", "description"):
        fields = {
            "name": "X",
            "publisher": "CN=Example Ltd",
            "publisher_display_name": "Example Ltd",
            "display_name": "X",
            "description": "d",
        }
        fields[field] = "  "
        with pytest.raises(PackagingError):
            PackageIdentity(**fields)  # type: ignore[arg-type]


# Manifests ----------------------------------------------------------------


def test_the_appx_manifest_is_well_formed_and_carries_the_identity():
    document = build_appx_manifest(IDENTITY, "0.3.0")
    root = ElementTree.fromstring(document)
    namespace = {"m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10"}
    identity = root.find("m:Identity", namespace)
    assert identity is not None
    assert identity.get("Name") == "CollectiveMindGraph"
    assert identity.get("Publisher") == "CN=Example Ltd"
    assert identity.get("Version") == "0.3.0.0"
    # The product records audio, so the capability must be declared.
    assert "microphone" in document
    assert "runFullTrust" in document


def test_the_app_installer_uses_the_2021_schema_and_matching_versions():
    document = build_app_installer(
        IDENTITY,
        "0.3.0",
        base_url="https://updates.example.test",
        channel=ReleaseChannel.BETA,
    )
    root = ElementTree.fromstring(document)
    assert root.tag == f"{{{APPINSTALLER_NAMESPACE}}}AppInstaller"
    assert parse_appinstaller_version(document) == "0.3.0.0"

    main_package = root.find(f"{{{APPINSTALLER_NAMESPACE}}}MainPackage")
    assert main_package is not None
    # The feed version and the package version must agree or the update stalls.
    assert main_package.get("Version") == root.get("Version")
    assert main_package.get("Publisher") == IDENTITY.publisher
    assert "/beta/" in str(main_package.get("Uri"))


def test_channels_produce_different_feeds():
    stable = build_app_installer(IDENTITY, "1.0.0", base_url="https://u.example.test")
    beta = build_app_installer(
        IDENTITY,
        "1.0.0",
        base_url="https://u.example.test",
        channel=ReleaseChannel.BETA,
    )
    assert "/stable/" in stable and "/beta/" not in stable
    assert "/beta/" in beta and "/stable/" not in beta


def test_update_feeds_must_be_https_and_sanely_scheduled():
    with pytest.raises(PackagingError, match="HTTPS"):
        build_app_installer(IDENTITY, "1.0.0", base_url="http://u.example.test")
    with pytest.raises(PackagingError):
        build_app_installer(
            IDENTITY,
            "1.0.0",
            base_url="https://u.example.test",
            hours_between_checks=0,
        )


def test_parsing_rejects_a_document_that_is_not_a_feed():
    with pytest.raises(PackagingError, match="valid XML"):
        parse_appinstaller_version("not xml")
    with pytest.raises(PackagingError, match="no version"):
        parse_appinstaller_version("<AppInstaller />")


# Checksums ----------------------------------------------------------------


def test_artefacts_are_hashed_in_a_stable_order(tmp_path: Path):
    for name, payload in (("b.dll", b"second"), ("a.exe", b"first")):
        (tmp_path / name).write_bytes(payload)
    digests = digest_artifacts(tmp_path.iterdir())
    assert [entry.name for entry in digests] == ["a.exe", "b.dll"]
    assert digests[0].sha256 == hashlib.sha256(b"first").hexdigest()
    assert digests[0].size_bytes == len(b"first")


def test_a_missing_artefact_is_an_error_not_a_silent_omission(tmp_path: Path):
    with pytest.raises(PackagingError, match="missing"):
        digest_artifacts([tmp_path / "absent.exe"])


def test_checksums_render_in_the_standard_format():
    digests = (
        ArtifactDigest(name="a.exe", sha256="a" * 64, size_bytes=1),
        ArtifactDigest(name="b.dll", sha256="b" * 64, size_bytes=2),
    )
    rendered = render_checksums(digests)
    assert rendered == f"{'a' * 64}  a.exe\n{'b' * 64}  b.dll\n"
    with pytest.raises(PackagingError, match="at least one artefact"):
        render_checksums(())


# Generator ----------------------------------------------------------------


def test_the_generator_writes_every_manifest_and_says_it_did_not_sign(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    from scripts.packaging.generate_release_manifests import main

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "CollectiveMindGraph.exe").write_bytes(b"binary")
    output = tmp_path / "release"

    assert main(["--output", str(output), "--bundle", str(bundle)]) == 0
    assert (output / "AppxManifest.xml").exists()
    assert (output / "CollectiveMindGraph.appinstaller").exists()
    checksums = (output / "SHA256SUMS").read_text(encoding="utf-8")
    assert hashlib.sha256(b"binary").hexdigest() in checksums

    printed = capsys.readouterr().out
    # The generator must never let an unsigned build look like a signed one.
    assert "UNSIGNED" in printed


def test_the_generator_still_writes_manifests_without_a_bundle(tmp_path: Path):
    from scripts.packaging.generate_release_manifests import main

    output = tmp_path / "release"
    assert main(["--output", str(output), "--bundle", str(tmp_path / "absent")]) == 0
    assert (output / "AppxManifest.xml").exists()
    assert not (output / "SHA256SUMS").exists()
