# Connectivity orthogonal layout experiment

## A–D. Repository and scope

Base `dev` and the already-current `feature/topology-orthogonal-layout` both
pointed to `70af0c5edfb03f242393231d65cacd5ad9d1a10f` at inspection. The working
tree was clean. The requested branch already existed, so no new branch command
was needed and no working-tree changes were carried. HEAD remains unchanged.
No commit, push or merge was performed.

This is a Connectivity renderer experiment. No API contract, route, database
model, migration, accepted relationship, reference-data assignment, authorization,
customer/site boundary, traversal rule or 100-node/500-edge policy changed.
Knowledge Graph and other topology views retain their renderers.

## E–L. Geometry

Previously most edges were direct SVG lines, often diagonal. Only projected
platform parents with at least three lower children used orthogonal rails.
Band-local grids and subsequent parent shifts did not reserve complete branch
footprints. Symmetric bounds around focus and vertically centred transforms
wasted canvas height and could shrink small graphs unnecessarily.

The new layout retains the existing explicit/Automatic rank calculation. It
selects a primary recorded upper neighbour for horizontal grouping, preferring
projected platform parents. Since these anchors always increase rank, their
presentation forest is cycle-safe even when the recorded graph contains cycles.
Subtree footprints are computed before parents. Occupied-row contours allow
compatible sibling footprints to share columns without overlapping cards; an
independent Network can use an otherwise empty band. A parent's children in
different positions reserve separate column groups. Parents approximately centre
over their visible descendant footprint. Leaf grids retain four columns, or six
for groups larger than twelve.

Occupied bands reserve 88px cards, 64px row gutters and 88px between bands. Empty
managed positions add no space. The existing band metadata remains available;
background position containers are intentionally deferred.

Every edge now uses an SVG path composed only of horizontal/vertical segments:

- A short vertical exit joins a shared horizontal distribution rail, followed by
  a vertical drop when clear. Physical fan-out uses the same geometry as hosting.
- Every segment is checked against all card rectangles padded by 6px. Later grid
  rows and skipped positions use candidate tracks in gutters or outside the
  graph. Common row spacing guarantees clear horizontal exits/entries, so an
  exterior route is available without a diagonal fallback.
- Stable edge-key ordering and deterministic distance/track costs select routes.
  Distinct targets avoid coincident long tracks where alternatives exist; later
  rows within one parent/column can share a clean gutter trunk.
- Same-row links, self-links, reverse links and Network membership use the same
  obstacle checks. Reversing presentation points preserves canonical arrows.
- Routing changes only geometry; shared rails never combine domain records.

Bounds include cards, disclosure space and routed edges. Fit uses these actual
bounds, horizontal centring and a 16px screen-space top inset after the existing
12px toolbar gap. Scale considers both dimensions and padding. Manual Fit,
refocus and disclosure count changes use this placement. Zoom and scroll/pan
remain available; ResizeObserver updates the available fullscreen/inspector
width while retaining layout coordinates and the existing zoom/pan rules.

## M–V. Semantics and interaction

Topology Position `sort_order` stays authoritative, including inactive
assignments. Relationships never move explicitly positioned Assets between
bands. Automatic inference remains unchanged. No vendor, type-name or position
name matching was introduced; names/keys only provide stable tie ordering.

Canvas relationship text and hover labels were removed only from Connectivity.
The inspector still lists source, relationship label, canonical arrow and target.
Single-click inspects, double-click refocuses; Search and Focus retain the
existing hops, category/class and Networks behavior.

The first-eight preview, attached collapsed-neighbour +N badge, connected +N more
control, pointer isolation, Tab/Enter/Space, local expansion and selection
preservation remain. Presentation connectors are routed without creating domain
relationships. Network icons/accents and dashed AssetInterface membership remain.
Fullscreen details hide/show preserves selection and refits to available width
under existing interaction rules.

## W–AB. Visual acceptance

Isolated browser fixtures call the production Python traversal and render the
production frontend. They never write live Atlas knowledge. Custom Asset Type
keys/names demonstrate that runtime layout does not depend on vendor naming.
The new fixture contains an edge/aggregation/access chain, three hosts with
18/4/3 workloads, and two appliances in a later configured position.

Before screenshots reproduced the small graph's empty space, diagonal
switch-to-appliance paths through host cards, and the fully expanded graph's
large blank upper area. After screenshots were visually inspected in both themes:

| Scenario | Observed result |
| --- | --- |
| Small focus | Near-toolbar placement, horizontal centring, straight vertical connection; manual Fit matches automatic Fit. |
| Chain and three-host fan-out | Vertical chain, shared horizontal rail and vertical drops. |
| Cross-position appliances | Hosts retain their band; backup/storage appliances remain below it, with separate drops through whitespace beside the hosts. |
| First eight / +10 more | Parent aligned over the visible child grid, orthogonal gutter routes and a connected circular remainder control. |
| All branches expanded | All 33 returned nodes remain in their positions, with distinct workload blocks, aligned parents and no card/edge collisions. |
| Fullscreen | More width for the expanded diagram; details hide/show, selection and Fit remain operational. |

