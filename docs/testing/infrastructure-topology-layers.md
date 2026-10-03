> Historical acceptance record for the former fixed metadata implementation.
> Superseded by [managed positions acceptance](infrastructure-topology-positions.md);
> field names, source paths and test totals below describe that earlier revision.

# Infrastructure Topology relationship layers — completion report

## A–C. Repository

- Branch: `feature/infrastructure-topology-v0`.
- HEAD: `2b8ee39bdc842678a7d619a17513e0267a807ae3`.
- Initial working tree was clean. No commit, push or merge performed.
- Final `git status --short` appears below.

## D–H. Schema and migration

`RelationshipType.topology_layer` is a non-null `varchar(32)` with server default
`other`, a database check constraint and bounded Create/PATCH/response schemas.
Migration `20260921_0021` follows `20260921_0020`. The one-time backfill applies
only to exact recognized stable keys with `system_defined=true`.

| Persisted value | UI label | Every current built-in assigned to it |
| --- | --- | --- |
| `platform` | Platform / containment | `contains`, `hosts`, `hosted_on`, `runs_on`, `runs`, `member_of` |
| `physical_network` | Physical / network | `connects_to`, `connected_to`, `belongs_to_network`, `uplinks_to`, `connected_via` |
| `data_resilience` | Data / resilience | `uses_storage`, `backs_up_to`, `backed_up_by`, `replicates_to`, `syncs_to` |
| `logical_operational` | Logical / operational | `protects`, `protected_by`, `depends_on`, `monitors`, `proxies`, `authenticates`, `exposes`, `served_by`, `provides_service_to`, `managed_by` |
| `other` | Other | `related_to`, `routes` |

The migration test verifies these are all 28 seeded built-ins. `provided_by` is
not a current built-in. Every existing custom or unrecognized type receives
`other`, including recognized keys marked custom and unknown system-defined keys.
Routes stays Other; no L3/routing inference is introduced.

IDs, keys, names, labels, direction, typed applicability, relationship rows,
lifecycle state and historical data are preserved. An inactive renamed built-in
is classified by key without changing its other fields. Re-running upgrade head
does not overwrite later administrator choices. Downgrade removes only the new
constraint/column. Migration was applied only to disposable test databases.

## I–K. Administration and API

Relationship Types has a compact Topology layer Add/Edit select, concise helper
text and plain list column. Add defaults to Other. Edit persists the selection;
deactivation retains it. No second visibility checkbox was added.

API accepts exactly the five registry keys. Arbitrary strings, labels, empty
strings, arrays and explicit null are rejected with 422. An omitted PATCH field
leaves the stored value unchanged. Existing global `relationship_types.manage`
authorization and audit events cover edits; scoped management cannot change
this global reference data. Existing direction, labels, Asset Type restrictions
and typed endpoint applicability remain intact.

## L–P. Connectivity and temporary filters

Defaults enable Platform / containment and Physical / network. Data / resilience,
Logical / operational and Other are off. The new Relationship layers section is
rendered from the bounded registry only in Connectivity; Asset categories remain.

Changed-count is the sum of category and layer values differing from their
respective defaults. Disabling Physical/network and enabling Logical/operational
counts as two. Reset restores current managed category defaults and layer defaults.
Ordinary tab entry resets layers. In-view refocus, Expand/close and Refresh retain
them. These controls do not write Reference Data.

`GET /api/topology/connectivity` adds comma-separated `topology_layers`; omission
uses defaults and an explicit empty string enables none. Unsupported values return
422. Existing routes and response contracts remain, with the additive Relationship
Type field. The default Connectivity result intentionally changes to infrastructure
layers. Platform and Knowledge Graph contracts/behavior are unchanged.

The backend filters RelationshipType layers before adjacency construction and BFS.
Tests prove disabled edges introduce no nodes, cannot supply second-hop paths and
consume no node slots, including logical peers that sort before the valid host.
The existing authorized endpoint projection remains authoritative for every layer.
Scope tests cover hidden customer/site endpoints and inaccessible focus, including
when all overlays are enabled.

## Q–U. Membership, fan-out and custom types

AssetInterface → Network membership remains separately derived, requires Physical /
network plus Networks visibility, and never becomes an AssetRelationship. A
Network explicitly focused while Physical/network is disabled can stand alone.

