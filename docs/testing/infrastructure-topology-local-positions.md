# Connectivity branch-local positions acceptance

## Repository and scope (A–C, Q–U)

Branch: `feature/topology-orthogonal-layout`.
HEAD at inspection: `aea66542e11d456e3b7638ae4d8b6470a21d53e1`.
The initial working tree was clean. No commit, push or merge was performed.

This is a presentation-only extension of the orthogonal renderer. Topology
Position records/order, Asset Type assignments, Categories, Relationship Types,
Topology Classes, accepted relationships, authorization, traversal and safety
limits are unchanged. No database model, migration, API contract or route changed.
The renderer consumes only the existing authorized projection; customer/site
boundaries remain enforced by the existing backend. Automatic rank inference is
unchanged. Runtime behavior has no vendor, type-name or position-name rules.

## Before and after (D–F)

The former renderer computed subtree X coordinates, then assigned one global Y
band per occupied rank. The isolated browser fixture reproduced the resulting
Infrastructure appliance row between Container host and Workload. Neither
traversal nor incorrect position data caused that space.

The new renderer uses managed/inferred rank as ordinal sequence. Every eligible
connected upper neighbour constrains local Y, including secondary neighbours;
the primary anchor selects horizontal branch membership. Strictly increasing
rank keeps the presentation forest cycle-safe. Same-position local siblings
share a baseline and leaf grids reserve their actual rows. A separate sibling
position consumes no row in the longer branch. Card/header/routing clearance,
rather than numeric sort-order gaps, determines vertical distance.

Measurements use the same 26-Asset fixture, focus, disclosure state and 700px
available width, with route-inclusive, unscaled layout bounds. It has one access
Asset, three platform Assets, two container hosts beneath one platform Asset,
two independent appliance Assets, and eighteen workloads under one container
host. Position orders are 50, 60, 65, 70 and 80; all Type keys are arbitrary.

| State | Previous height | New height | Reduction |
| --- | ---: | ---: | ---: |
| Child branch collapsed | 634px | 442px | 30.3% |
| First eight and +10 more | 1100px | 932px | 15.3% |
| All eighteen workloads | 1114px | 946px | 15.1% |

The corresponding widths are 1290→1266, 1518→1494 and 1860→1836px.
Measurements compare the pre-change module captured from HEAD against the new
module, using `connectivityPreview`, `connectivityLayout`, `connectivityRoutes`
and `connectivityBounds`. Removing only the sibling appliance branch does not
change the workload's Y in the new unit fixture.

## Containers (G–L)

Candidates share a durable managed position ID and primary upstream anchor.
Geometric proximity splits distant peers; a candidate box is also split if it
would enclose unrelated cards. Separate branches retain separate containers
with the same position label. Disconnected roots are not combined globally.

Only groups of two or more Assets receive containers. Single Assets, Automatic
nodes, Networks and +N controls are excluded. Labels and counts describe actual
Asset members. The more control sits beyond the real child grid; groups resize
as children become visible.

Labels come directly from `TopologyPosition.name`. A deterministic hash of the
position ID chooses an existing Atlas palette accent. Rename/reorder does not
change that tint; Category accents do not determine group identity. The UI uses
subtle theme-aware fill, a 1px border, an 8px radius and a small upper-left label.
Long labels ellipsize within their reserved width and retain the full accessible
label. Browser checks require label contrast of at least 4.5:1 in both themes.

## Routing and interactions (M–P, V–Z)

Existing orthogonal trunks, shared source rails, drops, canonical direction and
deterministic obstacle checks remain. Reserved label rectangles participate in
routing. Edges can cross presentation container borders/backgrounds without
clipping. No diagonal fallback or on-canvas relationship label was introduced.
The inspector retains relationship names and canonical arrows.

Subtree contours include cards and containers before parents are centred. Local
leaf runs do not reserve phantom columns when they follow a subtree. The existing
desktop card-readability regression remains enforced. Layout supports secondary
parents, cycles, reverse edges, same-row edges, self-links and Network membership.
It avoids tested card/label/container collisions, but does not claim a globally
optimal crossing-free layout for arbitrary dense graphs.

The attached collapsed +N badge, first-eight preview, connected +N more control,
keyboard/pointer behavior and local expansion remain. Expansion does not fetch
or mutate semantic state. Selection, search/focus, filters, hops and Networks
retain their existing behavior. Network icons/accents and dashed interface
membership edges remain distinct from position containers.

Bounds include containers and routes. Fit horizontally centres complete bounds
with its existing 16px viewport inset below the toolbar gap. Fullscreen and
details hide/show retain selection. Available width can reflow leaf grids from
four columns (six for more than twelve children), up to eight columns; the graph
then refits. Large fitted graphs still benefit from fullscreen or zoom to read
small card text.

## Browser and screenshot review (AA–AE)

