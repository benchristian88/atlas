# Showcase compact poster correction

Historical validation of the compact-layout change. Subsequent Networks-off and
singleton-category corrections supersede its Network handling, singleton groups,
footer counts and affected fixture dimensions; see the [current guide](../admin/showcase.md) and
[focused correction acceptance](showcase-networks-off.md).

Validated on 30 September 2026 on `feature/topology-showcase`, starting from
`2410259c9256776dcb75e795a16b92c40b75df4d`. This is a presentation correction to
[Showcase v1](showcase.md), with no database migration, API/domain changes,
new route, or changes to the operational Platform/Connectivity renderers.
No commit, push or merge was performed.

## Cause and geometry (A–E)

The old layout spent 236×94 logical pixels per explicit Asset (236×86 at the
last stage), plus 44px parent/child rails (30px when tightened). Individual
nodes carried Type and Position text. Groups had 276px width, a 58px heading
region and 58px member rows (52px/50px at the last stage). Tall nested subtrees
and packing whole subtree bounding rectangles (including empty space) exhausted
the fixed 900px content height; the old large
fixture mostly repeated collapsible leaves and missed this structural shape.

The new generic 50-Asset real-shape fixture reproduces the old failure. Against
the original renderer, its final stage measured 1948×1856 content pixels,
requiring approximately .484914 scale, below the .86 floor. This establishes the
geometry problem without relying on access to the user's production data.

| Element | Corrected presentation |
| --- | --- |
| Structural Asset | 204×44, 28px icon box, one 17px name line; roughly 60% less base card area. |
| Workload/endpoint member | 150px column, 32px row (28px tightened), 22px icon box with 20px artwork, one 15px name line; no nested card. Single-member groups provide 180px member width. |
| Category/Type group | 204px wide for one preview; 332/490/648/806px for two/three/four/five columns. 32px heading, compact rows, 26px total/+N footer. Four-member groups are 90px high, or 86px tightened. Wider name budgets avoid compressing text to the old 89px budget. |
| Position | Muted 14px local heading outside the Asset tile, 18px allowance only at position transitions, shared across sibling rows. Managed ordering and parentage unchanged. |
| Header | Atlas logo and Site title retained; divider y=84, content starts y=100 rather than y=140. |
| Unconnected / Other | Content-sized region, 30px heading, 10px bottom, 12px side padding; same icon/name tiles and truthful Type grouping. |

Types remain available for classification, collapse and icon fallback, but never
appear as an extra line in an individual Asset tile. Full names remain in SVG
titles; deterministic measured ellipsis is used when a name exceeds its budget.
No IP, hostname, status, counts or Position text enters an individual Asset tile.
Counts remain on groups, where they describe represented membership.

## Fit, grouping and diagnostics (F–K)

Following Connectivity’s geometry approach, occupied subtree contours are
packed in two dimensions. Short side branches can use space beside deeper
subtrees; branches no longer reserve their entire empty bounding rectangles.
Host-local category packing is bounded to 1100px (1000px tightened), allowing
three-to-five-column grids and intermediate hosts to wrap locally. This keeps
physical hosts beside compute branches where actual space permits.

The renderer tries all normal compaction stages against 1920×1080 first, retaining
the existing .86 minimum scale. If height prevents a fit, it selects the minimum
integer poster height across eligible layouts, including route extents, bounded
at 1358. Width stays 1920; more height cannot rescue insufficient width. The
maximum aspect is approximately A3 landscape (1920:1358). Input permutations
produce identical grouping, positions, routes and dimensions.

Endpoint groups still show four previews, truthful total and +N, with consolidated
connectors retaining every underlying relationship ID. Progressive stages retain
host-local workload previews, safe repetitive Automatic leaf grouping, tighter
spacing and wider packing. Intermediate hosts remain explicit. Categories never
merge across hosts. Nothing changes the authorized whole-site input, semantic
relationships, backend tenancy controls, category visibility rules, or managed
Position ordering. Frontend site filtering remains defence in depth only.

