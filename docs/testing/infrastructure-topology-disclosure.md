# Infrastructure Topology branch disclosure and capacity

## Scope and reproduction

Branch: `feature/infrastructure-topology-v0`.
Starting HEAD: `61c29acf653196ebbc22f768ea7f1243728facd4`.
The working tree was clean before this change. No commit, push or merge.

A focused arbitrary-type parent with 18 children and eight other infrastructure
neighbours reproduced the reported loss at two hops: the old 25-node request
returned 16 workloads with `truncated=true`. Clipping occurred in server BFS,
before API serialization or frontend layout. The same fixture now returns all
27 nodes, including all 18 children, without truncation. Existing arrival-state
anti-fan-out rules and one/two-hop bounds remain intact.

## Platform facts

Previously every root card emitted both counts, including zero children and
zero interfaces, and always used plural wording. Cards now show positive facts
only: `18 child Assets · 1 interface`, `1 interface`, or `1 child Asset · 2
interfaces`. Neither fact means no metadata element. Counts retain the existing
canonical parent projection: `runs_on`/`member_of` target is parent;
`hosts`/`contains`/`runs` source is parent. Parallel links count each child once.
No category, vendor or Asset Type name rules were introduced.

## Capacity, contracts and authorization

The service owns `MAX_CONNECTIVITY_NODES=100` and
`MAX_CONNECTIVITY_EDGES=500`. Previously the default/page request was 25 nodes,
the API allowed up to 60, and the service clipped edges at 150. The page now
omits `limit`, using the server default. Smaller explicit limits remain valid;
limits above 100 return 422. Responses add `node_limit`/`edge_limit`, and nodes
add `eligible_child_count`/`returned_child_count`. Existing fields and routes
remain. No database migration or accepted-knowledge write is required.

Counts use deduplicated canonical relationships after existing authorization,
customer/site scoping and category/class filters. Returned counts use the final
edge set. Networks and AssetInterface membership never become child Assets.
Eligible counts can exceed returned counts because of hop/arrival policy or
safety clipping. Expansion controls count only returned hidden nodes, so they
never promise unavailable children. The safety warning is independent of UI
collapse; the normal count excludes presentation controls.

The server retains cycle-safe bounded BFS and a discovery edge for every returned
node before dense-edge clipping. The existing loader still materializes the
scoped authorized topology before traversal; the 100/500 policy bounds traversal
and output, not SQL loading. No new queries, worker or discovery infrastructure.

## Branch controls and layout

- Focused parents show their first eight eligible returned children in stable
  name/key order. A connected circular `+N more` control reveals the remainder.
- Neighbours with no displayed children have a small sibling-button `+N` badge.
  It opens up to eight; further children get a connected more control. The two
  controls never appear simultaneously for one parent.
- Expansion changes only ephemeral state. It preserves focus, selected entity,
  filters, hops and Networks, survives Refresh/fullscreen, and resets when focus
  changes or Connectivity is left.
- Card click inspects and double-click refocuses. Disclosure controls stop pointer,
  click and double-click propagation and use native button keyboard behavior.
  Browser checks exercise Tab, Enter and Space.
- Synthetic nodes and edges live in separate presentation collections merged
  only for layout/rendering. They have no Asset icon/type/status/IP, no inspector
  action, and never enter the API, traversal, analysis or accepted knowledge.
- Children retain managed position bands and parent grouping. The more control
  follows the visible child group; existing distribution rails and canonical
  relationship arrow direction remain. Networks retain dashed membership edges.

## Validation

Commands run from `apps/api` unless noted. PostgreSQL checks use a freshly
migrated, disposable UTF-8 database with `ATLAS_TEST_DATABASE_URL`; tests roll
back their records. No live inventory was edited. Browser requests use isolated
fixtures and the production Python traversal against the production web build.

