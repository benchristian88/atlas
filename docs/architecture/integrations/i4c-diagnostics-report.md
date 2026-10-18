# I4C discovery diagnostics — local implementation and validation

**Local implementation and validation complete.** The original turn was interrupted
before completion; the remaining checks and documentation are now finished. Live
qualification/deployment remains the explicitly separate operator gate.

The interrupted implementation was resumed on 18 October 2026. Work is uncommitted
on Atlas `feature/integrations-i4c-proxmox-qualification` at
`88fd16b1b104dfd96910414bb08190b969375817` and Connectors
`feature/i4c-proxmox-qualification` at `3765d687fe7f72e55084c762814d21acc1c5edd5`.
SDK main remains unchanged at `8b0518c462289cca4758c3b9bf362f1130928a1c`.
No commit, push, merge, release, deployment or live source operation is performed.

Generic private sidecar diagnostics, permanent normal provenance, administrator-only
next-run debug, immutable intent, expiring debug storage/purge/deletion, backup
exclusion and run-detail/Integration controls are implemented. See the
[contract](discovery-diagnostics.md). Migration: **20261018_0030**. Routes and run
responses evolve additively; AIP/SDK and source privileges are unchanged.

The .3 diagnostic candidate is **UNQUALIFIED**, qualified_versions is empty.
Digest: `sha256:05c8ccb44b3964b780d3ffcef9a71a89b80ed2a5b7f4de22806ea7b0f62cf626`.
Independent verification checks all 19 packaged files. The operator-reported `.2`
COMPLETED/PARTIAL result (179 observations, 48 review items) remains failed live
qualification evidence; no live COMPLETE result or source qualification is claimed.

## Validation record

Initial implementation results: **1,215 API tests passed**, **68 existing nginx tests skipped**;
**623 release-critical tests passed**, **134 Connector tests passed**,
**308 frontend tests passed**, production Next build passed, and both production
Chrome matrices passed (**48 theme/accent/width combinations**). Contracts/docs,
Alembic single-head/fresh/upgrade checks, artifact identity and whitespace checks
passed. Detailed results and exact file inventory follow.

## One-shot concurrency correction

The final audit found that an Integration loaded before locking could retain a
stale `debug_next_run` value in SQLAlchemy's identity map. The API `scoped(...,
lock=True)` query and scheduled worker Integration query now use
`execution_options(populate_existing=True)` on their existing `SELECT FOR UPDATE`
reads. Debug intent, expiry and consumption use that refreshed row through the
existing creation transaction. Authorization, lock order and worker `skip_locked`
behaviour are preserved; retention and diagnostics contracts do not change.

`test_discovery_diagnostics_concurrency_postgres.py` uses two PostgreSQL connections
and overlapping transactions. The normal API/worker path retains the initially
unarmed ORM instance; the other connection arms and commits before the creator
locks. Both cases failed before the query correction and pass afterwards. Each
checks committed debug intent and the cleared flag, then creates an unarmed
following run. The release-critical selector includes these regressions. The
actual Runner termination test now covers cancellation and orchestration timeout,
directly querying the database flag after each terminal path to prove it remains
off. No terminal execution behaviour or database schema changes were required.

Follow-up validation logs are under `/private/tmp/atlas-i4c-debug-race`.
The two PostgreSQL concurrency regressions passed after reproducing both failures
before the fix; the focused diagnostics/orchestration/worker and actual Runner
checks passed **113 tests**, and the expanded release-critical suite passed
**626 tests**. The full API suite passed **1,218 tests**, with the same **68 nginx
skips** requiring nginx >=1.28 or `ATLAS_TEST_NGINX`. Alembic still has exactly one
head, `20261018_0030`, and `git diff --check` passes. Connector source fingerprints
match the pre-fix worktree. All checks use disposable services and synthetic source
fixtures; no live source operations or Git history operations are performed.

Commands for this follow-up (from `apps/api`, with the protected disposable test
environment loaded):

```bash
python -m pytest tests/test_discovery_diagnostics_concurrency_postgres.py -q --tb=short
python -m pytest tests/test_discovery_diagnostics.py tests/test_discovery_diagnostics_runtime.py tests/test_i4c_diagnostics_runtime.py tests/test_i3_runtime.py tests/test_i3_discovery.py tests/test_i3_live_runtime.py tests/test_i3_concurrency_postgres.py -q --tb=short
bash ../../infra/ci/release-critical.sh
python -m pytest -q --tb=short -rs
python -m alembic heads
git diff --check
```

## Security and remaining live work

Normal/debug schema rejects raw data and known credentials; runtime owns the
destination and checks inode/mode/link identity. Debug controls/view/delete require
global runtime management plus scoped view. Existing tenancy and observation/
reconciliation/absence rules remain in effect. Private execution files are removed
on terminal paths. Expired debug is unavailable, physically purged and excluded
from portable backups; normal provenance is retained.

After local operator review/checkpoint, reconstruct and independently verify .3
from clean committed source, deploy migration and matching runtime to the isolated
qualification instance, stage an exact fresh authorization, arm one run if desired,
and inspect its reasons. .1/.2 and Proxmox 9.2.11 stay unqualified; any validator fix
requires separate source evidence and review.

## Initial implementation checks

| Check | Result |
| --- | --- |
| Focused discovery/diagnostics/I3 checks | 98 passed |
| Model inventory after adding the new trace table | 14 passed |
| Complete API suite with all optional PostgreSQL/runtime suites enabled | 1,215 passed, 68 existing nginx skips |
| Release-critical selector, including new diagnostics and actual .3 Runner checks | 623 passed, no skips |
| Full Connector suite, including actual Runner and off/on equivalence | 134 passed |
| Focused frontend | 10 passed |
| Full frontend | 308 passed |
| Production Next build | Passed |
| New diagnostics production Chrome matrix | 24 theme/accent/width combinations passed |
| Retained I3 production Chrome matrix | 24 combinations passed |
| Contracts, repository docs and Markdown checks | 95 passed |
| Alembic heads | Single head 20261018_0030 |
| Candidate builds, independent verification and prior-artifact identity | Passed |
| Python compilation and both Git whitespace checks | Passed |

The resumed full API run exposed an outdated expected-table list. It was extended
for the additive trace table; the final clean-database rerun passed in full.
The 68 skips are the existing gateway tests requiring nginx >=1.28 or
ATLAS_TEST_NGINX; no suitable local executable was configured. No new skips or
weakened assertions were introduced. The final run includes the strengthened
actual-Runner preservation check for debug deletion.

The local tests use PostgreSQL 17, Redis and the exact pinned runtime/collection,
with synthetic source fixtures. No real Proxmox endpoint or source credential is
used. Production Chrome uses intercepted safe API fixtures; desktop/mobile images
were inspected in both themes. Existing dependency deprecation warnings remain.

## Reproduction and evidence

Logs and disposable test configuration are under
`/private/tmp/atlas-i4c-diagnostics`; private generated configuration stays mode
0600 and no credential values are copied here. Commands actually executed include:

```bash
# atlas/apps/api, with generated disposable PostgreSQL/Redis environment loaded
python -m pytest tests/test_discovery_diagnostics.py tests/test_discovery_diagnostics_runtime.py tests/test_i3_runtime.py tests/test_i3_discovery.py -q --tb=short
python -m pytest -q --tb=short -rs
python -m pytest tests/test_models.py -q --tb=short
bash ../../infra/ci/release-critical.sh
python -m alembic heads

