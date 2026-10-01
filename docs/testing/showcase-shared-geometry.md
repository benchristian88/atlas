# Showcase shared Connectivity geometry

The fixed-width envelope recorded here is superseded by
[adaptive-width acceptance](showcase-adaptive-width.md). Shared geometry and
node/category presentation remain unchanged.

Focused correction on `feature/topology-showcase`, starting from
`85b5b5153eca6daf5d8601a04134693d3f08b34c`. The initial working tree was clean.
No commit, push or merge. This supersedes the independent Showcase geometry in
[the Position-band record](showcase-position-bands.md) and earlier acceptance
records, which remain available as historical evidence.

## Correction and shared architecture (A–G)

Showcase previously constructed its own hosting/physical forest, global managed
Position bands, same-position subrows, horizontal packing and destination-row
routing. Only `orthogonalDetour` was shared. Its independent geometry reserved
height across unrelated branches and applied workload previews to fit the scene.

Connectivity's pure geometry now lives in
[`topology-geometry.mjs`](../../apps/web/lib/topology-geometry.mjs):

- `topologyGraphEligibility`: typed nodes and eligible endpoint edges;
- `buildTopologyLayoutModel`: managed ranks, Automatic inference, recorded upper
  anchors and cycle-safe same-position local depth;
- `calculateTopologyGeometry`: branch-local clearance, sibling grids, occupied
  contour packing, ancestor centering and optional focus origin;
- `routeTopologyEdges`: vertical trunks, horizontal rails, drops, exterior tracks,
  group connectors and bounded orthogonal detours;
- `topologyBounds`: node/group/route-inclusive extents.

The existing `connectivityLayout`, `connectivityRoutes`, position group,
bounds/Fit and other exports remain available through
`infrastructure-topology.mjs`. Connectivity's default dimensions, four-column
preview grids, position containers, selection, inspector, search and disclosure
are retained. Platform preparation and the React topology page are unchanged.

Inspection found one genuine shared gap: equal-rank physical switch neighbours
were not selected as hierarchical anchors. Local breadth-first distance from
recorded upper neighbours now keeps distribution → access switches ordered at
the same managed Position. It preserves rank and canonical edge meaning; parallel
records, bidirectional edges and anchored cycles remain deterministic. Unanchored
closed cycles remain level. All existing Connectivity tests pass unchanged.

Showcase-specific code now adapts the complete authorized current-site input,
assigns category wrappers after ownership, supplies compact dimensions/grid and
footprint settings, fits the existing poster bounds, and applies the enormous-site
preview policy. It has no structural parent inference, topology packer or router
of its own and imports no React Connectivity UI.

Networks-off eligibility uses actual `asset` identity, endpoint keys and the
`membership` edge kind. Logical Networks/VLANs and memberships are excluded before
model construction. Gateway, switches, APs and other network-device Assets stay.
Removing all logical Networks/interfaces from the reference input produces an
identical scene. There is no Showcase Networks toggle, focus or traversal depth.

Managed Position IDs/sort order and Automatic inference follow Connectivity.
There are no independent global Y bands. Relationships retain branch ownership;
category presentation never changes hosts, ranks or same-position depth. Local
category rules remain singleton/direct, 2–4/one column and 5+/two columns. Category
stacking beyond those existing membership rules is out of scope.

## Real-shape acceptance and collapse policy (H–K)

The unchanged generic fixtures exercise gateway → aggregation → distribution,
access branches, three peer platform hosts, physical-server → platform-host
branches, appliances, two container hosts and their child workloads, direct
workloads and a disconnected server. The 44-Asset fixture includes an additional
office-side host and three logical Networks with 44 memberships.

