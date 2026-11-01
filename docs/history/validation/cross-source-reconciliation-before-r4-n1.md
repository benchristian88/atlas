# Historical R1–R5 engineering assessment before R4-N1

Archived on 2 November 2026. The broad R4 acceptance claim below is withdrawn:
the subsequent independent review reproduced natural Network/Interface assertion
deadlocks and an authenticated discovery-completion HTTP 500. Executed tests
remain evidence of their narrower cases. This is historical evidence, not the
current acceptance verdict. See the [current A–J report](../../testing/cross-source-reconciliation.md).

---

# Cross-source reconciliation — R1–R5 final remediation

Branch: `fix/reconcilliation-fixes`. HEAD/base: `af32da2d3153e48feeec26adb91c64e7732e36a0`.
Date: 1 November 2026 (Pacific/Auckland). Git and deployment authority remain human-only.

## A. Executive verdict

**CONDITIONAL PASS. R1–R5 are corrected; no mandatory reconciliation gate remains
blocked.** Final code passed 373 focused tests (zero skips/failures), including all
158 PostgreSQL integrity/migration/fleet cases and all original 54 gates. The
complete backend/SDK/Proxmox run passed 2,592 with zero failures and 178 explicitly
accounted environmental skips. Frontend: 330 tests, production build and 48 browser
states passed. Linux/pinned-runtime/nginx CI and the separate enrolled exact-build
transition remain outside local release qualification; neither is claimed passed.

The earlier F1–F5 **CONDITIONAL PASS** is withdrawn as a complete reconciliation
integrity assessment: the second independent review disproved its refreshed-value,
absence, full-lock-graph and migration-history guarantees. Its executed tests
remain evidence of their narrower scenarios. The prior record is retained in
[withdrawn F1–F5 evidence](../../history/validation/cross-source-reconciliation-f1-f5-review-withdrawn.md);
the [initial pre-remediation assessment](../../history/validation/cross-source-reconciliation-pre-remediation.md)
also remains historical. No live acceptance-instance continuity is claimed.

## B. Finding disposition

| Finding | Reproduction and root cause | Correction | Permanent regression / persisted evidence | Final result |
| --- | --- | --- | --- | --- |
| R1 High | HTTP PATCH changed `Curated` to `New manual value`; refresh changed the token but displayed `Curated`; acceptance persisted `Observed` with the wrong Changes predecessor. Versioning read the live Asset while display/Changes read the original item snapshot. | One authorized `canonical_asset_snapshot` feeds review comparison, evidence details, version and locked before/after Changes. Original proposal snapshot stays in storage. Lock/reload before version validation; reject older tokens, including further concurrent edits. | `test_r1_refreshed_display_version_and_locked_changes_agree`: all eight fields, individual/bulk, old-token refusal, refreshed current values, selected assertion, original snapshot, exact predecessor/successor and one committed acceptance audit. `test_r1_r2_further_manual_patch_cannot_be_overwritten_after_refresh`: actual separate request connections, manual lock gate, no decision Changes on failure. Existing changed-back/versionless F2 gates retained. | **PASS** |
| R2 High | A versionless `mark_missing` accepted an old absence item after manual retirement: operational `missing`, accepted assertion `retired`. The versionless fallback excluded absence; lifecycle writes did not select matching status knowledge. | Require a reviewed `expected_version` for **every** absence acceptance. Under the Asset lock, status-writing choices create/select an explicit operator declaration through normal replacement. Keep/exception choices preserve status. Changes records the locked statuses and links the supporting absence assertion. | Every supported disposition × versioned/versionless × intervening/changed-back status; fresh valid decisions; bulk blocked; source observation and coverage retained; selected status, lifecycle Changes, prior declaration/lineage and audit independently inspected. The original `retired → missing` request returns 409. | **PASS** |
| R3 Medium | Actual baseline helpers on full 0031 generated accepted A1 → observed A2 → accepted B. Acceptance overwrote A1's overloaded pointer with B while source-stale. The old migration treated any stale row as source lineage. | Maintenance table lock and conservative preflight check source/canonical identity, predicate, lifecycle/timing and retained decision evidence. Move only provable acceptance pointers; retain only provable source pointers. Refuse erased/ambiguous history with assertion IDs and a safe operator recovery path. Never infer a missing A2 edge or choose an accepted winner. | Full-schema `test_knowledge_integrity_migration.py`, using frozen actual baseline helpers and reflected 0031 columns. Provable source/replacement/chains round-trip; overwritten cross/same-source, missing evidence, reselection, rejected/retracted and mismatched identities refuse. Cases with retained accepted review/Changes evidence also refuse when that evidence cannot recover the lost source successor. Independent SQL compares revision, every assertion value, columns and indexes after rollback. | **PASS** |
| R4 Medium | Separate HTTP transactions reproduced Asset FOR UPDATE → implicit manual-source FK KEY SHARE versus source FOR UPDATE → Asset, causing PostgreSQL 40P01. | Use source **FOR NO KEY UPDATE** consistently in retraction, decisions, link helpers and ingestion. It serializes source writers but permits FK KEY SHARE. Keep canonical subject serialization and source-local relationship refresh; prelock batch-linked Asset endpoints before ingestion claim writes. Manual PATCH shares the transaction-conflict guard. Run writer rows likewise use FK-compatible NO KEY UPDATE without changing control policy. | Deterministically synchronize the exact implicit-FK race in both request orders: both succeed with no 40P01, complete declarations and matching selected/operational values. Unrelated Assets proceed while one is held. Real PostgreSQL 40P01 raised **after all writes flush** on either request path proves controlled 409 and complete rollback; these are injected victim checks, not a claim of a remaining natural deadlock. Original source-link/cross-source races rerun. | **PASS** |
| R5 Medium | A valid new-schema A1 had source edge A2 and acceptance edge B. 0032 → 0031 → 0032 silently lost B. | Downgrade preflight before DDL/copy refuses dual lineage (including equal targets) and any state whose meaning cannot survive the conservative next upgrade. Supported histories remain lossless; no parallel history store or fabricated decisions. | Source-only, acceptance-only and chain round trips compare all rows; dual/equal-target, stale acceptance and ambiguous unselected source histories refuse at 0032. Both original lineage IDs, schema/indexes and usable database survive; upgrade head afterward remains usable. | **PASS** |