Fit shows the complete topology; a wide fully expanded graph still scales down
text, especially in the embedded pane. Fullscreen and zoom remain useful for
reading individual cards. This does not claim a globally optimal crossing-free
layout for arbitrary dense graphs.

Screenshots are local artifacts in `/tmp/atlas-orthogonal-browser/`. Names use
`orthogonal-{scenario}-{light|dark}-{1440|1100|800}.png`, with scenarios `small`,
`chain`, `three-hosts`, `cross-position`, `first-eight`, `all-expanded`,
`fullscreen`, and `fullscreen-details` (48 screenshots). Baseline counterparts
are in `/tmp/atlas-orthogonal-baseline/`; the original layered fixture is in
`/tmp/atlas-orthogonal-before/`. Full regression artifacts are in
`/tmp/atlas-orthogonal-full-browser/`.

## AC–AG. Validation

Commands below run from `apps/web`, except Alembic from `apps/api` and Git from
the repository root. Browser runs use installed Chrome and the local Playwright
module, with a production server at `http://127.0.0.1:3108`:

```bash
ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-topology-browser/node_modules/playwright/index.mjs \
ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
ATLAS_BROWSER_OUTPUT=/tmp/atlas-orthogonal-full-browser \
node scripts/check-infrastructure-topology-browser.mjs
```

| Command / check | Result |
| --- | --- |
| `node --test tests/connectivity-layout.test.mjs tests/infrastructure-topology.test.mjs` | 27 passed. |
| `npm test` | 163 passed. |
| `npm run build` | Passed production build. |
| Browser command above with `ATLAS_ORTHOGONAL_ONLY=1` | Six light/dark × 1440/1100/800 scenarios passed. |
| Complete production browser command above | Six light/dark × 1440/1100/800 scenarios passed, including pointer/keyboard disclosure, search/focus, managed positions/classes, Networks, fullscreen, pan/zoom, Fit and the new orthogonal cases. |
| `.venv/bin/alembic heads` | Single existing head `20260921_0023`; no migration. |
| `git diff --check` | Clean. |
| API test suite | Not run: no backend or shared API contract code changed. Browser fixtures exercise the existing production traversal. |

Geometry assertions cover arbitrary names/positions, empty ranks, one-to-many
rails, skipped positions, first-eight/full disclosure, centred parents, no card
overlap, no diagonal segments, no edge crossing card interiors, reverse direction,
cycles, membership, route-inclusive bounds and top-biased Fit. A deterministic
100-node/500-edge fixture also passes all collision checks. Rendered browser
geometry includes attached badges and more controls in obstacle assertions.

The old browser assertions that centred the focused node in both dimensions were
updated to assert horizontal whole-graph centring, a top inset and complete fitted
bounds, as required by this experiment. The existing 14-node card-readability
threshold remains in place. No failing tests were removed.

## Material files and documentation

| File | Change |
| --- | --- |
| `apps/web/lib/infrastructure-topology.mjs` | Subtree layout, contour packing, all-edge routing, bounds and Fit helpers. |
| `apps/web/app/topology/page.js` | Route rendering, label removal, bounds/Fit integration; existing inspector and controls retained. |
| `apps/web/app/globals.css` | Removed the unused Connectivity edge-label rule. |
| `apps/web/tests/connectivity-layout.test.mjs` | Geometry fixtures/assertions and updated route coverage. |
| `apps/web/scripts/check-infrastructure-topology-browser.mjs` | Realistic fixture, screenshots, rendered geometry/Fit assertions and SVG-path membership selectors. |
| `docs/admin/infrastructure-topology.md` | User-facing routing, position, labels and Fit behavior. |
| `docs/architecture/infrastructure-topology.md` | Layout/routing algorithm and preserved boundaries. |
| `docs/product/feature-ledger.md` | Connectivity implementation evidence updated. |
| `docs/testing/infrastructure-topology-orthogonal-layout.md` | This acceptance and completion record. |

No ADR decision changed. Background containers remain deferred by request.

## Repository state

`git status --short` at completion:

```text
 M apps/web/app/globals.css
 M apps/web/app/topology/page.js
 M apps/web/lib/infrastructure-topology.mjs
 M apps/web/scripts/check-infrastructure-topology-browser.mjs
 M apps/web/tests/connectivity-layout.test.mjs
 M docs/admin/infrastructure-topology.md
 M docs/architecture/infrastructure-topology.md
 M docs/product/feature-ledger.md
?? docs/testing/infrastructure-topology-orthogonal-layout.md
```
