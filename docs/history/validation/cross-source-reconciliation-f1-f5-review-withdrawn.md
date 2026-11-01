# Withdrawn F1–F5 remediation acceptance record

The following assessment is superseded by the second independent review and
the [R1–R5 final remediation record](../../testing/cross-source-reconciliation.md).
Its unqualified freshness, lock-order and migration-history claims were disproved.
It remains historical test evidence, not current release acceptance.

---

# Cross-source reconciliation — F1–F5 remediation acceptance

Branch: `fix/reconcilliation-fixes`. Base: `af32da2d3153e48feeec26adb91c64e7732e36a0`.
Date: 1 November 2026 (Pacific/Auckland). No Git mutation or deployment authorized.

## A. Executive result

**CONDITIONAL PASS.** All F1–F5 regressions pass in the 249-test focused
production-session run, including all 54 new integrity/migration tests with zero
failures/skips. The final broader run passed 2,461 tests with zero failures and 178 unrelated
environment skips. All 54 integrity gates also passed in a separate final run. This is
not an unconditional whole-environment release approval.
The original acceptance assessment is withdrawn and retained as a clearly marked
[historical record](../../history/validation/cross-source-reconciliation-pre-remediation.md).
It used PostgreSQL sessions whose default autoflush concealed F1 and did not
establish the cross-source concurrency invariants. Earlier PASS language does not
apply to that vulnerable implementation.

## B. Finding disposition

| Finding | Original failure evidence | Corrective change | Regression and persisted-state verification |
| --- | --- | --- | --- |
| F1 High | Three link variants returned success with zero open follow-up reviews under production session options. Changing the old fixture alone caused four existing failures. | Flush the accepted identity item before `create_item()`; association, follow-up, Changes and audit share one transaction. | `test_f1_link_commits_separate_review_and_rollback_retry` covers Asset/Interface/Network, injected failure, rollback/retry, distinct eligible follow-up, original UUID/configuration, audit and independent acceptance. `test_f1_concurrent_link_has_one_followup` covers Asset/Interface races. PASS. |
| F2 High | All eight supported fields were overwritten after normal HTTP PATCH; individual decisions returned 200 and bulk reported no failure. | Lock/reload canonical Asset before proposal validation; versions include current field and Asset update time (also detecting changed-back values). PATCH takes the same lock before reading old values. Versionless requests must match the stored canonical snapshot and cannot predate a newer Asset update. | Sixteen individual/bulk field cases; deterministic manual-lock-versus-acceptance race; unchanged/fresh proposals; partial bulk; changed-back value and legacy caller checks. Independent sessions confirm preserved manual value and open unaccepted proposal. PASS. |
| F3 High | Synchronized old accepted-set lookups both saw no winner; both HTTP decisions succeeded and two effective namespaced assertions persisted. | Canonical subject serialization across sources, refresh prior accepted flags after waiting, clear/flush replacement, complete scalar unique partial index. | Different/identical namespaced and core values, bulk versus individual, retraction and source supersession races, direct-index bypass checks, audit/Changes counts and lineage. Migration refuses retained duplicates without choosing a winner. PASS. |
| F4 Medium | Two simulated-source Asset link transactions reproduced PostgreSQL `DeadlockDetected` (40P01) in site-wide relationship resolution. | Refresh only source-local relationships referencing the linked external ID, with incidental identity persistence disabled. Prelock known canonical subjects; handle only expected database conflict states. | SQL source-lock barrier reproduces the old cycle; current requests both return 200, retain two correct immutable links, update both relevant relationship proposals and leave relationship acceptance independent. Safe 40P01/40001/55P03/23505 response tests and unknown-error propagation pass. |
| F5 Medium | Source A's identical re-observation returned 409 after selecting B; A remained source-current with acceptance replacement mislabelled source supersession. | Separate `acceptance_replaced_by_id` from source `superseded_by_id`; preserve current observations, coalesce eligible identical observations and preserve true source supersession. | A accept → B accept → A reobserve/reaccept, identical/changed repetition, rejected/retracted/superseded lifecycle, full HTTP ingestion with retained evidence and summary. PASS. |

