# Managed Topology Positions acceptance

## A–C. Repository

Branch: `feature/infrastructure-topology-v0`.
Base HEAD: `c09ff3fa81037ba1ee8ce76dfcd2464954716061`.
All changes remain uncommitted; no push or merge was performed.

## D–H. Current → target

The inspected implementation had bounded `AssetType.topology_role` introduced by
migration `20260921_0022` and bounded `RelationshipType.topology_layer` introduced
by `20260921_0021`. There was no intermediate position string.

The new `TopologyPosition` model has UUID id, immutable unique key, unique name,
description, unique nonnegative sort_order, active state and normal timestamps.
AssetType's sole writable placement field is nullable `topology_position_id`,
with a restrictive FK and joined `topology_position` response summary. Relationship
Type's bounded field is `topology_class`. Connectivity nodes carry the managed
summary; edges carry the renamed classification. The classification query argument
is `topology_classes`. First-party callers deploy with these intentional renames;
existing route paths, relationship meanings, direction and authorization remain.

## I–O. Migration

One new migration: `20260921_0023_managed_topology_positions.py`; previous migration
files are unchanged. Exactly one Alembic head: `20260921_0023`.

The actual registry contained these entries, seeded with their original labels:

| Key | Label | New sort order |
| --- | --- | --- |
| external | External / Internet | 0 |
| security_edge | Security / edge | 1 |
| routing | Routing | 2 |
| aggregation_network | Core / aggregation network | 3 |
| access_network | Access network | 4 |
| platform | Platform / host | 5 |
| infrastructure | Infrastructure appliance | 6 |
| workload | Workload | 7 |
| endpoint | Endpoint / device | 8 |
| automatic | No row; null FK | — |

**Ordering decision:** the actual former registry tied Platform/Infrastructure at
60 and Workload/Endpoint at 70. Exact same-band preservation conflicts with the
requested unique independently movable ranks. The implementation resolves each
tie in original registry sequence. This is the sole initial layout difference;
it is disclosed in the admin and architecture guides. All assignments and other
relative order are preserved.

Unexpected legacy values become extra positions, retaining distinct assignments.
Fresh and populated upgrade, downgrade and re-upgrade were executed on isolated
empty PostgreSQL databases. Tests compare Asset Type IDs/other fields, complete
Asset records and relationship classification values. Automatic becomes null.
Downgrade reconstructs keys and Automatic, retaining used custom keys in its
check. The older bounded API may not recognize retained custom keys. Assigned keys longer than the former varchar(32) capacity block downgrade
before modification; explicit reassignment is required, with no truncation.
Managed-only custom names/order/active state cannot be represented by the old
schema and are not preserved through downgrade.

## P–T. Administration

System → Reference Data → Topology Positions reuses CrudScreen and existing
`asset_types.view` / global `asset_types.manage` permissions. Each mutation is
audited. The page has Order, Name, Key, Description, Asset Types, State and actions.
Add appends; edit excludes key and numeric rank. Up/down swaps adjacent ranks,
serializing ordering writes with a PostgreSQL table lock and enforcing uniqueness
with a deferred constraint. Boundary moves are harmless and their UI controls
are disabled. Buttons have per-record aria labels and native keyboard access.

Used deletion is rejected in both the API and FK. Inactive positions retain
existing references and placement, remain resolvable in the editor, and cannot
be newly assigned. Usage counts count global Asset Types only. Asset Type options
load dynamically, start with Automatic, follow configured order and retain a
labelled inactive existing assignment. No operational tenant counts are exposed.

## U–Z. Layout

The fixed role registry and runtime rank mapping are removed. Explicit positions
use API sort_order; arbitrary keys and unusual ordering are authoritative. Pure
layout tests cover Alpha/Beta/Gamma/Delta, arbitrary Type names, inactive records,
renames, reordering and Storage Fabric inserted between existing positions.
Empty positions consume no band. `connectivityBands` exposes occupied position
id/key/name/order metadata for future presentation work without adding decoration.
Automatic uses bounded deterministic relationship/neighbour inference and a
neutral fallback. Layout never parses vendors, names, hostnames or Type labels.
Network placement still derives from structured interface membership.

