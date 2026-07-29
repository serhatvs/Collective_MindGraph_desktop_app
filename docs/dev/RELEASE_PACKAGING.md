# Release Packaging

## What this repository produces

`CollectiveMindGraph.spec` builds a **onedir** bundle. A one-file build unpacks
to a temporary directory on every launch, which is slow and leaves an update
with nothing stable to replace; MSIX and App Installer both want a directory
they can swap atomically.

`scripts/packaging/generate_release_manifests.py` renders, from the project
version so that all three agree:

- `AppxManifest.xml`
- `CollectiveMindGraph.appinstaller` (App Installer 2021 schema)
- `SHA256SUMS` over every file in the bundle

The Windows CI job builds the bundle, runs the packaged engine health smoke
against `dist/CollectiveMindGraph/CollectiveMindGraph.exe`, and generates the
manifests.

## What this repository cannot produce

**A signed package.** Signing needs a code-signing certificate or HSM that is
not held here, and the publisher string in `AppxManifest.xml` must be the
certificate subject exactly or Windows refuses to install. The generator prints
`UNSIGNED` on every run and a test asserts that it does, so an unsigned build
cannot be mistaken for a signed one.

To sign a release, on a machine holding the certificate:

```bash
signtool sign /fd SHA256 /a /tr http://timestamp.digicert.com /td SHA256 CollectiveMindGraph_<version>_x64.msix
```

Set `PackageIdentity.publisher` to that certificate's subject first. A mismatch
produces an install failure that is confusing to diagnose after the fact.

## Update channels

`stable` and `beta` produce separate feeds and separate package URIs from one
generator, so a beta cannot be published to the stable feed by editing a path
by hand. `OnLaunch` checks for updates with a prompt; the background task keeps
an idle install current.

## Upgrade safety

The engine already takes a backup and stages migrations in a sibling database
before atomic activation, so an upgrade that fails leaves the previous data
intact. Schema changes must stay N-1 compatible: the previous application
version has to keep reading the database after an upgrade, because a rollback
is otherwise a data-loss event.

## Still open in this stage

Recorded rather than implied as done:

- Signed artefacts, which need the certificate.
- The Helm chart for the synchronization service. The rootless image and the
  Compose example exist under `deploy/sync-server/`.
- OpenTelemetry traces and metrics for the service.
- PostgreSQL point-in-time-recovery, S3 lifecycle, restore-drill, and secret
  rotation runbooks.
- The EULA, privacy policy, DPA, and third-party NOTICE. These need legal
  review; drafting them here and calling them final would be worse than not
  having them.
