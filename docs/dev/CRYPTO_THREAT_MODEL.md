# End-to-End Encryption Threat Model

This document describes what Collective MindGraph's workspace encryption
protects, what it deliberately does not protect, and which properties an
independent reviewer must confirm before public `1.0.0`.

It covers stage 3 of the production programme documented in
`PRODUCTION_V1_PROGRAM.md`. Stages 4 to 6 add the sync service, identity, and
client that consume these primitives; this model is the contract they inherit.

## Scope

Encryption applies to synchronized workspace content: transcripts, corrections,
insights, evidence, knowledge nodes and edges, comments, activity, and, when a
workspace opts in, raw audio blobs.

Local-only use requires no account and no cloud key material. A local workspace
still owns a device key and a workspace key so that enabling sync later never
requires re-encrypting or re-uploading anything.

## Assets

| Asset | Where it lives | Protection |
| --- | --- | --- |
| Workspace key (`AES-256`) | Memory while unlocked; never on disk in the clear | Wrapped per recipient |
| Device private key (`X25519`) | `DeviceSecretStore`, outside SQLite | Windows DPAPI, user scope |
| Recovery code | Shown to the user once; never stored | Only a scrypt-derived wrapping exists |
| Content ciphertext | Local SQLite and, when sync is on, the server | AES-256-GCM with bound associated data |
| Routing metadata | Local SQLite and the server | Not encrypted; deliberately minimal |

## Trust boundaries

1. **The user's device is trusted.** Malware with the user's privileges can read
   plaintext while a workspace is unlocked. Encryption does not defend against
   a compromised endpoint, and the product must not claim otherwise.
2. **The sync server is untrusted for content.** It stores ciphertext and
   routing metadata only. It never receives workspace keys, device private
   keys, recovery codes, or search indexes.
3. **The transport is untrusted.** TLS is required, but confidentiality does not
   depend on it; every payload is already sealed.
4. **Other workspace members are trusted with the content they can read.**
   Sharing is a membership decision, not a cryptographic one.

## Primitives and bindings

- Content uses `AES-256-GCM` with a fresh 96-bit nonce per encryption.
- Associated data binds every ciphertext to its workspace, object type, object
  UUID, revision, and key version. Fields are length prefixed so that no two
  distinct bindings can encode to the same bytes. Replaying a ciphertext onto a
  different revision, object, or key version fails authentication.
- Device wrapping uses ephemeral `X25519` plus `HKDF-SHA256`. The HKDF info
  string commits to the workspace, key version, ephemeral public key, and
  recipient public key, and is reused as the AES-GCM associated data, so an
  envelope cannot be replayed against a different recipient or version.
- Recovery wrapping derives its key from the normalized recovery code with
  `scrypt` (N=2^15, r=8, p=1) and a per-envelope salt.
- Recovery codes carry 256 bits of entropy in Crockford base32 with a
  SHA-256-derived checksum, so mistyped codes are rejected before any
  key-derivation attempt.
- Primitive behaviour is pinned by published vectors: RFC 7748 for X25519,
  RFC 5869 for HKDF-SHA256, and the GCM specification's AES-256 cases.

## Server-visible metadata

The server can observe tenant, workspace, user subject, device, object type,
object UUID, revision, timestamps, ciphertext size, and ciphertext hash. It
cannot observe titles, bodies, transcripts, audio, evidence, or queries.

This is a deliberate accepted residual risk: traffic analysis can reveal
activity volume and rough workspace structure. Reducing it further would
require padding and cover traffic, which are out of scope for `1.0.0` and must
be stated plainly in the privacy policy rather than implied away.

## Key lifecycle

- **Initialization** creates key version one, wraps it for the current device,
  and produces a recovery bundle shown once.
- **Enrollment** requires an authorized member device that can already unlock
  the workspace. It wraps the current version for the joining device.
- **Recovery** unwraps the recovery envelope with the user's code and re-wraps
  the key for the recovering device.
- **Rotation** issues the next version and wraps it for every non-revoked
  device plus a fresh recovery envelope. Older versions stay decryptable so
  historical content remains readable.
- **Revocation** marks the device revoked, revokes its envelopes, and rotates.

## Explicit non-goals

- **Rotation is not retroactive.** A removed member or device cannot decrypt
  content created after rotation, but content it already downloaded or
  decrypted cannot be recalled. Product and security documentation must state
  this directly.
- **No forward secrecy for stored content.** Compromising a device private key
  plus stored envelopes exposes the workspace keys those envelopes wrap.
- **No protection against a malicious authorized member.** Anyone who can read
  a workspace can export or retype its content.
- **No server-side search.** Because the server never holds keys, it cannot
  build indexes; each client indexes locally after decrypting.

## Reviewer checklist

An independent reviewer must confirm, before public release, that:

1. Associated data is unambiguous and covers workspace, type, object, revision,
   and key version for every encrypted entity.
2. Nonces are never reused under one key, including after restore from backup.
3. Device private keys never reach SQLite, exports, logs, telemetry, or crash
   dumps.
4. Recovery codes are generated from a cryptographically secure source, shown
   once, and never persisted in any form other than the wrapped envelope.
5. Revocation and rotation cannot be bypassed by replaying an older envelope.
6. Failure paths reject rather than fall back to unauthenticated behaviour.
7. The non-goals above are reflected in the shipped privacy policy and product
   copy, without overstated claims.

## Open items for later stages

- Stage 4 must define server-side retention for revoked envelopes and confirm
  ciphertext hashes are computed over sealed bytes only.
- Stage 5 must bind device enrollment approval to an authenticated OIDC subject
  and an authorized role.
- Stage 6 must ensure conflict resolution never writes plaintext to the outbox
  and never reuses a nonce when a rejected push is retried.
- Stage 8 must ensure telemetry and diagnostics bundles exclude key material,
  recovery codes, and decrypted content.