Existing path-aware tests still pass: AdGuard → PVE1 with 19 sibling workloads
does not expand those siblings; arriving through Network membership does not
expand peers; explicit host/Network focus includes direct members; genuine
technical second hops and parallel technical paths remain eligible. Platform
parent/child keys and direction were not changed, including `hosted_on` remaining
outside that existing parent projection despite its platform layer.

Custom acceptance uses real API/database tests plus production-browser fixtures:

| Custom type | Configured layer | Result |
| --- | --- | --- |
| Connected by fibre | Physical / network | Default visibility, hop traversal and configured labels/direction verified. |
| Talks to | Logical / operational | Hidden by default; eligible with logical overlay. |
| Paired with | Default Other | API/UI default verified; hidden by default; eligible with Other overlay. |

## V–AC. Validation

Commands run from `apps/api` or `apps/web` as appropriate. PostgreSQL commands
used explicit disposable database URLs; the API test database used
`PGCLIENTENCODING=UTF8`. Browser commands used the installed Chrome executable,
`ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-topology-browser/node_modules/playwright/index.mjs`
and a local production frontend at `http://127.0.0.1:3112`.

| Check | Command / evidence | Result |
| --- | --- | --- |
| Backend baseline | `.venv/bin/pytest -q tests/test_infrastructure_topology.py tests/test_infrastructure_topology_postgres.py tests/test_administration.py tests/test_operational_graph.py` | 67 passed, 8 PostgreSQL tests skipped before database startup. |
| Frontend baseline | `node --test tests/infrastructure-topology.test.mjs` | 9 passed. |
| Focused API, traversal, administration, Knowledge Graph, migration | `.venv/bin/pytest -q tests/test_topology_layers.py tests/test_topology_layers_postgres.py tests/test_topology_layers_migration_postgres.py tests/test_infrastructure_topology.py tests/test_infrastructure_topology_postgres.py tests/test_administration.py tests/test_operational_graph.py` | 85 passed, no skips. |
| Full API | `.venv/bin/pytest -q` with disposable migrated database | 424 passed, 3 skipped. All three empty-database migration tests passed separately. Existing deprecation warnings remain. |
| Final focused route/traversal check | `.venv/bin/pytest -q tests/test_topology_layers.py tests/test_topology_layers_postgres.py tests/test_infrastructure_topology.py tests/test_infrastructure_topology_postgres.py` | 27 passed. |
| Empty chain | `.venv/bin/alembic upgrade head` on fresh database | Passed through all 21 migrations. |
| Previous-head migration | `tests/test_topology_layers_migration_postgres.py` in focused run | Passed upgrade from 0020, all built-ins, custom/unknown defaults, complete record/relationship/applicability preservation, bounded DB constraint, idempotent head, downgrade/re-upgrade and single head. |
| Existing migration regressions | `.venv/bin/pytest -q tests/test_asset_category_migration_postgres.py tests/test_presentation_migration_postgres.py` with two empty databases | 2 passed. |
| Frontend tests | `npm test` | 146 passed. |
| Production build | `npm run build` | Passed. |
| Knowledge Graph regression | Operational graph tests plus layer reclassification API test; `node scripts/check-expanded-graph-browser.mjs` | API projection unchanged apart from generated timestamp; all 8 browser scenarios passed in light/dark desktop/mobile. |
| Topology/admin production browser | `node scripts/check-infrastructure-topology-browser.mjs` | All 6 scenarios passed: light/dark at 1440, 1100 and 800px, including admin create/edit, custom layer visibility, defaults/toggles/count/reset/tab re-entry/refocus/Expand/Refresh and explicit empty selection. |
| Alembic head | `.venv/bin/alembic heads` | Single head `20260921_0021`. |
| Documentation links | Relative file-target check in the five edited guides/indexes | Passed. |
| Whitespace | `git diff --check` | Clean. |

Browser acceptance uses isolated API fixtures and the actual Python Connectivity
service; it never modifies live knowledge. Screenshots and logs are under
`/tmp/atlas-layers-browser`, `/tmp/atlas-layers-knowledge-browser` and
`/tmp/atlas-layers-*.log`. No live deployment was performed.

## Material files and documentation

