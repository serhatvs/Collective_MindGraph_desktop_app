# Public Production V1 Program

Collective MindGraph will reach public `1.0.0` through twelve squash-merged
pull requests. Every branch starts from the then-current `main`; `main` must
remain runnable and reversible after each merge.

## Delivery sequence

| Stage | Branch | Outcome | Status |
| --- | --- | --- | --- |
| 1 | `chore/production-quality-baseline` | Locked dependencies, CI, quality/security ratchets, SBOM and package smoke | Merged in PR [#15](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/15) (`4ee7949`) |
| 2 | `refactor/workspace-sync-identities` | Schema v3, workspace/global identities, outbox and encrypted backup foundation | Merged in PR [#21](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/21) (`1762b93`) |
| 3 | `feat/e2ee-key-management` | Device/workspace keys, recovery and rotation | Merged in PR [#23](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/23) (`883dfdb`) |
| 4 | `feat/sync-service-core` | Opaque PostgreSQL/S3 sync service and retention | Merged in PR [#24](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/24) (`2c85c5c`) |
| 5 | `feat/oidc-rbac-admin` | OIDC PKCE, fixed roles and content-free web admin | In review |
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

## Delivered cryptography contract

Stage 3 fixes the encryption contract every later stage depends on. Details and
the independent-reviewer checklist live in `CRYPTO_THREAT_MODEL.md`.

- Content uses AES-256-GCM. Associated data binds workspace, object type,
  object UUID, revision, and key version with length-prefixed fields.
- Workspace keys are wrapped per recipient with ephemeral X25519 and
  HKDF-SHA256; the derivation info also authenticates the envelope.
- Recovery uses a 256-bit Crockford base32 code with a checksum and scrypt
  derivation. The code is displayed once and never persisted.
- Device private keys live in a `DeviceSecretStore` outside SQLite, sealed with
  Windows DPAPI under the current user account.
- Removing a device revokes its envelopes and rotates the key. Rotation
  protects future content only and cannot recall already decrypted content.
- Primitive behaviour is pinned by RFC 7748, RFC 5869, and published AES-GCM
  specification vectors.

## Delivered service contract

Stage 4 adds `collective_mindgraph.sync_server`, a separate deployable that the
architecture rules forbid from importing the desktop, the local engine, or local
persistence. Details live in `SYNC_SERVICE.md`.

- Push batches are capped at 500 operations and 4 MiB, applied in one
  transaction, and made idempotent by client-generated operation identifiers.
- Writes are optimistic: a stale `base_revision` becomes a reported conflict,
  never a silent overwrite, and a replayed conflict returns the same answer.
- Pull is ordered by a per-workspace cursor claimed under a row lock.
- WebSocket invalidations carry a workspace identifier and a cursor only.
- Raw-audio blobs stay opt-in per workspace, upload in resumable chunks, and are
  verified per chunk and again on reassembly against the declared digest.
- Retention is enforced by `mindgraph-admin purge`: content 30 days, audit and
  tombstone metadata 90 days, encrypted backup and PITR data 35 days.
- Identity is a documented bootstrap resolver until stage 5 introduces OIDC;
  roles are already enforced on every route.

## Delivered identity contract

Stage 5 makes identity provider-independent OIDC. Details live in
`SYNC_SERVICE.md`.

- The desktop signs in through the operating system's browser with
  Authorization Code, PKCE `S256`, and a loopback redirect on a port chosen at
  request time, as RFC 8252 and RFC 7636 require. The PKCE challenge is pinned
  by the RFC 7636 appendix vector.
- The service verifies every token against the provider's JWKS, issuer, and
  audience, accepting asymmetric algorithms only.
- The admin surface completes its code flow on the server, so no token reaches
  a page, and protects sessions with signed `HttpOnly` cookies, CSRF tokens,
  and per-identity rate limits.
- The admin renders plain server-side HTML with no JavaScript, which allows a
  `default-src 'none'` policy. This replaces the planned vendored HTMX layer;
  the surface needs no scripting and gains a strictly stronger policy.
- With OIDC unconfigured the service warns at startup and the admin sign-in
  returns 401 rather than falling back to something weaker.

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
