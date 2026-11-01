# Cross-source reconciliation — R4-N1 Network/Interface remediation

Date: **2 November 2026** (Pacific/Auckland).
Branch: `fix/reconcilliation-fixes`.
HEAD/base: `af32da2d3153e48feeec26adb91c64e7732e36a0`.
Evidence: `/private/tmp/atlas-r4-remediation.q_tn9r_x/`.

## A. Executive verdict

**PASS for the requested reconciliation code-integrity remediation.** All three
independent natural-deadlock reproductions are eliminated in permanent regression
coverage. R1/R2/R3/R5 and all original 54 integrity gates remain green. Final
focused validation: **390 passed, no skips/failures**. Complete backend/SDK/Proxmox:
**2,609 passed, 178 environmental skips, no failures**. Final strengthened
persisted-state assertions in all **17 new gates** passed separately as well.

This is engineering acceptance for the implemented scope. Platform-specific
GitHub CI qualification remains **NOT VERIFIED**, and the separate enrolled
exact-build deployment transition remains **not approved**. Neither is implied by
this code-integrity verdict. No Git mutation, PR or deployment action occurred.

The earlier broad R4 acceptance claim was disproved by the final independent
review. That report and its evidence under
`/private/tmp/atlas-independent-final-review/` remain unchanged. The prior
engineering record is [archived with its R4 claim withdrawn](../history/validation/cross-source-reconciliation-before-r4-n1.md).
Earlier F1–F5 and pre-remediation archives remain intact.

## B. Finding disposition and before/after evidence

| Finding/scenario | Confirmed cause | Correction and permanent evidence | Result |
| --- | --- | --- | --- |
| R4-N1 Network ingestion versus cross-source acceptance | Technical ingestion locked its source and updated assertion A, then tried to mark B conflicted. Acceptance held the canonical Network and B, then waited to replace A. | `lock_ingestion_subjects` acquires the source and existing scoped canonical subjects before claims. `test_technical_ingestion_acceptance_lock_graph[decision-network]` and `[ingest-network]` use real independent PostgreSQL connections and HTTP acceptance. Both source and acceptance lineage, UUIDs, selected values, exact Changes values, source links and actor audit are inspected after commit. | **PASS** |
| R4-N1 Interface ingestion versus cross-source acceptance | Same assertion-row cycle, with an Interface and its owner Asset required for canonical ordering. | Shared prelock includes the linked Interface owner and observed owner/Network references, then Interface in the established model/UUID order. Both Interface transaction orders run in the same permanent module. | **PASS** |
| Third independent reproduction: authenticated HTTP Network completion versus HTTP acceptance | AIP finalisation called Asset ingestion and then the separate technical path; a Network-only payload never entered the Asset prelock. Natural 40P01 escaped completion as HTTP 500. | AIP prelocks all referenced canonical subjects across all batches/domains before any claims. `test_actual_http_network_finalisation_vs_acceptance` uses the real run-token authenticator, actual batch/completion routes, actual review/acceptance routes, production sessions and fresh SQL inspection. Both requests return 200 with no SQLSTATE conflict. | **PASS** |
| R1 canonical review/Changes | Previously corrected live canonical snapshots and exact legacy baseline validation. | All eight fields, individual/bulk, stale/changed-back/overlapping PATCH, missing baseline and cross-site tests rerun. No implementation changes to their snapshot/version/acceptance code in this increment. | **PASS** |
| R2 lifecycle safety | Previously corrected absence versions and explicit consistent status declarations. | Every disposition, stale/versionless states, selected status/history, keep/exception behavior and final summary wording rerun. | **PASS** |
| R3 legacy migration classification | Conservative provable-history classification and fail-closed ambiguity. | All 27 complete-schema migration tests rerun; migration and frozen baseline helpers are unchanged. | **PASS** |
| R5 downgrade preservation | Dual or otherwise unrepresentable lineage refuses before mutation. | Lossless round trips and atomic refusal/usable-database cases rerun; no migration change. | **PASS** |

Before changing implementation, copied independent scripts (only output paths
redirected to this evidence root) reproduced **all three failures**:
`reproductions-before.log/xml`. Both technical requests recorded natural `40P01`;
full HTTP completion returned **500**, acceptance **200**. PostgreSQL's own
`pg.log` records the two assertion UPDATE participants. The original old/source
successor write rolled back; no new claim or finalisation seal committed, and
staged evidence remained.

