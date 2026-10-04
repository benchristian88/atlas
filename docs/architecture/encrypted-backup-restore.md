# Encrypted Atlas backup and restore

Atlas implements portable **application data/state** backup, not VM snapshots,
container images, application binaries or operational Backup & Recovery domain
modelling. PostgreSQL remains the system of record. Both supported deployment
methods use the same portable archive and target-local configuration boundary.

## Authoritative state inventory

The inspected authoritative backup set is the entire Atlas PostgreSQL database
plus the source `ATLAS_DATA_ENCRYPTION_KEY`. Database-native dumps preserve all
tables, IDs, timestamps, constraints, accepted knowledge, observation/assertion
history, documents, topology configuration, managed taxonomy, users/password
hashes, assignments, settings, audit history and installation state.

| Location inspected | Current behavior and backup treatment |
| --- | --- |
| PostgreSQL / Compose `postgres_data` | All authoritative Atlas records; included in full custom-format dump. |
| Asset icons | Bounded image bytes/cache metadata in `asset_icon_cache`; included even though the cache is disposable. No filesystem image store. |
| Generated documents / uploads | `documents.content_markdown` is PostgreSQL state. No implemented persistent upload filesystem or external authoritative file store was found. Restore upload staging is transient. |
| MFA | `user_mfa.secret_ciphertext` and `pending_ciphertext` use the independent application key, with their nonce/version fields. Both are authenticated and rewrapped. Recovery verifiers are one-way hashes, not encrypted fields. |
| Other application crypto | Repository search found no other fields using the application data key. Plugin configuration references deployment-owned credentials; vendor secrets are not silently promoted to accepted knowledge. |
| Redis / Compose `redis_data` | No current application cache/job/session authority or executed queue was found. Not backed up; the target's dedicated logical Redis DB is flushed after restore/rollback. |
| Worker | Idle readiness/sleep loop, no mutation or job execution framework. It checks the maintenance marker; no queue was invented. |
| Native files / web assets | `/etc/atlas/atlas.env` is target-local deployment configuration; `/opt/atlas` binaries, bundled static assets and Next caches are rebuildable. Not portable backup components. |
| Backup/restore state directory / Compose `atlas_state` | Protected staging, job metadata and maintenance/recovery coordination only. Not canonical operational knowledge and not imported from the source. |

The archive deliberately excludes database passwords/URLs, Redis URLs,
`AUTH_SECRET_KEY`, bind address/port, hostnames/CORS, `.env` contents, TLS/proxy
configuration, setup-code plaintext, Docker host state and systemd paths.
Normal System Settings are portable database application state.

## Archive v1

`.atlasbackup` starts with a fixed 64-byte, big-endian envelope:
`>8sBBBBIII16s12sQ`. Its only fields are magic `ATLASBKP`, format version 1,
KDF/cipher IDs, a zero reserved byte, memory/time/parallelism, a random 16-byte
salt, random 12-byte nonce and ciphertext length. AES-GCM authenticates every
envelope byte as associated data. A 16-byte tag terminates the file.

The KDF is the established **Argon2id** implementation in `argon2-cffi`, already
installed by `pwdlib[argon2]`: Argon2 version 19, **65,536 KiB (64 MiB), three
iterations, one lane**, 256-bit output. V1 accepts exactly that bounded suite,
so a hostile header cannot select unbounded work. Passphrases have 12–1024
characters, confirmation on creation, and no arbitrary character-class rules.
Passphrases are neither stored nor recoverable by Atlas.

Encryption uses `cryptography` **AES-256-GCM**, with fresh per-backup 96-bit nonce
and 128-bit tag. File processing uses 1 MiB chunks. No whole database/archive is
loaded into application RAM. KDF memory is additional to bounded chunk buffers.
The implementation follows the library's [streaming cipher contracts](https://cryptography.io/en/latest/hazmat/primitives/symmetric-encryption/).

