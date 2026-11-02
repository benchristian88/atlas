# Historical cross-source reconciliation acceptance (withdrawn)

The assessment below is withdrawn. Independent review reproduced F1–F5 using
production session settings and multi-source races. Its test counts describe the
earlier run only and do not establish acceptance of the defective implementation.
The current [remediation acceptance record](../../testing/cross-source-reconciliation.md)
supersedes it. This copy preserves investigation provenance.

# Cross-source reconciliation acceptance — 2026-11-01

## A. Executive result

**CONDITIONAL PASS** for development acceptance. Explicit Asset, Interface and
Network linking uses existing APIs, retains canonical UUIDs and keeps observed
configuration under separate human review. The original live deployment was not
accessed. Its exact-build enrollment cannot currently be rotated to this build.
Automated results and remaining environment skips are recorded below.
The Asset Knowledge addendum (AK-01 and AK-02) is included in this same change.

## B. Root-cause analysis

- Confirmed missing workflow: the entity UI exposed only Asset linking although
  `link-technical` and source-scoped technical links already existed.
- Confirmed intended safety: accepting a new same-owner Interface named `eth0`
  when it already exists returns HTTP 409 with “explicitly link its source
  identity before applying changes”. The equivalent Network guard remains.
  The new PostgreSQL/HTTP fixture verifies the response, not just the badge.
- Confirmed propagation defect: technical linking updated its configuration
  claim but left current technical fact claims without the canonical subject ID.
  Later ingestion could therefore fail to coalesce them. Linking now propagates
  current source claims without accepting their values; repeated technical-fact
  ingestion retains one claim.
- Confirmed review gaps: technical links lacked version/freshness checks and
  supplied no accepted configuration in their follow-up proposal. Technical
  proposal versions also omitted intervening accepted configuration changes.
- Confirmed Asset knowledge inconsistency: linking a differently named Asset
  accepted the observed name assertion without changing its retained name. The
  new regression fails on the original application snapshot and passes with the
  fix; the name now remains an independent review.
- The controlled two-source reproduction finds no independent stale-parent
  projection defect: after Asset linking its facts resolve on refresh. Remaining
  waiting records correctly identify unresolved Network/Interface identities or
  relationship endpoints. Live `grafana`/`esphome` HTTP responses were not read;
  this diagnosis describes checked-in code and controlled reproduction.

### AK-01 — False unresolved Asset Type and acceptance consistency

The original unresolved calculation treated `len(active) > 1` as ambiguity even
when distinct values numbered one. It now compares distinct values only. Agreeing
unaccepted observations remain Observed/Awaiting acceptance; selected knowledge
and conflicting observations retain their separate meanings. The original-code
snapshot fails the identical-values regression with `unresolved=True`.

Legacy direct sync can write operational `Asset.asset_type` without assertions.
The Asset-link path also previously accepted only its name assertion and offered
no decisions for matching core fields; subsequent matching discovery skipped
those fields. Linking and matching unaccepted ingestion now expose field reviews.
No historical assertions or acceptance decisions are fabricated. The summary
reports operational values and missing/mismatched acceptance explicitly. Initial
new-Asset acceptance and manual declaration contracts remain intact.

### AK-02 — Relationship JSON and duplicate presentation

The original `_value` returned `value_json` before resolving relationship targets;
the UI then serialized it. Its value key also included source-specific external
IDs, so two assertions for one canonical target remained separate display values.
The new projection resolves canonical IDs, known legacy JSON IDs and exact
source links, checks target scope and returns managed labels/named authorized
links. Logical keys include canonical subject/target/type/scope, never names.
`accepted_values` still retains each assertion; additive logical groups retain
each source, timestamp, actor and assertion ID. Unresolved references and distinct
same-named targets remain separate. History now shares safe target resolution;
original raw values and historical evidence are untouched.

## C. Architecture decisions

Reuse `EntitySourceLink`, the existing link endpoints, `EntityReview`, assertion
ingestion and the decision/Changes/audit path. Technical choices lazily page the
existing authorized collection APIs. No schema migration, endpoint, dependency or
connector/runtime security change is required. Names remain candidate information,
never automatic cross-source identity proof. Identity decisions preserve accepted
configuration; separate proposals accept, reject or defer it.

