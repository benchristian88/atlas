# B1.3 implementation and acceptance record

Date: 21 October 2026. Scope: Atlas only, local uncommitted changes.

## A. Executive assessment

Delivered secure public catalogue retrieval, unchanged B1.1/B1.2 integration,
instance-global PostgreSQL trust foundations, anti-rollback/history enforcement,
leases, sanitized diagnostics and global status/manual-refresh APIs. Existing
bundled packages and installation/runtime paths are unchanged.

**Full B1.3 acceptance is blocked by publication policy.** Genuine live sequence-1
verification succeeded. Promotion correctly returned `publication_not_immutable`.
The current alias and historical snapshots share a mutable release; there is no
approved separately advancing current channel or independently enforceable
publication-approval evidence. No trusted live revision was accepted. A separate
[publication implementation plan](b1-3-publication-plan.md) records the required
work without changing `atlas-connectors`.

## B. Repository state

Branch: `feature/integrations-official-catalogue-b1-3`.
Original and final HEAD: `3bc8557d64cb8478bc829ef838c0301509db2013`.
Initial working tree was clean. Final tree contains only the changes below, left
uncommitted. No branch, commit, fetch, push, merge, PR, tag, release or settings
operation was performed. Neither adjacent repository was modified.

## C. Architecture and changed files

| File | Change |
| --- | --- |
| [catalogue_source.py](../../../apps/api/app/services/catalogue_source.py) | Fixed source policy, bounded HTTPS reader, genuine verification, channel/snapshot consistency and closed publication gate |
| [trusted_catalogue.py](../../../apps/api/app/services/trusted_catalogue.py) | Lease/coalescing, atomic promotion primitive, high-water/history checks, audit and safe diagnostics |
| [models.py](../../../apps/api/app/models.py) | Two instance-global catalogue tables |
| [20261021_0031_official_catalogue.py](../../../apps/api/migrations/versions/20261021_0031_official_catalogue.py) | Additive tables, bounds, FK and immutable/monotonic triggers |
| [integrations.py](../../../apps/api/app/routes/integrations.py) | Authorized static status/refresh routes before connector-ID routing |
| [connector_catalogue.py](../../../apps/api/app/services/connector_catalogue.py) | Read-only accepted metadata projection; remote metadata never becomes an installable selection |
| [accept_official_catalogue.py](../../../apps/api/scripts/accept_official_catalogue.py) | Explicit live test, empty disposable DB requirement, durable diagnostic/failure checks |
| [test_catalogue_source.py](../../../apps/api/tests/test_catalogue_source.py) | HTTP bounds, redirects, DNS, rate limits, identity races and genuine verifier pipeline |
| [test_trusted_catalogue.py](../../../apps/api/tests/test_trusted_catalogue.py) | Generic lifecycle, database transitions/leases/rollback/isolation, API permissions and migration tests |
| [test_catalogue_backup_postgres.py](../../../apps/api/tests/test_catalogue_backup_postgres.py) | Exact bytes, historical index and checkpoint survive encrypted backup/restore |
| [test_release_distribution.py](../../../apps/api/tests/test_release_distribution.py) | New schema-head expectation and inclusion in both release formats |
| [test_i3_migration_postgres.py](../../../apps/api/tests/test_i3_migration_postgres.py) | Existing legacy upgrade expects the new head |
| [test_backup_postgres.py](../../../apps/api/tests/test_backup_postgres.py) | Existing old-schema restore expects the new head |
| [release-critical.sh](../../../infra/ci/release-critical.sh) | Include deterministic secure-reader regression |
| [official-catalogue.md](../../deployment/official-catalogue.md) | Complete API, transport, trust, database, error and operator contract |
| [b1-3-publication-plan.md](b1-3-publication-plan.md) | Separate required publisher-side plan |
| [official-catalogue-v1.md](official-catalogue-v1.md) | Link consumer while preserving the B1.1 structural boundary |
| [v1.3 architecture](Atlas_Integration_Architecture_and_Design_Specification_v1.3.md) | Truthful B1.3 evidence and limitations |
| [integration-roadmap.md](integration-roadmap.md) | Delivered foundations and outstanding publication/B2/B3 work |
| [attestation-verification.md](../../deployment/attestation-verification.md) | Integrate B1.3 without overstating build provenance |
| [backup-restore.md](../../deployment/backup-restore.md) | Trust-table retention, restore locking and whole-database rollback caveat |
| [upgrades.md](../../deployment/upgrades.md) | Additive migration and packaging implications |
| [feature-ledger.md](../../product/feature-ledger.md) | B1.3 marked Partially implemented |
| [continuous-integration.md](../../testing/continuous-integration.md) | Deterministic suites and opt-in live procedure |
| This record | Completion, evidence and remaining gates |

