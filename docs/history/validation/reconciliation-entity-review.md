# Entity-centric reconciliation UX — completion report

Date: 2026-10-18

**Result: PASS WITH FOLLOW-UPS** — implementation and available automated acceptance pass. The existing Redis-dependent discovery test, dedicated-environment test gates and operator review of live qualification data remain outside the executed acceptance below.

## Repository

- Branch: `feature/integrations-i4c-proxmox-qualification`.
- HEAD: `85d750b626cdfe772706a92d1f9678f26c5f4e97`.
- Starting working tree: clean (`git status --short` returned no entries).
- All changes are uncommitted for operator review.

## Architecture and behavior

An additive, read-only backend entity projection extends the independent reconciliation model. It uses existing accepted source links, assertion ownership, managed taxonomy and canonical Interface configuration. It introduces no persistent grouping state and no migration.

Accepted entities group by durable type/ID; unresolved candidates use exact customer/site/source/type/external identity. Relationships belong to their source Asset. Interfaces and their facts belong to the Asset owner from their configuration or accepted link. Independently reviewed Networks retain their own entity card. External IDs remain opaque; no vendor or Connector identifier determines hierarchy.

The oldest identity record anchors the card across acceptance and re-observation. A current unresolved parent takes precedence over rejected historical parents for review. Existing manually curated Assets need no parent decision, and already linked sources share the accepted entity's card.

One card component supports new and existing Assets. New candidates expand; existing/accepted entities start compact. Facts, Relationships and Network disclose independently. Collapsed sections retain blocked/conflict warnings. Managed type/relationship labels and generic fact labels replace technical keys in normal review, while full keys and normalized proposals remain available in Evidence and details. Cached Asset images retain the existing safe identity fallback.

**Accept asset** calls individual acceptance and decides only the parent reconciliation record. Independent fact, Interface and relationship records stay unresolved. Existing initial configuration remains part of the parent proposal; assertions with independent reconciliation records are excluded from implicit matching-assertion confirmation. An accepted parent stays visible while matching child work remains.

**Accept all** sends the reviewed IDs and versions to the backend. The backend verifies authorized group membership, locks records/assertions, checks versions and reevaluates dependencies between Asset, technical configuration, fact and relationship phases. Each accepted record follows the existing acceptance, Changes, completeness and security-audit path. Savepoints isolate child failures. Responses explicitly report accepted, already-resolved, blocked and failed records with reasons. Another entity is never implicitly accepted as a prerequisite; lifecycle absence items still require an individual disposition.

The backend supplies named blockers and jump IDs. Cycle-safe dependency ordering provides stable review order without claiming a tree or operational impact. Queue, filter, cursor, focus and return state live in the URL through Next's integrated native History API. Prerequisite jumps expand/focus their target across pages; refresh, Back/Forward and Return retain useful review position. Backend previous-page cursors preserve the snapshot even when returning to the first page. Search matches entity presentation, and existing category/status/deferred/resolved meanings remain intact.

## Additive API contract

| Route | Purpose |
| --- | --- |
| `GET /reconciliation-entities` | Entity pages, exact scoped record/entity totals, filters/search and next/previous cursors. |
| `GET /reconciliation-entities/{id}` | Focused prerequisite review with unresolved work and parent context. |
| `GET /reconciliation-entities/{id}/section` | Bounded continuation for a section. |
| `POST /reconciliation-entities/{id}/accept` | Explicit reviewed group acceptance with per-record outcomes. |

Existing granular list, summary, link and decision routes remain available. Individual decision payloads add optional `expected_version`; the new UI sends it. Accept, Reject, Defer and source linking retain their existing authorization machinery. Individual decisions now serialize on their reconciliation row; stale/retracted/superseded acceptance is rejected.

## Security, tenancy and integrity

Explicit PostgreSQL tests cover RBAC, extra network/relationship permissions, customer and site boundaries, global reviewers constrained by an active context, scoped names/counts/blockers, malicious foreign child IDs and another visible entity supplied as a prerequisite. Read-only projection tests assert eight SELECTs and no writes. Concurrent independent connections accept the same proposal once and preserve exactly one acceptance audit event.