The saved vulnerable working tree (not merely the older base commit) was copied
to temporary storage before edits. A separate fresh database at revision 0031 ran
24 selected probes: 23 behavioral failures and one expected new-column compatibility
failure. F3's vulnerable-copy SQL gate synchronizes the old accepted-set SELECT,
because the old code has no canonical row-lock gate. F4 uses the same source-lock
gate in both implementations. An identical-reobservation F5 test fails at the
original HTTP 409, before any new-column assertion. These expected failures are
reproduction evidence, not passing tests.

## C. Architecture and transaction boundaries

Production and the new committed-state fixture both use `SessionLocal` with
`autoflush=False`, `expire_on_commit=False`, PostgreSQL READ COMMITTED and separate
connections. The existing I3 fixture and old concurrency fixtures now use those
options too. A cancellation test explicitly flushes its intent before locked
authentication reload, matching the real request boundary; it no longer relies
on accidental fixture autoflush.

Individual decisions and identity links are atomic through commit. Required
follow-ups, source associations, Changes and security audit cannot commit
independently. Bulk explicitly retains valid per-item successes using savepoints.
Domain changes flush before the ancillary completeness savepoint, so an implicit
preflush failure cannot be swallowed by completeness error isolation.

Decision order is DataSources by UUID; canonical Asset, Network, Interface,
AssetRelationship, Service, Business Function rows in that model order and UUID
order; review items by UUID; assertions by UUID. All known bulk subjects and
Interface owners are acquired before item/assertion locks. Manual Asset PATCH
locks its Asset before reading previous values or declaring changes, without
acquiring a discovery-source lock. Ingestion takes its source lock before claims.
Retraction uses source → canonical subject → assertion. Low-level acceptance also
locks its subject. Prior accepted flags are refreshed after lock acquisition.

Asset linking never walks unrelated site relationships or locks another source.
Source identities remain immutable and source-local; canonical entity UUIDs stay
unchanged. Relationships remain separately accepted knowledge. A missing source
identity is not inferred from matching labels.

A single-valued canonical subject/predicate has at most one non-retracted accepted
assertion, even for identical values. All observations remain distinct. Serialized
namespaced selections may both succeed; the later decision is effective, and
both audit/Changes records remain. Canonical-field version checks may instead
reject the later stale decision. Retraction does not automatically select another
observation. Source supersession does not silently retract selected knowledge.

Expected SQLSTATE 23505, 40001, 40P01 or 55P03 yields a generic actionable 409
(individual) or failed bulk record. There is no automatic transaction retry;
refresh and review before retrying. Other database errors propagate. PostgreSQL
uniqueness remains authoritative even for code paths bypassing service checks.

Migration `20261101_0032` is additive and data-preserving. It preflights duplicate
accepted scalars before DDL and refuses conflicting retained choices. It adds an
indexed self-FK for acceptance replacement, moves still-current legacy replacement
edges there without losing their target, and expands the existing scalar index
according to the complete `predicate_cardinality` rule. True source supersession
is retained. No observation, historical decision or evidence is deleted.
Migration tests verify refusal, lineage preservation, uniqueness, multi-value
exclusions and downgrade. Head expectations in packaging, I3 migration and backup
tests advance deliberately; committed migrations remain unchanged.

The [decision record](../../decisions/0017-reconciliation-knowledge-integrity.md)
contains the full contract. Neither PostgreSQL authority nor discovery authority
changes. No new queue, plugin, dependency or parallel knowledge store is added.

## D. Security and data integrity review

Scoped `reconciliation.decide`, active customer/site context and the existing
technical edit/relationship permissions remain backend requirements. Source/target
customer/site and accepted Interface owner checks remain independent of frontend
candidate filtering. Hidden target names and raw database error details are not
returned. Canonical scope is checked again before applying Asset fields.