Self-review also reproduced a directly related pending-history defect: with
`autoflush=False`, refreshing prior accepted assertions discarded unflushed source
supersession from manual/lifecycle declarations. Four strengthened cases failed
before correction. `accept_assertion` now flushes pending history **under the
canonical lock before refresh**, retaining source and acceptance edges together.
`test_r2_r4_manual_declaration_refresh_preserves_pending_source_history` and the
status-writing lifecycle checks verify the committed result.

Eight additional synthetic legacy cases exercise an explicit status-writing
choice with no operational field delta, with either missing or inconsistent
selected status knowledge. These initially failed. Every status-writing choice
now selects its own declared value, preserving the prior assertion and recording
the actual (possibly equal) locked operational before/after values. Keep/exception
continue to leave selected status untouched.

The final compatibility audit also covers legacy list presentation when an
existing field review retains null `entity_id` after identity attachment but its
assertion already identifies the canonical Asset. The legacy route now derives
that Asset from the attached subject, checks context and uses the same snapshot.
Its counterexample failed before correction and is a permanent real-HTTP gate.
No source link is inferred or written by presentation.

A full R4 lock-graph challenge also reproduced PostgreSQL **40P01** between
cross-source scalar acceptance and ingestion corroborating an existing operational
relationship. Ingestion had changed an old assertion before later taking its Asset
lock for a manual relationship declaration. Shared ingestion now prelocks only the
current batch's already-linked Asset subjects/endpoints in UUID order before
writing claims. It does not resolve identities or lock unreferenced Assets. A
separate held-unreferenced-Asset test protects independent concurrency. Evidence:
`ingestion-lock-sqlstate-before.log`; permanent tests in the final integrity module.

Four additional R1 boundary regressions failed before correction: two PATCH
transactions started before proposal creation, then committed a changed-back
status with `updated_at < proposal.created_at`, permitting an unsafe versionless
200; an old proposal without a provable canonical baseline; and missing/other-site
canonical targets falling back to original snapshot text. New items now retain a
private exact original canonical timestamp. Versionless field/value/timestamp
validation is equality-based under lock; old items without proof require a
reviewed version. Current-value projections are null when the canonical target
is unavailable or outside context. No historical baseline is backfilled/guessed.
Evidence: `canonical-boundaries-before.log`; all cases use real HTTP routes and
independent committed-state inspection.

The upstream R4 graph also reproduced an unhandled Run → Source → Run 40P01:
run control held DiscoveryRun FOR UPDATE while entering source work; acceptance
held that source while inserting a Change with a Run provenance FK. DiscoveryRun
writers now use FOR NO KEY UPDATE, allowing FK KEY SHARE while retaining exclusive
state writers. The regression uses the production run-scope helper, shared
ingestion, a real HTTP acceptance and independent connections. A second writer's
NOWAIT request still returns 55P03; the Run remains running and its provenance
Change commits. Only row-lock mode changes in run controllers: no lease fields,
admission/auth checks, cancellation policy, SDK or execution authorization changes.
Evidence: `run-fk-before.log`; permanent `test_r4_run_provenance_fk_and_source_lock_share_one_compatible_order`.

The supplied external probes were read in full and rerun before application
changes. Their four counterexamples reproduced; their green counterexample
assertions are evidence of vulnerable behavior, not integrity passes. Both
migration counterexamples were independently recreated on a complete 0031 schema.
Permanent tests import no external review scripts or temporary paths.

## C. Architecture and transactions

PostgreSQL remains authoritative. Tests use production `SessionLocal` options:
`autoflush=False`, `expire_on_commit=False`, READ COMMITTED, real commit and fresh
post-commit connections. No worker, connector, taxonomy, graph or secret-store
architecture changes were introduced.

The live authorized canonical Asset snapshot supplies `current`, API
`current_value_json`, version content and Changes predecessor. The persisted item
snapshot remains original proposal context. Versions also include Asset update
time, preventing changed-back bypass. Individual and bulk decisions lock/reload
before validating, and bulk validates the explicit reviewed proposal set before
applying its eligible independent decisions. Stale records fail without silently
changing accepted knowledge. Versionless changed-field requests require the exact original canonical
field/value/update timestamp, retained as private context on new proposals.
Older proposals without that baseline require a reviewed version. Transaction
start timestamps cannot safely be compared by greater-than against proposal
creation; overlapping manual PATCHes can start before a proposal yet commit a
changed-back value afterward. The exact comparison detects that race. Absence
acceptance always requires a version. Unavailable or out-of-context canonical
records render null current values rather than any original proposal snapshot.