Metadata reads are limited to identities referenced by the authorized review index; unrelated operational inventory is not loaded. The projection loads no Evidence payloads, receipts, diagnostics, Integration configuration or credentials. Source identity attachment is constrained by customer, site and source. GET projection does not persist identity resolution or alter accepted knowledge.

## Query and bounds

- Eight batched SELECTs per projection, independent of card count; covered by query-count regression.
- Default page: 50 entities; maximum: 100.
- Initial/continued section response: at most 20 records.
- Bulk operation: at most 1,000 explicitly reviewed records; larger groups remain individually reviewable.
- Whole-queue totals and global review order use a request-local scoped history index. Time/memory are linear in that index. SQL projection/caching for very large retained histories is a possible later optimization; no second source of truth or persistent group cache was introduced.

## Files changed

Backend implementation:

- [reconciliation_entities.py](../../../apps/api/app/services/reconciliation_entities.py): generic ownership/grouping, labels, eligibility, blockers, versions, ordering, bounded presentation and cursor navigation.
- [reconciliation.py](../../../apps/api/app/services/reconciliation.py): scope-safe accepted subject lookup, independent child-assertion preservation, source-scoped identity attachment and stale acceptance checks.
- [knowledge.py](../../../apps/api/app/routes/knowledge.py): additive entity endpoints, locked/versioned decisions and shared individual/bulk acceptance/audit flow.
- [schemas.py](../../../apps/api/app/schemas.py): explicit presentation, blocker, section, proposal-version and bulk outcome contracts.

Frontend implementation:

- [page.js](../../../apps/web/app/reconciliation/page.js): grouped queue consumption, search/section filters, URL navigation, prerequisite focus/return, decision outcomes and stale-response guards.
- [reconciliation-cards.js](../../../apps/web/components/reconciliation-cards.js): shared entity card, independently expandable sections, review rows/actions/provenance and query-history links; existing compatibility exports remain.
- [reconciliation.module.css](../../../apps/web/app/reconciliation/reconciliation.module.css): scoped token-based compact/responsive layout and focus/warning presentation.
- [reconciliation-queues.mjs](../../../apps/web/lib/reconciliation-queues.mjs): additive grouped request and safe jump/return URL codecs; legacy request/group helpers remain compatible.

Tests and acceptance fixtures:

- [test_reconciliation_entities.py](../../../apps/api/tests/test_reconciliation_entities.py): grouping, manual/existing Assets, Interfaces, dependencies, decisions/audits, failures, stale/concurrent proposals, re-observation, filters, paging, query counts and isolation.
- [test_knowledge_foundation.py](../../../apps/api/tests/test_knowledge_foundation.py): existing session fake accepts SQLAlchemy row-lock/refresh keyword arguments.
- [reconciliation-entities.test.mjs](../../../apps/web/tests/reconciliation-entities.test.mjs): component, disclosure, eligibility, identity, navigation and modified-link behavior.
- [reconciliation-navigation.test.mjs](../../../apps/web/tests/reconciliation-navigation.test.mjs): URL-history expectations reflect grouped review navigation; legacy queue coverage is retained.
- [check-reconciliation-browser.mjs](../../../apps/web/scripts/check-reconciliation-browser.mjs): fixture-backed production browser acceptance. All API calls are intercepted; no operator data is decided.

Documentation:

- [Entity review architecture](../../architecture/reconciliation-entity-review.md): contracts, semantics, bounds and operational limits.
- [Knowledge and reconciliation](../../architecture/knowledge-changes-and-reconciliation.md): explicit entity/group acceptance semantics.
- [UI architecture](../../architecture/ui-architecture.md): entity review's shared UI and backend presentation ownership.
- [Feature ledger](../../product/feature-ledger.md): repository reality updated without expanding live Connector qualification claims.
- This completion report records actual validation and repository state.

## Database

No migration, backfill or destructive/history change was required. Alembic reports the single head `20261018_0030`. Backend integration tests ran against a separately initialized temporary PostgreSQL 17 database. The qualification database was not used to manufacture states or decide records.

## Tests and validation

Backend commands ran from `apps/api` with `DATABASE_URL` and `ATLAS_TEST_DATABASE_URL` pointing to the disposable database, PostgreSQL 17 tools on PATH, and `PYTHONPATH=../../plugins/sdk:../../plugins/proxmox` for the broad suite:

```bash
.venv/bin/python -m pytest tests -q -rs --tb=short -k 'not test_run_now_real_redis_duplicate_hints_dispatch_once'
.venv/bin/python -m pytest tests/test_reconciliation_entities.py tests/test_reconciliation_listing.py tests/test_knowledge_foundation.py tests/test_repository_docs.py -q --tb=short
.venv/bin/python -m pytest tests/test_repository_docs.py tests/test_markdown_docs.py -q --tb=short
.venv/bin/python -m alembic heads
.venv/bin/python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; heads = ScriptDirectory.from_config(Config('alembic.ini')).get_heads(); assert len(heads) == 1; print('Single Alembic head:', heads[0])"
```

Broad API validation: **1,141 passed, 169 skipped, 1 deselected**. The final run completed successfully in 103.96 seconds.

Focused validation: **101 passed**. Final documentation/link checks: **18 passed**. Alembic head and explicit single-head assertion: **PASS**, `20261018_0030`.

The one explicitly excluded discovery test requires Redis; its earlier attempted execution failed because no Redis server was available on localhost:6379. Existing environment gates skipped 169 tests requiring dedicated migration/restore/role-security databases, pinned Ansible runtimes or nginx. These are not claimed as passing.

Frontend commands ran from `apps/web`:

```bash
npm test
NEXT_TELEMETRY_DISABLED=1 npm run build
ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-i4c-diagnostics/browser-tools/node_modules/playwright/index.mjs ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' node scripts/check-reconciliation-browser.mjs
```

- Frontend tests: **316 passed**, zero failures/skips.
- Production Next.js build: **PASS**.
- Production browser: **PASS**, 24 combinations of 1440/1024/800/390 px, light/dark mode and default/blue/purple accents; zero runtime errors.
- Browser interactions cover blocked evidence, independent sections, parent-only acceptance, bulk waiting outcomes, off-page prerequisite jump, refresh, Back/Forward, return, search and filtering.
- Screenshots were inspected at desktop and 390 px. Artifacts: `/tmp/atlas-reconciliation-validation/browser/`, including `reconciliation-light-1440.png`, `reconciliation-dark-390.png` and `report.json`.
- `git diff --check`: **PASS**.

## Follow-ups and confirmations

Operator review against retained live qualification data remains appropriate before deployment; this task did not deploy or decide that data. The unavailable Redis test and existing dedicated-environment skips remain explicit validation limits. Very large retained histories may benefit from a narrower SQL metadata index later.

Confirmed:

- `atlas-connectors` was not changed; its final working tree is clean.
- `atlas-connector-sdk` was not changed; its final working tree is clean.
- No Connector manifests, AIP schemas, Connector behavior or Proxmox discovery behavior changed.
- No Proxmox-specific presentation parsing or vendor hierarchy logic was introduced.
- No reconciliation decisions, history, assertions or evidence were destroyed.
- No automatic or discovery-triggered knowledge acceptance was added.
- Nothing was committed, pushed, merged, rebased, tagged or released.

## Exact repository state

`git status --short --untracked-files=all`:

```text
 M apps/api/app/routes/knowledge.py
 M apps/api/app/schemas.py
 M apps/api/app/services/reconciliation.py
 M apps/api/tests/test_knowledge_foundation.py
 M apps/web/app/reconciliation/page.js
 M apps/web/app/reconciliation/reconciliation.module.css
 M apps/web/components/reconciliation-cards.js
 M apps/web/lib/reconciliation-queues.mjs
 M apps/web/tests/reconciliation-navigation.test.mjs
 M docs/architecture/knowledge-changes-and-reconciliation.md
 M docs/architecture/ui-architecture.md
 M docs/product/feature-ledger.md
?? apps/api/app/services/reconciliation_entities.py
?? apps/api/tests/test_reconciliation_entities.py
?? apps/web/scripts/check-reconciliation-browser.mjs
?? apps/web/tests/reconciliation-entities.test.mjs
?? docs/architecture/reconciliation-entity-review.md
?? docs/history/validation/reconciliation-entity-review.md
```