| Fixture | Assets | Explicit / groups | Logical scene | Scale | PNG |
| --- | ---: | ---: | --- | ---: | --- |
| Small | 6 | 4 / 2 | 1920×1080 | 1 | 3840×2160 |
| Medium | 43 | 10 / 8 | 1920×1080 | 1 | 3840×2160 |
| Large grouped | 236 | 10 / 8 | 1920×1080 | 1 | 3840×2160 |
| Connectivity-shaped reference | 44 | 18 / 15 | 1920×1080 | 1 | 3840×2160 |
| Larger real shape | 50 | 17 / 14 | 1920×1080 | 1 | 3840×2160 |
| Adaptive | 102 | 52 / 50 | 1920×1237 | .860592 | 3840×2474 |
| Near maximum | 104 | 54 / 50 | 1920×1354 | .860563 | 3840×2708 |
| Deliberately oversized | 122 | 62 / 60 | Incomplete | Would require .832880 at maximum height | Export unavailable |

The 44-Asset acceptance fixture adds the office-side platform and its Home
Automation workload beneath an access switch. It contains 18 explicit structural
Assets, three APs and 23 workload leaves, including children of two container
hosts. All workloads remain visible; no workload preview is truncated. Its
1848×888 content fits 1920×1080 at native scale. The larger 50-Asset fixture also
fits 16:9 at native scale (1848×922 content), with host-local preview collapse.
Neither fixture uses extra poster height or global shrinking.

The larger real-shape fixture contains gateway → aggregation → distribution; two access
switches and five APs; three platform hosts; two infrastructure appliances; 18
children on the first platform host including two intermediate container hosts
with their own children; three workloads on each other main platform host; two
physical hosts separately attached to aggregation, each hosting a platform and
workload; and one disconnected server. Every Asset is represented, every
relationship survives connector consolidation, and nested parentage is asserted.

Internal diagnostics expose Asset count, explicit structural nodes, collapsed
groups, workload categories, forest roots, measured content width/height, selected
poster height, required scale, .86 floor, failure reason and stage attempts.
Development logs report incomplete layouts; production UI shows only the concise
incomplete message and provides no partial SVG or export.

## Routing, export and compatibility (L–P)

Card/group sizes, anchors, obstacle padding and rail spacing use compact geometry.
External Position headings are obstacles; a node's incoming connector ends above
its heading instead of making a box-shaped detour around the text. The existing
shared orthogonal router remains unchanged. Tests check all route segments against
cards and captions, scene bounds, non-overlap and retention of relationship IDs.
Wrapped branches may still need longer external rails.

The preview frame and SVG use the chosen logical dimensions. Export clones the
same scene and derives canvas width/height directly from its viewBox at exactly
2×. No reflow, crop or stretch back to 16:9 occurs. All nine browser scenarios
export successfully while offline, after resources have resolved. Cached icon,
Type fallback and failed optional icon cases remain covered. Browser resizing
preserves logical geometry and causes no topology refetch.

Pixel comparisons at export resolution cover medium, 44-Asset reference, larger
real-shape, adaptive and near-maximum scenes. The tolerance allows small SVG vs
canvas antialiasing differences (mean channel difference below 2/255 and fraction
of substantially changed pixels below .02). Final measured results are in
`/tmp/atlas-showcase-compact-browser/report.json`. The largest measured mean
channel difference is .008049/255; the largest substantially changed pixel fraction
is .0000742. Medium and adaptive exports are
byte-identical between light and dark Atlas UI. Showcase itself remains light.

Platform content before and after Showcase was identical in all nine scenarios.
The existing projection regression test verifies Showcase does not mutate either
Platform or Connectivity inputs/results. Their source modules and domain/API
contracts are unchanged.

## Executed validation (Q–T)

Commands below run from `apps/web` unless stated otherwise. Browser checks use
isolated authorized API fixtures served through the production `/topology` route,
not writes to live knowledge. Chrome/Playwright use the existing local test tools.