The uncompressed encrypted frame contains a four-byte manifest length, at most
16 KiB of JSON, exactly 32 bytes of source data-key material and the PostgreSQL
dump. There is no tar/zip extraction, filename dispatch, links or devices.
The only manifest component names are `database.dump` and
`crypto/data-encryption-material`; extra/duplicate JSON keys, unknown members,
paths, malformed lengths and mismatching SHA-256 checksums are rejected.

The manifest records format/payload/key versions, backup UUID, UTC time, Atlas
version/channel/build, source install method, Alembic revision, PostgreSQL major
and the exact component sizes/checksums. It is entirely encrypted. Neither source
key nor application/customer metadata appears in the outer envelope.

Decrypt first writes a private frame and verifies the final tag before parsing
or exposing any usable restore component. Checksums, supported source revision,
PostgreSQL framing/TOC and the dump's actual Alembic revision are checked before
maintenance or live database writes. Wrong passphrases/corrupt/unsupported
archives make no live database changes during archive preflight, including
preflight failure audit rows. Initialized-install authorization occurs earlier
and retains password/factor attempt and replay bookkeeping; that is distinct
from replacing application state from an archive.

## Native database behavior and compatibility

`pg_dump --format=custom --compress=0 --no-owner --no-privileges` uses an exported
repeatable-read snapshot; manifest revision and dump share that snapshot. An
Atlas role owning its database suffices; a schema-only owner also needs CREATE
privilege on the configured database to recreate that schema. Both are checked
before replacement. No roles or grants are backed
up, no Docker socket is mounted and no backup-specific superuser grant is introduced.

Backup/restore supports PostgreSQL 16/17 with client tools matching the target server major;
the reference Docker runtime carries client 17. PostgreSQL 17 was actually
tested. The source major must not exceed the target. Custom archive versions
1.15/1.16 with compression NONE are allowed; compressed/unknown dumps are
rejected before `pg_restore`. Source schemas must be known ancestors from
`20261004_0025` through the current single head; older foundation and unknown/newer
schemas are rejected. Post-restore migrations use Alembic ancestry, not version
string guesses, and do not downgrade the running application.

Restore drops/recreates the owned `public` application schema under maintenance,
then runs native `pg_restore --single-transaction --exit-on-error --clean
--if-exists --no-owner --no-privileges`. Resetting the schema also removes target
tables absent from older backups. The entire restore/migrate/rewrap workflow is
**not claimed to be atomic**; its protected rollback snapshot covers failures
after the PostgreSQL transaction has committed.

As with native PostgreSQL recovery, restore archives must come from a trusted
Atlas installation. Passphrase authentication proves archive integrity, not
source operator identity. Dumps carry SQL defined by their source database;
PostgreSQL's [restore documentation](https://www.postgresql.org/docs/17/app-pgrestore.html)
describes that trust boundary. Atlas does not provide a sandbox for foreign SQL or
a cryptographic source-signing infrastructure. Use the normal unprivileged,
database-owning Atlas role on native installations.

Child processes use argument arrays, no shell or credential-bearing URI/CLI
arguments. Target credentials go through a narrowly constructed libpq
environment; inherited PG service/options are excluded. Output errors are
discarded and replaced by fixed categories; logs report exception class only.
Commands have a 30-minute bound and generated files have a 2 GiB bound.

## Authorization, jobs and download lifecycle

Backend permission/global scope checks plus the existing protected global Master
Administrator role are required for export/import. A custom global settings
administrator or customer/site administrator cannot export an environment.
Creation requires current-password reauthentication. Existing restore requires
current password, a current TOTP/recovery factor when enabled, and `RESTORE`
acknowledgement. MFA row locks, attempt limits, factor consumption and replay
protection are reused. Origin defenses and generic credential-validation errors
apply. Setup restore requires the valid one-time setup cookie/generation.

The current worker has no safe job framework. One bounded API-process executor
per installation runs generation/preflight/restore; no passphrase is serialized
into PostgreSQL, Redis, environment files or a queue. States include requested,
uploading, preparing, ready, restoring, complete, failed and expired. Locks
serialize UI and local jobs. Pending upload authorization expires after ten
minutes; encrypted downloads after fifteen minutes, with one download claim.
Status metadata expires after 24 hours. A 30-second janitor and startup cleanup
remove expired/stale material. Interrupted jobs must be requested again.

