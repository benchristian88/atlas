# H3 encrypted backup and restore — implementation and validation

Recorded 2026-10-04 on `feature/h3-encrypted-backup-restore`, based on accepted,
merged H2 HEAD `295c8a0f3330d7d5f61f114b09d3ad518aaadbd2` (also `dev`). The initial
working tree was clean. No commit, push, merge, rebase or history rewrite was
performed. This report describes uncommitted working-tree implementation.

**H1/H1.1 — ACCEPTED. H2 — ACCEPTED. H3 — implemented and locally validated;
real Docker acceptance pending.** H3 is not recorded as accepted solely from
automated/local evidence. Native/systemd real lifecycle remains the H6 gate.

## Result and compatibility

System Settings now provides passphrase-encrypted `.atlasbackup` downloads and
deliberately authorized overwrite restore. Fresh installations restore through
the existing one-time-code `/setup` flow. Both paths preserve target deployment
configuration, rewrap restored MFA to the target application key, invalidate old
sessions, migrate/reconcile safely, and release maintenance only after validation.
The local CLI shares the same service and supports crash recovery.

No new schema migration was required. The existing single Alembic head remains
`20261004_0026`; `auth.restore_epoch` is an internal, redacted, read-only record in
the existing System Settings table. Existing routes/contracts remain available.
Backup/restore/status routes and the session epoch claim are additive. Before a
restore, legacy cookies without an epoch retain their existing behavior. H3
changes no graph, topology, relationship direction, accepted knowledge,
discovery/reconciliation or customer/site entity authorization semantics.

Export/import requires the existing protected **global Master Administrator**
boundary, independent of a custom role's global settings permission. Full-state
restore deliberately restores all tenant records under that installation-wide
boundary; it does not introduce a tenant export or weaker entity traversal model.

## Evidence actually executed

| Check | Actual evidence |
| --- | --- |
| API/SDK/plugin/PostgreSQL/migrations | **681 passed, zero skipped**, final full regression; all optional PostgreSQL migration/domain/H1/H2/H3 suites enabled on disposable databases, with real Redis and nginx. |
| H3 crypto/parser/runtime tests | 38 parameterized cases in `test_backups.py`; authenticated round trips/randomness, confidentiality, wrong passphrase, ciphertext/header/tag tampering, truncation, excessive/unsupported KDF parameters before derivation, manifest paths/links/extra members/duplicate JSON/checksums, ancestry, permissions/symlink rejection, locking/drain, atomic metadata replacement/read concurrency, interruption cleanup and audit redaction. |
| H3 PostgreSQL tests | 16 parameterized cases in `test_backup_postgres.py`, including a real CLI subprocess and actual maintenance API behavior. Source/target owned by a non-superuser, non-createdb Atlas role. |
| Frontend tests | **276 passed, zero skipped**, `npm test`. |
| Production frontend build | **Passed**, `npm run build`, including the MFA-status correction. |
| Browser acceptance | **Passed**, actual production Next/API/PostgreSQL/Redis/nginx and installed Chrome; no mocked API responses. Details below. |
| Alembic | **Passed**, `python -m alembic heads`: only `20261004_0026 (head)`. No migration files changed. |
| Python compilation | **Passed**, `python -m compileall -q apps/api/app apps/api/scripts apps/api/tests apps/worker/worker infra/install plugins`. |
| Schema permission drill | **Passed**, a separate actual database with Atlas schema ownership but no database CREATE privilege was rejected in preflight; schema remained untouched. Test database removed afterward. |
| Dependency audit | `npm audit --json` ran; **five findings remain**, detailed below. This is not a clean audit. |
| Docker Compose CLI/build | **Not run:** no Docker CLI/daemon in this macOS execution environment. Existing Compose structure/prerequisite/ingress tests ran; this is not actual Compose config/build validation. |
| Native/systemd lifecycle | **Not run:** no Linux systemd runtime. Native adapter/static tests ran; no install/start/restart/reboot claim. |
| Documentation links / diff | Final results recorded below. |

