# Infrastructure Topology — layered Connectivity completion report

## A–C. Repository

- Branch: `feature/infrastructure-topology-v0`.
- HEAD: `ef371c0f889e86f93f1c204b49507f3b09b78741`.
- Initial tree was clean. No commit, push, merge or branch change was performed.
- Final `git status --short` is recorded below.

## D–G. Managed Asset Type presentation

Inspection found managed category assignment, default icon URL, sort order,
lifecycle and descriptive metadata on AssetType, but no equivalent infrastructure
role field. Category remains responsible for filtering, accent, category icon and
broad taxonomy. Individual Asset icons retain cached Asset → Type default → generic
precedence.

The final bounded role registry is:

| Stable key | Label | Internal placement |
| --- | --- | --- |
| external | External / Internet | 10 |
| security_edge | Security / edge | 20 |
| routing | Routing | 30 |
| aggregation_network | Core / aggregation network | 40 |
| access_network | Access network | 50 |
| platform | Platform / host | 60 |
| infrastructure | Infrastructure appliance | 60 |
| workload | Workload | 70 |
| endpoint | Endpoint / device | 70 |
| automatic | Automatic | Relationship context; neutral fallback |

Administrators choose labels, never numeric ranks. Add/Edit has a compact
**Topology role** dropdown with the requested helper text, and the list shows the
configured label. Custom Types default to Automatic. Role writes use the existing
global `asset_types.manage` authorization and audit path; explicit null and
unsupported values return 422, while omitted PATCH fields remain unchanged.

Migration `20260921_0022` adds one non-null column/default/check constraint after
`0021`. Its exact built-in mapping is:

| Role | Built-in keys |
| --- | --- |
| security_edge | firewall |
| routing | router |
| access_network | switch, network_switch, access_point, network_bridge |
| platform | proxmox_host, hypervisor_node, node, server, physical_server, docker_host |
| infrastructure | nas, storage_pool, backup_target |
| workload | virtual_machine, container, lxc_container, docker_container, application, proxy, database, backup_job |
| automatic | unknown, network, vlan, proxmox_cluster, service |

These are all 28 current built-ins. Defaults apply only when the exact key is
recognized and `system_defined=true`. Custom Types, recognized keys marked custom,
and unknown future built-ins remain Automatic. There are no dedicated external,
aggregation or endpoint built-ins to classify; none are invented. Migration tests
preserve names, IDs, categories, icons, lifecycle state, Assets and relationships;
they also verify reapplying head retains subsequent administrator choices.

## H–L. Layout algorithm and generic behavior

The Connectivity API adds each Asset node's persisted role and each relationship
edge's managed layer plus optional `platform_parent_key` from the existing backend
projection. Traversal, authorization, hop/node/edge limits and canonical direction
are unchanged. There are no new routes or breaking response changes.

Pure layout helpers assign explicit roles to ordered horizontal bands. Only
occupied ranks consume space. Automatic uses recorded parent/child hints first,
then adjacent known physical/network roles. Snapshot rounds are bounded and do
not update explicit roles. An unanchored containment tree seeds a neutral root;
closed cycles and isolated Assets remain neutral instead of inventing hierarchy.
No Asset Type key, vendor, Asset name, icon or descriptive-text matching determines
placement. Name and durable identity are used solely for deterministic ordering.

Recorded upper neighbours determine horizontal grouping, with projected platform
parents preferred. Stable grids have up to four columns, widening to six for
expanded groups larger than twelve. Parents centre over their children; row
collision resolution and reserved grid height prevent card overlap. Final
coordinates translate around focus, preserving semantic vertical placement while
Fit/recentre clears stale pan and zoom. Positions are not persisted, and layout
remains separate from traversal so future optional overrides can be added.

## M–Q. Hosts, preview and rails

A focused host displays the first eight directly hosted/contained children in the
returned graph, ordered by name then durable key. **+N more** expands the remaining
returned children without a fetch, focus/hop change, data mutation or synthetic
domain node. Expansion survives in-view refocus, Refresh and expanded mode;
leaving Connectivity resets it. API truncation notices remain separate, so local
expansion never claims to fetch beyond the existing 25-node response.

Neighbour hosts retain their child counts and summarize second-hop child fan-out.
Direct focus neighbours and ancestors remain eligible. Double-clicking a host
refocuses and makes its own preview eligible. Backend anti-fan-out logic is
unchanged; this is an additional presentation preview over authorized results.

Hosted child grids share orthogonal distribution rails. Later rows use card
gutters, with arrow geometry respecting the original source/target direction.
Repeated labels are suppressed when the parent is selected; hover titles and
child selection/inspector retain individual relationship meaning and inspection.
No stored relationship is combined or reversed.

## R–T. Networks and relationship layers

Network nodes position relative to actual interface members: between differing
member ranks or just above a single member rank. They remain Network entities,
with configured icon/accent and dashed membership edges. Multihomed Assets retain
their own semantic rank; membership may cross bands.

