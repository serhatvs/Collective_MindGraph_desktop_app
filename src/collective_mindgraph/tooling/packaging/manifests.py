"""MSIX and App Installer manifest generation.

Generating these rather than hand-editing XML keeps the version, the publisher,
and the update channel consistent across three files that must agree. Signing
is deliberately absent: it needs a certificate this repository does not and
should not hold.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from xml.etree import ElementTree

# MSIX requires a strict four-part version whose last part is zero.
MSIX_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+\.0$")
APPINSTALLER_NAMESPACE = "http://schemas.microsoft.com/appx/appinstaller/2021"


class ReleaseChannel(StrEnum):
    """Which audience an update targets."""

    STABLE = "stable"
    BETA = "beta"


class PackagingError(ValueError):
    """Raised when a manifest cannot be generated safely."""


@dataclass(frozen=True, slots=True)
class PackageIdentity:
    """Who publishes the package and under what name."""

    name: str
    publisher: str
    publisher_display_name: str
    display_name: str
    description: str

    def __post_init__(self) -> None:
        for label, value in (
            ("name", self.name),
            ("publisher", self.publisher),
            ("publisher display name", self.publisher_display_name),
            ("display name", self.display_name),
            ("description", self.description),
        ):
            if not value.strip():
                raise PackagingError(f"The package {label} is required.")
        # The publisher string must be the certificate subject exactly, or
        # Windows refuses to install the signed package.
        if "CN=" not in self.publisher:
            raise PackagingError(
                "The publisher must be the certificate subject, for example 'CN=Example Ltd'."
            )


def msix_version(project_version: str) -> str:
    """Convert a project version into the four-part form MSIX requires."""

    core = project_version.split("+")[0].split("-")[0]
    parts = core.split(".")
    if not 1 <= len(parts) <= 3 or not all(part.isdigit() for part in parts):
        raise PackagingError(f"Unusable project version: {project_version!r}.")
    padded = (*parts, *("0" for _ in range(3 - len(parts))), "0")
    version = ".".join(padded)
    if not MSIX_VERSION_PATTERN.match(version):
        raise PackagingError(f"Unusable project version: {project_version!r}.")
    return version


def build_appx_manifest(identity: PackageIdentity, project_version: str) -> str:
    """Render `AppxManifest.xml` for one release."""

    version = msix_version(project_version)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Package
  xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
  xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
  xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities">
  <Identity Name="{identity.name}"
            Publisher="{identity.publisher}"
            Version="{version}"
            ProcessorArchitecture="x64" />
  <Properties>
    <DisplayName>{identity.display_name}</DisplayName>
    <PublisherDisplayName>{identity.publisher_display_name}</PublisherDisplayName>
    <Description>{identity.description}</Description>
    <Logo>Assets\\StoreLogo.png</Logo>
  </Properties>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop"
                        MinVersion="10.0.19045.0"
                        MaxVersionTested="10.0.26100.0" />
  </Dependencies>
  <Resources>
    <Resource Language="en-us" />
    <Resource Language="tr-tr" />
  </Resources>
  <Applications>
    <Application Id="CollectiveMindGraph"
                 Executable="CollectiveMindGraph.exe"
                 EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="{identity.display_name}"
                          Description="{identity.description}"
                          BackgroundColor="transparent"
                          Square150x150Logo="Assets\\Square150x150Logo.png"
                          Square44x44Logo="Assets\\Square44x44Logo.png" />
    </Application>
  </Applications>
  <Capabilities>
    <rescap:Capability Name="runFullTrust" />
    <DeviceCapability Name="microphone" />
  </Capabilities>
</Package>
"""


def build_app_installer(
    identity: PackageIdentity,
    project_version: str,
    *,
    base_url: str,
    channel: ReleaseChannel = ReleaseChannel.STABLE,
    hours_between_checks: int = 8,
) -> str:
    """Render an `.appinstaller` file using the 2021 schema."""

    if not base_url.startswith("https://"):
        raise PackagingError("Update feeds must be served over HTTPS.")
    if hours_between_checks < 1:
        raise PackagingError("The update interval must be at least one hour.")
    version = msix_version(project_version)
    root = base_url.rstrip("/")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<AppInstaller
  xmlns="{APPINSTALLER_NAMESPACE}"
  Uri="{root}/{channel.value}/CollectiveMindGraph.appinstaller"
  Version="{version}">
  <MainPackage Name="{identity.name}"
               Publisher="{identity.publisher}"
               Version="{version}"
               ProcessorArchitecture="x64"
               Uri="{root}/{channel.value}/CollectiveMindGraph_{version}_x64.msix" />
  <UpdateSettings>
    <OnLaunch HoursBetweenUpdateChecks="{hours_between_checks}" ShowPrompt="true" />
    <AutomaticBackgroundTask />
    <ForceUpdateFromAnyVersion>false</ForceUpdateFromAnyVersion>
  </UpdateSettings>
</AppInstaller>
"""


@dataclass(frozen=True, slots=True)
class ArtifactDigest:
    """One released file and its digest."""

    name: str
    sha256: str
    size_bytes: int


def digest_artifacts(paths: Iterable[Path]) -> tuple[ArtifactDigest, ...]:
    """Hash every release artefact, in a stable order."""

    digests: list[ArtifactDigest] = []
    for path in sorted(paths, key=lambda entry: entry.name):
        if not path.is_file():
            raise PackagingError(f"Release artefact is missing: {path}")
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                hasher.update(chunk)
        digests.append(
            ArtifactDigest(
                name=path.name,
                sha256=hasher.hexdigest(),
                size_bytes=path.stat().st_size,
            )
        )
    return tuple(digests)


def render_checksums(digests: Sequence[ArtifactDigest]) -> str:
    """Render a `sha256sum`-compatible manifest."""

    if not digests:
        raise PackagingError("A release must publish at least one artefact.")
    return "".join(f"{entry.sha256}  {entry.name}\n" for entry in digests)


def parse_appinstaller_version(document: str) -> str:
    """Read the version back out, so a published feed can be checked."""

    try:
        root = ElementTree.fromstring(document)
    except ElementTree.ParseError as error:
        raise PackagingError("The App Installer document is not valid XML.") from error
    version = root.get("Version")
    if not version:
        raise PackagingError("The App Installer document declares no version.")
    return version


__all__ = [
    "APPINSTALLER_NAMESPACE",
    "ArtifactDigest",
    "PackageIdentity",
    "PackagingError",
    "ReleaseChannel",
    "build_app_installer",
    "build_appx_manifest",
    "digest_artifacts",
    "msix_version",
    "parse_appinstaller_version",
    "render_checksums",
]