The regression environment used Python 3.14, PostgreSQL/client 17.11 and a
separate Redis 7.4.6 process. PostgreSQL 17 ran on loopback port 55441; H3 source
and target used the `atlas_h3_owner` role without superuser/createdb privileges.
Redis ran on loopback port 56379. General domain, setup, MFA and every migration
suite had separate disposable databases. No user's installation/database was
modified. The Docker reference remains Python 3.12 and PostgreSQL 17; running the
Python 3.14 suite is not evidence of an actual Docker image build.

Regression invocation, from `apps/api` with all documented `ATLAS_TEST_*`
database variables supplied:

```bash
python -m pytest tests ../../plugins/sdk/tests ../../plugins/proxmox/tests \
  -q -rs --tb=short --junitxml=/private/tmp/atlas-h3-regression-results.xml
```

The temporary orchestration harness created/migrated the isolated databases,
supplied the actual nginx binary and real Redis URL, then executed that command.
Earlier test runs exposed a scoped-assignment fixture autoflush error; that
fixture was corrected. A repeated run exposed a concurrent metadata reader
checking the old inode after atomic replacement; read-only unlinked private
snapshots are now accepted while hard links remain rejected. A deterministic
concurrency regression verifies both old/new snapshots and hard-link denial.
Test fixture teardown waits for executor cleanup before changing process-global
environment. Browser runs exposed accessible field-label issues and
the missing current-user MFA flag assumption; labels were corrected and the
form now queries the existing `/auth/mfa/status` endpoint. The final results do
not count those failed runs as passes. Existing Pydantic/SQLAlchemy warning
output remains visible; a passing suite does not imply warning-free output.

## Browser acceptance actually performed

`apps/web/scripts/check-backup-browser.mjs` exercised two isolated installations
using independently generated protected deployment configurations and different
signing/data keys. The source ran the real production startup module; the target
was migrated/seeded and served by the real API. Both used a production Next build
behind the checked-in nginx ingress, adapted only for local paths/upstream ports.
The full lifecycle of Docker/systemd was not involved.

1. Entered the source one-time setup code and created the first global Master
   through the UI; logged in and created a representative manual Asset.
2. Enrolled MFA through Profile using the real H2 endpoints.
3. Opened System Settings, entered/confirmed the passphrase, reauthenticated,
   waited for readiness and downloaded the encrypted file through the UI.
   Verified safe date filename and `ATLASBKP` envelope magic.
4. Changed the Asset after the backup and changed session lifetime through UI.
5. Attempted overwrite restore with a wrong passphrase and current MFA.
   Saw the fixed error and proved the later Asset change remained.
6. Repeated with the correct archive/passphrase, explicit `RESTORE`, current
   password and a new MFA code. Followed progress to login; signed in with the
   restored password/authenticator. Verified backed-up Asset name and setting
   returned, replacing the later changes.
7. Entered the fresh target setup code, chose Restore, imported the same archive,
   followed progress to login and signed in with restored password/MFA. Verified
   the Asset, initialized status and rejection of the former setup code.
8. Compared both protected environment files to their generated values: signing
   key, data key, database password, bind and port were unchanged. No source
   environment was copied into the target.

No browser page errors occurred. Layout checks passed without horizontal page
overflow at **1440, 1024, 800 and 390 px**. Screenshots were taken before secret
forms opened; no passphrase, setup code, seed, QR, OTP or recovery plaintext was
captured. Secrets arrived through stdin and stayed in memory. The downloaded
encrypted archive is protected mode 0600. TOTP was generated locally for the
test account; no physical authenticator application was claimed.

Local evidence: `/private/tmp/atlas-h3-browser-1b336475/artifacts/report.json`,
`backup-settings-{1440,1024,800,390}.png` and encrypted `acceptance.atlasbackup`.
These temporary files are not committed repository artifacts and do not publish
credentials or plaintext exports.