Existing layer defaults remain Platform + Physical/network, including membership
when Networks are enabled. Data/resilience, Logical/operational and Other remain
optional. Layer filtering still happens before backend traversal. Existing
category/layer controls, tab resets, scope checks and path-aware anti-fan-out tests
remain in the validation suite.

## U–W. Expanded inspector

Expanded Connectivity has an icon-only **Hide details panel** / **Show details
panel** control with matching tooltip and accessible label. Hiding removes the
inspector's grid track, preserves selection and keeps the graph mounted. Selecting
another node while hidden updates inspection state; reopening shows that node.
Closing expanded mode restores the embedded inspector, with no global persistence.

The existing ResizeObserver updates available dimensions; Fit and zoom remain
valid after both transitions. Browser checks verify released width, selection,
no refetch, node containment and restoration. Embedded mode has no toggle.

## X–Z. Acceptance fixtures

- Custom Type fixtures use arbitrary keys/names with explicit roles for edge,
  fabric, compute and runtime; the browser calls the actual Python Connectivity
  service. Both API and browser tests verify metadata flows through without a
  vendor/type-name rule.
- The homelab-shaped fixture includes external/edge/fabric/access infrastructure,
  three hosts, and child counts 18/4/3. Tests assert top-to-bottom geometry, aligned
  hosts, recorded horizontal grouping and neighbour summaries. Browser checks use
  bounded neighbourhoods: a fabric focus shows the upper hierarchy and hosts;
  host focus shows the lower hierarchy and workloads. They do not bypass hops or
  expand neighbour-host families to fabricate an all-environment graph.
- An 18-child focused host shows exactly eight plus **+10 more**, then all 18 using
  rails and a wider grid. Refocusing a workload preserves its position below its
  host and excludes siblings. A custom Automatic appliance falls between its
  recorded network and platform neighbours.
- Light/dark at 1440, 1100 and 800px exercise layout, local expansion/reset,
  role edit/reload, inspector hide/select/show/close, Fit and card containment.
- Unit fixtures additionally cover missing layers without placeholders,
  multihoming without role movement, deterministic ordering, cycles and canonical
  rail direction.

## AA–AF. Tests and validation

Commands run from `apps/api` or `apps/web` as applicable. PostgreSQL checks use
explicit disposable database URLs and `PGCLIENTENCODING=UTF8`. Browser runs use
installed Chrome, the local Playwright module and the production frontend at
`http://127.0.0.1:3112`; fixtures never write to live Atlas knowledge.

| Check | Command | Result |
| --- | --- | --- |
| Backend baseline | `.venv/bin/pytest -q tests/test_infrastructure_topology.py tests/test_topology_layers.py tests/test_infrastructure_topology_postgres.py tests/test_topology_layers_postgres.py tests/test_administration.py` | 54 passed with PostgreSQL; initial unconfigured run was 44 passed / 10 skipped. |
| Frontend baseline | `node --test tests/infrastructure-topology.test.mjs` | 10 passed. |
| Browser baseline | `node scripts/check-infrastructure-topology-browser.mjs` | All six light/dark/width scenarios passed against the prior production build. |
| Final focused backend | `.venv/bin/pytest -q tests/test_topology_roles.py tests/test_topology_roles_postgres.py tests/test_infrastructure_topology.py tests/test_topology_layers.py tests/test_infrastructure_topology_postgres.py tests/test_topology_layers_postgres.py tests/test_administration.py tests/test_models.py` | 71 passed. |
| Full backend | `.venv/bin/pytest -q` | 427 passed, four empty-database migration tests skipped here and passed separately. |
| New role migration | `tests/test_topology_roles_migration_postgres.py` in the migration-enabled focused run | Passed empty chain → 0021 → head, preservation, all built-in/custom defaults, constraints, idempotent head, downgrade and re-upgrade. |
| Existing migrations | `.venv/bin/pytest -q tests/test_asset_category_migration_postgres.py tests/test_presentation_migration_postgres.py tests/test_topology_layers_migration_postgres.py` | 3 passed on separate empty databases. |
| Frontend tests | `npm test` | 151 passed. |
| Production build | `npm run build` | Passed. |
| Targeted layered browser | `ATLAS_LAYERED_ONLY=1 node scripts/check-infrastructure-topology-browser.mjs` | All six scenarios passed. |
| Complete topology browser | `node scripts/check-infrastructure-topology-browser.mjs` | All six complete light/dark/width scenarios passed, including layered acceptance and relationship-layer regressions. |
| Knowledge Graph browser | `node scripts/check-expanded-graph-browser.mjs` | All eight scenarios passed. |
| Alembic heads | `.venv/bin/alembic heads` | Single head `20260921_0022`. |
| Documentation links | Relative file-target check across six changed guides/indexes | Passed. |
| Whitespace | `git diff --check` | Clean. |

Existing framework deprecation warnings remain. Logs are under
`/tmp/atlas-layered-*.log`; topology screenshots are under
`/tmp/atlas-layered-browser`, baseline screenshots under
`/tmp/atlas-layered-baseline`, and Knowledge Graph screenshots under
`/tmp/atlas-layered-knowledge-browser`. Representative light-theme three-host,
eight-child and expanded 18-child screenshots were visually inspected.

