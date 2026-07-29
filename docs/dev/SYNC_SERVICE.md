# Synchronization Service

The service stores sealed bytes plus bounded routing and audit metadata. It
holds no workspace keys, no device private keys, and no recovery codes, so it
cannot decrypt anything it stores. `CRYPTO_THREAT_MODEL.md` is the contract this
service inherits; this document describes what stage 4 delivered against it.

## Surface

Every route lives under `/sync/v1` and requires an authenticated principal.

| Route | Minimum role | Purpose |
| --- | --- | --- |
| `GET /health` | none | Liveness plus negotiated limits |
| `GET`/`POST /workspaces` | member / any | List or create a workspace |
| `PUT /workspaces/{id}/raw-audio` | admin | Opt raw-audio sync in or out |
| `PUT`/`DELETE /workspaces/{id}/members` | admin | Seat or remove a member |
| `POST /workspaces/{id}/devices` | viewer | Register a device public key |
| `DELETE /workspaces/{id}/devices/{device}` | admin | Revoke a device |
| `POST /workspaces/{id}/envelopes` | editor | Store a wrapped key |
| `GET .../devices/{device}/envelopes` | viewer | Fetch a device's envelopes |
| `POST /workspaces/{id}/push` | editor | Apply an idempotent batch |
| `GET /workspaces/{id}/pull` | viewer | Read changes after a cursor |
| `POST`/`PUT`/`GET .../blobs...` | editor / viewer | Resumable blob transfer |
| `GET /workspaces/{id}/usage` | viewer | Content-free quota counters |
| `WS /workspaces/{id}/invalidations` | viewer | Cursor hints only |

## Synchronization model

- A push carries at most 500 operations and 4 MiB of ciphertext. Both limits are
  configurable downward and are enforced before anything is written.
- Every operation carries a client-generated `operation_id`. Replaying a batch
  returns the original outcome rather than applying it twice, so a client that
  loses a response can retry safely.
- Writes are optimistic. An operation whose `base_revision` does not match the
  stored revision is recorded as a conflict and reported with the server's
  revision. The client resolves and pushes a new revision; the service never
  merges and never silently overwrites.
- A batch is one transaction. Mixed outcomes are normal: accepted operations
  are durable even when others in the same batch conflict.
- Pull is ordered by a per-workspace cursor sequence claimed under a row lock,
  so ordering is total and gap-free within a workspace.
- Deletions keep the row as a tombstone, clear the ciphertext immediately, and
  start the retention window.

## Invalidations

The WebSocket carries `{workspace_id, cursor}` and nothing else. A client
reacts by pulling through the authorized path, so a leaked hint reveals only
that a workspace changed. Saturated subscribers are skipped rather than allowed
to block a push; they converge on their next pull.

## Blobs

Raw-audio sync is per workspace and defaults to off. When enabled, uploads are
chunked at 8 MiB, resumable, and verified twice: each chunk against its recorded
digest and the reassembled ciphertext against the digest the client declared.
The filesystem adapter confines every key beneath the blob root; an
S3-compatible adapter uses the same key layout.

## Retention

| Data | Window |
| --- | --- |
| Deleted content ciphertext | 30 days |
| Audit and tombstone metadata | 90 days |
| Encrypted backup and PITR data | 35 days |

`mindgraph-admin purge` applies every window in one pass and reports what it
removed. `mindgraph-admin show-retention` prints the configured windows.

## Identity

Identity is provider-independent OIDC. Every request is authenticated by
verifying a signed access token against the provider's published JWKS, its
issuer, and this deployment's audience. Only asymmetric algorithms are
accepted, so an `alg: none` or symmetric token is refused before any signature
check. Keys are cached and refreshed once when a token presents an unknown key
id, so provider rotation does not require a restart.

The bootstrap bearer-token resolver from stage 4 remains for self-host first
run and for tests. It is not an identity provider: when OIDC is unconfigured
the service logs a warning at startup and the admin sign-in returns 401 rather
than degrading to something weaker.

## Administration surface

`/admin` renders membership, device, quota, and content-free audit metadata.
It cannot reach ciphertext, and its templates have no field that could render
it.

- Sign-in completes the authorization-code flow **on the server**, so no token
  is ever exposed to a page. PKCE is applied even though the flow is
  confidential.
- The session is a signed, `HttpOnly`, `SameSite=Lax` cookie with an eight-hour
  lifetime, `Secure` whenever the request arrived over HTTPS.
- Every state-changing form carries a CSRF token bound to the session.
- Requests are rate limited per identity.
- The surface is plain server-rendered HTML with **no JavaScript**, so the
  Content-Security-Policy is `default-src 'none'` with `form-action 'self'`.
  The programme sketched a vendored HTMX layer; dropping it removes the need
  for `script-src` entirely, and the surface loses nothing it needed.

## Configuration

| Variable | Required | Meaning |
| --- | --- | --- |
| `CMG_SYNC_DATABASE_URL` | yes | `postgresql+asyncpg://` or `sqlite+aiosqlite://` |
| `CMG_SYNC_BLOB_ROOT` | yes | Root for sealed blob chunks |
| `CMG_SYNC_BOOTSTRAP_TOKENS` | bootstrap only | `token=subject` pairs |
| `CMG_SYNC_OIDC_ISSUER` | public use | HTTPS issuer; enables OIDC when set |
| `CMG_SYNC_OIDC_AUDIENCE` | with OIDC | Audience this deployment accepts |
| `CMG_SYNC_OIDC_JWKS_URI` | with OIDC | HTTPS JWKS document |
| `CMG_SYNC_OIDC_CLIENT_ID` | with OIDC | Client identifier |
| `CMG_SYNC_OIDC_AUTHORIZATION_ENDPOINT` | admin surface | Browser sign-in endpoint |
| `CMG_SYNC_OIDC_TOKEN_ENDPOINT` | admin surface | Code exchange endpoint |
| `CMG_SYNC_OIDC_ALGORITHMS` | no | Defaults to the asymmetric set |
| `CMG_SYNC_ADMIN_SESSION_SECRET` | admin surface | At least 32 bytes; shared across replicas |
| `CMG_SYNC_PUSH_OPERATION_LIMIT` | no | Default 500 |
| `CMG_SYNC_PUSH_BYTE_LIMIT` | no | Default 4 MiB |
| `CMG_SYNC_BLOB_CHUNK_BYTES` | no | Default 8 MiB |
| `CMG_SYNC_PULL_LIMIT` | no | Default 500, maximum 2000 |
| `CMG_SYNC_*_RETENTION_DAYS` | no | Content 30, audit 90, backup 35 |

## Operating

```bash
alembic -c src/collective_mindgraph/sync_server/migrations/alembic.ini upgrade head
```

`deploy/sync-server/` contains a rootless image and a Compose example that runs
migrations before the service starts. TLS termination, secret management, and
PostgreSQL backups belong to the deployment and are covered in stage 11.

## Verification

The suite runs against SQLite by default. Setting `CMG_SYNC_TEST_DATABASE_URL`
points the same tests at a real PostgreSQL server, which is what the dedicated
CI job does after applying the Alembic migrations.
