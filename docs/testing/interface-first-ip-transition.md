# Interface-first IP transition — audit and acceptance

## Repository baseline

- Branch: `feature/infrastructure-topology-v0`
- HEAD: `0599f0f6a2e1eeae8b4e6252d7b0de1fad22ee21`
- Working tree was clean before this work. No commit, push or merge performed.
- Database: no migration added or changed. `alembic heads` reports the single
  existing head `20260921_0019`.

## Product result

IP addresses belong to Asset Interfaces. The shared Asset create/edit form no
longer initializes, renders or submits `Asset.ip_address`. It directs users to
Interfaces on Asset detail. Detail no longer presents a top-level IP; addresses
remain in **Interfaces and networks**. Legacy `ip_address` assertions are omitted
from the current knowledge summary; History and Raw assertions preserve their
provenance. Interface assertions are unaffected.

Shared entity/relationship cards had no additional direct legacy-IP reads or
fallbacks. Platform and Connectivity retain the shared deterministic Interface-IP
helper: primary first, otherwise name/ID, unique first address plus `+N`, absent
when there is no Interface IP. The Assets table retains no IP column. List search
continues matching authorized Interface IPs, with no legacy-field search branch.

The knowledge-profile editor also offered the legacy field and defaulted its
alternative-field rule to it. New choices omit it and use `description` as the
alternative default. Existing rules retain their selected legacy field with an
explicit deprecated label. Loading an existing one-of rule now preserves its
first field as well as its alternative; this prevents a legacy rule being
silently reinterpreted when edited. The existing interface-IP rule remains the
recommended way to express IP completeness.

## Every remaining legacy usage

Searches covered `ip_address`, `Asset.ip_address`, `Primary IP`, and case-insensitive
Asset/IP references across source, tests, fixtures, migrations and documentation.
Paths below are relative to the repository root.

| File / symbols | Classification and reason retained |
| --- | --- |
| `apps/api/app/models.py`: `Asset.ip_address` | Deprecated nullable storage and index, retained for existing data. `AssetInterface.ip_address` is a separate canonical field. |
| `apps/api/app/schemas.py`: `ManualAssetCreate`, `ManualAssetUpdate`, `ManualAssetResponse` | Backward-compatible acceptance and serialization, with unchanged defaults, requiredness and length limits. JSON Schema/OpenAPI marks only the Asset field `deprecated: true` and directs callers to `/asset-interfaces`. Schema-only metadata avoids Pydantic/FastAPI runtime deprecation warnings. |
| `apps/api/app/presenters.py`: `asset_response_data` | Continues returning the legacy field, including consumers using the common Asset serializer. The web does not use it as the current IP. |
| `apps/api/app/routes/assets.py`: create/update | Generic schema dump/application still writes explicitly supplied legacy values; omitted updates preserve storage. No direct legacy search predicate. |
| `apps/api/app/routes/manual_assets.py` | Compatibility routes delegate create/update and use the same serializer. Existing external callers retain read/write/clear behavior. |
| `apps/api/app/services/manual_knowledge.py`: `MANUAL_ASSET_KNOWLEDGE_FIELDS` | Preserves declaration/assertion/change history for explicit API writes. Ordinary web edits omit the field and do not clear or redeclare it. |
| `apps/api/app/services/reconciliation.py`: `_accept_new_asset`, `SAFE_ASSET_FIELDS`, `_accept_changed_fact` | Accepted new-Asset candidates still copy `facts.ip_address`; explicitly accepted changed-fact items can still set it. Retained to avoid losing old candidate data or breaking reviewed acceptance. `_create_interfaces` independently preserves observed Interface addresses. No automatic migration or overwrite was added. |
| `apps/api/app/services/knowledge_requirement_references.py`: `SUPPORTED_ASSET_FIELDS`; generic field evaluation in `knowledge_completeness.py` | Retains API validation and evaluation of existing persisted legacy-field rules. New web rules offer Interface-IP semantics. |
| `apps/web/components/asset-knowledge-profile.js` | Only selected existing legacy-rule options remain, clearly labeled deprecated. It reads rule configuration, not an Asset IP value. |
| `apps/web/app/assets/[id]/page.js` | The remaining literal excludes legacy assertions from current summary. Generic History/Raw assertions remain available as evidence, not as current Interface addresses. |
| `apps/api/migrations/versions/20260714_0002_manual_infrastructure_fields.py` | Historical column/index creation and downgrade. Unchanged migration history. |
| `apps/api/tests/test_models.py` | Legacy storage contract assertion. |
| `apps/api/tests/test_assertion_list.py` | Historical legacy-predicate fixtures and null-evidence behavior. |
| `apps/api/tests/test_operations_experience.py` | Deliberately conflicting legacy IP verifies interface-backed operational context. |
| `apps/api/tests/test_infrastructure_topology_postgres.py` | Existing legacy-search exclusion fixture, plus API compatibility and exact two-Interface acceptance tests for both route families. |
| `apps/api/tests/test_crud.py` | Added schema acceptance, omitted/null updates and deprecation regressions. |
| `apps/web/tests/infrastructure-topology.test.mjs` | Stale legacy fixture verifies interface display/search and list exclusion. |
| `apps/web/tests/interface-ip-ui.test.mjs` | Added create/edit/detail/profile and no-fallback regressions. |
| `apps/web/scripts/check-infrastructure-topology-browser.mjs` | Existing deliberately stale legacy values verify topology never displays them. |
| `apps/web/scripts/check-interface-ip-browser.mjs` | Added stale legacy value and old accepted assertion, captured create/edit request bodies, two Interface addresses, empty/no-address variants and actual rendered Platform/Connectivity checks. |
| `README.md`, `docs/product/development-roadmap.md`, `docs/product/feature-ledger.md`, `docs/architecture/homelab-operations-experience.md`, this audit | Current compatibility/deprecation documentation. User instructions point to Interfaces. |
| `docs/architecture/infrastructure-topology.md`, `docs/testing/infrastructure-topology-polish.md` | Existing interface-only topology/search behavior and prior validation record. |
| `docs/product/c2-readiness-audit.md`, `docs/product/release-c2-plan.md` | Historical readiness evidence and original increment boundaries; not rewritten as current implementation claims. |
| `docs/history/implementation-prompts/{atlas-codex-context,c2-1-shared-operational-graph-codex-prompt}.md`, `docs/history/product-reviews/atlas-product-feature-status-review-reconciled.md` | Archived plans and prior partial-implementation findings, preserved as history. |