`mark_missing`, `mark_inactive`, `mark_retired`/`retire` select a new operator
status declaration, including when the column already matches but legacy selected
knowledge is missing/inconsistent. Matching current manual declarations coalesce;
prior declarations and both lineages remain retained. `keep_active` means preserve current status; `exception` records a
lifecycle exception without changing status. Neither promotes status to active.
Absence observation, coverage and supporting evidence remain distinct.

Explicit and implicit locking:

0. Upstream run control retains its existing Integration writer lock and takes
   DiscoveryRun **FOR NO KEY UPDATE**. Another run state writer remains excluded,
   but immutable Run FK KEY SHARE is compatible. Core decisions do not acquire
   a run writer lock; their provenance inserts cannot create a backward Run wait.
1. Source writer rows **FOR NO KEY UPDATE**, sorted by UUID, including discovery,
   identity helpers, decisions and assertion lifecycle operations.
2. Canonical subjects **FOR UPDATE**: Assets, Networks, Interfaces,
   AssetRelationships, Services, Business Functions, in that model order and UUID
   order. Known bulk targets and Interface owners precede later locks. Ingestion prelocks
   already-linked subjects/endpoints referenced by its batch before any claim
   changes; it never holds a claim and then first waits for a known Asset during
   relationship corroboration. Unreferenced source-linked Assets remain unlocked.
3. Review items by UUID, then assertions by UUID. Low-level acceptance reacquires
   its canonical subject, flushes pending source history, refreshes prior selected
   flags, clears/flushes replacement and selects the new claim.
4. Assertion/source-link inserts implicitly take FK KEY SHARE on their referenced
   source, canonical entity, run, evidence, customer/site and actor records.
   Assertion replacement updates old rows and takes a successor FK KEY SHARE.
   These source KEY SHARE locks are compatible with the source writer mode.
   Normal non-key source updates also use NO KEY UPDATE; identity/key mutation is
   not part of these operations.
5. Manual PATCH holds/reloads its Asset and may take compatible manual-source
   KEY SHARE through declaration inserts. It never requests a source writer
   lock. Retraction takes source writer → subject → assertion. This removes the
   reproduced Asset/source cycle without a site/global application mutex.
6. Maintenance migration takes ACCESS EXCLUSIVE on assertions before preflight;
   it is a separate maintenance boundary, not an online request operation.

Individual links/decisions commit operational state, assertions, source links,
follow-up reviews, Changes and audit together. Bulk retains independent successes
through savepoints. SQLSTATE 23505/40001/40P01/55P03 gives a controlled 409 or failed
bulk entry; no automatic retry. Unknown database failures propagate. Existing CRUD
helpers separately map IntegrityError to 409. No audit claims a rolled-back action.

## D. Migration assessment

0032 was untracked at handoff and has no Git history; it is unmerged/unreleased.
The handoff/deployment record states the acceptance deployment remains bound to
the baseline. The task explicitly permits amendment of this unreleased migration.
No live deployment/database was accessed to verify or change it. Committed
migration history is untouched; the single head remains `20261101_0032`.

A source-current, current, deselected, non-retracted scalar edge can prove
acceptance replacement for the same canonical subject/predicate/context. A
still-accepted source-stale superseded row can prove source-only lineage when
source/external identity and successor observation/validity timing match.
Source-stale deselected history is deliberately refused: baseline cleared its
acceptance timestamps and could overwrite its original source edge. Decision
records can prove acceptance, but cannot reconstruct that missing edge. Even an
apparently simple unselected source-only row may refuse without sufficient proof.
This is intentional fail-closed behavior, not an automatic data repair.