The browser harness renders the production frontend against isolated fixtures
using the real Python Connectivity traversal. It does not write live Atlas data.
The new scenario is included in the complete browser suite and can be selected
with `ATLAS_POSITIONS_ONLY=1`.

Screenshots use `positions-{scenario}-{theme}-{width}.png`, with scenarios
`siblings`, `first-eight`, `all-expanded`, `fullscreen`, `fullscreen-details`;
themes `light`/`dark`; widths 1440, 1100 and 800px.

- Baseline: `/tmp/atlas-position-before/` (30 screenshots).
- Final production suite: `/tmp/atlas-position-full-browser/` (30 position
  screenshots plus the existing regression screenshots).

The reviewed before image has the appliance row inserted between runtime and
workload. After images show Platform / host and Infrastructure appliance beside
one another, with the runtime and workload branch strictly below its parent.
The separate labelled containers make their different positions clear despite
sharing Y. Fills remain quiet and cards dominate in both themes. Header detours
remain orthogonal and clear of labels. First-eight and full expansion resize
the workload container, and fullscreen gives the graph more usable space.

## Validation (AF–AJ)

Run from `apps/web` unless otherwise stated:

```bash
node --test tests/connectivity-layout.test.mjs tests/infrastructure-topology.test.mjs
npm test
npm run build
ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-topology-browser/node_modules/playwright/index.mjs \
ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
ATLAS_BROWSER_OUTPUT=/tmp/atlas-position-full-browser \
node scripts/check-infrastructure-topology-browser.mjs
```

| Check | Result |
| --- | --- |
| Focused Connectivity / Infrastructure Topology tests | 32 passed. |
| `npm test` | 168 passed. |
| `npm run build` | Passed. |
| Complete production browser suite | All six light/dark × 1440/1100/800px scenarios passed, including search/focus, Networks, disclosure, managed positions/classes, fullscreen/details, orthogonal routing and local groups. |
| API: `.venv/bin/pytest tests/test_topology_positions.py tests/test_topology_layers.py tests/test_infrastructure_topology.py -q` | 22 passed. |
| API: `.venv/bin/alembic heads` | Single existing head `20260921_0023`. |
| Root: `git diff --check` | Clean. |
| Relative Markdown links in changed documentation | Passed. |

Unit coverage includes sibling row removal, distinct local clusters, singleton
exclusion, long branch order, expansion/reflow, secondary upstream constraints,
stable tints, determinism, unchanged inputs, group/card/label collision checks,
route-inclusive bounds and dense 100-node/500-edge routing. An additional local
stress check exercised 200 deterministic random 25-node/40-edge fixtures without
routing failures or container overlap.

The former global-row assertions were updated to assert configured order along
actual connected branches and side-by-side independent siblings. No test was
removed. The full PostgreSQL integration suite was not run; there are no backend,
database or API changes.

## Material files and repository state

| File | Purpose |
| --- | --- |
| `apps/web/lib/infrastructure-topology.mjs` | Branch-local Y, contour packing, local containers, header obstacles and bounds. |
| `apps/web/app/topology/page.js` | Render containers and recompute geometry for available width. |
| `apps/web/app/globals.css` | Subtle theme-aware containers and labels. |
| `apps/web/tests/connectivity-layout.test.mjs` | Geometry/disclosure/grouping and readability regressions. |
| `apps/web/scripts/check-infrastructure-topology-browser.mjs` | Realistic fixture, group/label/contrast assertions, screenshots and updated branch-order expectations. |
| `docs/admin/infrastructure-topology.md` | User-facing layout and grouping behavior. |
| `docs/admin/topology-positions.md` | Branch-local ordering and derived presentation semantics. |
| `docs/architecture/infrastructure-topology.md` | Algorithm, routing and preserved boundaries. |
| `docs/product/feature-ledger.md` | Truthful Connectivity and position implementation evidence. |
| `docs/testing/infrastructure-topology-local-positions.md` | This acceptance/completion record. |
| `docs/testing/infrastructure-topology-orthogonal-layout.md` | Links the historical global-band/container details to this refinement. |

No accepted ADR changes. The earlier orthogonal-layout acceptance record remains
historical; this record supersedes its global-band and deferred-container details.

Final `git status --short`:

```text
 M apps/web/app/globals.css
 M apps/web/app/topology/page.js
 M apps/web/lib/infrastructure-topology.mjs
 M apps/web/scripts/check-infrastructure-topology-browser.mjs
 M apps/web/tests/connectivity-layout.test.mjs
 M docs/admin/infrastructure-topology.md
 M docs/admin/topology-positions.md
 M docs/architecture/infrastructure-topology.md
 M docs/product/feature-ledger.md
 M docs/testing/infrastructure-topology-orthogonal-layout.md
?? docs/testing/infrastructure-topology-local-positions.md
```
