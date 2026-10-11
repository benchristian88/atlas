# SecretProvider v1 specification

**Implemented for I2 Test Connection.** `integration_secrets.py` implements the
provider and `encrypted_data.py` registers its rewrap adapter using the existing
Atlas application-key lifecycle and maintained `cryptography` AESGCM. No second
master key exists. Discovery/job cancellation semantics below remain I3 targets.
See the [audit](../integration-alignment-matrix.md) and [contract ownership](README.md).

## Interface and authority

| Operation | Internal input | Safe result |
| --- | --- | --- |
| create | persisted Integration ownership, manifest-declared secret fields, sensitive write-only values | opaque SecretReference and configured field names |
| replace | authorized existing reference and declared replacement values | new revision/configured-state receipt; no old plaintext |
| delete | authorized existing reference | idempotent retired state, revoke leases and destroy stored credential material |
| state | authorized existing reference | configured/not-configured field state and safe rotation timestamps |
| materialize_for_job | reference, immutable test/run request, declared required field names, expiry | internal JobSecretLease bound to exactly one request/job |
| revoke_lease | lease ID and owning job/request | idempotent revoked/cleaned receipt |

UI/API write paths enforce existing `Principal` and `integrations.manage` scope,
load Integration/Customer/Site, validate required visible fields and exclude
secret values from serialized responses/repr/audit/errors. SecretReference is
opaque and is not permission to read plaintext. There is no browser/user `get`
secret operation. A global admin also cannot reveal stored secrets. Update
validation checks configured state internally and requests a new value only for
a new required credential; it never sends stored material back to forms.

JobSecretLease is an internal capability containing lease ID, owning request/run,
required fields, expiry and protected materialisation handle. Value access is
limited to the authorized internal runtime job transport; it is not a public
API response or AIP field. Lease lifetime cannot exceed job deadline; create/
replace/delete/expire/cancel invalidates relevant leases. Record revisions prevent
a stale lease from switching silently to newly rotated credentials.

## Encryption and versioned context

`app/config.py:data_encryption_key()` validates the existing 32-byte
`ATLAS_DATA_ENCRYPTION_KEY`. Installer generation/upgrade preserves it through
`infra/install/configuration.py`; never replace a key to recover an unreadable
ciphertext and never fall back to plaintext. Missing/malformed key, unknown
version or bad AEAD tag fails closed with a fixed safe diagnostic.

Use maintained AESGCM with fresh random 12-byte nonce per field/replacement.
Integration domain separation uses versioned associated data:

```text
atlas-integration-secret:v1:<customer_uuid>:<site_uuid>:<integration_uuid>:<field_key>:<revision_uuid>
```

Use canonical lowercase UUIDs and declared field keys with no colon. Store context
IDs/revision/encryption version alongside ciphertext/nonce; recompute AAD from
persisted immutable ownership, never caller-supplied AAD. Reassigning scope is a
reviewed re-encryption operation, not a metadata edit that bypasses the context.
The distinct prefix separates Integration secrets from existing
`atlas-mfa:v1:<user_uuid>` records without adding an operator-managed key.
Do not reuse MFA-specific base32 seed functions for generic credential values.

PostgreSQL stores ciphertext and safe metadata only. Integration non-secret JSON,
raw source payloads, AIP/evidence, frontend bundles, logs and exception strings
must contain no credential values. Authorized input still requires safe source
output minimization/redaction; schema validation alone cannot prove no secret
is embedded inside arbitrary source strings.

## Portable backup and restore

Register an Integration adapter in
`app/services/encrypted_data.py:ENCRYPTED_DATA_ADAPTERS` and reuse
`rewrap_application_data`. Adapter follows existing keyset batching/fresh nonce/
version validation and may flush but never commit. Existing caller transaction
authenticates and rewraps every encrypted field from source key to target key;
any invalid field rolls back all adapter writes. I2 includes actual PostgreSQL crypto, bad-context/key, portable encrypted backup
and destination-key restore regressions.

Existing encrypted backup stores the source key inside the encrypted archive.
Restore retains the destination `ATLAS_DATA_ENCRYPTION_KEY`, rewraps protected
records and preserves history. `AUTH_SECRET`, runtime-control secret and transient
run tokens remain destination-local; restored active tokens/leases must be
invalidated and runtime package/trust state revalidated before dispatch.
Existing backup quiescence and protected rollback recovery are mandatory for
new worker mutations; no second backup format/store/recovery path is introduced.

## Cleanup and history

Lease only required fields, use private ephemeral material with restrictive
permissions and bounded lifespan, redact events/stdout/errors and remove/revoke
material on success/failure/cancel and recovery of abandoned jobs. Avoid claims
of guaranteed physical RAM zeroisation in managed Python/Ansible runtimes; prove
access revocation and file/workspace cleanup instead.

Disable preserves credentials/configuration/history but stops dispatch; settle
any in-flight job under Atlas authority and revoke its lease when terminal.
Remove connection revokes jobs/leases and destroys credential material while
retaining run/evidence/Changes/source links/accepted knowledge. Backup archives
retain their historical ciphertext under normal existing retention; removing a
live secret cannot erase already-exported backups. Recovered connection state
must be explicit to the operator, with trust validation before execution.

## I2 implementation boundary

Secrets are separate revisioned `integration_secrets` records; the Integration
holds only an opaque UUID reference. AES-GCM binds Customer, Site, Integration,
field and revision through the AAD above. Full replacement encrypts first, swaps
and deletes the old revision in the same transaction. Clear and retirement destroy
live credential material and leave provenance intact. API state returns declared
field names only. No plaintext GET/reveal endpoint exists.

A saved probe holds the Integration row lock through a request-bound 30-second
in-memory lease, preventing replacement/clear races. The runtime has a 22-second
process deadline, reads credentials through a private pipe and deletes its 0700
workspace and 0600 input/result material in `finally`. Startup removes abandoned
owned probe directories. Lease exit revokes access and clears values; there is no
claim of physical RAM zeroisation. Unsaved previews use a transient lease and
persist only safe requested/result audit metadata, never an Integration/DataSource.