The new permanent tests were executed before the fix as well:
`permanent-before-final.log/xml` has **five failures**, covering the two technical
kinds in both orderings and the full HTTP scenario. Their vulnerable states and
assertion-row deadlock participants match the independent evidence. Permanent
tests import no temporary scripts or paths.

After the fix, the 17 new permanent cases pass. Synchronization accepts either a
canonical lock attempt (corrected path) or the original claim UPDATE (vulnerable
path); it does not require a waiting transaction to write while its holder is
paused. Synthetic UUID ordering fixes legitimate SQLAlchemy flush order for the
counterexample. No lock implementation is mocked and no SQLSTATE is raised in
these natural no-deadlock races.

When acceptance acquires its canonical lock first, acceptance and ingestion both
succeed. When ingestion commits first, marking the pending B proposal conflicted
changes its reviewed epoch. Acceptance safely returns **409** for the old token,
with no acceptance Change/audit; a fresh, explicitly reviewed request then
succeeds. This preserves freshness rather than weakening versions to force two
200 responses.

Initial test-development attempts are retained honestly: one invocation used the
wrong working directory; the first permanent HTTP gate observed the upstream
Integration lock too early and was tightened to the canonical Network before the
five-failure run. The first after-fix run had 80 passes/two assertion failures
because ingestion-first appropriately returned 409; tests now require that stale
refusal and explicit refresh. No production behavior was weakened to satisfy a
test, and the no-natural-deadlock invariant remained mandatory throughout.

## C. Architecture, explicit/implicit locks and transaction assessment

PostgreSQL remains the system of record. Production `SessionLocal` still uses
`autoflush=False`, `expire_on_commit=False` and READ COMMITTED. No new graph store,
worker, queue, retry mechanism, global mutex or persistent lock state is added.

The reproduced cycle was:

```text
Acceptance B                         Technical ingestion A
source B NO KEY UPDATE               source A NO KEY UPDATE
canonical Network/Interface UPDATE
item B UPDATE
assertion B UPDATE                   update old assertion A (source supersession)
wait: replace accepted assertion A   wait: mark current assertion B conflicted
              B-claim -> A-claim -> B-claim
```

Source/Run NO KEY UPDATE compatibility already fixed other FK cycles. It cannot
resolve contradictory acquisition of A/B assertion rows after one path skips
canonical serialization.

The corrected ordering is:

```text
Upstream Integration writer -> Run NO KEY UPDATE (existing admission policy)
  -> source NO KEY UPDATE (existing writer serialization)
  -> referenced Assets by UUID (including Interface owners/relationship endpoints)
  -> referenced Networks by UUID
  -> referenced Interfaces by UUID
  -> review item/claim locks or ingestion claim writes
  -> source history / selected-set replacement / Changes / audit / caller commit
```

`lock_ingestion_subjects` resolves only exact existing source/customer/site/type/
external-ID links. It reuses `lock_subjects`' model/UUID order and reload behavior.
It neither infers identities nor accepts knowledge. AIP supplies the full set
across **all receipts and domains** before its first Asset or technical claim;
later per-observation calls reacquire subsets. This prevents a larger Network
UUID in an earlier payload batch from preceding a smaller later one, and prevents
an Interface owner Asset being discovered while already holding Network/claim
locks. Complete-snapshot current/baseline Asset identities are included before
later absence/re-observation work. Simulation retains the same source/Asset
ordering through the shared helper.

Three blocking-holder HTTP tests verify that no assertion INSERT/UPDATE occurs
before the whole relevant set is acquired: later-batch smaller Network UUID,
later Interface owner Asset, and an omitted complete-snapshot baseline Asset.
The latter remains active and receives only an individual open absence review.
The two unrelated-entity tests hold ingestion's target and still commit an edit
to an unrelated Network or an Interface on a different owner with a bounded lock
timeout. Same-source writer serialization and shared-owner ordering are retained;
no site-wide canonical lock is introduced.

Implicit FK dependencies remain part of the contract. Assertion/source-link,
Changes and evidence writes can acquire KEY SHARE on DataSource, Run, canonical
entities, evidence, customer/site and actor identities. Source and Run writer
NO KEY UPDATE still permits these immutable-identity FK reads and excludes
competing writers. Canonical subjects are locked before cross-source assertion
updates and successor-FK writes. Interface owners precede Interface locks;
relationship endpoint Assets precede relationship materialization. Existing
Asset/manual-source and Run/source/provenance races remain green.