| Check | Result |
| --- | --- |
| `.venv/bin/pytest -q tests/test_infrastructure_topology.py tests/test_infrastructure_topology_postgres.py tests/test_topology_layers.py tests/test_topology_layers_postgres.py tests/test_topology_positions.py tests/test_topology_positions_postgres.py tests/test_auth.py tests/test_operational_graph.py` | 108 passed, including API serialization, hidden endpoint/count non-disclosure, site/customer boundaries, managed positions/classes, 18/120-child fixtures, dense edge clipping and graph regression. |
| Subsequent focused `.venv/bin/pytest -q tests/test_infrastructure_topology.py` | 13 passed after adding category/class/deduplication count regression. |
| Web `node --test tests/infrastructure-topology.test.mjs tests/connectivity-layout.test.mjs` | 21 passed. |
| Web `npm test` | 157 passed. |
| Web `npm run build` | Passed. |
| Web `ATLAS_DISCLOSURE_ONLY=1 node scripts/check-infrastructure-topology-browser.mjs` | Six light/dark scenarios at 1440/1100/800 px passed, including explicit Tab navigation, both expansion stages, selection/focus preservation and fullscreen. |
| Web `node scripts/check-infrastructure-topology-browser.mjs` | Six light/dark scenarios at 1440/1100/800 px passed. Includes search/focus, one/two hops, filters, Networks, anti-fan-out, pointer inspection/refocus, full screen, Fit, safety clipping and managed-position CRUD/order. |
| `.venv/bin/alembic heads` | Single existing head `20260921_0023`; no migration added. |
| `git diff --check` | Clean. |

The initial test-database setup exposed its SQL_ASCII default; a separate UTF-8
disposable database resolved the driver failure. Framework deprecation warnings
remain. No test failures were removed or suppressed.

Local in-memory measurements over 100 runs: traversal medians were 0.09 ms for
18 children, 0.40 ms for 120, and 2.09 ms for 1,000 (the latter two return 100
nodes with truncation). Pure disclosure/layout median was 0.09 ms for the
nine-node preview and 0.36 ms for 100 expanded nodes. These are local smoke
measurements, not database latency or production performance claims.

Logs/screenshots: `/tmp/atlas-disclosure-api.log`,
`/tmp/atlas-disclosure-web-tests.log`, `/tmp/atlas-disclosure-build.log`,
`/tmp/atlas-disclosure-browser`, `/tmp/atlas-disclosure-full-browser` and matching
browser logs. Representative initial/expanded light/dark screenshots were
visually inspected. Shared Knowledge Graph components were not changed; existing
operational graph regression tests and the web suite passed.

## Material files

| File | Purpose |
| --- | --- |
| `apps/api/app/services/infrastructure_topology.py` | Authoritative capacity and scoped eligible/returned child metadata. |
| `apps/api/app/routes/topology.py` | Server-owned default and maximum request limit. |
| `apps/api/app/schemas.py` | Additive limit/count response fields. |
| `apps/api/tests/test_infrastructure_topology.py` | Reproduction, limits, class/category/deduplication and dense-edge tests. |
| `apps/api/tests/test_infrastructure_topology_postgres.py` | Actual API capacity and unauthorized-child count tests. |
| `apps/web/lib/infrastructure-topology.mjs` | Fact formatting, branch disclosure and synthetic layout inputs. |
| `apps/web/app/topology/page.js` | Non-zero facts, local buttons, state, safety copy and visible count. |
| `apps/web/app/globals.css` | Circular disclosure controls and focus styling. |
| `apps/web/tests/connectivity-layout.test.mjs` | Local expansion, shared children/cycles, synthetic placement and clipping. |
| `apps/web/tests/infrastructure-topology.test.mjs` | Fact grammar and zero omission. |
| `apps/web/scripts/check-infrastructure-topology-browser.mjs` | Production pointer/keyboard/scale acceptance and updated limit expectations. |
| `docs/admin/infrastructure-topology.md` | User-facing facts, branch controls and capacity behavior. |
| `docs/architecture/infrastructure-topology.md` | Contract, safety policy, state and presentation boundary. |
| `docs/product/feature-ledger.md` | Implemented facts and disclosure/capacity evidence. |
| `docs/testing/infrastructure-topology-disclosure.md` | This reproduction and validation record. |

No unresolved implementation issues identified. Live-data manual acceptance was
not performed; browser acceptance used isolated fixtures. Hop/arrival exclusions
remain intentional and cannot be expanded with presentation controls.
