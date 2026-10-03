# Infrastructure Topology usability polish validation

21 September 2026. Isolated fixtures shaped like the reported homelab were used;
no live homelab records were accessed or changed. This supplements the original
[implementation record](infrastructure-topology-v0.md).

## A–C: Repository

- Branch: `feature/infrastructure-topology-v0`.
- HEAD: `4884d9a0b912d98c15d32d152f27a864cb311d9c`.
- Starting working tree was clean. No commit, push, merge or branch change.
- Final `git status --short` appears below.

## D–G: Overview and navigation

Overview shows six Assets per category, ordered by name then durable ID. The
category total and **+N** remainder use the authorized, category-filtered
projection. Categories with six or fewer Assets show all previews without +0.
**View all** and **+N** link to `/assets?category_id=<managed UUID>`. Each preview
links to `/assets/<UUID>`; native Back returns to Overview. Overview never renders
an Asset inspector or Close details control, and changing view clears selection.
The sidebar reads **Topology**, while the heading remains **Infrastructure
Topology**, the route stays `/topology`, and its distinct icon is retained.

## H–I: Detached icons

The old rendering boundary mixed SVG `foreignObject` coordinates with the shared
AssetIcon's relatively positioned slot and absolutely positioned image layers.
Cards now live in an HTML layer over SVG edges. Each fixed 180×88 card contains
its shared AssetIcon (or semantic Network icon) in a normal flex slot. One world
transform moves/scales cards and edges together. Cached-image loading and fallback
do not alter card dimensions. Focus and selection borders enclose the whole card.
Browser checks measure both icon slots and image rectangles inside card bounds,
including broken cached icons, both themes, zoom, canvas scrolling and Fit.

## J–P: Traversal, limits and layout

The congestion came from undirected BFS over all edge families: child → parent →
siblings and Asset → Network → peer memberships were treated as ordinary second
hops. The service now records arrival state for each traversal path:

- After child→parent containment arrival, suppress parent→child containment
  expansion. Canonical keys remain `runs_on`/`member_of` (target is parent) and
  `hosts`/`contains`/`runs` (source is parent).
- After Asset→Network interface-membership arrival, suppress membership expansion
  back to peer Assets.
- Other recorded relationships remain eligible. A host's technical connection to
  a switch still continues. A separate eligible parallel technical path is not
  accidentally suppressed by a containment path.
- Explicit host or Network focus starts without an arrival restriction, so its
  direct children/members remain eligible.

Authorization and category filtering precede traversal. Direction labels remain
recorded direction, including reverse traversal. Cycles and alternate arrival
states are bounded by the existing 1/2-hop and 1–60-node API limits. The UI still
requests 25 nodes; the edge cap remains 150. The existing `truncated` flag drives
**Result limited — showing N nodes… Refine the focus or filters**. Semantic
suppression is not falsely reported as cap truncation. Edge clipping retains
connection paths.

The additive nullable `parent_key` identifies each returned node's discovery
branch. Frontend layout uses that metadata, places the focus centrally, arranges
first-hop targets radially and places second hops outside the inner ring near
that branch. Targets snap to cells based on card dimensions plus 24px gaps, so a
dense branch can use adjacent rows. Layout bounds grow; Fit scales uniformly
rather than compressing positions underneath fixed cards. The embedded canvas
has more height, while expanded height fits the available viewport. Dense graphs
still benefit from zoom or a narrower focus. No positions are persisted.

## Q: Expand control

Topology uses the same `NavigationIcon name="expand"` and
`button button-secondary graph-icon-button` treatment as Knowledge Graph. The
button has title/aria-label **Expand Infrastructure Topology**, without visible
long text. The existing single-tree ExpandedGraphSurface, Escape/close behavior,
focus return, scroll lock and state retention remain intact. No Fullscreen API.

## R–U: Interface IPs and Assets

One helper resolves compact display: interfaces with IPs are sorted primary first,
then interface name and ID. The first distinct IP is displayed; additional distinct
IPs are counted as **+N**, including when a primary exists. One IP has no suffix;
no IP omits the line. Both Platform parent cards and compact child tiles use this
helper. Tests cover primary, one, multiple, duplicate and absent addresses.

The Assets table keeps hostname and removes its legacy Asset IP value. Topology
presentation/search and its inspector also stop falling back to that legacy
field. Asset interface detail remains available. API list search uses correlated
EXISTS over interface IPs, with `networks.view` on the owning Asset's scope;
existing Asset/customer/site restrictions still apply. Duplicate interface matches
do not duplicate list rows or distort pagination. Assets-only access cannot use
IP searches to infer hidden interface data. Legacy schema/API fields and
create/edit forms remain; no migration was required. Alembic still has the single
`20260921_0019` head.

## V–Y: Executed validation

Commands run from `apps/api` or `apps/web` as appropriate. PostgreSQL checks used
the existing disposable database on localhost port 55439. Browser checks used the
production build at localhost 3108, installed Chrome, and Playwright under `/tmp`.
The browser topology fixture invokes the actual Python traversal service rather
than duplicating its algorithm in JavaScript.