## D. Implementation inventory

Branch: `fix/reconcilliation-fixes`. Starting HEAD:
`af32da2d3153e48feeec26adb91c64e7732e36a0`. All work remains uncommitted.

| File | Change |
| --- | --- |
| `apps/api/app/routes/knowledge.py` | Active-context enforcement, versioned links, shared source/item/assertion/target locking, safe conflict responses and refreshed bulk eligibility. |
| `apps/api/app/routes/changes.py` | Pass summary caller permissions and apply the same scoped target resolution to History. |
| `apps/api/app/schemas.py` | Additive optional link versions and technical review metadata. |
| `apps/api/app/services/entity_resolution.py` | Serialize source-link insertion and reject conflicting targets across scopes. |
| `apps/api/app/services/reconciliation.py` | Freshness/context/owner validation, technical claim propagation, retained configuration review, conflicting Asset-name review and Interface owner locking. |
| `apps/api/app/services/knowledge_summary.py` | AK-01 distinct-value states/canonical consistency; AK-02 batched semantic target resolution, grouping and retained provenance. |
| `apps/api/app/services/simulated_discovery.py` | Expose matching unaccepted core fields for explicit review rather than leaving acceptance gaps unreachable. |
| `apps/api/app/services/reconciliation_entities.py` | Authoritative link eligibility/owner metadata, current configuration presentation and configuration-aware versions. |
| `apps/api/tests/test_cross_source_reconciliation.py` | Real AIP/PostgreSQL/HTTP two-source, preservation, repeated discovery, stale decisions, candidate scope, permissions and concurrent decisions. |
| `apps/api/tests/test_asset_knowledge_summary.py` | AK-01/AK-02 PostgreSQL/HTTP agreement/conflict, consistency, target forms/scopes, grouping, history/raw retention, acceptance transitions and bounded metadata-query count. |
| `apps/api/tests/test_knowledge_foundation.py` | Give the existing direct-route fixture its required reconciliation permission after removing unsafe cross-scope Asset-edit fallback. |
| `apps/web/app/assets/[id]/page.js` | Use the focused semantic knowledge component while retaining History/Raw tabs and IP exclusions. |
| `apps/web/components/asset-knowledge-summary.js` | Named values/links, separate operational/accepted/observed states, logical groups and individual source provenance. |
| `apps/web/app/globals.css` | Scoped knowledge value wrapping, provenance spacing and readable long target names. |
| `apps/web/app/reconciliation/page.js` | Bounded lazy candidate requests, versioned linking, request invalidation and refresh/feedback. |
| `apps/web/components/reconciliation-cards.js` | Contextual Interface/Network selectors, identifying fields, empty/error states and explicit configuration review. |
| `apps/web/tests/reconciliation-entities.test.mjs` | Candidate ownership/scope, disabled states, lazy loading, errors and distinct configuration rendering. |
| `apps/web/tests/reconciliation-navigation.test.mjs` | Version payload and stale candidate invalidation checks. |
| `apps/web/tests/asset-knowledge-summary.test.mjs` | AK-01 state consistency and AK-02 named logical values, safe fallbacks, retained sources and responsive wrapping. |
| `apps/web/tests/knowledge-v2-ui.test.mjs` | Follow the extracted summary component while retaining History/Raw assertions requirements. |
| `apps/web/tests/interface-ip-ui.test.mjs` | Preserve Interface-only current IP presentation after summary extraction. |
| `apps/web/scripts/check-reconciliation-browser.mjs` | Keyboard linking, invalid candidate filtering, stale decision/refresh, preserved configuration and responsive evidence. |
| `docs/architecture/reconciliation-entity-review.md` | Identity, configuration, scope and transaction contract. |
| `docs/architecture/knowledge-changes-and-reconciliation.md` | Provenance and separate identity/configuration decisions. |
| `docs/admin/cross-source-reconciliation.md` | Operator procedure and waiting/partial-result interpretation. |
| `docs/deployment/local-release-acceptance.md` | Exact-build transition limitation and supported isolated-development alternative. |
| `docs/deployment/upgrades.md` | Link the enrolled-instance exception before ordinary upgrades. |
| `docs/product/feature-ledger.md` | Describe the reachable technical linking workflow and limits. |
| `docs/README.md` | Make the operator guide discoverable. |
| `docs/testing/cross-source-reconciliation.md` | This acceptance record and human handoff. |