# atlas root
PYTHONPATH=plugins/sdk:plugins/proxmox apps/api/.venv/bin/python -m pytest docs/architecture/integrations/contracts/tests apps/api/tests/test_repository_docs.py apps/api/tests/test_markdown_docs.py -q --tb=short

# atlas/apps/web
node --test tests/discovery-diagnostics.test.mjs tests/discovery.test.mjs
npm test
npm run build
node scripts/check-discovery-diagnostics-browser.mjs
node scripts/check-i3-discovery-browser.mjs

# atlas-connectors, pinned runtime Python and reviewed collection configured
python -m pytest -q --tb=short
python tools/build_bundle.py --candidate --output /private/tmp/atlas-i4c-diagnostics/candidate-final-a
python tools/build_bundle.py --candidate --output /private/tmp/atlas-i4c-diagnostics/candidate-final-b
python tools/verify_candidate.py --directory dist/proxmox-candidate-0.2.0-i4b.3 --expected-digest sha256:05c8ccb44b3964b780d3ffcef9a71a89b80ed2a5b7f4de22806ea7b0f62cf626
```

Candidate archive and detached manifests compare byte-identically across the two
builds. The verified local review artifact also matches them and is saved at
`atlas-connectors/dist/proxmox-candidate-0.2.0-i4b.3/` (ignored build output).
Independent verification checks all 19 files, metadata and dependency/contracts.
Clean-commit provenance verification remains the later operator checkpoint.

Original `.1`: `sha256:d283441dfa70d8e589fd3da868075bdb795a8cda938a78931437432b572166c8`.
Original `.2`: `sha256:3dcf374e487a65a4398fe3ec2b3c0158c9fbdeaa5c8f885b85d8c3361904ffb5`.
The `.1` archive hash is unchanged. A read-only Git export of the reviewed
Connector HEAD rebuilds `.2` byte-identically to the pre-edit archive. Existing
`.1`/`.2` archives are never overwritten; regression covers both prior filenames.
The default production build matches its pre-task bytes. Atlas's embedded 0.1.0
bootstrap independently matches its reviewed Git HEAD. These are separate preserved
production artifacts; no equality between those two historical builds is asserted.

## Security review

Review and executed tests cover allowlisted normal/debug fields, generated secret
markers, source token, Authorization header, runtime-control/ingestion credentials,
body/config/comment exclusion, malformed events, count/size limits and incomplete
prefixes. Destination checks cover symlinks, hardlinks, FIFOs, replaced inodes and
host-path/control injection. Source off/on fixtures have identical observations,
relationships, warnings, completeness and request sequences. Complete seals cannot
hide diagnostic processing/source warnings. Existing validators stay strict.

Global management plus scoped view is required for arming and trace GET/DELETE;
non-admin and cross-customer/site access are denied. Debug deletion retains normal
provenance and all run knowledge; the actual .3 Runner regression also compares
retained evidence/assertions/reconciliation/run-observation counts before/after.
Expiry physically purges rows through the existing worker/read lifecycle. Portable
backup/restore tests prove debug rows are excluded while normal provenance survives.
No raw-source endpoint, new privilege, SDK change or vendor parser is introduced.

No unresolved architectural decision remains for local scope. The existing
runtime remains ephemeral: abrupt loss of the entire service before result pickup
can lose its transient trace. Source-child/Ansible crash, incomplete completion,
cancellation and timeout traces are validated. Retention cleanup uses the existing
worker, which resumes expiry purging after restart. Live deployment/qualification
is deliberately still an operator gate.

## Material files and repository state

Models/schema/migration introduce separate immutable intent and trace storage.
API presenters, administration, orchestration and runtime control implement scoped
one-shot lifecycle and sanitized persistence. Backup/worker/runtime lifecycle adds
physical cleanup. UI pages/components reuse Section/DataTable/Button/status
primitives; their unit/browser tests cover administrator visibility and responsive
behavior. The new synthetic .3 fixture complements the unchanged I4B fixture.
Documentation and the feature ledger record current local capability and live limits.
Connector metadata, fixed discovery playbook, modules and packaging/verifier add
.3 diagnostics; Connector tests and runbook preserve the earlier artifact evidence.
SDK is clean and unchanged. The following is the exact changed-file inventory from
`git status --short --untracked-files=all`; all work remains uncommitted.

### atlas

```text
 M apps/api/app/models.py
 M apps/api/app/routes/integration_connections.py
 M apps/api/app/routes/integration_discovery.py
 M apps/api/app/routes/knowledge.py
 M apps/api/app/schemas.py
 M apps/api/app/services/backup_postgres.py
 M apps/api/app/services/discovery_orchestration.py
 M apps/api/app/services/integration_runtime.py
 M apps/api/tests/test_backup_postgres.py
 M apps/api/tests/test_i3_backup_postgres.py
 M apps/api/tests/test_i3_migration_postgres.py
 M apps/api/tests/test_models.py
 M apps/api/tests/test_release_distribution.py
 M apps/runtime/ansible/atlas_runtime/discovery_worker.py
 M apps/runtime/ansible/atlas_runtime/jobs.py
 M apps/runtime/ansible/atlas_runtime/server.py
 M apps/web/app/discovery-runs/[id]/page.js
 M apps/web/app/integrations/[id]/page.js
 M apps/worker/worker/main.py
 M docs/architecture/integrations/i3-implementation.md
 M docs/architecture/integrations/i4c-live-qualification-fixes.md
 M docs/deployment/discovery-runs.md
 M docs/deployment/integration-runtime.md
 M docs/product/feature-ledger.md
 M infra/ci/release-critical.sh