PostgreSQL tests additionally verified preserved IDs, password hashes/RBAC,
customers/sites, Assets/Interfaces/Networks/relationships, Services/Business
Functions, image bytes, settings and audit history; second target-key restore;
working restored TOTP and recovery verifier; same-signing-key/version session
collision rejection; H1-to-H2 schema migration; atomic active/pending rewrap
failure; rollback and failed-rollback crash recovery; damaged-database portable
local recovery; creator download isolation, scoped/custom-admin denial and setup
status isolation. This is representative data validation, not a claim that every
possible table populated by every plugin was individually compared.

## H2 acceptance documentation

The acceptance report, roadmap and feature ledger now record H2 as accepted.
The supplied real evidence is preserved precisely: a throwaway Debian
Docker/LXC upgrade using the key-addition helper, Compose config validation,
successful build/upgrade, then a snapshotted real homelab installation upgraded
with the same procedure, preserved data and a user-tested working application.
The helper preserved existing secrets. No more granular real MFA/reset actions
or native/systemd lifecycle are inferred. H2's historical 627 backend and 272
frontend passes and browser evidence remain documented as historical evidence.

## Security review and limits

The H3 diff was reviewed for passphrase/data-key/seed/credential exposure,
authenticated encryption/KDF bounds/randomness, parser/path/decompression
hazards, native command invocation/privileges, IDOR, Origin/setup/global-Master
authorization, MFA reauthentication, session collision/replay, quiescence,
partial restore/rewrap, Redis invalidation, target configuration preservation,
staging permissions/cleanup and credential-safe audit/errors. Scoped-actor tests,
missing-factor denial, Origin denial, epoch collision rejection and actual
maintenance endpoint tests substantiate the boundaries.

Corrections during review included checking both PostgreSQL client majors and
target schema-recreation permission before destructive work,
bounding schema reset lock/statement waits, ensuring operation locks release
despite cleanup errors, retiring the current TOTP step after backup rewind,
using the real MFA status contract in the form, guarding startup migrations and
remaining local mutation scripts, and preserving explicit API-base configuration
for download links. No source signing key is carried in the
archive, no shell or password/URI command argument is used, and subprocess output
never reaches browser/audit. Temporary names are generated; files/directories
are private service-owned regular files with symlink/hardlink checks.

Archive preflight failures perform no schema/data replacement or archive-driven
audit writes. The initialized UI's prior H2 reauthentication still consumes a
factor and maintains attempt/replay state; the unchanged-data browser assertion
checks application records rather than claiming that authentication bookkeeping
never changes.

The native dump is trusted-source SQL. Integrity authentication does not prove
the source operator's identity or sandbox SQL. The Atlas database-owning role is
the privilege boundary; no superuser grant was added for H3. Uncompressed native
dumps and bounded frames avoid archive extraction/decompression bombs. Full
authentication precedes usable components and live replacement. Rewrap is one
transaction; the overall schema replacement/migration/rewrap workflow is not
atomic, so a protected encrypted rollback snapshot is required.

Known limits: one API runtime and shared target-local state directory per
installation; 2 GiB archive/upload cap; PostgreSQL 16/17 policy with **17 actually
tested**; known H1-or-newer Alembic ancestors; no continuous backups/server archive
repository; no resumable process/queue jobs. SQL privilege confinement, SSD/media
secure erasure, peak RSS at maximum archive size and real power-loss recovery
were not independently proven. Cleanup removes files; physical media erasure is
not claimed. Interrupted destructive work stays closed rather than reopening
on TTL. The operator recovery path prevents a maintenance marker from becoming
an unsupported permanent outage.

The npm lockfile/dependency versions were unchanged. Actual `npm audit --json`
reported one critical (`next`), three high (`nanoid`, `postcss`, `sharp`) and one
moderate (`baseline-browser-mapping`), **five total**. These are retained later
hardening work; they were not fixed or declared harmless by H3. Redis 6.4.0 is
the sole added pinned API dependency; Argon2 and cryptography were existing
dependencies. This is a targeted H3 review, not whole-product certification.