## Material files

| File | Purpose |
| --- | --- |
| `apps/api/app/models.py` | Persisted role/default/database bound. |
| `apps/api/app/topology_roles.py` | Bounded API role registry. |
| `apps/api/app/schemas.py` | Create/PATCH/response role validation and additive graph metadata. |
| `apps/api/app/routes/reference_data.py` | Asset Type admin responses carry persisted role. |
| `apps/api/app/services/infrastructure_topology.py` | Serialize role/layer/projected parent without changing traversal. |
| `apps/api/migrations/versions/20260921_0022_asset_type_topology_roles.py` | One additive, conservative built-in backfill migration. |
| `apps/api/tests/test_topology_roles.py` | Registry/schema/default/metadata invariance checks. |
| `apps/api/tests/test_topology_roles_postgres.py` | Custom admin lifecycle, graph metadata and scope checks. |
| `apps/api/tests/test_topology_roles_migration_postgres.py` | Upgrade/preservation/default/constraint/downgrade checks. |
| `apps/api/tests/test_administration.py` | Existing unpersisted fixture supplies the new persisted default. |
| `apps/api/tests/test_models.py` | Expected additive column. |
| `apps/api/tests/test_asset_category_migration_postgres.py` | Expected current head. |
| `apps/api/tests/test_topology_layers_migration_postgres.py` | Expected current head. |
| `apps/web/lib/topology-roles.json` | Role labels and internal layout ranks. |
| `apps/web/lib/infrastructure-topology.mjs` | Layered layout, Automatic hints, local preview and rail geometry. |
| `apps/web/app/admin/asset-types/page.js` | Compact role Add/Edit/select/default/payload/list. |
| `apps/web/app/topology/page.js` | Preview expansion, rail rendering and ephemeral inspector state. |
| `apps/web/app/globals.css` | Released inspector track, compact preview button and rail hover. |
| `apps/web/components/navigation-icon.mjs` | Small panel icon following existing icon conventions. |
| `apps/web/tests/connectivity-layout.test.mjs` | Custom/missing/homelab/host/Automatic/Network geometry regressions. |
| `apps/web/tests/infrastructure-topology.test.mjs` | Replace obsolete radial-sector assertion with layered determinism. |
| `apps/web/scripts/check-infrastructure-topology-browser.mjs` | Production fixtures and new role/layout/preview/panel acceptance. |
| `docs/admin/asset-types.md` | New administrator role guide. |
| `docs/admin/infrastructure-topology.md` | Layered presentation, preview and panel behavior. |
| `docs/architecture/infrastructure-topology.md` | Algorithm, boundaries, metadata contract and exact migration mapping. |
| `docs/architecture/data-model-v0.md` | Additive presentation field. |
| `docs/product/feature-ledger.md` | Implemented capability and evidence. |
| `docs/README.md` | Asset Type guide link. |
| `docs/testing/infrastructure-topology-layered-layout.md` | This completion report. |

## Remaining boundaries

No live-data deployment was performed. Apply migration `0022` through the normal
deployment process before running this API on an existing application database.
Persisted manual positions remain intentionally deferred. The existing 1/2-hop,
25-node and 150-edge bounds remain; +N expands only children within that result.
No discovery, accepted-knowledge, reconciliation, impact-analysis or worker
behavior was added or changed.

## Repository state

```text
 M apps/api/app/models.py
 M apps/api/app/routes/reference_data.py
 M apps/api/app/schemas.py
 M apps/api/app/services/infrastructure_topology.py
 M apps/api/tests/test_administration.py
 M apps/api/tests/test_asset_category_migration_postgres.py
 M apps/api/tests/test_models.py
 M apps/api/tests/test_topology_layers_migration_postgres.py
 M apps/web/app/admin/asset-types/page.js
 M apps/web/app/globals.css
 M apps/web/app/topology/page.js
 M apps/web/components/navigation-icon.mjs
 M apps/web/lib/infrastructure-topology.mjs
 M apps/web/scripts/check-infrastructure-topology-browser.mjs
 M apps/web/tests/infrastructure-topology.test.mjs
 M docs/README.md
 M docs/admin/infrastructure-topology.md
 M docs/architecture/data-model-v0.md
 M docs/architecture/infrastructure-topology.md
 M docs/product/feature-ledger.md
?? apps/api/app/topology_roles.py
?? apps/api/migrations/versions/20260921_0022_asset_type_topology_roles.py
?? apps/api/tests/test_topology_roles.py
?? apps/api/tests/test_topology_roles_migration_postgres.py
?? apps/api/tests/test_topology_roles_postgres.py
?? apps/web/lib/topology-roles.json
?? apps/web/tests/connectivity-layout.test.mjs
?? docs/admin/asset-types.md
?? docs/testing/infrastructure-topology-layered-layout.md
```