Other `ip_address` matches are canonical Interface fields, not legacy Asset reads:
Interface schemas/routes/model and their original `20260714_0003` migration;
`operational_graph.py`, `infrastructure_topology.py`, `knowledge_completeness.py`,
`simulated_discovery.py` and its namespaced predicate documentation;
`apps/web/lib/infrastructure-topology.mjs`, topology Network/inspector rows,
Asset Interface forms/rows, and the discovery simulation example. Interface-only
fixtures are in `test_knowledge_completeness.py`, `test_infrastructure_topology.py`,
`test_knowledge_foundation.py` and the topology/operations tests listed above.
Python `ipaddress.ip_address` calls in network validators and `asset_icons.py`
validate addresses/security boundaries and have no relationship to the legacy
Asset property.

`discovery_sync.py`'s explicit normalized-Asset update map does not write the
legacy IP. The SDK/Proxmox normalizers have no direct `Asset.ip_address` mapping.
Simulation preserves candidate facts and Interface observations; accepted
candidate facts can reach the reconciliation writer described above. It is not
safe to discard that compatibility input in a UI-only cleanup.

Generated Markdown (`apps/api/app/services/markdown_docs.py`) consumes normalized
plugin data, with generic fact and metadata rendering. It does not access
`Asset.ip_address` or insert a “Primary IP” field. Existing sourced documents and
assertion history are not deleted or rewritten.

## Security and compatibility

No API route, authorization rule, customer/site boundary or topology contract
changed. Existing search requires both Asset visibility and `networks.view` in
the owning Asset scope before matching Interface IPs. PostgreSQL regressions
exercise scoped search, inaccessible Interface exclusion and duplicate-free
pagination. Browser tests intercept all API calls and never mutate live data.

An external caller can still create/read/update/clear the deprecated field
through `/assets` and `/manual-assets`. An ordinary update that omits it preserves
its stored value. Interfaces remain independent. OpenAPI is the only API-contract
metadata change; no database data or historical knowledge is discarded.

## Exact acceptance case

Asset: **AdGuard Home**, stale `Asset.ip_address = 192.0.2.254`.
Interfaces: primary **eth0 = 192.168.99.5**, **eth1 = 192.168.5.5**.

| Surface | Expected and tested result |
| --- | --- |
| Create | No Primary IP input; captured POST body has no `ip_address`. |
| Edit | No Primary IP input or stale value; captured PATCH omits `ip_address`; stored compatibility value is preserved. |
| Detail | No top-level IP or legacy current-summary assertion; both named Interface rows show their addresses. |
| No Interfaces | Detail reports no interfaces; topology omits IP instead of showing `192.0.2.254`. |
| Interface without IP | Detail reports `No IP` on that Interface; topology still omits the IP summary. |
| Platform | `192.168.99.5 +1`; no legacy fallback. |
| Connectivity | `192.168.99.5 +1`; no legacy fallback. |
| Assets table | No IP column or stale value. |
| Real PostgreSQL list search | Either `192.168.99.5` or `192.168.5.5` resolves the created Asset; `192.0.2.254` does not. |