Duplicate scalar preflight does not pick a winner. Ambiguity/duplicate refusal
leaves 0031, all original values, columns/indexes and rows intact. Downgrade
refusal leaves 0032 and both lineages intact. Supported representable histories
round-trip; downgrade is **not generally reversible**. Equal source/acceptance
targets still carry two meanings and refuse. No production-volume migration
benchmark was run. See [upgrade/migration operations](../../deployment/upgrades.md#reconciliation-integrity-migration-0032).

## E. Security assessment

The integrity fixtures override principal acquisition and active context, while
exercising real permission/scoping code, real HTTP decisions and production
PostgreSQL sessions. They are not end-to-end login/runtime-attestation tests.
Browser APIs are intercepted and provide presentation evidence only. Broader auth
and control tests are included in the backend run; the platform skips below are
not treated as passes.

Existing authentication, `reconciliation.decide`, `assets.edit`, technical and
relationship permissions, active customer/site context and ownership checks
remain backend boundaries. Canonical display uses a context-checked Asset; stale
or mismatched canonical targets cannot disclose values or receive absence writes.
No new route/permission or frontend authorization boundary was added. New
ingestion locks read only source-local, customer/site-scoped links for the
current batch, retain explicit identity decisions and leave unreferenced Assets
independent.

Source identity associations remain explicit, immutable and source-scoped.
Canonical Asset/Interface UUIDs and Network reuse remain intact. The database
scalar uniqueness boundary is preserved. Manual data is first-class; refreshed
approval is an explicit human selection rather than a silent discovery override.
Observation history, old declarations, decision provenance and audit are retained.
Migration diagnostics contain assertion IDs and recovery instructions, not source
values or secrets. No live credentials, protected enrollment or execution authority
were accessed or modified.

## F. File inventory and compatibility

Incremental application changes since the 36-modified/12-untracked handoff:

| Files | Purpose |
| --- | --- |
| `app/services/reconciliation.py` | Shared canonical field/snapshot, exact private legacy baseline; actual locked Changes values; explicit consistent lifecycle status declarations and context check. |
| `app/services/reconciliation_entities.py` | Live canonical comparison/evidence and version from the same snapshot. |
| `app/routes/knowledge.py` | Exact versionless field baseline and unavailable-target handling; mandatory absence version; context-safe presentation; compatible source mode; shared conflict guard. |
| `app/routes/assets.py`, `app/services/knowledge_locks.py` | Manual PATCH conflict rollback; shared resolved-signature wrapper; explicit/implicit locking contract. |
| `app/services/entity_resolution.py`, `app/services/simulated_discovery.py` | Source writer NO KEY UPDATE consistently in linking and ingestion; source-local batch Asset locks before claims. |
| `app/services/discovery_orchestration.py`, `app/routes/integration_discovery.py` | Run lock mode only: writer exclusion retained, provenance FK KEY SHARE permitted. Lease/admission/authorization/cancellation fields and checks unchanged. |
| `app/services/knowledge_assertions.py` | Flush pending source history before refreshing the accepted set under the canonical lock. |
| `migrations/versions/20261101_0032_knowledge_acceptance_integrity.py` | Conservative legacy classification, maintenance preflight, duplicate refusal and lossless/refused downgrade. |
| `tests/test_reconciliation_final_integrity.py` | HTTP display/version/Changes, lifecycle, changed-back, concurrency, both rollback paths and pending-history coverage. |
| `tests/test_reconciliation_integrity_postgres.py` | Retain all 53 original cases; synchronize source gates on the deliberate NO KEY UPDATE mode. |
| `tests/test_knowledge_integrity_migration.py` | Replace abbreviated migration fixture with complete 0031 schemas, historical helper sequences, independent SQL refusal/round-trip checks. |
| `tests/test_trusted_catalogue.py` | Isolate only the two preexisting migration tests from shared domain lineage; catalogue implementation and refusal assertions are unchanged; an explicit Integration sentinel verifies preservation. |
| `tests/fixtures/knowledge_assertions_0031.py` | Frozen actual baseline helpers with source commit/hash; rebound only to reflected 0031 columns. |
| `tests/test_cross_source_fleet_postgres.py` | Permanent 34-identity fleet probe, production request sessions, independent post-commit checks, isolated-schema cleanup. |

Paths above are relative to `apps/api/`. Frontend incremental changes are
`apps/web/tests/reconciliation-entities.test.mjs` (snapshot rendering) and
`apps/web/scripts/check-reconciliation-browser.mjs` (individual/bulk stale-refresh
behavior). No component, layout, route, stylesheet or dependency was changed in
this incremental remediation. Interface/Network selectors and AK-01/AK-02 remain.

Documentation changed: both reconciliation architecture guides, ADR 0017's dated
clarification (earlier text retained), administrator guide, upgrade/migration
contract, feature ledger and this record. The former F1–F5 assessment is archived
with an explicit withdrawal notice. **AK-HISTORY-PAGINATION** is Planned but not
implemented: Raw defaults to 200 rows (API max 1,000), Fact History caps at 500,
and Asset detail pages neither. A 520-row Summary can exceed both visible tabs;
no retained rows were deleted.

All earlier operator changes remain preserved. The completion inventory includes
the whole dirty tree below; unrelated handoff files were not edited. Existing
routes/payload fields remain; canonical current-value presentation is corrected,
and absence acceptance now requires `expected_version` (intentional legacy
behavior tightening). The original field baseline is additive JSON proposal context on new items,
not a schema change or a second operational truth store. Older items are not
backfilled. No new schema revision beyond the unreleased 0032 amendment. The prior handoff
already normalized relationship `value` objects in per-assertion summary arrays;
that behavior is retained. Consumers parsing earlier arbitrary summary JSON
should review the full-branch contract; Raw assertion values remain original.

The following **28 handoff files are byte-for-byte unchanged by this incremental
remediation**. Their preexisting operator changes remain part of the delivered
working tree and were included in validation:

| Preserved material file | Existing role |
| --- | --- |
| `apps/api/app/models.py` | Existing acceptance-lineage mapping and scalar unique index. |
| `apps/api/app/routes/changes.py` | Existing authorized semantic history presentation. |
| `apps/api/app/schemas.py` | Existing response/link/knowledge metadata contracts. |
| `apps/api/app/services/knowledge_lifecycle.py` | Existing dual-lineage retention checks. |
| `apps/api/app/services/knowledge_summary.py` | Existing AK-01/AK-02 summary/provenance semantics. |
| `apps/api/tests/test_asset_knowledge_summary.py` | Existing AK-01/AK-02 API regression. |
| `apps/api/tests/test_backup_postgres.py` | Existing regression/session/schema compatibility coverage, rerun in the complete suite. |
| `apps/api/tests/test_cross_source_reconciliation.py` | Existing original two-source HTTP/AIP fixture. |
| `apps/api/tests/test_i3_discovery.py` | Existing regression/session/schema compatibility coverage, rerun in the complete suite. |
| `apps/api/tests/test_i3_migration_postgres.py` | Existing regression/session/schema compatibility coverage, rerun in the complete suite. |
| `apps/api/tests/test_knowledge_foundation.py` | Existing regression/session/schema compatibility coverage, rerun in the complete suite. |
| `apps/api/tests/test_knowledge_lifecycle.py` | Existing regression/session/schema compatibility coverage, rerun in the complete suite. |
| `apps/api/tests/test_models.py` | Existing regression/session/schema compatibility coverage, rerun in the complete suite. |
| `apps/api/tests/test_reconciliation_entities.py` | Existing regression/session/schema compatibility coverage, rerun in the complete suite. |
| `apps/api/tests/test_release_distribution.py` | Existing regression/session/schema compatibility coverage, rerun in the complete suite. |
| `apps/web/app/assets/[id]/page.js` | Existing Summary/History/Raw Asset integration. |
| `apps/web/app/globals.css` | Existing Atlas Knowledge/Reconciliation styling. |
| `apps/web/app/reconciliation/page.js` | Existing explicit linking, version forwarding and bulk interaction. |
| `apps/web/components/asset-knowledge-summary.js` | Existing AK-01/AK-02 grouped Knowledge presentation. |
| `apps/web/components/reconciliation-cards.js` | Existing scoped selectors and independent configuration-review UI. |
| `apps/web/tests/asset-knowledge-summary.test.mjs` | Existing UI contract regression, rerun in the complete frontend suite. |
| `apps/web/tests/interface-ip-ui.test.mjs` | Existing UI contract regression, rerun in the complete frontend suite. |
| `apps/web/tests/knowledge-v2-ui.test.mjs` | Existing UI contract regression, rerun in the complete frontend suite. |
| `apps/web/tests/reconciliation-navigation.test.mjs` | Existing UI contract regression, rerun in the complete frontend suite. |
| `docs/README.md` | Existing documentation index. |
| `docs/decisions/README.md` | Existing ADR index. |
| `docs/deployment/local-release-acceptance.md` | Existing exact-build deployment limitation. |
| `docs/history/validation/cross-source-reconciliation-pre-remediation.md` | Existing withdrawn historical acceptance record. |

## G. Test matrix and evidence

Evidence: `/private/tmp/atlas-final-remediation.3u0cofdo/`. Handoff copies/hashes,
full initial diff/status, reproduction logs/scripts, JUnit, browser screenshots,
final file hashes and an incremental patch are retained there. Permanent tests
import no external review files or temporary paths.

New native PostgreSQL **17.11**, loopback **55684**, READ COMMITTED. Test roles
`atlas_final` (focused) and `atlas_handoff` (final complete run) are ordinary owners:
NOSUPERUSER/NOCREATEDB/NOCREATEROLE. Production `SessionLocal` uses
`autoflush=False`, `expire_on_commit=False`; fixtures assert those settings.
Each complete attempt received fifteen newly provisioned disposable CI database
categories. New volume-free Redis **7.4.6**, loopback **56684**, separate logical
application/backup DBs. Python **3.14.7**, Node **24.19.0**, existing dependencies.
No acceptance-instance database, service, identity, credential or volume was used.

| Final validation | Exact command / evidence | Result |
| --- | --- | --- |
| Focused acceptance | Command below / `focused-handoff.xml`, `focused-handoff.log` | **373 passed, zero skipped/failed**. All original 54 gates retained; all 158 PostgreSQL integrity/migration/fleet cases run. Includes diagnostics/control regressions. |
| Complete backend + SDK + Proxmox | Command below / `backend-handoff.xml`, `backend-handoff.log` | **2,592 passed, 178 skipped, zero failed**. All mandatory integrity modules run without skips. |
| Frontend | `npm test` in `apps/web` / `frontend.log` | **330 passed, zero skipped/failed**. |
| Production build | `NEXT_TELEMETRY_DISABLED=1 npm run build` in a full copied `apps/web` under the evidence directory / `build.log` | Passed; no build output written in the original working tree. |
| Browser | Command below / `browser/report.json`, `browser.log`, screenshots | **48 recorded states**, no runtime errors. Individual/bulk stale refresh, selectors, keyboard interaction, AK-01/AK-02 and responsive layouts; intercepted synthetic APIs. |
| Architecture contracts | `PYTHONDONTWRITEBYTECODE=1 apps/api/.venv/bin/python -m pytest -p no:cacheprovider docs/architecture/integrations/contracts/tests -q --tb=short` from root / `contracts.log` | **77 passed**. |
| Documentation and CI contracts | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/test_repository_docs.py tests/test_markdown_docs.py tests/test_ci_workflow.py -q --tb=short` in `apps/api` | **33 passed**; final report recheck recorded below. |
| Workflow lint | `/private/tmp/atlas-phase4b2-tools/actionlint .github/workflows/ci.yml .github/workflows/release.yml` from root | Passed, exit 0. |
| Migration head | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m alembic heads` in `apps/api` | Exactly **20261101_0032 (head)**. |
| Python compilation | `PYTHONPYCACHEPREFIX=/private/tmp/atlas-final-remediation.3u0cofdo/pycache .venv/bin/python -m compileall -q app migrations tests` in `apps/api` | Passed, exit 0; bytecode confined to temporary evidence storage. |
| Whitespace | `git diff --check` from root; documentation scanner also covers untracked Markdown | Clean. |
| Catalogue fixture / unchanged verifier rerun | `.venv/bin/python -m pytest -p no:cacheprovider tests/test_trusted_catalogue.py tests/test_official_provenance.py -q --tb=short --junitxml=/private/tmp/atlas-final-remediation.3u0cofdo/catalogue-isolation.xml` / `catalogue-isolation.log` | **110 passed**, zero failed/skipped. No verifier implementation change. |
| Final lifecycle-summary wording | `.venv/bin/python -m pytest -p no:cacheprovider tests/test_reconciliation_final_integrity.py -k fresh_explicit_lifecycle -q --tb=short --junitxml=/private/tmp/atlas-final-remediation.3u0cofdo/lifecycle-wording.xml` / `lifecycle-wording.log` | **12 passed**, 65 deselected. Follow-up after a wording-only fix: keep-current summaries describe the actual inactive/retired status rather than falsely claiming active. Operational behavior, routes and audit fields unchanged. |
| Concrete migration sentinel | `.venv/bin/python -m pytest -p no:cacheprovider tests/test_trusted_catalogue.py -k "additive_migration or migration_downgrade" -q --tb=short` / `catalogue-sentinel.log` | **2 passed**, 27 deselected. Explicit preexisting Integration retained. |

The two main commands, from `apps/api`, source generated disposable configuration
first (`test.env` for focused; `handoff.env` for the final complete run). All Python
runs disable bytecode and pytest cache.

```bash
.venv/bin/python -m pytest -p no:cacheprovider \
  tests/test_reconciliation_final_integrity.py tests/test_knowledge_integrity_migration.py \
  tests/test_reconciliation_integrity_postgres.py tests/test_cross_source_fleet_postgres.py \
  tests/test_cross_source_reconciliation.py tests/test_knowledge_foundation.py \
  tests/test_reconciliation_entities.py tests/test_asset_knowledge_summary.py \
  tests/test_source_identity.py tests/test_i3_discovery.py \
  tests/test_reconciliation_listing.py tests/test_knowledge_lifecycle.py \
  tests/test_discovery_diagnostics.py tests/test_discovery_diagnostics_concurrency_postgres.py \
  -q --tb=short --junitxml=/private/tmp/atlas-final-remediation.3u0cofdo/focused-handoff.xml

PYTHONPATH=/Users/Ben/Code/atlas/plugins/sdk:/Users/Ben/Code/atlas/plugins/proxmox \
  .venv/bin/python -m pytest -p no:cacheprovider tests \
  ../../plugins/sdk/tests ../../plugins/proxmox/tests -q -rs --tb=short \
  --junitxml=/private/tmp/atlas-final-remediation.3u0cofdo/backend-handoff.xml

# apps/web; production server is the copied build at loopback 31684
ATLAS_PLAYWRIGHT_MODULE=/private/tmp/atlas-reconciliation-browser-tools/node_modules/playwright/index.mjs \
ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
ATLAS_BROWSER_BASE_URL=http://127.0.0.1:31684 \
ATLAS_BROWSER_OUTPUT=/private/tmp/atlas-final-remediation.3u0cofdo/browser \
node scripts/check-reconciliation-browser.mjs
```

Skip audit from final JUnit (all **178**, none in mandatory integrity modules):

| Count | Modules / exact environment reason | Existing CI coverage |
| --- | --- | --- |
| 83 | Local-release authority 18, recovery 32, remediation 33: root in a disposable container and migrated PostgreSQL required. | Backend job's separate root Docker regression rejects skips. Not executed locally as root/Linux. |
| 27 | I3 live 6, I4A 1, I4B 12, I4C 8: exact pinned Ansible runtime environment absent. | Backend job installs the pinned runtime and rejects ordinary-suite skips. |
| 68 | nginx gateway: nginx >=1.28 / `ATLAS_TEST_NGINX` absent. | Backend job installs test nginx and rejects ordinary-suite skips. |

All mandatory new integrity tests are collected by ordinary `pytest tests`, with
no opt-in flags. CI provisions the already mandatory `ATLAS_TEST_DATABASE_URL`
and rejects any skip in its ordinary-user job. No additional CI environment or
infrastructure is required. Workflow tests/actionlint verify configuration, not a
remotely executed CI result. Browser script remains a manual acceptance command,
not an enforced frontend CI step. No platform-specific skip is claimed passed.

Reproduction evidence before corrections:

- Original independent HTTP/state/lock/cap probes: `reproductions.log`, four
  counterexamples reproduced. Green counterexample assertions mean vulnerable
  behavior was found, not that integrity passed. Command:
  `PYTHONPATH=/Users/Ben/Code/atlas/apps/api .venv/bin/python -m pytest -p no:cacheprovider /private/tmp/atlas-independent-review.IerNaY/test_independent_probes.py -q -s --tb=short`.
- Complete-schema migration witnesses: `migration-reproductions.log`, using
  `apps/api/.venv/bin/python /private/tmp/atlas-final-remediation.3u0cofdo/reproduce_migrations.py`
  from root. Both misclassified legacy replacement and lost dual-lineage downgrade
  were reproduced before migration amendment.
- Pending supersession: `pending-lineage-before.log`, four failing cases before
  flush-before-refresh correction.
- Status choice without field delta: `status-no-delta-before.log`, eight failing
  synthetic legacy cases before explicit selection correction.
- Legacy list projection: `legacy-projection-before.log`, old displayed value
  reproduced with an attached canonical subject and null item entity ID.
- Asset/claim ingestion cycle: `ingestion-lock-sqlstate-before.log`, actual 40P01.
- Overlapping transactions / unavailable current values: `canonical-boundaries-before.log`,
  four failures, including a real versionless changed-back 200 with canonical
  update time earlier than proposal creation.
- Run/source provenance FK cycle: `run-fk-before.log`, actual DeadlockDetected.
  Final regression also verifies a second run writer still fails NOWAIT with
  55P03 while FK KEY SHARE is permitted.

An intermediate complete run (`backend-final.xml`) had 2,573 passes, 178 skips and
three failures. Two preexisting catalogue migration tests downgraded the shared
regression database containing unrelated valid dual lineage; the new safety guard
correctly refused. Only their fixtures now use complete isolated schemas, retaining
refusal assertions and an explicit Integration preservation sentinel. The other
failure was an OS PermissionError killing a verifier subprocess group; the
unchanged verifier suite passed on rerun and in the final complete run. No
Sigstore/verifier behavior was modified. An earlier broad run was intentionally
interrupted after 954 passes to strengthen coverage; it is not a complete pass.
Intermediate green counts did not waive later counterexamples. Only the final
handoff matrix above qualifies the delivered source state. After the complete
run, a wording-only correction made `keep_active` Change summaries describe the
actual retained status; the 12 affected lifecycle cases were rerun successfully.
No transaction, authorization, lease or state-transition logic changed in that
final wording follow-up.

## H. Original feature regression

The permanent fleet starts from its verified synthetic input map: 34 canonical
Assets, 34 Interfaces and one Network, already associated to Source A. Actual AIP
Source B ingestion, explicit HTTP Asset/Interface/Network linking and bulk follow-up
review use production request sessions and real commits. Fresh connections verify
all original UUIDs, one reused Network, 33 relationships and 138 source links.
169 independent reviews are accepted. All 102 original Source B evidence records
remain; repeat discovery retains 204 and produces zero renewed identity proposals.
Counts derive from the fixture identity map, not production inventory assumptions.

The focused suite reruns dependent relationship/Network prerequisites, scoped
ownership and cross-customer/site rejection, stale/replayed decisions, follow-up
rollback/retry, partial bulk, scalar uniqueness, cross-source acceptance/retraction
and source supersession, and legitimate re-observation. AK-01 distinguishes
agreement from acceptance and operational discrepancy. AK-02 retains verified
semantic targets, grouping, authorized names/links and individual provenance.
Browser checks preserve selectors, keyboard behavior, responsive presentation,
History/Raw tabs and both stale-refresh decision paths. Those tab checks do not
assert unlimited retained-history pagination.

## I. Residual risks

1. **Deployment blocker, separate scope:** the enrolled exact-build instance has
   no supported build-transition procedure. No deployment/enrollment/key/binding
   change was made; this work does not certify its upgrade continuity. See the
   [existing limitation](../../deployment/local-release-acceptance.md#reconciliation-fix-build-transition).
2. **Intentional historical safety gate:** real 0031 data may refuse upgrade if
   lineage was overwritten or cannot be proved. Preserve backup/current schema;
   use independent historical evidence for a separately reviewed repair, or a
   verified pre-loss backup. No live-data preflight or production-volume timing
   was performed. Downgrade is limited to demonstrably lossless cases.
3. **History browsing:** AK-HISTORY-PAGINATION remains separate planned work;
   current Raw/History tabs do not expose all retained rows above their caps.
4. The 178 platform/runtime skips are enumerated in G. Linux/pinned-runtime/nginx
   CI remains necessary for broader release qualification. No mandatory
   reconciliation gate is skipped, and no remote CI result is claimed.

## J. Independent review handoff

Challenge `canonical_asset_field`, `canonical_asset_snapshot`, `item_version`, `EntityReview.present_item`,
`_decision_item`, `_accept_changed_fact`, `_accept_absence` and `accept_item` through
real HTTP sessions: refresh after a PATCH, inspect both displayed current values,
reject old/changed-back tokens and versionless calls without an exact retained
baseline (including PATCH transactions starting before proposal creation), then approve a fresh token and independently read
Asset, selected assertions, both lineage edges, Changes and security audit. Repeat
through bulk and race another PATCH while acceptance waits for the canonical lock.
Try every lifecycle disposition with/without versions; ensure keep/exception do
not promote status and bulk never chooses an individual lifecycle disposition.

Challenge all source-lock sites (`entity_resolution`, `simulated_discovery`,
knowledge decision/retraction routes) for NO KEY UPDATE and their implicit FK
compatibility. Run both deterministic PATCH/retraction orders, forced real
post-flush conflict rollback on either path, unrelated-Asset concurrency and the
original multi-source/source-local-link races. Challenge upstream Run/source
provenance FKs and verify another Run state writer is still excluded with NOWAIT. Inspect source history after the
accepted-set refresh; it must not discard pending supersession.

Populate **full revision 0031** with the frozen actual baseline helpers. Try
A1 accept → A2 observation → B accept, same-source replacement, repeated selection,
missing/retained accepted decision evidence, rejected/retracted histories and
invalid identity contexts. Ambiguity must refuse without schema/version/data
mutation. Try 0032 dual lineage (including equal targets) and lossless chains;
unsafe downgrade must leave 0032 and both lineage IDs unchanged. Do not resolve
refusal by clearing an old edge or selecting a winner. Review the actual conservative
classification boundary rather than assuming all source-stale rows are source-only.

Recheck the 34-identity fixture and API ownership cases. Challenge AK-01/AK-02
without inferring complete History/Raw pagination from the Summary count. The
human operator alone controls Git and deployment. No application-repository commit, push, reset, merge,
rebase, tag, release, live DB access or deployment occurred. Synthetic Git/key
fixtures used by existing tests remain confined to their disposable test storage.

## Repository state

`fix/reconcilliation-fixes` remains at
`af32da2d3153e48feeec26adb91c64e7732e36a0`. Initial **36 modified / 12 untracked**
files were copied/hashed before editing. Final state: **39 modified / 16 untracked**,
including 27 incremental material files and the 28 unchanged handoff files above.
No repository history/branch operation or live deployment/database access occurred.

Actual `git status --short`:

```text
 M apps/api/app/models.py
 M apps/api/app/routes/assets.py
 M apps/api/app/routes/changes.py
 M apps/api/app/routes/integration_discovery.py
 M apps/api/app/routes/knowledge.py
 M apps/api/app/schemas.py
 M apps/api/app/services/discovery_orchestration.py
 M apps/api/app/services/entity_resolution.py
 M apps/api/app/services/knowledge_assertions.py
 M apps/api/app/services/knowledge_lifecycle.py
 M apps/api/app/services/knowledge_summary.py
 M apps/api/app/services/reconciliation.py
 M apps/api/app/services/reconciliation_entities.py
 M apps/api/app/services/simulated_discovery.py
 M apps/api/tests/test_backup_postgres.py
 M apps/api/tests/test_i3_discovery.py
 M apps/api/tests/test_i3_migration_postgres.py
 M apps/api/tests/test_knowledge_foundation.py
 M apps/api/tests/test_knowledge_lifecycle.py
 M apps/api/tests/test_models.py
 M apps/api/tests/test_reconciliation_entities.py
 M apps/api/tests/test_release_distribution.py
 M apps/api/tests/test_trusted_catalogue.py
 M apps/web/app/assets/[id]/page.js
 M apps/web/app/globals.css
 M apps/web/app/reconciliation/page.js
 M apps/web/components/reconciliation-cards.js
 M apps/web/scripts/check-reconciliation-browser.mjs
 M apps/web/tests/interface-ip-ui.test.mjs
 M apps/web/tests/knowledge-v2-ui.test.mjs
 M apps/web/tests/reconciliation-entities.test.mjs
 M apps/web/tests/reconciliation-navigation.test.mjs
 M docs/README.md
 M docs/architecture/knowledge-changes-and-reconciliation.md
 M docs/architecture/reconciliation-entity-review.md
 M docs/decisions/README.md
 M docs/deployment/local-release-acceptance.md
 M docs/deployment/upgrades.md
 M docs/product/feature-ledger.md
?? apps/api/app/services/knowledge_locks.py
?? apps/api/migrations/versions/20261101_0032_knowledge_acceptance_integrity.py
?? apps/api/tests/fixtures/knowledge_assertions_0031.py
?? apps/api/tests/test_asset_knowledge_summary.py
?? apps/api/tests/test_cross_source_fleet_postgres.py
?? apps/api/tests/test_cross_source_reconciliation.py
?? apps/api/tests/test_knowledge_integrity_migration.py
?? apps/api/tests/test_reconciliation_final_integrity.py
?? apps/api/tests/test_reconciliation_integrity_postgres.py
?? apps/web/components/asset-knowledge-summary.js
?? apps/web/tests/asset-knowledge-summary.test.mjs
?? docs/admin/cross-source-reconciliation.md
?? docs/decisions/0017-reconciliation-knowledge-integrity.md
?? docs/history/validation/cross-source-reconciliation-f1-f5-review-withdrawn.md
?? docs/history/validation/cross-source-reconciliation-pre-remediation.md
?? docs/testing/cross-source-reconciliation.md
```

Final documentation/link/CI checks, actionlint, Python compilation, migration-head
and whitespace checks passed. Disposable browser/frontend, Redis and PostgreSQL
services created for this work are stopped at handoff; evidence and disposable
PostgreSQL files remain under the evidence directory. No live service was touched.