Existing routes and payload fields remain available. `expected_version` remains
optional for older callers; the UI supplies it. New review fields are additive.
Summary per-assertion arrays remain, with additive semantic/display fields and
logical groups. Relationship summary values normalize legacy heterogeneous JSON
to safe semantic targets; complete original values remain in Raw assertions.
Requests relying on Asset-edit permission instead of the item's own scoped
reconciliation permission are now denied.
No migrations or production dependencies were added. PostgreSQL remains the sole
operational system of record.

## E. Security review

Backend checks cover active customer/site, reconciliation decision permission,
technical edit permission, target scope, accepted Interface owner and immutable
source target. Candidate APIs retain `networks.view`. Cross-scope target errors
do not disclose names/MAC values. Technical link freshness is checked even for
legacy callers omitting a version. Original source links and evidence remain.

Source row locks serialize competing identity decisions, including absent-link
creation. Items/assertions and existing technical targets lock in deterministic
order; uniqueness/scoped foreign keys remain authoritative. Bulk operations use
per-item savepoints and retain independent successes. Real PostgreSQL races cover
link/link, competing-item targets and link/accept, retaining one association and
one security audit. Technical configuration versions reject intervening accepted
field edits in individual and bulk decisions. Linking itself never writes those
fields. This is a focused code/security review, not a claim of external security
certification. No signing, admission, enrollment, package-verification, secret or
coverage code was modified.
The independent review also removed an authorization fallback that could combine
reconciliation permission in one site with Asset-edit permission in another.
The AK-02 target resolver and History enforce both caller permission and the
subject's exact customer/site before returning names, IDs or links. Unsafe JSON
names are never trusted. Metadata queries remain bounded independently of claim
count; a 30-assertion relationship test verifies at most eight SELECTs.

## F. Test matrix and environment

Python 3.14 virtualenv: `apps/api/.venv`. Native Homebrew PostgreSQL 17.11, fresh
temporary cluster, loopback port `55479`, database `atlas_reconciliation_test`.
Migrated from empty through single head `20261021_0031`. Temporary Redis
`redis:7.4.6-alpine` on loopback port `56389`. No existing database or Redis was
used. Node 24.19.0, existing frontend dependencies, installed Chrome and temporary
Playwright 1.56.1 outside the repository.

Backend commands use:

```bash
export ATLAS_TEST_DATABASE_URL=postgresql+psycopg://atlas_reconciliation_test@127.0.0.1:55479/atlas_reconciliation_test
export REDIS_URL=redis://127.0.0.1:56389/0
```

These are disposable local test identities, not deployment credentials.

| Command | Environment / result |
| --- | --- |
| `DATABASE_URL=$ATLAS_TEST_DATABASE_URL .venv/bin/alembic upgrade head` | Fresh PostgreSQL; migrated all 31 revisions. |
| `.venv/bin/python -m pytest tests/test_asset_knowledge_summary.py tests/test_cross_source_reconciliation.py tests/test_knowledge_foundation.py tests/test_reconciliation_entities.py tests/test_reconciliation_listing.py tests/test_source_identity.py tests/test_i3_discovery.py -q --tb=short` | 180 passed, zero failed/skipped; real PostgreSQL/AIP/HTTP, concurrency and existing unit checks. |
| `.venv/bin/python -m pytest -q -rs --tb=short` | Final full backend: 2,331 passed, zero failed, 254 explicitly skipped; 156.99 seconds. Skip categories below. Earlier run had one docs-link failure while this record was still being written; fixed and revalidated. |
| `npm test` | 329 passed, zero failed/skipped. Includes 20 reconciliation component/navigation and five AK-01/AK-02 component tests. |
| `npm run build` | Production build passed. |
| `node scripts/check-reconciliation-browser.mjs` with temporary Playwright/Chrome environment | Intercepted fixture APIs, not a live backend integration. Light/dark, three accents and 36 viewport states passed. Keyboard link/stale refresh/navigation; AK-01 state, AK-02 target/provenance, History/Raw; no overflow or runtime errors. Desktop/mobile screenshots visually inspected. |
| `.venv/bin/python -m pytest tests/test_repository_docs.py -q --tb=short` | 14 passed, zero failed/skipped. |
| `.venv/bin/alembic heads` | Exactly one head: `20261021_0031`; no new migration. |
| `apps/api/.venv/bin/python -m pytest docs/architecture/integrations/contracts/tests -q --tb=short` (repository root) | 77 passed, zero failed/skipped. |
| `git diff --check` | Clean. |
| Original-code snapshot: `python -m pytest tests/test_cross_source_reconciliation.py::test_asset_link_does_not_accept_a_conflicting_name -q --tb=short` | Expected failure on original `af32da2…`: conflicting name assertion was accepted. The same test passes with the fix. Snapshot and tests were copied to temporary storage; checkout was not reverted. |
| Original-code snapshot: `python -m pytest tests/test_asset_knowledge_summary.py -k agreement -q --tb=short --maxfail=1` | Expected failure: two identical unaccepted Asset Types incorrectly produce `unresolved=True`. Current code passes all agreeing/conflicting-value regressions. |

