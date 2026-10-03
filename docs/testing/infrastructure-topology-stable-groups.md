# Connectivity: stable local groups and compact sibling grids

Branch: `feature/topology-orthogonal-layout`.
Starting HEAD: `cf6e526664f007ca49d58c691ea5567d2517d60f`.
The working tree was initially clean. No commit, push or merge was performed.

## Grouping and geometry

The former container builder started with parent/Position peers, then split them
by distance and by whether their proposed rectangle enclosed a foreign card.
It suppressed each resulting singleton. Expanding descendant footprints could
therefore split three hosts into singletons and remove their Platform background.
Group IDs also included the first member of each geometric fragment.

Membership now has the stable key `JSON.stringify([layoutParentKey, positionId])`.
It is independent of coordinates, names, descendant count and box visibility.
Singleton identities remain available internally; only groups with two or more
visible Assets draw backgrounds. Controls attach to this exact identity without
becoming members. Different upstream anchors remain different groups.

Packing treats each semantic sibling group as a unit, protecting its bounds
from unrelated cards. Background geometry follows current cards and controls.
Platform membership stays PVE1/PVE2/PVE3 when any or all descendants expand.
The Container Host case follows the same rules, including a member with its own
child. Branch-local vertical compaction, footer labels and subtle ID-based tint
remain in place.

## Grid, disclosure and routing

Four columns are used at all viewport sizes. No five-column exception is enabled.
The established name/ID order fills left-to-right, then top-to-bottom. Card gaps
are 32px horizontally and vertically. First-eight is 4+4 with a centred +10 more
control inside the Workload box. Full expansion is 4+4+4+4+2. Descendants of grid
members start below the full parent group; expanding them does not restore one
long row of sibling cards.

In the isolated 18/2/1-child fixture with the same managed labels and 900px layout
option, the PVE1 Workload container changes from **2,654 × 492** to
**854 × 636** layout pixels: approximately **68% less width**. Exact padding
width varies with the managed label. The old algorithm used at least six columns
for eighteen children, with additional horizontal lanes for successive rows;
it was not literally eighteen columns in this fixture, but occupied similar width.

A group with matching backend-projected platform parent relationships receives
one presentation-only connection ending at its top border. Selection of any
member highlights it. Single children use their actual direct edge; mixed
relationship metadata, physical relationships and Network membership retain
individual routes. Relationship records and inspector content are unchanged.
There is no group Asset, persisted relationship, canvas relationship label or
synthetic domain arrow.

External routes retain orthogonal trunks/rails/drops and obstacle checks. An
individual Network or other overlay targeting an interior grid card may route
through card gaps inside its endpoint group; it still avoids cards, footer
labels and unrelated containers. This replaces the former requirement for
staggered drop lanes for every hosting relationship.

## Production-browser acceptance and screenshots

The existing harness uses isolated API fixtures and the actual Python
Connectivity traversal. It performs no writes to live Atlas knowledge.
Both themes are exercised at 1440, 1100 and 800px widths. The PVE fixture contains
18, two and one workloads respectively, plus upstream fabric and sibling
infrastructure appliances. Assertions check the host group's semantic ID and
three-member count, four-column row geometry, complete Fit bounds, card/label
collisions, orthogonality, disclosure, fullscreen and inspector hide/show.

Artifacts: `/tmp/atlas-grid-full-browser/`. Each filename below also has dark
and narrower viewport variants:

| Requested state | Screenshot |
| --- | --- |
| PVE1 first eight | `orthogonal-first-eight-light-1440.png` |
| PVE1 all eighteen | `orthogonal-eighteen-light-1440.png` |
| PVE3 one child | `orthogonal-one-child-light-1440.png` |
| PVE2 two children | `orthogonal-two-children-light-1440.png` |
| All hosts expanded | `orthogonal-all-expanded-light-1440.png` |
| Fullscreen all expanded | `orthogonal-fullscreen-light-1440.png` |
| Light mode | `orthogonal-first-eight-light-1440.png` |
| Dark mode | `orthogonal-fullscreen-dark-1440.png` |

Visual review confirms stable host backgrounds, aligned compact grids, contained
controls, bottom-left labels and clear group connectors. Fullscreen uses the
additional space for readability while retaining four columns. Fit necessarily
scales a complete multi-branch graph; zoom remains available. Focused final-build
screenshots are in `/tmp/atlas-grid-browser/`.

## Scope and compatibility

No migration, API/route change or backend change. Asset records, managed taxonomy,
relationship records, traversal and 100-node/500-edge limits are unchanged.
The renderer still consumes only backend-authorized projections; customer/site
scoping remains authoritative on the backend. Networks and dashed interface
membership, filters, search/focus, selection and inspector behavior are retained.
The architecture document and feature ledger describe the new presentation;
the previous external-routing acceptance record is retained as historical.

## Validation

- `node --test apps/web/tests/connectivity-layout.test.mjs`: 29 passed, including
  the bounded 100-node/500-edge graph, reverse/cyclic routes, Network overlays,
  semantic membership, unrelated groups, first-eight/full grids and nested
  descendants on every preview member.
- `cd apps/web && npm test`: 177 passed. Includes Infrastructure Topology,
  progressive disclosure, managed positions, relationship classes, search/focus,
  Networks and fullscreen regressions.
- `cd apps/web && npm run build`: production build passed.
- Production Chrome harness: all six complete theme/width scenarios passed.
  `ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-topology-browser/node_modules/playwright/index.mjs`
  and `ATLAS_CHROME_PATH=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
  select the available browser tooling. Run
  `node apps/web/scripts/check-infrastructure-topology-browser.mjs` against the
  production server on port 3108; set `ATLAS_BROWSER_OUTPUT` for artifacts.
  `ATLAS_ORTHOGONAL_ONLY=1` selects the focused grid/group acceptance cases;
  all six focused cases also passed against the final build.
- Relative Markdown links in changed documentation: passed.
- `git diff --check`: passed.

No unresolved acceptance failures. Browser tests use fixtures, not live homelab
credentials or a live authorized user session. Backend isolation is unchanged;
no new backend authorization claim is inferred from browser fixtures.