## Validation

| Command / check | Executed result |
| --- | --- |
| Baseline web: `node --test tests/infrastructure-topology.test.mjs tests/entity-detail.test.mjs tests/services-ui.test.mjs` from `apps/web` | 17 passed. |
| Baseline API: `.venv/bin/pytest -q tests/test_crud.py tests/test_infrastructure_topology.py tests/test_infrastructure_topology_postgres.py tests/test_operations_experience.py` from `apps/api` | 33 passed, seven PostgreSQL-dependent tests skipped before starting the disposable cluster. |
| Focused API: same selection with `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://127.0.0.1:55439/atlas_topology_utf8` | 43 passed, including real search/authorization and both API compatibility routes. |
| Full API: `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://127.0.0.1:55439/atlas_topology_utf8 .venv/bin/pytest -q --tb=short` | 407 passed, one skipped: the existing category migration test requires a separate empty migration database. No migrations changed. 525 existing FastAPI/Starlette deprecation warnings. |
| Final web: `npm test` from `apps/web` | 139 passed, no failures/skips. |
| Production: `npm run build` from `apps/web` | Passed, including all 37 static pages. |
| `node scripts/check-interface-ip-browser.mjs` against the production build | Four scenarios passed: light/dark at 1440 and 800px. Captured POST/PATCH bodies omit the legacy field; detail, old summary assertion exclusion, both empty variants, Platform, Connectivity and table checked. |
| `node scripts/check-infrastructure-topology-browser.mjs` against the production build | Six existing scenarios passed: light/dark at 1440, 1100 and 800px, including layout, expansion, topology semantics, interface addresses and Assets cleanup. |
| `.venv/bin/alembic heads` | Single head `20260921_0019`; no migrations introduced. |
| Direct `app.openapi()` assertions | All three Asset schema fields expose `deprecated: true`; all three Interface schema fields remain non-deprecated. |
| Local Markdown link check in changed documentation | 57 local targets exist. |
| `git diff --check` | Clean. |

Browser execution used `ATLAS_BROWSER_BASE_URL=http://127.0.0.1:3109`,
`ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-topology-browser/node_modules/playwright/index.mjs`
and the installed Google Chrome executable through `ATLAS_CHROME_PATH`. All API
responses were fixtures. The temporary web server and disposable test cluster
were stopped after validation.

Early validation failures were confined to new fixture setup: missing topology
fixture fields, Playwright URL/locator mistakes, a missing relationship-types
array, and a duplicate test user. They were corrected before the passing runs
above. The initial PostgreSQL connection used the wrong local role; the final
commands use the cluster's default role. No production failures were suppressed.
The production server used the existing `npm run start` script, which emits the
repository's standalone-output startup warning; the browser suites passed.

## Material files changed

| Files | Purpose |
| --- | --- |
| `apps/web/components/asset-form.js` | Remove legacy state/control/payload; direct users to Interfaces. |
| `apps/web/app/assets/[id]/page.js` | Remove top-level IP and legacy current-summary predicate, retain Interface display and historical evidence. |
| `apps/web/components/asset-knowledge-profile.js` | Remove legacy choices/defaults for new rules, preserve existing rule selection. |
| `apps/api/app/models.py`, `apps/api/app/schemas.py` | Document storage compatibility; publish API deprecation metadata. |
| `apps/api/tests/test_crud.py`, `apps/api/tests/test_infrastructure_topology_postgres.py` | Schema/API compatibility and actual two-Interface search acceptance. |
| `apps/web/tests/interface-ip-ui.test.mjs`, `apps/web/scripts/check-interface-ip-browser.mjs` | Regression tests and rendered browser acceptance with captured payloads. |
| `README.md`, `docs/admin/infrastructure-topology.md`, `docs/admin/knowledge-profiles.md` | Interface-first operator instructions. |
| `docs/architecture/homelab-operations-experience.md`, `docs/product/development-roadmap.md`, `docs/product/feature-ledger.md` | Truthful delivered status and retained compatibility debt. |
| `docs/testing/interface-first-ip-transition.md` | Audit, acceptance and validation evidence. |

Remaining deliberate debt: deprecated storage/API removal, migration of older
reconciliation candidates and administrator-owned legacy completeness rules.
These require separate compatibility decisions, not silent data conversion.