?? apps/api/app/services/discovery_diagnostics.py
?? apps/api/migrations/versions/20261018_0030_discovery_diagnostics.py
?? apps/api/tests/fixtures/i4c-diagnostics/bundle.tar.gz
?? apps/api/tests/fixtures/i4c-diagnostics/candidate-manifest.json
?? apps/api/tests/fixtures/i4c-diagnostics/manifest.json
?? apps/api/tests/test_discovery_diagnostics.py
?? apps/api/tests/test_discovery_diagnostics_concurrency_postgres.py
?? apps/api/tests/test_discovery_diagnostics_runtime.py
?? apps/api/tests/test_i4c_diagnostics_runtime.py
?? apps/runtime/ansible/atlas_runtime/diagnostics.py
?? apps/web/components/discovery-diagnostics.js
?? apps/web/components/run-diagnostics.js
?? apps/web/scripts/check-discovery-diagnostics-browser.mjs
?? apps/web/tests/discovery-diagnostics.test.mjs
?? docs/architecture/integrations/discovery-diagnostics.md
?? docs/architecture/integrations/i4c-diagnostics-report.md
```

### atlas-connectors

```text
 M README.md
 M connectors/proxmox/candidate/manifest.json
 M connectors/proxmox/candidate/sbom.spdx.json
 M connectors/proxmox/discover.yml
 M connectors/proxmox/docs/i4c-live-qualification.md
 M connectors/proxmox/module_utils/atlas_discovery.py
 M connectors/proxmox/module_utils/atlas_normalization.py
 M connectors/proxmox/module_utils/atlas_transport.py
 M tests/test_i4c_checkpoint.py
 M tests/test_proxmox_ansible.py
 M tools/build_bundle.py
 M tools/verify_candidate.py
?? connectors/proxmox/docs/i4c-discovery-diagnostics.md
?? connectors/proxmox/module_utils/atlas_diagnostics.py
?? tests/test_discovery_diagnostics.py
```