## Completion checklist A–AW

| Item | Result |
| --- | --- |
| A. H2 acceptance | Supplied real Docker upgrade evidence recorded without inventing actions; H1/H1.1 and H2 accepted. |
| B. Material files | Complete inventory below. |
| C. Migrations | None; existing single head `20261004_0026`, internal epoch uses current table. |
| D. Authoritative inventory | PostgreSQL plus application data key; inspected filesystem/icons/documents, Redis, worker, setup/auth, volumes and deployment configuration. |
| E. Backup scope | Full native database, IDs/history/knowledge/settings/audit/auth/MFA, plus encrypted source data material. |
| F. Deployment exclusions | No source environment, database/Redis credentials, signing key, bind/network/CORS/proxy/TLS/host paths, binaries or images. |
| G. Format | `.atlasbackup`, `ATLASBKP`, envelope/frame/manifest v1; no general archive extraction. |
| H. Dump | Native custom uncompressed `pg_dump`, `--no-owner --no-privileges`, exported repeatable-read snapshot shared with manifest revision. |
| I. KDF | argon2-cffi Argon2id v19, 65,536 KiB, time 3, lane 1, 32-byte output; exact bounded suite checked before KDF. |
| J. Encryption | cryptography streaming AES-256-GCM. |
| K. Nonce/tag/header | Fresh salt16/nonce12, tag16; whole fixed64-byte envelope AAD. |
| L. Streaming/memory | 1 MiB file chunks, bounded16KiB manifest/1MiB native metadata; no whole archive/database buffering. KDF uses64MiB; maximum-size RSS not measured. |
| M. Temporary protection | Target-local0700 directories/0600 owner-checked files, controlled UUID names, no static URLs, cleanup/expiry; encrypted rollback retained only for uncertain recovery. |
| N. Manifest | Encrypted versions/UUID/UTC/build/install/schema/PG metadata and exact allowlisted component lengths/SHA256; duplicate JSON/unknown fields rejected. |
| O. Authorization | Backend global permission plus protected global Master; creator/session-scoped jobs/downloads; customer/site/custom global admins denied. |
| P. Reauthentication | Creation password; overwrite password+enabled TOTP/recovery+RESTORE; H2 locks/limits/replay reused; fresh valid setup authorization. |
| Q. Backup UI | Restrained System Settings Section with existing fields/buttons; validation, background progress, download. |
| R. Lifecycle | One serialized in-process executor; credentials memory-only; pending upload10min, single-use download15min, status24h, janitor30s/startup cleanup. |
| S. Fresh restore | One-time setup code/cookie, choose restore, no new admin, upload/passphrase, progress, login with restored account/MFA. Actual browser passed. |
| T. Existing restore | Explicit replacement acknowledgement/password/factor, upload/preflight, maintenance/rollback, login. Actual browser passed. |
| U. Setup integration | Existing H1 generation rechecked before replacement; restore clears verifier/increments generation/closes setup. |
| V. Quiesce | Durable marker outside DB, shared request/background locks, bounded exclusive drain; normal reads/writes/login/setup rejected; health/scoped status only. Idle worker checks pause, no new queue. |
| W. Native restore | Owned schema reset then `pg_restore --single-transaction --exit-on-error --clean --if-exists --no-owner --no-privileges`; target configured DB/role retained. |
| X. Rollback | Encrypted protected pre-restore snapshot; post-replacement failures recover original DB; failed rollback/crash remains closed with local recovery. Injected tests passed. |
| Y. Compatibility | Known H1/current-head ancestors, forward migration/reconciliation; newer/unknown formats/schema, compressed dumps and higher source PG major refused; PG16/17 matching clients. |
| Z. Source data key | Only encrypted portable component, briefly inside private authenticated staging frame; never deployment config/logs/audit. |
| AA. Rewrap | Explicit adapter registry, keyset batches/row locks, source-key authentication, fresh nonce/target key, caller-owned all-or-nothing transaction; active/pending MFA covered. |
| AB. Signing key | Source `AUTH_SECRET_KEY` excluded; target unchanged. |
| AC. Auth invalidation | New restore epoch plus session-version increment; challenges/pending enrollment/setup authorizations retired; current TOTP step advanced; passwords/active MFA/recovery/RBAC retained. |
| AD. Redis/cache | Source Redis excluded; target dedicated logical DB PING preflight and FLUSHDB before release/rollback. PostgreSQL icon cache preserved. |
| AE. Audit | Existing audit service, safe actor+UUID/revisions; backup created/failed, restore started/completed/failed/rollback completed/failed. Completion in restored DB. Preflight makes no DB/audit changes. |
| AF. Parser | Magic/version/exact KDF suite/sizes/tag before usable components; fixed member frame, JSON allowlist/checksums, uncompressed PG header/TOC/actual schema validation, no pickle/shell/extraction. |
| AG. Docker | API client17, unprivileged protected persistent state volume, worker read-only mount, ingress upload streaming; actual Docker execution not performed. |
| AH. Native | Existing service account/protected env, client prerequisites, API StateDirectory0700/shared worker marker, same hardening; lifecycle not performed. |
| AI. Local management | Shared `scripts.backup create/restore/recover [--input]` and native wrapper, getpass and RESTORE confirmation; actual local create/restore and domain recovery exercised. |
| AJ. Crypto tests | 38 crypto/parser/runtime parameterized cases, including deterministic concurrent replacement/read and hard-link denial. Final full result below. |
| AK. PostgreSQL tests | 16 H3 parameterized cases; full state, API boundaries, older migration, CLI, preflight/rollback/recovery and maintenance. Final totals below. |
| AL. Rewrap tests | Different target keys, second restore, active/pending fields, wrong key/corrupt field transaction rollback, working restored TOTP/recovery. |
| AM. Concurrency/maintenance | Real shared/exclusive lock drain, competing operation refusal, API reads/writes/login/setup503 with health/scoped progress; H2 PostgreSQL concurrency regression enabled. |
| AN. Frontend | 276 passed, zero skipped. |
| AO. Build | Production build passed. |
| AP. Browser | Actual Chrome/production stack source+fresh target passed; responsive widths1440/1024/800/390, zero page errors, no secret screenshots. |
| AQ. Real Docker | Not performed; repeatable disposable/homelab acceptance plan in operator guide. |
| AR. Native lifecycle | Not performed; later H6 gate. |
| AS. Diff review | Targeted H3 review and fixes above; no full-product certification. |
| AT. Dependency audit | Five unresolved existing npm findings; lockfile unchanged. |
| AU. Not tested | Actual Docker/systemd, physical app, PG16, maximum-size/resource profiling, real power interruption/media erasure; explicitly bounded supported implementation. |
| AV. Diff check | Final result below. |
| AW. Git state | Full final `git status --short` below; no commits/pushes. |