| Check | Command / result |
| --- | --- |
| Baseline API | `.venv/bin/pytest -q tests/test_infrastructure_topology.py tests/test_infrastructure_topology_postgres.py tests/test_crud.py`: 23 passed, four PostgreSQL tests skipped before the disposable server was started. |
| Baseline frontend | Focused topology/navigation Node tests: 11 passed. |
| Final focused API | Same focused pytest command with `ATLAS_TEST_DATABASE_URL`: **32 passed**. Includes the additional authorized 25-Asset count test. |
| Full API | `ATLAS_TEST_DATABASE_URL=… .venv/bin/pytest -q`: **403 passed, 1 skipped**. The separate empty-database migration test was skipped; no migrations changed. The subsequently added count test passed in the focused run. Existing deprecation warnings remain. |
| Frontend | `npm test`: **135 passed**. |
| Production build | `npm run build`: **passed**. |
| Topology browser | `node scripts/check-infrastructure-topology-browser.mjs`: **6 scenarios passed**, light/dark at 1440, 1100 and 800px. |
| Knowledge Graph browser | `node scripts/check-expanded-graph-browser.mjs`: **8 scenarios passed**, including narrow/mobile expanded-state regression. |
| Migration head | `.venv/bin/alembic heads`: **20260921_0019**, one head. |
| Whitespace | `git diff --check`: **clean**. |

Screenshots are written to `/tmp/atlas-topology-browser-results` and
`/tmp/atlas-expanded-graph-browser`. They include AdGuard two-hop, genuine 14-node
connectivity, expanded connectivity, and Platform views in both themes.

## Z: Exact fixture acceptance

| Scenario | Result |
| --- | --- |
| AdGuard → PVE1 with 20 total workloads | At two hops, **5 nodes**: AdGuard, PVE1, Management, Apps and USW-16-poe. The other 19 PVE1 workloads and Network peers do not appear solely through sharing the host/Network. |
| PVE1 direct focus | At one hop, **22 nodes**: PVE1, its 20 children and its recorded switch connection. |
| Management Network | AdGuard focus does not expand its peers. Direct Network focus returns **21 nodes**: the Network and its 20 member Assets. |
| PVE1 → USW-16-poe | The recorded switch is retained at distance 2 from AdGuard with PVE1 as `parent_key`. |
| Category containing 25 Assets | Count **25**, exactly **6** previews, **+19**, canonical Asset links and category-filtered View all. A one-Asset category has one icon and no remainder. PostgreSQL separately verifies 25 authorized Assets with other-site Assets excluded. |
| Genuine larger graph | PVE2 fixture returns **14 nodes**; no card collisions, focus centred in canvas, second-hop branches grouped, icons contained. Desktop Fit card-width regression threshold is checked. |
| Safety cap | Adding ten more recorded PVE1 children returns **25 nodes** with a visible Result limited notice. |
| Platform IPs | PVE1 shows `10.0.99.21`; AdGuard shows primary `10.0.99.5 +1`. Fixture legacy IP `192.0.2.254` is absent from Platform and Assets table. |

## Material files

| Paths | Purpose |
| --- | --- |
| `apps/api/app/services/infrastructure_topology.py` | Path-aware traversal, explicit Network focus, authorized discovery-parent metadata. |
| `apps/api/app/routes/topology.py`, `apps/api/app/schemas.py` | Additive Network-focus query and parent-key response field. Existing Asset-focus queries remain compatible. |
| `apps/api/app/routes/assets.py` | Permission-scoped interface IP search without duplicate rows. |
| `apps/web/app/topology/page.js`, `apps/web/lib/infrastructure-topology.mjs`, `apps/web/app/globals.css` | Overview links/remainders, interface IPs, contained card/icon rendering, deterministic collision-free layout, compact expansion and Network refocus. |
| `apps/web/app/assets/page.js` | Hostname-only table column; no legacy IP value. |
| `apps/web/lib/navigation-model.mjs` | Topology sidebar display label. |
| `apps/api/tests/test_infrastructure_topology.py`, `apps/api/tests/test_infrastructure_topology_postgres.py` | Homelab semantics, authorization, search, counts and bounds regressions. |
| `apps/web/tests/infrastructure-topology.test.mjs`, `apps/web/tests/navigation-model.test.mjs` | Layout, interface-IP, table, navigation and expand regressions. |
| `apps/web/scripts/check-infrastructure-topology-browser.mjs` | Homelab-shaped production browser acceptance using the real traversal service. |
| `docs/admin/infrastructure-topology.md`, `docs/architecture/infrastructure-topology.md`, `docs/product/feature-ledger.md` | Current behavior, contracts and remaining interface-first limitations. |
| `docs/testing/infrastructure-topology-polish.md` | This validation record. |

The managed category model and four-view architecture are preserved. No telemetry,
subnet inference, discovered-knowledge overwrite, new persistent source of truth
or authorization model was introduced. Live acceptance on the user's actual
homelab remains external to these isolated checks.

## Final repository state

```text
 M apps/api/app/routes/assets.py
 M apps/api/app/routes/topology.py
 M apps/api/app/schemas.py
 M apps/api/app/services/infrastructure_topology.py
 M apps/api/tests/test_infrastructure_topology.py
 M apps/api/tests/test_infrastructure_topology_postgres.py
 M apps/web/app/assets/page.js
 M apps/web/app/globals.css
 M apps/web/app/topology/page.js
 M apps/web/lib/infrastructure-topology.mjs
 M apps/web/lib/navigation-model.mjs
 M apps/web/scripts/check-infrastructure-topology-browser.mjs
 M apps/web/tests/infrastructure-topology.test.mjs
 M apps/web/tests/navigation-model.test.mjs
 M docs/admin/infrastructure-topology.md
 M docs/architecture/infrastructure-topology.md
 M docs/product/feature-ledger.md
?? docs/testing/infrastructure-topology-polish.md
```