Reused the existing SDK parser, real verifier and pinned distribution, aiohttp
session conventions, SQLAlchemy sessions/advisory locks, audit helper, global RBAC,
normal-operation restore protection and release packaging directories. No second
connector/package system, new broker or scheduler was introduced.

## D. Retrieval and publication policy

The source is the existing `catalogue-v1` release, ID 416561696, in numeric
repository 1414494920 / owner 93822871. The reader uses repository, release-by-tag,
asset-by-ID and digest-attestation APIs. It never uses repository-wide latest.
Only fixed HTTPS API/distribution origins, public unicast DNS and verified TLS
are admitted. Redirects, compression, credentials, memory, retries and time are
bounded as documented in the [operator contract](../../deployment/official-catalogue.md).

Original catalogue bytes are bounded to 4 MiB; metadata to 256 KiB; total
attestation response to 1 MiB. One binary 302 is permitted to the exact GitHub
asset distribution host. TLS/protocol failures are not retried. Public access is
coalesced by a 150-second lease and a durable 15-minute cooldown, extended for
rate limits. The retrieval budget is 90 seconds with the verifier budget reserved.

The checked-in publisher workflow prepares and attests only. Even marking the
same alias release immutable would prevent channel advancement, so that change
alone cannot enable trust. `current_channel_policy_unavailable` remains the
second closed gate. No new URL or approval claim was invented.

## E. Genuine verification

The production path calls the actual `GithubSigstoreVerifier.verify_catalogue`
with original bytes and embedded genuine evidence. The unchanged B1.2 suite
exercises signature/log/root failures and wrong identity/ref/subject/profile
checks; consumer pipeline tests use real crypto rather than successful mocks.

Live authenticated identity:

- Digest: `55533ca67e7e9a14f82961e0a8c34ad78e2596049b3db02fde787494e3975afd`.
- Catalogue workflow: `.github/workflows/catalogue.yml@refs/heads/main`.
- Source commit: `91dfd86f18d0b59ff977bb1e8a5fef42c5329943`.
- GitHub CLI: 2.102.1; Public Good root ID `sigstore-public-good-2026-10-21`.
- Root digest: `3c2cc7f357dc064ec527fdcd78da6e9245c21a381e1abaa0f2b62b186bcac1a1`.
- Subject: `catalogue.json`; repository/owner IDs: 1414494920 / 93822871.

This authenticates build provenance, not release approval or immutable history.

## F. Persistence and migrations

`20261021_0031` follows `20261018_0030`; exactly one head remains. Fresh migration,
upgrade from legacy populated integration history, empty downgrade/upgrade and
refusal to downgrade accepted trust history were exercised on PostgreSQL 17.

Revisions preserve original bytes and bounded evidence; PostgreSQL blocks
UPDATE/DELETE. The singleton's sequence/digest FK and trigger prevent checkpoint
replacement/decrease. Refresh commits its lease before remote work, then checks
ownership/expiry and current committed state before atomic revision/state/audit
persistence. Failed persistence preserves prior trusted data. Missing/older state
can recover from retained revisions without renewing currentness; streamed
recovery has count and time bounds. No production DB or deployment was accessed.

Encrypted backup/restore preserves the trust data. The existing filesystem
normal-operation lock prevents a refresh spanning database replacement. Absolute
rollback resistance against restoring the entire trust DB is unavailable without
an external checkpoint; none is introduced here.

## G. Anti-rollback and lifecycle