## AA–AH. Classification and UX

Relationship Type admin says Topology class; Connectivity Filters say Relationship
classes. The five bounded keys and defaults are unchanged: platform and
physical/network on; data/resilience, logical/operational and other off. Filtering
still occurs before traversal and preserves anti-fan-out, bounds, cycles and
canonical edge direction. Existing API tests include scope/non-disclosure and
Knowledge Graph invariance.

Browser acceptance exercises eight-child host preview, local +N expansion,
compact neighbour hosts, layered geometry, single-click selection, double-click
and explicit refocus, Network membership/toggle, Fit, full-screen inspector
hide/show, and light/dark at 1440, 1100 and 800px. New reference-data acceptance
covers CRUD, immutable key, keyboard movement, reload persistence, usage counts,
inactive options and arbitrary custom-position ordering.

## AI–AN. Validation

All commands ran from the relevant `apps/api` or `apps/web` directory. PostgreSQL
runs used `PGCLIENTENCODING=UTF8` and explicitly provisioned disposable databases
through the existing test environment variables. No application database was
migrated. Initial connection attempts exposed a role-name/client-encoding setup
issue; corrected baseline database tests passed.

| Check | Executed result |
| --- | --- |
| Baseline focused backend | 60 passed |
| Baseline PostgreSQL role/class/topology APIs | 11 passed |
| Baseline `npm test` | 151 passed |
| Full backend `.venv/bin/pytest -q` | 429 passed, 5 separate empty-database migration tests skipped |
| Final position/model tests, including two added rank/reorder checks | 19 passed |
| New position migration test | 1 passed: fresh/populated upgrade, downgrade, re-upgrade, unexpected legacy key, long-key rollback protection |
| Four historical migration tests on separate empty databases | 4 passed |
| Final `npm test` | 152 passed |
| `npm run build` | Passed; new admin route included |
| Focused production-browser topology and Reference Data | 6 scenarios passed |
| Full production-browser acceptance | 6 scenarios passed, including arbitrary custom positions and graph reorder |
| `.venv/bin/alembic heads` | `20260921_0023 (head)` |
| Local documentation destination check | 64 checked, 0 missing |
| `git diff --check` | Passed |

Browser harness: `scripts/check-infrastructure-topology-browser.mjs`, using the
production Next build and isolated intercepted API fixtures. Its graph requests
execute the real Python Connectivity service. PostgreSQL API tests separately
exercise persistence, permissions and migration behavior. This is production-build
browser acceptance, not a live-data manual session. No shared Knowledge Graph
renderer changed; its backend and frontend regressions run in the full suites.

The old-term audit covers the complete active source tree. Remaining occurrences
are limited to unchanged historical migrations, explicit upgrade/downgrade code,
migration regression tests, the migration explanation in architecture docs and this acceptance report,
and two clearly marked historical testing records. Runtime/UI have none.
The classification regression test filenames retain their historical names.

Documentation updated: admin Asset Types, Relationship Types, Topology Positions,
Infrastructure Topology, data model, topology architecture, docs index and feature
ledger. Prior fixed-metadata acceptance reports are marked historical.

Final browser screenshots and logs: `/tmp/atlas-positions-browser-final` and
`/tmp/atlas-positions-browser-final.log`. Representative admin and narrow graph
screenshots were visually inspected. Backend, migration, frontend and build logs
are `/tmp/atlas-positions-api-full.log`, `/tmp/atlas-positions-history-tests.log`,
`/tmp/atlas-positions-web-tests.log` and `/tmp/atlas-positions-build.log`.

Principal executed validation commands (database/browser environment configured
as described above):

```bash
# apps/api
.venv/bin/pytest -q
.venv/bin/pytest -q tests/test_topology_positions_postgres.py tests/test_models.py
.venv/bin/pytest -q tests/test_topology_positions_migration_postgres.py
.venv/bin/pytest -q tests/test_asset_category_migration_postgres.py tests/test_presentation_migration_postgres.py tests/test_topology_layers_migration_postgres.py tests/test_topology_roles_migration_postgres.py
.venv/bin/alembic heads
# apps/web
npm test
npm run build
ATLAS_LAYERED_ONLY=1 node scripts/check-infrastructure-topology-browser.mjs
node scripts/check-infrastructure-topology-browser.mjs
# repository root
git diff --check
git status --short --untracked-files=all
```