Initial infrastructure-only failures were resolved without suppressing tests:
PostgreSQL startup required sandbox permission; the first focused run had 93
passes and one Redis connection failure before the disposable service existed.
The first browser attempt exposed macOS headless native-select arrow behavior;
type-ahead plus Tab was verified on a synthetic select and used for keyboard
acceptance. No assertions were removed to obtain a passing result.

Logs and screenshots are temporary development artifacts under
`/private/tmp/atlas-reconciliation-*` and `/private/tmp/atlas-knowledge-summary-*`;
they contain synthetic fixtures and are not committed product artifacts.

The full backend's 254 skips are not reported as passes:

| Skipped | Required environment absent |
| --- | --- |
| 10 | Separately empty general, integration, setup and MFA migration databases. |
| 21 | Dedicated source/restore PostgreSQL database pairs owned by their Atlas roles. |
| 45 | Separate setup/MFA migrated database fixtures. The primary domain PostgreSQL URL was present. |
| 27 | Exact installed/pinned Ansible runtime and I4A environments. |
| 83 | Root inside a disposable container for local-release authority suites. |
| 68 | nginx >=1.28 or `ATLAS_TEST_NGINX`. |

All 180 focused parent/addendum tests ran without skips. No broad baseline
changes or suppressed failures were used. Frontend source-contract assertions
were updated to follow summary extraction; their IP exclusions and History/Raw
requirements remain, with new rendered component and browser regressions.

Browser command (from `apps/web`, against the built app on loopback `3149`):

```bash
ATLAS_PLAYWRIGHT_MODULE=/private/tmp/atlas-reconciliation-browser-tools/node_modules/playwright/index.mjs \
ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
ATLAS_BROWSER_OUTPUT=/private/tmp/atlas-reconciliation-browser-evidence \
node scripts/check-reconciliation-browser.mjs
```

The screenshots include `technical-link-{light,dark}-{1440,390}.png` and
`asset-knowledge-{light,dark}-{1440,390}.png`; `report.json` records all 36 states
and zero browser runtime errors. The native test PostgreSQL, Redis container and
web server are stopped after verification; retained temporary logs/data are
development evidence, unrelated to the protected acceptance instance.

AK-01 tests cover agreeing/unaccepted, disagreeing/unaccepted, accepted agreeing,
accepted conflicting, canonical-only and mismatched accepted/operational types,
and a real link → field acceptance → refreshed summary transition. AK-02 tests
cover object IDs, legacy JSON and source-link targets; two contributing sources;
same-named distinct targets; unresolved, historical, rejected and retracted claims;
cross-customer/site/permission/missing/malformed targets; original Raw values;
response-schema validation and batched lookup performance. Browser checks verify
long names, keyboard links/provenance, themes and layouts; backend scope tests are
separate real PostgreSQL/HTTP tests, not inferred from mocks.

## G. Documentation