## Material file inventory

Every changed path is listed; related files share a row only when they serve the
same purpose. No new model/migration, graph semantics or vendor plugin code was
introduced.

| Files | Purpose |
| --- | --- |
| `.gitignore` | Ignore private development staging and operator archive files. |
| `apps/api/app/services/backup_archive.py` | Versioned authenticated streaming frame, KDF and hardened manifest/parser. |
| `apps/api/app/services/backup_postgres.py` | Native snapshot/validation/replacement, compatibility and bounded child tools. |
| `apps/api/app/services/backup_runtime.py` | Protected staging/atomic metadata, locks, maintenance, expiry/crash cleanup. |
| `apps/api/app/services/backups.py` | Shared jobs/restore/rollback, auth sanitization, migrations/reconciliation and Redis invalidation. |
| `apps/api/app/services/encrypted_data.py` | Explicit transactional application-key rewrap adapters. |
| `apps/api/app/routes/backups.py` | Master/settings and setup authorization, streaming upload/download, scoped progress. |
| `apps/api/scripts/backup.py` | Interactive shared-service local backup/restore/recovery. |
| `apps/api/app/auth.py`, `apps/api/app/routes/auth.py` | Restore epoch validation and new-session epoch issuance. |
| `apps/api/app/routes/system_settings.py`, `apps/api/app/audit.py` | Protect internal epoch and redact backup credentials/keys. |
| `apps/api/app/main.py` | Routes, credential-safe validation/no-store, maintenance request guard and cleanup lifespan. |
| `apps/api/app/services/asset_icons.py` | Guard the existing background database mutation during restore. |
| `apps/api/migrations/env.py` | Reuse caller-owned transactional connection; preserve application logging for programmatic migration. |
| `apps/api/scripts/start.py`, `apps/api/scripts/setup_code.py`, `apps/api/scripts/mfa.py`, `apps/api/scripts/create_user.py`, `apps/api/scripts/seed_system.py` | Startup recovery handling and local mutation quiescence, including migrations/system definitions. |
| `apps/api/requirements.txt`, `apps/api/Dockerfile` | Pinned Redis client, PostgreSQL client17 and unprivileged protected state. |
| `apps/api/tests/test_backups.py`, `apps/api/tests/test_backup_postgres.py` | Crypto/runtime and real disposable PostgreSQL/API/CLI/security regressions. |
| `apps/web/components/backup-restore.js`, `apps/web/components/backup-restore.module.css`, `apps/web/lib/backup.mjs` | Shared restrained credential-safe UI, validation, current MFA status and download/progress lifecycle. |
| `apps/web/app/admin/system-settings/page.js`, `apps/web/app/setup/page.js` | Reachable Master-only settings capability and authorized first-run choice. |
| `apps/web/tests/backup.test.mjs`, `apps/web/tests/setup.test.mjs` | Backup policy/form and setup choice regression. |
| `apps/web/scripts/check-backup-browser.mjs`, `apps/web/scripts/check-first-run-browser.mjs` | Actual H3 acceptance workflow and updated H1 restore-choice expectation. |
| `apps/worker/worker/main.py` | Explicit maintenance pause at current idle worker boundary. |
| `infra/docker/docker-compose.yml`, `infra/docker/gateway/default.conf` | Protected state volume and scoped streaming upload ingress. |
| `infra/install/manage.py`, `infra/install/native.py` | Shared local CLI dispatch/state path and native client prerequisites/setup path. |
| `infra/systemd/atlas-api.service`, `infra/systemd/atlas-worker.service` | Persistent protected StateDirectory and shared worker maintenance path. |
| `docs/architecture/encrypted-backup-restore.md`, `docs/deployment/h3-backup-restore.md` | State inventory/security/format/runtime and Docker/native/UI/local recovery/acceptance procedures. |
| `docs/architecture/authentication-and-access-control.md`, `docs/architecture/local-two-factor-authentication.md` | Current key portability, session invalidation and auth boundaries. |
| `docs/architecture/deployment-and-upgrades.md`, `docs/deployment/h1-installation.md`, `docs/deployment/h2-mfa.md` | Current restore/setup/deployment/key behavior without back-editing accepted decisions. |
| `docs/product/development-roadmap.md`, `docs/product/feature-ledger.md` | H2 accepted evidence and truthful H3 scope/status. |
| `docs/testing/h2-local-two-factor-authentication.md` | Supplied H2 real Docker acceptance facts, historical evidence and remaining gates. |
| `README.md`, `docs/README.md`, `docs/testing/h3-encrypted-backup-restore.md` | Discoverability and complete implementation/validation report. |