Different sources converge on the same canonical subject lock. Source identity
uniqueness/scoped foreign keys and the scalar index remain database boundaries.
The replacement query now explicitly includes customer/site; unresolved external
subjects remain source-scoped. The decision's canonical value cannot be read from
a stale identity map after waiting. Manual changes and reconciliation share the
Asset serialization boundary.

Acceptance replacement never closes another source's current claim. True source
supersession, rejected decisions, retraction, evidence, source provenance, Changes
and security audit remain preserved. Lifecycle deletion safety counts both source
and acceptance replacement references. Reacceptance keeps prior replacement
lineage and full decision history. No security checks, signing policy, connector
provenance or protected enrollment are altered.

The new route fixture overrides only database session, principal acquisition and
active context. Real FastAPI permission/scope dependencies and HTTP routes run;
this is not a login/session-authentication acceptance test. Existing tenancy and
permission negative tests run with the corrected PostgreSQL fixture. The browser
uses intercepted synthetic APIs and is distinct from backend authorization proof.

## E. Implementation inventory

The initial status contained 24 modified and six untracked files; all were
preserved. A SHA-256 inventory and saved vulnerable API were recorded before any
edit. Existing frontend, knowledge-summary, deployment and unrelated operator
changes remain byte-identical to that starting inventory. Remediation is layered
onto the existing feature branch without resets, checkout changes or commits.

| Remediation files | Purpose |
| --- | --- |
| `apps/api/app/models.py`; `apps/api/app/schemas.py` | Acceptance-lineage FK, complete scalar index and additive response field. |
| `apps/api/app/routes/assets.py` | Manual PATCH canonical row lock and refresh before deriving declarations. |
| `apps/api/app/routes/knowledge.py` | Shared target/source lock order, post-lock version validation, safe conflicts, domain flush and retraction serialization. |
| `apps/api/app/services/knowledge_locks.py` | Reusable canonical subject lock order. |
| `apps/api/app/services/knowledge_assertions.py` | Cross-source acceptance serialization, refreshed replacement, source-scoped unresolved subjects and independent lineage. |
| `apps/api/app/services/knowledge_lifecycle.py` | Preserve deletion safety across both lineage dimensions. |
| `apps/api/app/services/reconciliation.py` | Explicit link flushes; bounded source-local relationship refresh. |
| `apps/api/app/services/reconciliation_entities.py` | Canonical field/time version tokens and fresh Asset loading. |
| `apps/api/app/services/simulated_discovery.py` | Source-before-claims ingestion locking. |
| `apps/api/migrations/versions/20261101_0032_knowledge_acceptance_integrity.py` | Fail-closed preflight, acceptance lineage and complete unique index. |
| `apps/api/tests/test_reconciliation_integrity_postgres.py`; `test_knowledge_integrity_migration.py` | 54 new mandatory HTTP/state/race/migration regressions. |
| `apps/api/tests/test_i3_discovery.py`; `test_cross_source_reconciliation.py`; `test_reconciliation_entities.py`; `test_knowledge_lifecycle.py` | Production-equivalent sessions, explicit persistence before reload and locked lifecycle mock. |
| `apps/api/tests/test_models.py`; `test_release_distribution.py`; `test_i3_migration_postgres.py`; `test_backup_postgres.py` | Deliberate new-column/head expectations. |
| Architecture, admin and ledger files listed below; ADR 0017/index; historical acceptance archive; this report | Correct contracts and withdraw unsupported earlier acceptance claims. |

Routes and existing payload shapes are retained. Proposal version tokens are
opaque and now deliberately invalidate older canonical field reviews. Assertion
responses add nullable `acceptance_replaced_by_id`. No production or frontend
dependency changes. No frontend source changes were needed for the remediation.
The exact complete modified/untracked inventory appears at the end of this report.

## F. Test matrix and environment

