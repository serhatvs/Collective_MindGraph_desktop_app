# Security Policy

## Reporting a vulnerability

Report suspected vulnerabilities privately through GitHub's **Report a
vulnerability** button on the Security tab of this repository. Please do not
open a public issue for anything that could expose user data.

Include what you did, what happened, and what you expected. A proof of concept
helps but is not required to report.

We aim to acknowledge a report within three working days and to give an initial
assessment within ten. Those are targets, not contractual commitments.

## What is in scope

- The desktop application and the localhost engine.
- The synchronization service, its administration surface, and its migrations.
- The end-to-end encryption design in `docs/dev/CRYPTO_THREAT_MODEL.md`.
- The signed model catalogue and installer.

## What is deliberately not protected

These are design decisions, documented so that a report about them can be
answered honestly rather than treated as news:

- **A compromised endpoint.** Malware running with the user's privileges can
  read plaintext while a workspace is unlocked. Encryption does not defend
  against that and the product must not claim it does.
- **Rotation is not retroactive.** Removing a member or a device rotates future
  keys. Content already downloaded and decrypted cannot be recalled.
- **No forward secrecy for stored content.** A device private key plus stored
  envelopes exposes the workspace keys those envelopes wrap.
- **Server-visible metadata.** The service can observe tenant, workspace, user,
  device, object type, revision, timestamps, sizes, and ciphertext hashes.
  Traffic analysis over that metadata is an accepted residual risk.

## Current gaps

Stated plainly rather than left for a reporter to discover:

- This repository is private and GitHub reports that Advanced Security has not
  been purchased. CodeQL and dependency review therefore cannot run; Bandit and
  `pip-audit` are the enforcing gates meanwhile. See the programme document.
- The independent cryptography review listed in
  `docs/dev/CRYPTO_THREAT_MODEL.md` has not yet been performed.
- Release artefacts are **not signed**. Signing requires a code-signing
  certificate that is not held here.

## Supported versions

No public release has been made. Until `1.0.0` ships, only the `main` branch is
supported.