Architecture and knowledge-change contracts describe multiple source identities,
UUID retention, current prerequisite resolution, explicit configuration acceptance,
transaction boundaries and security. The administration guide provides the
`grafana`/`eth0` workflow. The ledger describes repository capability without
claiming live Proxmox acceptance. Deployment and upgrades explicitly identify the
unsupported exact-build transition. Historical ADRs are unchanged.

## H. Live acceptance readiness

The current enrolled `atlas-test-docker` build is exactly
`af32da2d3153e48feeec26adb91c64e7732e36a0`. Authority binds its protected public
enrollment, PostgreSQL checkpoint, original store/deployment, signing authority,
staged immutable evidence, grants and leases. ADRs 0014/0015/0016 do not support
build/key rotation. Renewal, recovery and bundled restoration retain that build.
Pulling/rebuilding/restarting with a new build is not a supported transition.

Leave that instance untouched. A separate reviewed build-migration engineering
task is required to preserve its existing data/decisions/authority/evidence/history
while changing builds. Do not spoof build IDs, modify enrollment rows, regenerate
or copy keys, reset enrollment or delete evidence. A new isolated deployment with
its own supported authority and synthetic inventory can validate the new workflow;
it is not evidence of an upgrade preserving the original instance.

After a supported human-operated transition, compare the original canonical IDs,
source links, accepted MAC/IP/VLAN/Network values, assertion/evidence history,
decision audits and inventory counts. Link only verified matches, then review
configuration conflicts, dependencies and partial bulk results. Repeat Source B
discovery and verify no renewed identity proposals or duplicate retained entities.
Do not hardcode a final asset count or infer identity from display names. Record
actual HTTP statuses/reasons for any remaining waiting/failed items and retain
screenshots without secrets or real raw evidence in this repository.

## I. Outstanding risks

- **High operational blocker:** no supported exact-build transition for the live
  enrolled instance; separate reviewed engineering is required before deployment.
- **Acceptance limitation:** synthetic AIP/PostgreSQL/HTTP and intercepted browser
  tests are not live Proxmox or native/systemd qualification.
- **Validation limitation:** broader optional setup, MFA, backup/restore, migration
  and runtime suites need their separately isolated environments. Skips are
  reported explicitly; focused reconciliation tests use real PostgreSQL.
- **Existing deferred limitation:** archived-run suppression remains unsupported
  because coalesced assertions lack complete contributing-run provenance.
- **AK-01 retained-data limitation:** preexisting operational/assertion gaps are
  reported, not backfilled. Operators must review available proposals; next
  matching discovery makes previously skipped unaccepted fields reviewable.
- **AK-02 presentation limitation:** unresolved or inaccessible targets remain
  separate safe fallback values until explicit identity resolution; source names
  and matching display labels never establish equivalence. No unresolved AK-01
  or AK-02 regression failure is being waived.

## J. Human operator handoff

Review the visible working-tree diff and the test evidence, especially source
locks, version checking, scope/owner validation and separate configuration review.
The human operator may then commit and open a PR, run normal CI with all required
isolated fixtures, and plan the build-transition task separately. No commit,
push, PR, tag, deployment or live database/enrollment operation was performed.
Resume Proxmox 0.2.2 acceptance only through the supported deployment path above.

## Repository state at handoff

```text
 M apps/api/app/routes/changes.py
 M apps/api/app/routes/knowledge.py
 M apps/api/app/schemas.py
 M apps/api/app/services/entity_resolution.py
 M apps/api/app/services/knowledge_summary.py
 M apps/api/app/services/reconciliation.py
 M apps/api/app/services/reconciliation_entities.py
 M apps/api/app/services/simulated_discovery.py
 M apps/api/tests/test_knowledge_foundation.py
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
 M docs/deployment/local-release-acceptance.md
 M docs/deployment/upgrades.md
 M docs/product/feature-ledger.md
?? apps/api/tests/test_asset_knowledge_summary.py
?? apps/api/tests/test_cross_source_reconciliation.py
?? apps/web/components/asset-knowledge-summary.js
?? apps/web/tests/asset-knowledge-summary.test.mjs
?? docs/admin/cross-source-reconciliation.md
?? docs/testing/cross-source-reconciliation.md
```