The authenticated ingestion request now wraps admission through commit in the
existing `decision_conflicts` boundary. Only SQLSTATE **23505, 40001, 40P01,
55P03** rolls back and returns generic **409**. There is no automatic retry.
Unknown database failures propagate. Actual HTTP lock timeout verifies rollback
and an explicit caller resubmission; separate post-flush PostgreSQL abort tests
verify each known state and an unknown 08006. These injected fallback checks are
labelled separately from the natural races and are not proof of deadlock removal.
Failed finalisation retains staged evidence/receipts, Run status/seal, source
success/error timestamps, assertions, Changes and audit exactly as before.

All canonical discovery writers were inspected: Asset/scalar and relationship
normalization in `ingest_observations`; technical configuration and namespaced
facts in `ingest_technical_observation`; AIP cross-domain finalisation; and complete
snapshot absence/re-observation. Their relevant referenced sets are acquired
before phase writers. Existing reconciliation and retraction use the established
source/canonical ordering. This is bounded row serialization, not a guarantee
that no future code or arbitrary database operation can ever cause a conflict.

## D. Database and migration assessment

**No migration was required or changed.** Model/schema and source/acceptance
lineage definitions are unchanged. The single Alembic head remains
`20261101_0032`; the migration file and frozen actual 0031 helpers match handoff
hashes. All 27 full-schema migration gates pass in the focused and complete runs.

Provable source/acceptance histories round-trip; overwritten or ambiguous legacy
history refuses atomically at 0031 without guessed edges. Dual/equal-target and
other unrepresentable downgrades refuse with 0032 and both lineages intact. The
conservative maintenance-window contract and duplicate accepted-scalar preflight
remain unchanged. No deployed migration/schema was accessed, no winner selected
and no historical record deleted. Production-volume migration timing remains
outside this remediation's verification.

## E. Security, knowledge integrity and tenant isolation

Source ownership and customer/site checks are enforced by the backend and the
prelock's exact scoped link lookup, backed by existing context/owner FKs. The new
negative source-context/reference test confirms no canonical row is acquired for
an unreferenced identity or mismatched source context. Existing permission,
active-context, cross-customer/site, ownership and immutable-link API tests pass.

Canonical Asset/Interface/Network UUIDs and source-scoped identities are preserved.
Discovery still creates observations/reviews; it does not select its changed
configuration automatically. Both lineages and original assertion values survive
serialized races. Selected B matches the unchanged canonical configuration after
explicit acceptance. Tests inspect exact Changes predecessor/successor, successful
actor audit, retained evidence and both immutable source links. Failed/stale
requests do not publish misleading acceptance records.

Integration admission, generation/token binding, cancellation, lease controls,
credential isolation, run state policy and execution authorization are unchanged.
The only new route behavior is rollback/409 for expected transaction conflicts,
including admission lock conflicts. The full HTTP regression uses a synthetic
configured Integration and real run-token authentication in isolated pytest
storage. Principal/context acquisition in normal fixture routes is overridden,
while real scope/permission code executes; this is not end-to-end login or live
runtime qualification.

No protected installation, database, keys, enrollment, volumes, credentials or
services were accessed. No secret, authority material or source value is included
in the new generic conflict response. No plugin/catalogue/verifier or vendor
normalization policy is changed.

## F. Material files changed and compatibility

These **13 incremental files** implement this task; all earlier operator work is
preserved. The evidence contains before copies/hashes and `incremental.patch`
separating these edits from the existing dirty tree.