| Fixture | Assets | Visible Asset tiles | Collapsed workload groups | Logical dimensions | Scale | PNG |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| Connectivity-shaped reference | 44 | 44 | 0 | 1920×1080 | .964657 | 3840×2160 |
| Larger real shape | 50 | 50 | 0 | 1920×1080 | .865672 | 3840×2160 |
| Large repetitive site | 236 | 44 | 2 | 1920×1166 | .860233 | 3840×2332 |
| Taller complete fixture | 64 | 64 | 0 | 1920×1158 | .860738 | 3840×2316 |
| Near-maximum complete fixture | 78 | 78 | 0 | 1920×1350 | .860169 | 3840×2700 |

The generic PVE1-equivalent is **Platform Host A**, shown once. Container Host A
and Container Host B stay its children; Photo Library/Auth Service children stay
with the corresponding container host. Every one of its 10 direct workloads in
the reference and 16 direct workloads in the larger fixture is visible. No +12,
other workload preview or endpoint roll-up is used in either fixture.

Every normal fixture's geometry is compared to Connectivity by stable node key:
managed rank, local same-position depth and primary layout parent must match.
Physical hosts remain below aggregation and their platform hosts remain their
children. Structural horizontal branch order matches the renderer reference.
Terminal sibling grids can use one column, and category wrappers use one/two
columns with smaller rectangles; these are presentation metric differences.

All Assets are attempted first at the unchanged .86 scale floor and existing
1920×1080/1358 height bounds. A complete taller poster is preferred over a
preview. Only sites above 100 Assets may try four-member workload previews after
complete geometry fails at every permitted height. The 236-Asset fixture's two
100-member categories each show four plus +96 because their complete 1896px
content height cannot fit. Original member IDs and relationship IDs are retained.
Uniform hosting semantics and no secondary neighbours are required for collapse.

The 43-Asset endpoint-heavy fixture needs 1920×1166 because its terminal branch
contains 15 separately visible endpoints. This is different from the compact
44/50-Asset homelab shapes. Extremely wide forests can still fail the shared
Connectivity packer's bounded poster width; the 182-Asset stress fixture explicitly
refuses export. No independent structural rearrangement or adaptive-size redesign
was added to bypass that constraint.

## Browser comparison and export (L–P)

The browser harness supplies the same complete authorized fixture to the existing
Connectivity renderer and Showcase. Connectivity is captured with Networks off,
all categories enabled and every disclosure expanded: 44 and 50 visible nodes.
The complete renderer fixture deliberately bypasses the query's neighbourhood
cap so geometry can be compared; it is not evidence that a real three-hop query
returns a whole site. The separate unchanged regression harness invokes the real
Python traversal service for 1/2/3 hops and authorization-compatible subsets.

The two screenshot pairs were visually inspected. Both show the same gateway,
distribution/access ownership, three compute peers, nested container branches and
separate physical/server branches. Showcase uses a compact light presentation,
local categories and no operational Position containers. All Assets appear as
icon/name tiles; no Type, IP, status, counts or second metadata line appears on an
individual tile. Long names use a middle ellipsis to preserve distinguishing
prefixes/endings; accessible SVG titles retain full names. Browser checks assert
all 44/50 displayed names remain distinguishable.

Artifacts in `/tmp/atlas-shared-showcase-browser/`:

- `reference-connectivity-networks-off-expanded.png`, `reference-light-scene.png`,
  `reference-light-export.png`;
- `real-shape-connectivity-networks-off-expanded.png`, `real-shape-light-scene.png`,
  `real-shape-light-export.png`;
- small/medium/large/adaptive/maximum light scenes and PNGs; medium/adaptive dark
  UI screenshots and exports; `oversized-incomplete.png`; `report.json`.

The existing SVG/resource/PNG export path remains unchanged. Nine browser
scenarios cover image fallbacks, name-only content, full titles, measured text
budgets, exact category member placement, viewport resize without geometry/refetch,
offline PNG download, scene dimensions, empty/incomplete refusal and Platform
content before/after Showcase. Five scenes compare preview/PNG pixels at export
resolution, with mean channel difference below 2/255 and changed fraction below
.02. Medium and adaptive PNGs are byte-identical between light and dark Atlas UI.