Downloads recheck the current authorized creator/session generation, use
unguessable UUID IDs, no-store/nosniff and safe UTC Content-Disposition, and
stream without browser/server whole-file buffering. UI download links disable
Next prefetch. Files are never served as static content. Restore progress has a
separate random HttpOnly/SameSite cookie scoped to `/api/restore-status`, with
only its verifier persisted. It reveals only the authorized job's fixed progress
messages and survives normal session invalidation. It grants no application access.

## Quiescence, failure and key portability

`ATLAS_STATE_DIR` is target-local: Docker `/var/lib/atlas` (persistent protected
volume), systemd `StateDirectory=atlas`, development a protected API-local
`.atlas-state`. Directory mode is 0700, files 0600, ownership matches the service
account. Symlinks/hardlinked/non-regular files are refused; names are controlled,
unpredictable and outside web roots. Stale plaintext is removed on safe restart.

Kernel file locks guard API requests, startup migrations, local mutation scripts
and the Asset-icon background mutation,
and serialize restore/local operations. The durable maintenance marker is
written before a bounded 60-second drain wait. Normal reads/writes, login and
setup mutations then return no-store 503 with a maintenance message; health and
scoped restore progress remain available. The idle worker performs no writes.
Future worker handlers must hold this same normal-operation guard. Backup/restore supports
one API process/runtime per installation; replicas with independent state paths
are unsupported. Maintenance files are not stored in the replaced database.

After drain, authorization is rechecked. A native rollback dump is immediately
encrypted into `rollback.atlasbackup` using the target data key as local KDF
material; plaintext rollback dump is removed before replacement. This is a
temporary, local-only recovery artifact, never an HTTP download or passphrase-
free portable backup. All ordinary plaintext work is removed on success/failure.

Migrations and existing non-destructive system-definition reconciliation are
reused. An explicit adapter registry rewraps active and pending MFA fields
inside one transaction, authenticating each seed with source key/account-bound
AAD and re-encrypting with fresh nonce/target key. A bad field aborts every
adapter. No ad-hoc ciphertext SQL replacement occurs. Pending enrollment is then
retired as transient authorization; active seed semantics, replay counters and
unused/consumed recovery verifier history remain intact. The accepted TOTP step
is advanced at least through the current restore step, so restoring an older
counter does not reaccept the current sensitive-action code. Use a new code
after restore. The source key is no
longer needed after success.

Every restore regenerates internal `auth.restore_epoch`, increments session
versions, deletes login challenges, clears the setup verifier and advances setup
generation. Login cookies include the restore epoch; old cookies are rejected
even if source/target signing keys and session versions collide. This internal
setting is redacted/read-only through Settings. `AUTH_SECRET_KEY` and target data
key/environment files are never imported or rewritten. A restored installation
must have a usable global Master and consistent active MFA, and stays initialized.

Redis is flushed before normal operation resumes. On failure after replacement,
the original database is restored from the protected rollback archive, validated
and audited. Safe rollback clears maintenance. Failed rollback or a crash in
replacement remains fail-closed, retains only encrypted recovery and requires
the local recovery command. An abandoned pre-destructive drain is safe to clear.
TTL never silently reopens an uncertain restored database. Startup serves limited
maintenance health/progress and skips migrations/seeds until recovery.

Audit uses existing conventions: `backup.created`, `backup.failed`,
`restore.started`, `restore.completed`, `restore.failed`,
`restore.rollback_completed`, `restore.rollback_failed`. Completion is in the
restored DB, with safe actor snapshot, backup UUID and source/target revision.
Setup uses `setup/local-system`; CLI uses `local-operator`. No credential/key,
seed, dump content or passphrase is audit metadata. If the DB itself is damaged,
sanitized logs report audit unavailability; they do not imply a durable event exists.

See [operator procedures and local recovery](../deployment/backup-restore.md).
