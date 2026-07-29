"""Generate the MSIX, App Installer, and checksum manifests for a release.

Signing is not performed here. It needs a code-signing certificate or HSM that
this repository does not hold, and a manifest generator that pretended to sign
would be worse than one that does not.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from collective_mindgraph import __version__
from collective_mindgraph.tooling.packaging.manifests import (
    PackageIdentity,
    ReleaseChannel,
    build_app_installer,
    build_appx_manifest,
    digest_artifacts,
    msix_version,
    render_checksums,
)

DEFAULT_IDENTITY = PackageIdentity(
    name="CollectiveMindGraph",
    publisher="CN=Collective MindGraph",
    publisher_display_name="Collective MindGraph",
    display_name="Collective MindGraph",
    description="Local-first meeting capture, memory, and knowledge workspace.",
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="generate-release-manifests")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, default=Path("dist/CollectiveMindGraph"))
    parser.add_argument("--base-url", default="https://updates.example.invalid")
    parser.add_argument(
        "--channel",
        choices=[channel.value for channel in ReleaseChannel],
        default=ReleaseChannel.STABLE.value,
    )
    arguments = parser.parse_args(list(argv) if argv is not None else None)

    output = arguments.output.expanduser()
    output.mkdir(parents=True, exist_ok=True)
    (output / "AppxManifest.xml").write_text(
        build_appx_manifest(DEFAULT_IDENTITY, __version__),
        encoding="utf-8",
    )
    (output / "CollectiveMindGraph.appinstaller").write_text(
        build_app_installer(
            DEFAULT_IDENTITY,
            __version__,
            base_url=arguments.base_url,
            channel=ReleaseChannel(arguments.channel),
        ),
        encoding="utf-8",
    )

    bundle = arguments.bundle.expanduser()
    if bundle.is_dir():
        files = [path for path in sorted(bundle.rglob("*")) if path.is_file()]
        if files:
            (output / "SHA256SUMS").write_text(
                render_checksums(digest_artifacts(files)),
                encoding="utf-8",
            )
    print(f"Wrote release manifests for {msix_version(__version__)} to {output}.")
    print("The package is UNSIGNED: signing requires the release certificate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