| File | Incremental purpose |
| --- | --- |
| `apps/api/app/services/knowledge_locks.py` | Shared scoped source/canonical prelock using existing model/UUID order; explicit/implicit order documentation. |
| `apps/api/app/services/simulated_discovery.py` | Reuse shared Asset ordering and add technical target/owner/Network serialization before claims. |
| `apps/api/app/services/aip_ingestion.py` | Gather the complete known set across batches/domains before phase writers. |
| `apps/api/app/services/discovery_observations.py` | Read matching current/baseline Asset identities for early complete-snapshot locking. |
| `apps/api/app/routes/integration_discovery.py` | Wrap existing authenticated ingestion through commit in shared rollback/known-conflict handling. |
| `apps/api/tests/test_reconciliation_technical_locking_postgres.py` | Seven permanent production-session gates: both kinds/orders, unrelated writes and scoped reference/context locking. |
| `apps/api/tests/test_reconciliation_ingestion_http_postgres.py` | Ten permanent full HTTP gates: exact third reproduction, natural lock-timeout, five post-flush error states and three whole-run ordering boundaries. |
| `docs/architecture/knowledge-changes-and-reconciliation.md` | Technical/batch ordering, known conflict behavior and preserved knowledge semantics. |
| `docs/architecture/reconciliation-entity-review.md` | Matching review/ingestion serialization and stale-after-ingestion behavior. |
| `docs/decisions/0017-reconciliation-knowledge-integrity.md` | Dated implementation clarification enforcing the existing accepted ordering; original decision text retained. |
| `docs/product/feature-ledger.md` | Truthful whole-run prelock and controlled ingestion-conflict guarantee; pagination follow-up retained. |
| `docs/history/validation/cross-source-reconciliation-before-r4-n1.md` | Preserve the earlier engineering record, explicitly withdrawing its disproved broad R4 claim. |
| `docs/testing/cross-source-reconciliation.md` | Current complete A–J report and executed evidence. |

Successful API payloads, routes and schemas remain unchanged. Expected ingestion
transaction conflicts intentionally return 409 where the reproduced completion
previously returned 500; other existing error behavior remains. No UI component,
CSS, selector, frontend contract, dependency or migration change is made.

## G. Tests, commands and evidence

Fresh PostgreSQL **17.11 UTF-8**, loopback **55686**, ordinary `r4_review` and
`r4_full` owners (NOSUPERUSER/NOCREATEDB/NOCREATEROLE), READ COMMITTED; production
session settings asserted. Two sets of fifteen disposable CI-category databases
were prepared. New volume-free Redis **7.4.6**, loopback **56686**. Python **3.14.7**,
Node **24.19.0**, macOS arm64. Observed details: `environment.json`.
All Python runs disable bytecode/cache; compilation redirects bytecode outside the
repository. Synthetic fixture authority stays in temporary pytest storage.

| Executed validation | Result | Evidence |
| --- | --- | --- |
| Three original independent probes, before fix | **3 failures**, natural 40P01; HTTP completion 500 | `reproductions-before.log/xml`, `pg.log`, `technical-*.json`, `http-finalisation-race.json` |
| Permanent before-fix races | **5 failures**, both technical kinds/orders plus HTTP | `permanent-before-final.log/xml` |
| Final focused reconciliation/integrity/migration/fleet suite | **390 passed, 0 failed/skipped** | `focused.log/xml` |
| Complete backend/SDK/Proxmox | **2,609 passed, 178 skipped, 0 failed** | `backend.log/xml`, `skips.json` |
| Final strengthened new gates | **17 passed, 0 failed/skipped** | `final-gates.log/xml` |
| Frontend regression | **330 passed, 0 failed/skipped** | `frontend.log` |
| Architecture contracts | **77 passed** | `contracts.log/xml` |
| Final docs/Markdown/CI contracts | ****33 passed**** | `docs.log/xml` |
| Workflow lint | Both workflows exit 0 | `actionlint.log` |
| Python compilation | Exit 0, temporary pycache only | Command below |
| Alembic heads | Exactly `20261101_0032` | Executed `alembic heads`; observed migrated revision in `environment.json` |
| Whitespace | Clean `git diff --check` | Executed after final edits |

The complete application-code run was followed by stronger exact Changes/audit/
source-link assertions in the test files; all 17 final gates were rerun after
those assertion-only changes. No application behavior changed after the focused
or complete application-code runs. The earlier 389-case focused run predates the
additional complete-snapshot test; only the final 390-case result is quoted above.
Intermediate logs remain evidence, not substitutions for final results.

All original **54 integrity gates** remain intact (53 original PostgreSQL cases
plus the original migration acceptance gate). Expanded migration tests remain 27,
and final R1/R2/R4 tests remain 77. The 17 new tests are collected by normal
`pytest tests` under existing CI PostgreSQL provisioning; no optional flag, new
service or new CI permission is required. Existing CI rejects mandatory skips.

All **178 skips** are explicit environmental exclusions, not passes:

| Count | Reason / modules |
| --- | --- |
| 83 | Linux/root disposable-container local-release authority (18), recovery (32), remediation (33). |
| 27 | Exact pinned Ansible runtime absent: I3 live (6), I4A (1), I4B (12), I4C diagnostics (8). |
| 68 | nginx >=1.28 / `ATLAS_TEST_NGINX` unavailable. |