No unresolved implementation or validation failures remain. Initial shared-band
placement is deliberately changed as described above; downgrade limitations are
explicit. No production database or live operational records were modified.

## Material files and repository state

The inventory below includes every changed/new/deleted file and its purpose.

| File | Purpose |
| --- | --- |
| `apps/api/app/main.py` | Register the managed-position API. |
| `apps/api/app/models.py` | Managed Position model, Asset Type FK and classification rename. |
| `apps/api/app/routes/reference_data.py` | Validate position assignments and return managed metadata. |
| `apps/api/app/routes/topology.py` | Rename the Connectivity classification query. |
| `apps/api/app/schemas.py` | Explicit position contracts and renamed bounded class schemas. |
| `apps/api/app/services/infrastructure_topology.py` | Project managed node metadata and preserve class eligibility. |
| `apps/api/app/topology_layers.py` | Replaced by topology_classes.py. |
| `apps/api/app/topology_roles.py` | Remove the obsolete fixed placement registry. |
| `apps/api/tests/test_administration.py` | Contract, layout, lifecycle, authorization or classification regression coverage. |
| `apps/api/tests/test_asset_category_migration_postgres.py` | Migration round-trip coverage or updated head expectation. |
| `apps/api/tests/test_infrastructure_topology.py` | Contract, layout, lifecycle, authorization or classification regression coverage. |
| `apps/api/tests/test_models.py` | Contract, layout, lifecycle, authorization or classification regression coverage. |
| `apps/api/tests/test_topology_layers.py` | Contract, layout, lifecycle, authorization or classification regression coverage. |
| `apps/api/tests/test_topology_layers_migration_postgres.py` | Migration round-trip coverage or updated head expectation. |
| `apps/api/tests/test_topology_layers_postgres.py` | Contract, layout, lifecycle, authorization or classification regression coverage. |
| `apps/api/tests/test_topology_roles.py` | Superseded by managed-position tests. |
| `apps/api/tests/test_topology_roles_migration_postgres.py` | Migration round-trip coverage or updated head expectation. |
| `apps/api/tests/test_topology_roles_postgres.py` | Superseded by managed-position tests. |
| `apps/web/app/admin/asset-types/page.js` | Dynamic managed-position assignment and inactive labels. |
| `apps/web/app/admin/relationship-types/page.js` | Topology class labels and payload. |
| `apps/web/app/topology/page.js` | Classification controls and query rename. |
| `apps/web/components/crud-screen.js` | Optional accessible reordering and configurable empty select label. |
| `apps/web/components/topology-category-filter.js` | Relationship classes control labels and props. |
| `apps/web/lib/infrastructure-topology.mjs` | Data-driven ranks, Automatic inference and occupied-band metadata. |
| `apps/web/lib/system-navigation.mjs` | Add the authorized Reference Data destination. |
| `apps/web/lib/topology-layers.json` | Replaced by topology-classes.json. |
| `apps/web/lib/topology-roles.json` | Remove the obsolete fixed rank registry. |
| `apps/web/scripts/check-infrastructure-topology-browser.mjs` | Production-browser metadata, lifecycle, reorder and UX acceptance. |
| `apps/web/tests/connectivity-layout.test.mjs` | Contract, layout, lifecycle, authorization or classification regression coverage. |
| `apps/web/tests/infrastructure-topology.test.mjs` | Contract, layout, lifecycle, authorization or classification regression coverage. |
| `docs/README.md` | Document the current model, lifecycle, terminology and initial tie resolution. |
| `docs/admin/asset-types.md` | Document the current model, lifecycle, terminology and initial tie resolution. |
| `docs/admin/infrastructure-topology.md` | Document the current model, lifecycle, terminology and initial tie resolution. |
| `docs/admin/relationship-types.md` | Document the current model, lifecycle, terminology and initial tie resolution. |
| `docs/architecture/data-model-v0.md` | Document the current model, lifecycle, terminology and initial tie resolution. |
| `docs/architecture/infrastructure-topology.md` | Document the current model, lifecycle, terminology and initial tie resolution. |
| `docs/product/feature-ledger.md` | Document the current model, lifecycle, terminology and initial tie resolution. |
| `docs/testing/infrastructure-topology-layered-layout.md` | Mark the prior acceptance record historical without rewriting its evidence. |
| `docs/testing/infrastructure-topology-layers.md` | Mark the prior acceptance record historical without rewriting its evidence. |
| `apps/api/app/routes/topology_positions.py` | Audited CRUD, usage counts and serialized adjacent movement. |
| `apps/api/app/topology_classes.py` | Renamed bounded classification registry. |
| `apps/api/migrations/versions/20260921_0023_managed_topology_positions.py` | Direct preserving upgrade and safe downgrade to the actual former fields. |
| `apps/api/tests/test_topology_positions.py` | Contract, layout, lifecycle, authorization or classification regression coverage. |
| `apps/api/tests/test_topology_positions_migration_postgres.py` | Migration round-trip coverage or updated head expectation. |
| `apps/api/tests/test_topology_positions_postgres.py` | Contract, layout, lifecycle, authorization or classification regression coverage. |
| `apps/web/app/admin/topology-positions/page.js` | Reference Data management page. |
| `apps/web/lib/topology-classes.json` | Unchanged bounded classification choices under the new name. |
| `docs/admin/topology-positions.md` | Document the current model, lifecycle, terminology and initial tie resolution. |
| `docs/testing/infrastructure-topology-positions.md` | Completion report, test evidence and complete repository inventory. |

