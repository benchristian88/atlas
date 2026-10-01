# Showcase global Topology Position bands

> Historical acceptance record. Layout descriptions and measurements below are
> superseded by [shared Connectivity geometry](showcase-shared-geometry.md).

Layout-only correction on `feature/topology-showcase`, starting from
`d51cd5ffd881d863ff65b9f1140390e54c2559bc`. No commit or push. This supersedes the
branch-local geometry and three-to-five-column category descriptions in the
historical compact-poster and Networks-off acceptance records.

## Layout behavior (A–F)

Previously the occupied-contour packer tried both X and Y offsets for each
subtree. That filled whitespace independently per branch and placed Assets with
the same managed Position at unrelated heights. Category grids also widened to
as many as five columns.

Occupied Topology Position IDs now define global bands, sorted by their managed
sort order and labeled with their managed name. No Position names or ordering
are hard-coded. The existing presentation forest supplies same-position chain
depth. A switch chain occupies local subrows wholly inside its band's bounds;
subsequent Positions begin below the complete preceding band. Structural peers
under different parents, and unconnected peers, share Y.

Only occupied Positions reserve space. Compaction reduces row/rail gaps and
member spacing, then uses the unchanged uniform-scale floor. Horizontal contour
packing cannot change Y. Workload categories stack within the local parent's
band. Very wide sibling sets can wrap into deterministic band-local rows, with
inherited rows for descendants; they never interleave Platform and Workload
bands. Unconnected Assets occupy a separate side region at their assigned levels.

Category rules use total membership, including collapsed groups:

| Members | Presentation |
| --- | --- |
| 1 | Direct Asset tile; no category wrapper |
| 2–4 | One column, 204px card |
| 5+ | Exactly two 150px member columns, 332px card |

Maximum category columns: **2**. Existing name/ID ordering is filled row-wise
left-to-right. Tests cover 1, 2, 3, 4, 5, 8, 16 and 20 members. Larger groups grow
taller, with existing truthful +N collapse available at later fit stages.

## Fixture and routing results (G–K)

The existing 44-Asset reference is complete at 1920×1220, scale 0.86076. The
50-Asset real-shape variant is complete at 1920×1170, scale 0.86070. Physical and
Platform hosts align across branches, including the office-side Platform in the
44-Asset fixture; every workload is below the Platform band. Relationships and
host-local membership are unchanged.

Routing uses destination-row horizontal rails and short drops. Stacked groups
prefer shared side trunks; the existing orthogonal obstacle router handles
remaining obstructions. Tests verify node/caption avoidance, bounds, no category
content crossings, and no vertical backtracking on the reference category
trunks. Every accepted Asset relationship retains its underlying identity.

Network/VLAN entities and interface memberships remain excluded before layout;
the 44-Asset reference produces identical geometry when its three logical
Networks and 44 memberships are removed. Network-device Assets remain.
Platform/Connectivity implementation and output are unchanged. Regression tests
compare both projections before and after Showcase, and the existing frontend
suite covers their layout behavior. Browser acceptance compares Platform content
before and after visiting Showcase.

A 70-branch/142-Asset structural fixture now fits because overflow rows compact
whole bands. The oversized refusal fixture consequently uses 90 branches/182
Assets and still refuses partial rendering/export. Adaptive and near-maximum
fixtures use 50 branches with 2 and 6 extra same-position spine nodes, measuring
1920×1109 and 1920×1343. Readability and completeness limits were not changed.

## Validation (L–P)

Commands run from `apps/web` unless noted:

- `npm test`: 247 passed, including 32 Showcase tests.
- `npm run build`: production build passed.
- `node scripts/check-showcase-browser.mjs`, using the existing temporary
  Playwright module and local Chrome against isolated authorized API fixtures:
  nine light/dark scenarios, PNG export, offline export, same-scene parity,
  responsive geometry, icons/name-only tiles, category grid ordering, aligned
  bands, empty-site refusal and oversized refusal.
- `git diff --check` from the repository root: clean.

Browser artifacts are in `/tmp/atlas-showcase-position-bands/`, including
`reference-light-scene.png`, `real-shape-light-scene.png`, their exported PNGs,
`maximum-light-scene.png`, `oversized-incomplete.png` and `report.json`.
The reference and real-shape screenshots and exported reference PNG were visually
inspected against the earlier
`/tmp/atlas-showcase-networks-off/reference-light-scene.png`. Fixtures are generic;
the user's live homelab data was not accessed.

## Scope and files

- `apps/web/lib/showcase.mjs`: band geometry, horizontal packing, category widths,
  band-aware routing and bounds for the aligned unconnected region.
- `apps/web/tests/showcase.test.mjs`: focused regression and real-shape assertions.
- `apps/web/scripts/check-showcase-browser.mjs`: band/grid browser assertions and
  updated stress-fixture dimensions.
- `docs/architecture/showcase.md`, `docs/admin/showcase.md`,
  `docs/product/feature-ledger.md`: current layout behavior.
- `docs/testing/showcase-position-bands.md`: this validation record.

No database migrations, API contracts, authorization/customer/site scoping,
data projection, structural semantics, icon loading, export implementation,
renderer styling, Site title, Platform or Connectivity changes. Backend/database
tests were not rerun for this frontend-only correction. Final `git status --short`
is included in the completion response.