| File | Purpose |
| --- | --- |
| `apps/api/app/models.py` | Persisted layer and database bound. |
| `apps/api/app/topology_layers.py` | Bounded API/domain presentation keys and defaults. |
| `apps/api/app/schemas.py` | Create/PATCH/response validation. |
| `apps/api/app/routes/reference_data.py` | Existing admin response includes layer. |
| `apps/api/app/routes/topology.py` | Optional Connectivity layer selection query. |
| `apps/api/app/services/infrastructure_topology.py` | Filter before traversal; physical membership eligibility. |
| `apps/api/migrations/versions/20260921_0021_relationship_topology_layers.py` | Additive column, constraint and conservative built-in backfill. |
| `apps/api/tests/test_topology_layers.py` | Registry/schema/default/overlay/path/limit regressions. |
| `apps/api/tests/test_topology_layers_postgres.py` | Real admin/custom relationship API lifecycle, scope and Knowledge Graph invariance. |
| `apps/api/tests/test_topology_layers_migration_postgres.py` | Empty-chain/previous-head preservation, backfill, constraint and rollback. |
| `apps/api/tests/test_infrastructure_topology.py` | Existing fixtures explicitly classify their technical connections. |
| `apps/api/tests/test_models.py` | Additive schema inventory expectation. |
| `apps/api/tests/test_asset_category_migration_postgres.py` | New expected head for existing regression. |
| `apps/web/lib/topology-layers.json` | Shared frontend layer registry. |
| `apps/web/lib/infrastructure-topology.mjs` | Registry selection/default/count helper. |
| `apps/web/components/topology-category-filter.js` | Compact relationship-layer section. |
| `apps/web/app/topology/page.js` | Query selection, combined counts and reset/preservation lifecycle. |
| `apps/web/app/admin/relationship-types/page.js` | Select, safe default, list column and payload. |
| `apps/web/tests/infrastructure-topology.test.mjs` | Layer/default/combined-count/reset tests. |
| `apps/web/scripts/check-infrastructure-topology-browser.mjs` | Existing regressions plus production admin/layer acceptance fixtures. |
| `docs/admin/relationship-types.md` | Administrator classification guide. |
| `docs/admin/infrastructure-topology.md` | Default layers, temporary filters and membership behavior. |
| `docs/architecture/infrastructure-topology.md` | Registry, exact migration mapping, API contract and traversal boundaries. |
| `docs/architecture/data-model-v0.md` | Additive field semantics. |
| `docs/product/feature-ledger.md` | Implemented capability and evidence. |
| `docs/README.md` | Administrator guide link. |
| `docs/testing/infrastructure-topology-layers.md` | This completion report and validation evidence. |

## Remaining issues

None within the requested scope. Live-data deployment/acceptance was not performed;
production-build acceptance used isolated fixtures. Apply the migration through
the normal deployment process before running the updated API against an existing
application database.

## Repository state

```text
 M apps/api/app/models.py
 M apps/api/app/routes/reference_data.py
 M apps/api/app/routes/topology.py
 M apps/api/app/schemas.py
 M apps/api/app/services/infrastructure_topology.py
 M apps/api/tests/test_asset_category_migration_postgres.py
 M apps/api/tests/test_infrastructure_topology.py
 M apps/api/tests/test_models.py
 M apps/web/app/admin/relationship-types/page.js
 M apps/web/app/topology/page.js
 M apps/web/components/topology-category-filter.js
 M apps/web/lib/infrastructure-topology.mjs
 M apps/web/scripts/check-infrastructure-topology-browser.mjs
 M apps/web/tests/infrastructure-topology.test.mjs
 M docs/README.md
 M docs/admin/infrastructure-topology.md
 M docs/architecture/data-model-v0.md
 M docs/architecture/infrastructure-topology.md
 M docs/product/feature-ledger.md
?? apps/api/app/topology_layers.py
?? apps/api/migrations/versions/20260921_0021_relationship_topology_layers.py
?? apps/api/tests/test_topology_layers.py
?? apps/api/tests/test_topology_layers_migration_postgres.py
?? apps/api/tests/test_topology_layers_postgres.py
?? apps/web/lib/topology-layers.json
?? docs/admin/relationship-types.md
?? docs/testing/infrastructure-topology-layers.md
```