`git status --short --untracked-files=all`:

```text
 M apps/api/app/main.py
 M apps/api/app/models.py
 M apps/api/app/routes/reference_data.py
 M apps/api/app/routes/topology.py
 M apps/api/app/schemas.py
 M apps/api/app/services/infrastructure_topology.py
 D apps/api/app/topology_layers.py
 D apps/api/app/topology_roles.py
 M apps/api/tests/test_administration.py
 M apps/api/tests/test_asset_category_migration_postgres.py
 M apps/api/tests/test_infrastructure_topology.py
 M apps/api/tests/test_models.py
 M apps/api/tests/test_topology_layers.py
 M apps/api/tests/test_topology_layers_migration_postgres.py
 M apps/api/tests/test_topology_layers_postgres.py
 D apps/api/tests/test_topology_roles.py
 M apps/api/tests/test_topology_roles_migration_postgres.py
 D apps/api/tests/test_topology_roles_postgres.py
 M apps/web/app/admin/asset-types/page.js
 M apps/web/app/admin/relationship-types/page.js
 M apps/web/app/topology/page.js
 M apps/web/components/crud-screen.js
 M apps/web/components/topology-category-filter.js
 M apps/web/lib/infrastructure-topology.mjs
 M apps/web/lib/system-navigation.mjs
 D apps/web/lib/topology-layers.json
 D apps/web/lib/topology-roles.json
 M apps/web/scripts/check-infrastructure-topology-browser.mjs
 M apps/web/tests/connectivity-layout.test.mjs
 M apps/web/tests/infrastructure-topology.test.mjs
 M docs/README.md
 M docs/admin/asset-types.md
 M docs/admin/infrastructure-topology.md
 M docs/admin/relationship-types.md
 M docs/architecture/data-model-v0.md
 M docs/architecture/infrastructure-topology.md
 M docs/product/feature-ledger.md
 M docs/testing/infrastructure-topology-layered-layout.md
 M docs/testing/infrastructure-topology-layers.md
?? apps/api/app/routes/topology_positions.py
?? apps/api/app/topology_classes.py
?? apps/api/migrations/versions/20260921_0023_managed_topology_positions.py
?? apps/api/tests/test_topology_positions.py
?? apps/api/tests/test_topology_positions_migration_postgres.py
?? apps/api/tests/test_topology_positions_postgres.py
?? apps/web/app/admin/topology-positions/page.js
?? apps/web/lib/topology-classes.json
?? docs/admin/topology-positions.md
?? docs/testing/infrastructure-topology-positions.md
```
