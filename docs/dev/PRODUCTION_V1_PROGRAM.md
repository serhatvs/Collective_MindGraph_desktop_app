# Public Production V1 Program

Collective MindGraph will reach public `1.0.0` through twelve squash-merged
pull requests. Every branch starts from the then-current `main`; `main` must
remain runnable and reversible after each merge.

## Delivery sequence

| Stage | Branch | Outcome | Status |
| --- | --- | --- | --- |
| 1 | `chore/production-quality-baseline` | Locked dependencies, CI, quality/security ratchets, SBOM and package smoke | Merged in PR [#15](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/15) (`4ee7949`) |
| 2 | `refactor/workspace-sync-identities` | Schema v3, workspace/global identities, outbox and encrypted backup foundation | Active |
| 3 | `feat/e2ee-key-management` | Device/workspace keys, recovery and rotation | Planned |
| 4 | `feat/sync-service-core` | Opaque PostgreSQL/S3 sync service and retention | Planned |
| 5 | `feat/oidc-rbac-admin` | OIDC PKCE, fixed roles and content-free web admin | Planned |
| 6 | `feat/desktop-sync-client` | Engine-owned offline/near-real-time sync and conflicts | Planned |
| 7 | `feat/collaboration-experience` | Workspace, activity, comments, mentions and recovery UX | Planned |
| 8 | `feat/desktop-product-polish` | Themes, virtualized UI, capture/review/accessibility polish | Planned |
| 9 | `feat/knowledge-canvas-retrieval` | Native graph canvas, FTS5 and local ANN/RRF retrieval | Planned |
| 10 | `feat/audio-model-quality` | Signed model manager and evidence-based audio/retrieval gates | Planned |
| 11 | `build/signed-msix-release` | Signed MSIX/App Installer and deployable self-host stack | Planned |
| 12 | `release/production-v1-hardening` | Scale, clean-machine, restore, security and 1.0.0 gates | Planned |

## Non-negotiable boundaries

- Local-only use remains complete and requires no account.
- The desktop talks to the localhost engine; it never talks directly to cloud
  services.
- Sync servers receive only ciphertext plus bounded routing/audit metadata.
  Transcript, audio, evidence, knowledge content, and search indexes remain
  client-side.
- Legacy HTTP/WebSocket and `/api/v1` golden contracts remain compatible.
- Existing user data is upgraded only through backup, sibling staging,
  integrity/foreign-key/count validation, and atomic activation.
- Raw-audio sync and content-free telemetry are separately opt-in and default
  to off. Model downloads always require explicit approval.

## Release gates

- Windows 10 22H2 and Windows 11 install, update, repair, rollback, migration,
  OIDC, model download, engine lifecycle, and uninstall smoke must pass.
- Branch-inclusive coverage is at least 85%; changed production lines are at
  least 90%; domain, application, migration, sync, and cryptography are at
  least 95%.
- Real Turkish validation uses at least 30 consented/licensed meetings and 20
  hours with reference transcripts. Required targets are clean median WER
  `<=20%`, noisy/far-field WER `<=35%`, domain-term recall `>=85%`, retrieval
  Recall@10 `>=0.85`, citation precision `1.0`, and zero unsupported grounded
  claims.
- The EU service target is 100 concurrent users per workspace, 100,000
  meetings, one million knowledge items, 99.9% control-plane availability,
  RPO `<=15 minutes`, and RTO `<=4 hours`.
- Public release is blocked by any P0/P1 defect, high/critical dependency
  vulnerability, known data-loss path, unresolved security finding, or
  independent cryptography-review finding.

External release inputs remain required: a code-signing certificate/HSM,
provider OIDC registrations, EU PostgreSQL/S3/SMTP infrastructure, two clean
Windows hardware profiles, licensed Turkish validation data, and an independent
security/cryptography reviewer.