Native PostgreSQL 17.11 on a new cluster below
`/private/tmp/atlas-f1-f5-remediation`, loopback port 55483. Two initial databases
separate vulnerable reproduction from development. Final verification provisions
CI's fifteen database categories under new NOSUPERUSER/NOCREATEDB/NOCREATEROLE
`atlas_remediation_final_app`: five migrated and ten initially empty. The final
main DB is `remediation_final_domain`; focused verification used the equivalent
earlier `atlas_remediation_app` / `remediation_domain` database. Production-equivalent session options apply.
Dedicated `atlas-f1-f5-redis` uses `redis:7.4.6-alpine` on loopback port 56393.
No existing application database, Redis instance or acceptance deployment is used.
Python 3.14.7, existing API virtualenv; Node 24.19.0 and existing frontend packages;
installed Chrome with temporary Playwright outside the repository.

Final backend commands run from `apps/api` after sourcing the protected temporary
`verified-final.env` produced by `provision-final.py`. It sets the fifteen `ATLAS_TEST_*` URL
variables using only the new disposable role, plus `DATABASE_URL`, `REDIS_URL` and
`ATLAS_TEST_H3_REDIS_URL`. The fresh five databases were migrated with
`DATABASE_URL=<disposable-url> .venv/bin/python -m alembic upgrade head`.

```bash
.venv/bin/python -m pytest tests/test_reconciliation_integrity_postgres.py tests/test_knowledge_integrity_migration.py tests/test_cross_source_reconciliation.py tests/test_knowledge_foundation.py tests/test_reconciliation_entities.py tests/test_asset_knowledge_summary.py tests/test_source_identity.py tests/test_i3_discovery.py tests/test_reconciliation_listing.py tests/test_knowledge_lifecycle.py -q --tb=short --junitxml=/private/tmp/atlas-f1-f5-remediation/focused-final.xml
.venv/bin/python -m pytest -q -rs --tb=short --junitxml=/private/tmp/atlas-f1-f5-remediation/backend-final.xml
```

| Executed command / evidence | Result |
| --- | --- |
| Focused command above | 249 passed, 0 failed, 0 skipped; fresh non-superuser database. Includes 53 integrity HTTP/race cases and one migration-safety case. |
| Complete backend command above | 2,461 passed, 0 failed, 178 skipped; 221.28 seconds. All fifteen PostgreSQL database categories enabled; mandatory integrity tests executed. |
| Earlier complete backend with only domain DB enabled | 2,379 passed, two schema-expectation failures, 254 skipped. The stale model-column and package-head expectations were corrected; this earlier run is not acceptance. |
| `npm test` from `apps/web` | 329 passed, 0 failed/skipped. Includes reconciliation and AK-01/AK-02 tests. |
| `npm run build` from `apps/web` | Production build passed. |
| Browser command below | 36 viewport/theme/accent states passed; keyboard links, stale refresh, navigation, AK-01/AK-02/provenance/History/Raw; zero reported runtime errors/overflow. Desktop knowledge and mobile technical-link screenshots inspected. |
| `apps/api/.venv/bin/python -m pytest docs/architecture/integrations/contracts/tests -q --tb=short` from root | 77 passed, 0 failed/skipped. |
| `apps/api/.venv/bin/python -m pytest apps/api/tests/test_repository_docs.py apps/api/tests/test_ci_workflow.py apps/api/tests/test_models.py -q --tb=short` from root | 43 passed, 0 failed/skipped; repeated after final report completion. |
| `.venv/bin/python -m pytest tests/test_reconciliation_integrity_postgres.py tests/test_knowledge_integrity_migration.py -q --tb=short --junitxml=/private/tmp/atlas-f1-f5-remediation/integrity-final.xml` | 54 passed, 0 failed/skipped. Final deterministic source-lock barrier and actual rejected assertion lifecycle included. |
| `.venv/bin/alembic heads` from `apps/api` | Exactly one head: `20261101_0032`. |
| `apps/api/.venv/bin/python -m compileall -q apps/api/app apps/api/migrations apps/api/tests` from root | Passed. |
| `git diff --check` | Clean at review; repeated at final handoff. |