## Executed validation (N–R)

Commands from `apps/web` unless otherwise specified:

| Command | Result |
| --- | --- |
| `node --test tests/showcase.test.mjs tests/connectivity-layout.test.mjs tests/infrastructure-topology.test.mjs` | 64 passed, including 23 Showcase tests and all 29 unchanged Connectivity layout tests. |
| `npm test` | 238 passed; none failed or skipped. |
| `npm run build` | Passed; 38 pages generated. |
| `node scripts/check-showcase-browser.mjs` with temporary Playwright/local Chrome | Nine scenarios passed, including both fully expanded Connectivity comparisons and offline exports; zero page errors. |
| Unchanged `node scripts/check-infrastructure-topology-browser.mjs` with local Chrome | Six light/dark scenarios at 1440, 1100 and 800px passed. Covers 1/2 hops, fullscreen 3 hops, Networks, Relationship Classes, search/refocus, selection, inspector, Position groups, disclosure, orthogonal routing, Platform filters/previews and content. |
| Repository root: `apps/api/.venv/bin/python -m pytest apps/api/tests/test_showcase_projection.py apps/api/tests/test_infrastructure_topology.py apps/api/tests/test_topology_positions.py -q` | 21 passed. |
| Repository root: `git diff --check` | Clean. |
| Relative Markdown link check across changed documentation | 41 relative links resolve across eight documents. |

The previous Showcase tests requiring global Y bands, endpoint previews and exact
independent-packer dimensions were updated for this explicitly authorized change.
Completeness, scope, canonical edges, cycle handling, category membership, fitting,
determinism, obstacle avoidance and export regression coverage remain. Connectivity
and Platform test files and the existing browser regression script are unchanged.

No database migrations or API contracts/routes changed. Backend authorization,
customer/site scope, accepted-knowledge projection and existing discovery code are
unchanged. The frontend still filters to the selected site as defence in depth.
No live homelab data was accessed or written; all browser writes are intercepted
fixture operations. The local test server and browser tools are temporary.

## Material files

| File | Purpose |
| --- | --- |
| `apps/web/lib/topology-geometry.mjs` | Extracted pure Connectivity model, placement, groups, bounds and routing, configurable compact metrics and shared same-position network-chain fix. |
| `apps/web/lib/infrastructure-topology.mjs` | Compatibility re-exports; existing Platform/disclosure/search preparation retained. |
| `apps/web/lib/showcase.mjs` | Complete site input, typed Networks-off eligibility, category skin and bounded poster/preview policy using shared geometry. |
| `apps/web/components/showcase.js` | Compact name/icon tiles, distinguishable middle-ellipsis names and matching category spacing. |
| `apps/web/tests/showcase.test.mjs` | Shared model/geometry, 44/50 completeness/ownership, fitting, grouping, edge identity, cycle, determinism, scope and compatibility tests. |
| `apps/web/tests/fixtures/showcase.mjs` | Retained real-shape fixtures; added a tall complete-workload fixture. |
| `apps/web/scripts/check-showcase-browser.mjs` | Same-fixture renderer comparisons, normal-size completeness/names and updated fallback/export acceptance. |
| `docs/architecture/showcase.md` | Shared engine and presentation boundary. |
| `docs/admin/showcase.md` | Current visible behavior, complete-site policy and export guidance. |
| `docs/product/feature-ledger.md` | Truthful implementation evidence and acceptance link. |
| `docs/testing/showcase.md`, `showcase-compact-poster.md`, `showcase-networks-off.md`, `showcase-position-bands.md` | Mark earlier independent geometry records historical; retain their evidence. |
| `docs/testing/showcase-shared-geometry.md` | This correction/validation record. |

No outstanding acceptance failure. Generic fixtures validate the requested shape;
the user's actual live site was not tested. Very wide sites retain an explicit
incomplete state, and future category stacking remains deliberately out of scope.
The final `git status --short` is included in the completion response.
