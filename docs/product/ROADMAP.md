# Collective MindGraph Roadmap

The current release establishes the single-package, single-data-owner product
architecture. The public-production-v1 program now advances it through twelve
independently reviewable and reversible PRs.

## Production quality foundation

- Keep Windows/Linux Python 3.11-3.13 tests, golden contracts, strict typing
  ratchets, coverage, dependency audit, secret scanning, CodeQL, SBOM, and
  packaged-engine smoke green.
- Raise branch-inclusive coverage from the measured 75% baseline to 85%, with
  90% changed-line coverage and 95% in domain, application, migration, sync,
  and cryptography code.
- Remove every 400-line and complexity-12 exception before public 1.0.0.

## Workspace identity and encrypted synchronization

- Introduce stable workspace/entity UUIDs and schema-v3 migration without
  changing local integer identifiers or `/api/v1` contracts.
- Add optional provider-independent OIDC, five fixed workspace roles, device
  trust, recovery, and end-to-end encrypted synchronization.
- Keep local-only usage complete and keep content unreadable to sync servers.

## Collaboration and desktop experience

- Add workspace switching, conflict resolution, comments, mentions, activity,
  dark/system themes, virtualized large lists, richer capture and review tools,
  and an E2EE-aware administration surface.
- Add a native bounded knowledge canvas while retaining table exploration.

## Quality evidence

- Build human-reviewed Turkish meeting-room fixtures across noise, distance,
  overlap, and microphone conditions.
- Report WER/CER and domain-term accuracy only against those references.
- Validate optional Silero behavior on target Windows hardware.

## Retrieval quality

- Evaluate real local embedding models with labelled search judgments.
- Add explainable reranking when evidence shows a measurable benefit.
- Expand relationship extraction without weakening source traceability.

## Audio and speaker research

- Bound streaming backlog and upload size.
- Validate speaker separation before promoting it from Labs.
- Preserve channel information where it improves multi-speaker recordings.

## Distribution

- Move the onedir application bundle into signed MSIX/App Installer channels.
- Add repeatable install, repair, signing, update, backup, and rollback
  validation on clean Windows 10 and Windows 11 machines.
- Ship a rootless sync-server container, self-host examples, restore runbooks,
  content-free telemetry, legal notices, and signed SBOM/checksums.
- Keep the canonical user-data path stable across upgrades.

Mobile clients, macOS/Linux distribution, a full web client, live co-editing,
server-side content search/AI, checkout, and initial multi-region SaaS remain
outside public 1.0.0.
