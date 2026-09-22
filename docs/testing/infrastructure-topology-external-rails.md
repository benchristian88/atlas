# Connectivity external routing zones

Historical acceptance record. The later [stable groups and compact grid refinement](infrastructure-topology-stable-groups.md) replaces staggered hosting grids and per-child drops with aligned grids and presentation-only group connectors.

Branch: `feature/topology-orthogonal-layout`; starting HEAD:
`4b977f065754b8cb985c5f70603b2fd4f102b44b`. The working tree was initially clean.
No commit, push or merge was performed. This is renderer geometry only: no API,
database, migration, authorization, traversal, position assignment, relationship
semantics or disclosure-state changes.

## A–I. Correction and invariants

| Item | Result |
| --- | --- |
| A. Root cause | Rail Y was measured from the parent card, while the parent container extended farther down through its footer. Backgrounds were not horizontal obstacles. Later grid rows also needed horizontal jogs around earlier cards. |
| B. Routing zone | Each connected branch reserves a zone between complete parent and child bounds. This uses actual card height, group padding, label footer and disclosure extents, independently of global rank rows. |
| C. Parent clearance | At least 16 layout pixels below the parent card or complete parent container, whichever applies. |
| D. Child clearance | At least 16 layout pixels above the child container/card. Rails do not touch container borders. |
| E. Labels | Bottom-left labels remain protected obstacles. Their footer leaves a clear vertical exit at every member’s X, including parents in the leftmost column. |
| F. Vertical drops | Staggered grid rows reserve distinct X lanes around earlier cards. External connectors enter the child container vertically once and continue to the target without horizontal segments inside it. |
| G. +N more | Remains inside its matching group; it receives a vertical branch from the external rail. The preview count, counts/labels, expansion actions and accepted relationship records are unchanged. |
| H. Compaction | Independent sibling branches still share Y. Only local boundary clearance is reserved. No global position ranks or sort-order distances were introduced. |
| I. Multiple groups | A common upstream rail remains outside both Platform and Infrastructure containers. Each group receives its own vertical drops. Long position labels do not split otherwise local siblings merely because their footer needs an exit lane. |

Unrelated containers block both horizontal and vertical transit. An endpoint
container allows only its terminal vertical exit/drop. Relationships whose two
endpoints are inside the same local container may use internal tracks, while
still avoiding cards and label zones. Canonical arrows remain unchanged.

Simple shared rails are preferred. A deterministic exterior track handles
intervening obstacles. Dense overlays that require additional turns use a
bounded rectilinear visibility search over the finite set of obstacle boundary
coordinates. Every resulting segment is checked; no diagonal fallback exists.

The wider horizontal spacing in staggered child grids is deliberate: vertically
aligned cards in successive rows would block direct vertical drops. Fullscreen
and zoom remain useful when many children are fully expanded. This does not
claim globally optimal width or crossing-free routing for arbitrary overlays.

## J. Screenshots and visual review

The production browser harness uses isolated fixtures and the real Python
Connectivity traversal, without writing live Atlas data.

Final artifacts are in `/tmp/atlas-external-rails-full-browser/`:

- `orthogonal-first-eight-{theme}-{width}.png`: a host with eight children and
  +10 more inside its child container.
- `positions-first-eight-{theme}-{width}.png`: the Container Host to Workload
  branch with its external rail and contained disclosure control.
- `positions-siblings-{theme}-{width}.png`: independent Platform and Infrastructure
  groups sharing an upstream rail.
- `positions-all-expanded-{theme}-{width}.png`: full expansion.
- `positions-fullscreen-{theme}-{width}.png` and
  `positions-fullscreen-details-{theme}-{width}.png`: fullscreen and inspector.

Themes are `light` and `dark`; widths are 1440, 1100 and 800px. Dedicated preliminary
runs are in `/tmp/atlas-external-rails-browser/` and
`/tmp/atlas-external-rails-orthogonal/`.

Visual review checks card/outline clearance, rail/border separation, footer
labels, vertical-drop alignment, +N containment and new whitespace. The rows
stagger horizontally, making lower-row connections visibly vertical; no extra
global vertical bands are present. The diagram is wider at full expansion.

## K–M. Validation

From `apps/web`:

```bash
node --test tests/connectivity-layout.test.mjs tests/infrastructure-topology.test.mjs
npm test
npm run build
ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-topology-browser/node_modules/playwright/index.mjs \
ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
ATLAS_BROWSER_OUTPUT=/tmp/atlas-external-rails-full-browser \
node scripts/check-infrastructure-topology-browser.mjs
```

| Validation | Result |
| --- | --- |
| Focused Connectivity / Infrastructure Topology tests | 36 passed, including progressive disclosure. |
| `npm test` | 172 passed. |
| `npm run build` | Passed production build. |
| Dedicated local-position browser run (`ATLAS_POSITIONS_ONLY=1`) | Six light/dark × 1440/1100/800 scenarios passed. |
| Dedicated routing browser run (`ATLAS_ORTHOGONAL_ONLY=1`) | Six scenarios passed, including fullscreen and full expansion. |
| Complete final production browser suite | All six light/dark × 1440/1100/800 scenarios passed, including full expansion, fullscreen and interaction regressions. |
| `git diff --check` | Clean. |

Geometry tests enforce external horizontal segments, label/card/container
collision avoidance, shared source rails, minimum clearances and exactly one
vertical crossing of each child group’s top boundary. The existing dense
100-node/500-edge regression remains deterministic. Two former assumptions
were updated: independent branches need not align when their group geometry
differs, and staggered rows have distinct X coordinates even within one column.
No test was removed. The backend suite was not rerun because backend code,
contracts and database models are unchanged.

## Files changed

- `apps/web/lib/infrastructure-topology.mjs`: local routing zones, staggered entry
  lanes, complete container packing, footer clearance and container-aware routes.
- `apps/web/tests/connectivity-layout.test.mjs`: clearance, group-boundary,
  vertical-entry and long-label regressions.
- `apps/web/scripts/check-infrastructure-topology-browser.mjs`: rendered
  horizontal/vertical container collision checks and updated local geometry checks.
- `docs/admin/infrastructure-topology.md`: external-rail behavior and width tradeoff.
- `docs/architecture/infrastructure-topology.md`: geometry and obstacle rules.
- `docs/product/feature-ledger.md`: updated routing implementation evidence.
- `docs/testing/infrastructure-topology-external-rails.md`: this acceptance record.