The checked-in Linux CI installs these dependencies and exercises root-container
qualification separately. Workflow/contract lint validates configuration only;
no remote GitHub CI result is claimed. Production frontend build/browser checks
were not rerun in this increment because frontend implementation is unchanged;
earlier browser evidence is historical, not a new execution claim.

Exact main commands (from `apps/api`, except where noted):

```bash
source /private/tmp/atlas-r4-remediation.q_tn9r_x/review.env
.venv/bin/python -m pytest -p no:cacheprovider \
  /private/tmp/atlas-r4-remediation.q_tn9r_x/test_independent_attacks.py \
  /private/tmp/atlas-r4-remediation.q_tn9r_x/test_independent_http_ingestion.py \
  -q -s --tb=short --basetemp=/private/tmp/atlas-r4-remediation.q_tn9r_x/reproduction-temp \
  --junitxml=/private/tmp/atlas-r4-remediation.q_tn9r_x/reproductions-before.xml

.venv/bin/python -m pytest -p no:cacheprovider \
  tests/test_reconciliation_technical_locking_postgres.py \
  tests/test_reconciliation_ingestion_http_postgres.py \
  tests/test_reconciliation_final_integrity.py tests/test_knowledge_integrity_migration.py \
  tests/test_reconciliation_integrity_postgres.py tests/test_cross_source_fleet_postgres.py \
  tests/test_cross_source_reconciliation.py tests/test_knowledge_foundation.py \
  tests/test_reconciliation_entities.py tests/test_asset_knowledge_summary.py \
  tests/test_source_identity.py tests/test_i3_discovery.py tests/test_reconciliation_listing.py \
  tests/test_knowledge_lifecycle.py tests/test_discovery_diagnostics.py \
  tests/test_discovery_diagnostics_concurrency_postgres.py -q --tb=short \
  --basetemp=/private/tmp/atlas-r4-remediation.q_tn9r_x/focused-final-temp \
  --junitxml=/private/tmp/atlas-r4-remediation.q_tn9r_x/focused.xml

source /private/tmp/atlas-r4-remediation.q_tn9r_x/full.env
PYTHONPATH=/Users/Ben/Code/atlas/plugins/sdk:/Users/Ben/Code/atlas/plugins/proxmox \
  .venv/bin/python -m pytest -p no:cacheprovider tests ../../plugins/sdk/tests \
  ../../plugins/proxmox/tests -q -rs --tb=short \
  --basetemp=/private/tmp/atlas-r4-remediation.q_tn9r_x/backend-temp \
  --junitxml=/private/tmp/atlas-r4-remediation.q_tn9r_x/backend.xml

source /private/tmp/atlas-r4-remediation.q_tn9r_x/review.env
.venv/bin/python -m pytest -p no:cacheprovider \
  tests/test_reconciliation_technical_locking_postgres.py tests/test_reconciliation_ingestion_http_postgres.py \
  -q --tb=short --basetemp=/private/tmp/atlas-r4-remediation.q_tn9r_x/final-gates-temp \
  --junitxml=/private/tmp/atlas-r4-remediation.q_tn9r_x/final-gates.xml

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider \
  tests/test_repository_docs.py tests/test_markdown_docs.py tests/test_ci_workflow.py \
  -q --tb=short --junitxml=/private/tmp/atlas-r4-remediation.q_tn9r_x/docs.xml
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m alembic heads
# apps/web
npm test
# repository root
PYTHONDONTWRITEBYTECODE=1 apps/api/.venv/bin/python -m pytest -p no:cacheprovider \
  docs/architecture/integrations/contracts/tests -q --tb=short \
  --junitxml=/private/tmp/atlas-r4-remediation.q_tn9r_x/contracts.xml
/private/tmp/atlas-phase4b2-tools/actionlint .github/workflows/ci.yml .github/workflows/release.yml
PYTHONPYCACHEPREFIX=/private/tmp/atlas-r4-remediation.q_tn9r_x/pycache \
  apps/api/.venv/bin/python -m compileall -q apps/api/app apps/api/migrations apps/api/tests
git diff --check
```

## H. Original feature and fleet regression

Asset, Interface and Network explicit linking, independent configuration/fact
reviews, dependent prerequisites, bulk partial success, re-observation and AK-01/
AK-02 knowledge/relationship presentation remain covered by the focused/full
backend and frontend runs. No accepted knowledge is silently replaced by linking
or discovery. Canonical fields and selected status remain protected by reviewed
versions and shared canonical serialization.