First acceptance enforces the independent sequence floor and exact sequence-1
digest. Equal sequence/equal bytes deduplicates. Higher sequence requires full
trust plus immutable historical identities. Lower sequence and same-sequence
substitution reject and record conflicts. Malformed/unauthenticated higher
candidates cannot advance trust. Complete Manifest, package digest, tag and asset
identity remain protected for every observed ID/version. Withdrawals survive
omission and cannot silently reactivate. Absence neither withdraws nor removes
packages. An incompatible new version can remain valid catalogue metadata.

## H. API and authorization

- `GET /api/integration-catalogue/status`: global `integration_runtime.view`.
- `POST /api/integration-catalogue/refresh`: global `integration_runtime.manage`;
  no selection parameters, only absent body or `{}`.

Responses expose safe status/stage timestamps and read-only accepted metadata,
not attestation bundles, lease UUIDs or transport URLs. Results are accepted,
unchanged, in-progress, cooldown or failed; authorization/input/maintenance retain
existing HTTP conventions. Scoped managers and unauthenticated callers are denied.
Existing bootstrap list/detail/install response contracts and UI remain intact.

## I. Dynamic catalogue readiness

A valid `future-example/1.0.0` entry is constructed through the existing Manifest
contract and passes generic parsing, history storage and read-only projection.
New versions, incompatibility and retained withdrawals are tested independently.
No production connector ID, vendor or version allowlist was added. These storage
tests explicitly label evidence as unauthenticated; they make no invented
cryptographic-success claim. A genuine future publication remains a B4 live gate.

## J. Automated tests

Host tests used the existing Python 3.14.7 virtual environment and isolated local
PostgreSQL 17. Docker execution used Python 3.12 on Linux arm64. Ordinary suites
used frozen HTTP/attestation fixtures and no live GitHub. Counts below are per
command and overlap; they are not summed as unique tests.

Executed from `apps/api` with `.venv/bin/python`:

```bash
python -m pytest tests/test_official_catalogue.py tests/test_official_provenance.py -q
```

**221 passed**, no failures/skips.

```bash
python -m pytest tests/test_catalogue_source.py tests/test_trusted_catalogue.py \
  tests/test_official_catalogue.py tests/test_official_provenance.py \
  tests/test_attestation_distribution.py tests/test_integration_catalogue_api.py \
  tests/test_connector_lifecycle_api.py tests/test_connector_lifecycle_postgres.py \
  tests/test_connector_packages.py tests/test_connector_bootstrap.py \
  tests/test_integration_runtime.py tests/test_runtime_packaging.py \
  tests/test_i2_runtime.py tests/test_i3_runtime.py -q --tb=short
```

**526 passed**, no failures/skips, before subsequent additional test cases.

```bash
python -m pytest tests/test_catalogue_source.py tests/test_trusted_catalogue.py \
  tests/test_catalogue_backup_postgres.py \
  tests/test_backup_postgres.py::test_h1_schema_restores_and_migrates_forward_without_stale_new_tables \
  tests/test_i3_migration_postgres.py tests/test_release_distribution.py \
  tests/test_native_install.py tests/test_ci_workflow.py tests/test_backups.py -q --tb=short
```

**193 passed**, no failures/skips. Uses explicit disposable
`ATLAS_TEST_DATABASE_URL`, `ATLAS_TEST_H3_SOURCE_URL`, `ATLAS_TEST_H3_TARGET_URL`
and `ATLAS_TEST_I3_MIGRATION_URL`. Backup databases have a separate non-superuser
owner. PostgreSQL tools 17 were selected through PATH. Redis-backed restore tests
outside this selected group were not run.

```bash
python -m pytest tests/test_catalogue_source.py tests/test_trusted_catalogue.py -q --tb=short
```

**82 passed**, no failures/skips after adding genuine rollback, higher-sequence
old-attestation rejection and durable rate-limit checks.

```bash
python -m pytest tests/test_catalogue_source.py -q --tb=short
```

**55 passed**, no failures/skips after final TLS/non-transient retry rejection
coverage. The source suite now has 55 tests, the trust suite 29, plus one backup test.

Other executed gates:

- `python -m alembic upgrade head`: fresh UTF-8 disposable DB passed all migrations.
- `python -m alembic heads`: `20261021_0031 (head)` only.
- `python -m compileall -q ...`: changed API/services/migration/scripts/tests and
  existing application tree compiled successfully.
- `bash -n infra/ci/release-critical.sh`: passed.
- `git diff --check`: clean.
- Working-tree release dry-run/reproducibility, inclusion and packaged Markdown
  link checks passed in `test_release_distribution.py` for Docker and native.
- `docker build --platform linux/arm64 -f apps/api/Dockerfile -t atlas-b13-api:arm64 .`:
  built successfully; no publication or deployed container changes.
- Offline `docker run --rm --network none` as UID 10001: genuine fixture verification,
  publication rejection, route registration and single-head checks passed.
- Disposable native-path copy at `/opt/atlas/apps/api`, verified as unprivileged
  `atlas`: same offline smoke passed. This is not a full systemd installation test.

An initial release test failed because it pinned the previous schema head; its
expected head and related legacy restore assertions were updated and passed.
The initial empty cluster database inherited SQL_ASCII; validation used fresh
UTF-8 databases instead. Sandbox-denied network/database attempts were rerun with
approved access to only the task's disposable resources. Incorrect initial test
selectors were corrected; the successful commands above are the acceptance runs.
Existing library deprecation warnings remain. No standalone Python linter is
configured for the API; compilation, test and shell syntax checks were used.
Full repository CI, frontend build, amd64 image execution and full native
systemd installation/reboot were not run for this backend-only change.

## K. Live acceptance

```bash
python -m scripts.accept_official_catalogue --allow-live-github --disposable-database
```

Executed with a separate empty `atlas_b13_live` database and private temporary
state directory. Public GitHub bytes and genuine attestations were retrieved;
actual verification completed at **2026-10-21 07:48:57 UTC**. Release/asset rereads
and matching snapshot bytes succeeded. Release 416561696 reported immutable false;
current asset 653915685 and snapshot asset 653915743 matched the frozen digest.

Result: crypto verified, **promotion failed**, zero durable accepted revisions,
null confirmed-current timestamp and durable sanitized failure/stage timestamps.
Reopening the session and simulated GitHub failure preserved this state. No
package was downloaded or activated. Live last-known-good recovery cannot yet
be demonstrated because there is no acceptable first live revision; deterministic
storage tests cover it. The script explicitly printed `milestone_accepted: false`.

## L. Security review

The current producer cannot establish the required advancing authoritative
channel and immutable snapshot policy. That remains a hard gate, with no override.
The verifier's frozen roots retain their documented revocation-awareness limits.
Database/host administrators remain inside the trust boundary; whole-DB rollback
cannot be detected absolutely. History/candidate/rate limits deliberately fail
closed and may require reviewed capacity/policy updates at larger scales.

Independent current-channel approval, publication races/immutability, immutable
package releases and a new live acceptance run remain required before promotion.
No release settings or publisher workflows were changed here.

## M. PR readiness

Ready for operator-managed review as **B1.3 foundations with explicit publication
blocker**, not as fully accepted B1.3. Changes are uncommitted and include one
additive migration. Relevant suites, packaging, backup/restore and real-verifier
checks passed. No Git operations are required or performed by this task.

## N. B2 handoff

Available: reusable bounded reader, actual verifier integration, original-byte
storage, sequence/history index, retained withdrawal information, durable leases,
audit, safe status and distinct timestamps. Still needed: daily scheduler,
authoritative confirmation age <72 hours for remote eligibility, conflicts-aware
lifecycle/version/compatibility projection and catalogue UI integration. Never
renew currentness from generated time, cached verification or historical-only reads.

## O. B3 prerequisites

Establish approved immutable catalogue and package publication first. Then add
explicit administrator-approved package retrieval, genuine package-profile
verification bound to accepted metadata, freshness/withdrawal/compatibility gates,
protected-store archive validation and existing activation safeguards. Catalogue
provenance alone must never authorize execution. B4 must prove future connectors
appear without rebuilding Atlas after that publisher/consumer contract exists.