## Final validation and repository state

The final full regression completed with **681 passed, zero failed and zero
skipped** (111.14 seconds). H3 contributes **54 cases: 38 crypto/parser/runtime
and 16 PostgreSQL/API/CLI cases**. The 276 web tests and production build passed.
Final Chrome acceptance passed at the artifact path above, including actual
overwrite/fresh restore and restored MFA with distinct deployment secrets.

Compilation includes `apps/api/migrations` in addition to application/scripts,
tests, worker, installer and plugins. Alembic has only `20261004_0026 (head)`.
The changed-Markdown check passed **13 documents, 159 local link targets and
balanced code fences**; it does not claim external URL or anchor validation.
`git diff --check` is clean. No Docker/systemd execution is claimed.

Local test orchestration/logs are temporary evidence:
`/private/tmp/atlas-h3-run-regression.py`, `atlas-h3-final-regression.log`,
`atlas-h3-regression-results.xml`, `atlas-h3-browser-harness.py`,
`atlas-h3-final-browser.log`, `atlas-h3-web-final-tests.log`,
`atlas-h3-web-final-build.log`, `atlas-h3-npm-audit.json`,
`atlas-h3-check-docs.py` and `atlas-h3-check-schema-permission.py`.
They are not checked-in release artifacts.

Final repository state: **36 modified tracked files and 17 new untracked files**,
all scoped to H3/H2 acceptance documentation. The complete material inventory
above identifies all 53 paths. Branch/HEAD remain
`feature/h3-encrypted-backup-restore` /
`295c8a0f3330d7d5f61f114b09d3ad518aaadbd2`. No commit, push, merge or rebase.