| Command | Result |
| --- | --- |
| `node --test tests/showcase.test.mjs` | 16 passed: existing semantic coverage plus native-scale 16:9 reference/real shape, adaptive/minimal height, near maximum, pathological diagnostics, permutation determinism, captions and route/card geometry. |
| `npm test` | 231 passed, none skipped. |
| `npm run build` | Passed; all 38 pages generated. |
| `node scripts/check-showcase-browser.mjs` | Nine scenarios passed: small, medium, large, reference, real shape, adaptive, maximum in light UI; medium and adaptive in dark UI. Name-only assertions, full titles, text budgets, dimensions, offline PNGs, pixel parity, resize, empty/incomplete and Platform checks; zero page errors. |
| `node scripts/check-infrastructure-topology-browser.mjs` | Six scenarios passed: light/dark UI at 1440, 1100 and 800px; existing Platform filtering, previews and selection plus Connectivity traversal, hierarchy, local expansion, inspector, controls and routing. Shared operational code/CSS was unchanged by subsequent Showcase-only packing refinements. |
| `git diff --check` (repository root) | Clean. |
| Local Markdown link check | 37 relative links across six changed Markdown documents resolve. |

Backend/database tests were not rerun for this frontend-only correction. No API,
schema or migration files changed; original implementation evidence is retained
in the historical record rather than presented as new validation.

Screenshots and raw results are in `/tmp/atlas-showcase-compact-browser/`.
Visually inspected the final small, reference, real-shape, large, adaptive and near-maximum
scenes; host-local category and collapsed AP crops; 16:9 and taller PNGs; and the
taller light poster inside dark Atlas UI. Cards are compact, names are single
lines, categories are dense, Position labels are restrained, the disconnected
section is content-sized, and connectors avoid text/card interiors. Longer names
are ellipsized with full titles. Both the 44-Asset and 50-Asset shapes render completely at native-scale 16:9.

Representative artifacts:

- `small-light-scene.png` and `small-light-export.png`
- `reference-light-scene.png` and `reference-light-export.png`
- `real-shape-light-scene.png` and `real-shape-light-export.png`
- `large-light-scene.png`
- `adaptive-light-scene.png` and `adaptive-light-export.png`
- `maximum-light-scene.png` and `maximum-light-export.png`
- `real-shape-light-host-local-category.png`
- `real-shape-light-wireless-group.png`
- `adaptive-dark.png`, `oversized-incomplete.png`, `report.json`

## Material files and repository state (U)

| File | Purpose |
| --- | --- |
| `apps/web/lib/showcase.mjs` | Compact geometry, occupied-contour packing, local Position captions, adjusted routing, adaptive dimensions and fit diagnostics. |
| `apps/web/components/showcase.js` | Icon/name-only tiles, compact header/groups, external captions and dynamic preview. |
| `apps/web/lib/showcase-export.mjs` | Derive PNG dimensions from the displayed scene. |
| `apps/web/app/globals.css` | Remove the fixed 16:9 frame constraint. |
| `apps/web/tests/fixtures/showcase.mjs` | Generic real-shape and adaptive/maximum/pathological fixtures. |
| `apps/web/tests/showcase.test.mjs` | Geometry, completeness, grouping, fit and regression assertions. |
| `apps/web/scripts/check-showcase-browser.mjs` | Expanded browser/export/visual acceptance. |
| `docs/admin/showcase.md` | Current compact poster and export guidance. |
| `docs/admin/infrastructure-topology.md` | Correct the fixed-format description. |
| `docs/architecture/showcase.md` | Current geometry, routing, adaptive fit and diagnostics. |
| `docs/product/feature-ledger.md` | Record implemented compact/adaptive behavior. |
| `docs/testing/showcase.md` | Mark original geometry evidence as historical and link this correction. |
| `docs/testing/showcase-compact-poster.md` | This completion and validation record. |

No unresolved implementation failures. Validation uses a generic topology shaped
like the report; the user's live homelab data was not accessed. Pathological
structures still deliberately refuse export at the unchanged readability floor.

Final `git status --short` is recorded after validation in the completion response.