The synthetic permanent fleet runs in focused/full suites with production request
sessions and fresh post-commit reads. Its verified input map retains **34 Asset
UUIDs, 34 Interface UUIDs, one reused Network, 33 relationships and 138 explicit
source links**. It accepts 169 independent reviews, retains 102 original Source B
evidence records, reaches 204 after repeat discovery and creates **zero renewed
identity proposals**. Counts describe synthetic fixture input, not a live estate.

## I. Residual risks and limitations

1. **No reproduced mandatory reconciliation blocker remains.** Finite synchronized
   tests do not prove arbitrary future database schedules. Preserve canonical
   ordering when extending ingestion domains; per-row fixes without a complete
   multi-entity set can reintroduce cycles.
2. **Platform CI qualification remains outstanding:** all 178 local skips above
   require the appropriate environment. No skip is counted as a pass.
3. **Exact-build deployment transition remains separate and unapproved.** The
   protected installation is bound to its existing build/authority. This work
   does not authorize deployment, enrollment/key changes or identity spoofing.
4. **Migration limitations remain intentional:** maintenance locking, conservative
   historical refusal, restricted downgrade and no production-volume benchmark.
5. **AK-HISTORY-PAGINATION remains planned, out of scope.** Raw defaults to 200
   (API maximum 1,000); Fact History caps at 500; Asset detail pages neither.
   Summary may count more retained records than either tab shows. No evidence
   deletion is implied or introduced.

## J. Human and independent-review handoff / repository state

Challenge the same A-selected/B-unreviewed/equal-config preconditions with equal
opaque external strings under distinct source IDs. Reproduce both canonical lock
orders for Network and Interface, and the real authenticated completion route.
Require no natural 40P01, actual persisted source/acceptance lineages, unchanged
canonical UUIDs/configuration, precise Changes and actor audit. Ingestion-first
must invalidate the old proposal token; explicitly refresh before accepting.

Challenge all-batch/model ordering with a later smaller Network UUID, later
Interface owner and omitted baseline Asset. Hold unrelated entities and verify
independent writes. Force an actual PostgreSQL lock timeout and post-flush known
conflicts: require 409, no failed-request progress/seal/audit and explicit retry.
Unknown DB errors must propagate. Rerun original Asset/manual-source and Run/
source/provenance gates, the original 54 gates, migration refusal/round trips and
the 34-identity fleet. Platform CI and any deployment approval remain human steps.

No application-repository commit, push, PR, merge, rebase, reset, tag, release or
deployment occurred. No protected installation was accessed. Existing tracked and
untracked work is preserved; before copies/hashes, incremental file list/patch and
final hashes/status are retained in the evidence directory. Initial state was
**39 modified / 16 untracked**. Final state is **41 modified / 19 untracked**.
Of the original 55 dirty files, 47 remain byte-for-byte unchanged; the other
eight contain only the listed scoped extensions, with their handoff copies retained.
Migration/authority/lease/verifier/frontend implementation files match handoff
hashes except the explicitly listed authenticated-ingestion error boundary.

Actual final `git status --short`:

```text
 M apps/api/app/models.py
 M apps/api/app/routes/assets.py
 M apps/api/app/routes/changes.py
 M apps/api/app/routes/integration_discovery.py
 M apps/api/app/routes/knowledge.py
 M apps/api/app/schemas.py
 M apps/api/app/services/aip_ingestion.py
 M apps/api/app/services/discovery_observations.py
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
?? apps/api/tests/test_reconciliation_ingestion_http_postgres.py
?? apps/api/tests/test_reconciliation_integrity_postgres.py
?? apps/api/tests/test_reconciliation_technical_locking_postgres.py
?? apps/web/components/asset-knowledge-summary.js
?? apps/web/tests/asset-knowledge-summary.test.mjs
?? docs/admin/cross-source-reconciliation.md
?? docs/decisions/0017-reconciliation-knowledge-integrity.md
?? docs/history/validation/cross-source-reconciliation-before-r4-n1.md
?? docs/history/validation/cross-source-reconciliation-f1-f5-review-withdrawn.md
?? docs/history/validation/cross-source-reconciliation-pre-remediation.md
?? docs/testing/cross-source-reconciliation.md
```

Disposable PostgreSQL/Redis created for this task are stopped at handoff; evidence
and database files remain under the evidence root. No live service was touched.