Actual `git status --short`:

```text
 M .gitignore
 M README.md
 M apps/api/Dockerfile
 M apps/api/app/audit.py
 M apps/api/app/auth.py
 M apps/api/app/main.py
 M apps/api/app/routes/auth.py
 M apps/api/app/routes/system_settings.py
 M apps/api/app/services/asset_icons.py
 M apps/api/migrations/env.py
 M apps/api/requirements.txt
 M apps/api/scripts/create_user.py
 M apps/api/scripts/mfa.py
 M apps/api/scripts/seed_system.py
 M apps/api/scripts/setup_code.py
 M apps/api/scripts/start.py
 M apps/web/app/admin/system-settings/page.js
 M apps/web/app/setup/page.js
 M apps/web/scripts/check-first-run-browser.mjs
 M apps/web/tests/setup.test.mjs
 M apps/worker/worker/main.py
 M docs/README.md
 M docs/architecture/authentication-and-access-control.md
 M docs/architecture/deployment-and-upgrades.md
 M docs/architecture/local-two-factor-authentication.md
 M docs/deployment/h1-installation.md
 M docs/deployment/h2-mfa.md
 M docs/product/development-roadmap.md
 M docs/product/feature-ledger.md
 M docs/testing/h2-local-two-factor-authentication.md
 M infra/docker/docker-compose.yml
 M infra/docker/gateway/default.conf
 M infra/install/manage.py
 M infra/install/native.py
 M infra/systemd/atlas-api.service
 M infra/systemd/atlas-worker.service
?? apps/api/app/routes/backups.py
?? apps/api/app/services/backup_archive.py
?? apps/api/app/services/backup_postgres.py
?? apps/api/app/services/backup_runtime.py
?? apps/api/app/services/backups.py
?? apps/api/app/services/encrypted_data.py
?? apps/api/scripts/backup.py
?? apps/api/tests/test_backup_postgres.py
?? apps/api/tests/test_backups.py
?? apps/web/components/backup-restore.js
?? apps/web/components/backup-restore.module.css
?? apps/web/lib/backup.mjs
?? apps/web/scripts/check-backup-browser.mjs
?? apps/web/tests/backup.test.mjs
?? docs/architecture/encrypted-backup-restore.md
?? docs/deployment/h3-backup-restore.md
?? docs/testing/h3-encrypted-backup-restore.md
```