Browser command from `apps/web`:

```bash
ATLAS_PLAYWRIGHT_MODULE=/private/tmp/atlas-reconciliation-browser-tools/node_modules/playwright/index.mjs \
ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
ATLAS_BROWSER_BASE_URL=http://127.0.0.1:3153 \
ATLAS_BROWSER_OUTPUT=/private/tmp/atlas-f1-f5-remediation/browser \
node scripts/check-reconciliation-browser.mjs
```

The 178 skips are not passes and none is an F1–F5 test:

| Count | Environment absent in this native run | Responsible enforced CI coverage |
| --- | --- | --- |
| 83 | Root inside a dedicated disposable Linux container: local-release authority/recovery/remediation. | Backend job's separate root-only Docker regression, no-skips enforced. |
| 27 | Exact installed/pinned Ansible runtime: I3 live (6), I4A (1), I4B (12), I4C diagnostics (8). | Backend job installs its isolated pinned runtime before ordinary regression. |
| 68 | nginx >=1.28 executable. | Backend job installs test nginx before ordinary regression. |

The earlier 76 skips for empty migrations, setup/MFA and backup source/target
fixtures were removed by provisioning their dedicated databases. All of those
suites executed successfully in the final complete run. The conditional result
retains the 178 platform/runtime limitations; it does not waive new integrity gates.

Race coverage uses independent request sessions/connections and SQL barriers or
explicit events, with bounded waits and database timeouts. F3 gates both canonical
lock attempts; F4 gates independent source-lock attempts. F2 holds the manual
Asset lock until reconciliation reaches its competing lock attempt. No arbitrary
sleep is used as the concurrency proof. Checks reopen independent sessions after
commit to inspect canonical values, source links, effective/source-current flags,
replacement lineage, decision statuses, Changes, audit and retained evidence.

CI's existing **Backend / PostgreSQL** job provisions all fifteen database URLs,
runs `pytest tests` (including both new automatically collected test modules), and
fails on any JUnit skip. The production-session fixture is used by ordinary
cross-source/entity/knowledge suites. Neither new suite adds an optional custom
flag: `ATLAS_TEST_DATABASE_URL` is the existing mandatory CI domain environment.
CI already enforces no skips and exactly one migration head; no workflow
infrastructure change is needed. CI itself has not been remotely run or claimed.

Temporary evidence includes initial status/hashes, vulnerable API copy, migration
logs, expected-failure logs, final JUnit/logs and browser report/screenshots. These
synthetic development artifacts are outside the repository. Baseline and final
runs use separate databases. No passing command with skipped F1–F5 tests counts
as acceptance; the 54 new tests all executed in the focused run.

## G. Original feature regression

| Feature | Verdict / evidence |
| --- | --- |
| Asset linking | PASS: retains UUIDs, immutable source links, explicit conflicting name/field reviews and repeat-discovery identity. |
| Interface linking | PASS: retains owner/UUID/configuration until independent decision; follow-up, duplicates, prerequisites, scope and races. |
| Network linking | PASS: independent source identity and configuration review; customer/site and candidates enforced. |
| Bulk acceptance | PASS: phase prerequisites, independent valid successes, stale failures, per-item audit and concurrent individual decisions. |
| AK-01 | PASS: agreeing unaccepted observations do not imply unresolved/accepted knowledge; canonical consistency and conflicts remain explicit; full A→B→A HTTP lifecycle refreshes the summary. |
| AK-02 | PASS: scoped semantic Runs On targets, equivalent-target grouping, same-named distinct targets, per-source provenance and retained History/Raw. |

Evidence: existing 34 cross-source, 25 entity, 33 knowledge-foundation, 29 listing,
19 Asset-summary and six source-identity tests, plus the new integrity tests,
frontend suite and intercepted browser checks. No live Connector acceptance is
inferred from these results.

## H. Documentation

Updated `docs/architecture/reconciliation-entity-review.md`,
`docs/architecture/knowledge-changes-and-reconciliation.md`,
`docs/admin/cross-source-reconciliation.md`, `docs/product/feature-ledger.md` and
this testing report. Added ADR 0017 and its index entry, preserving existing ADRs.
The withdrawn initial acceptance is retained in `docs/history/validation` with a
clear supersession warning. The ledger links verification/limits instead of
claiming live operational acceptance or deployment compatibility.

## I. Residual risks and supported limitations

1. Migration refuses any retained duplicate accepted scalar choices. A human must
   review a data correction before migration; it never selects or deletes a claim.
   This has not been run against the protected live acceptance database.
2. Live enrolled exact-build transition remains a separate unresolved engineering
   issue. No deployment, build binding, enrollment, signing key or Sigstore change
   was made. Synthetic acceptance is not live Proxmox/native qualification.
3. Local broader test environments and skips are reported in the final matrix.
   No mandatory F1–F5 test is waived. CI's own enforced no-skip run remains a human
   Git/PR handoff activity.
4. Versions conservatively invalidate canonical-field reviews after any Asset
   row update. Legacy callers without a version use the persisted canonical value
   snapshot and reject newer Asset row timestamps; they should send the freshly reviewed version for intentional
   reconsideration. Bulk transactions intentionally allow partial success.
5. The scalar index covers canonical IDs. Unresolved external IDs remain distinct
   source-local identities until explicit resolution. Future cardinality changes
   require an index migration. PostgreSQL table/index migration locking must be
   planned for a maintenance window at deployment scale.
6. Existing archived-run suppression/contributing-run provenance limitations remain
   deferred. Coalescing keeps raw evidence and latest assertion evidence pointers;
   it does not invent a complete per-assertion contributing-run history.

## J. Independent review handoff

Challenge source → canonical → review → assertion order across manual PATCH,
individual/bulk decisions, technical ownership, retraction and ingestion. Verify
that newly added acceptance paths also acquire the subject boundary before
assertion locks, and that relationship refresh cannot acquire another source.
Repeat F3's race against the old copy and confirm two effective scalar values;
repeat F4's source-lock barrier and confirm the old PostgreSQL deadlock. Confirm
new behavior through independent connections rather than identity-map state.

Review migration preflight against a copy of real retained data, especially
previously duplicated scalar acceptances and still-current legacy replacement
edges. Challenge unknown scalar/object/interface predicate classification, fresh
review after manual changes, and A→B→A source freshness/acceptance lineage. Inspect
audit/Changes and source evidence after failed links, conflict responses and bulk
partial successes. Confirm hidden customer/site targets cannot be enumerated.

The human operator retains commit, push, PR and deployment authority. No commit,
push, reset, rebase, tag, PR, live database update, enrollment change or deployment
was performed. Final exact repository state follows.

## Repository state

`git status --short` at handoff (36 modified, 12 untracked files, including the
24 modified and six untracked files present before this remediation):

```text
 M apps/api/app/models.py
 M apps/api/app/routes/assets.py
 M apps/api/app/routes/changes.py
 M apps/api/app/routes/knowledge.py
 M apps/api/app/schemas.py
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
?? apps/api/tests/test_asset_knowledge_summary.py
?? apps/api/tests/test_cross_source_reconciliation.py
?? apps/api/tests/test_knowledge_integrity_migration.py
?? apps/api/tests/test_reconciliation_integrity_postgres.py
?? apps/web/components/asset-knowledge-summary.js
?? apps/web/tests/asset-knowledge-summary.test.mjs
?? docs/admin/cross-source-reconciliation.md
?? docs/decisions/0017-reconciliation-knowledge-integrity.md
?? docs/history/validation/cross-source-reconciliation-pre-remediation.md
?? docs/testing/cross-source-reconciliation.md
```
