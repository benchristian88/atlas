# Showcase adaptive width acceptance

The routing failures noted here are addressed by the subsequent
[routing correction](showcase-routing.md). Poster fitting and node placement
remain as recorded here; separate overlapping geometry is not redesigned.

Validated against `feature/topology-showcase`, starting at
`6f7f14ea2b3a55023b40eb293f474fe581a05694`, with a clean working tree.
No commit, push, migration or backend/API change.

## Cause and dimension selection (A–E)

**A/B.** Showcase's remaining width limit was its fixed 1920px logical canvas,
with 1856px available after margins. Geometry wider than about 2158.14px could
not meet the 0.86 readability floor. An early width check rejected it before
routing. Increasing height could never resolve this horizontal constraint.

**C/D.** Keep 1920×1080 preferred. Compute minimum independent integer extents:
`W = max(1920, ceil(bounds.width × .86 + 64))` and
`H = max(1080, ceil(bounds.height × .86 + 132))`.
Width is capped at 3024 and height at 1358. At 1080px height the maximum aspect
is exactly 2.8:1. Return incomplete when either required extent exceeds its cap.
Final scale is `min(1, (W−64)/bounds.width, (H−132)/bounds.height)`.
The layout is translated and uniformly scaled; node placement is never repacked
for the selected dimensions. No intermediate width is hard-coded.

**E.** `topologyBounds` measures shared compact node/category geometry and
orthogonal route extents after `routeTopologyEdges` succeeds. No Asset count,
category count or relationship count estimates width. If routing fails, the
same diagnostics use explicitly marked node/group-only bounds and a routing
failure reason. The pure shared geometry module, Connectivity, Platform,
category rules, compact metrics and node styling are unchanged.

## Measured outcomes (F–L)

| Fixture | Assets / visible tiles | Components / roots | Natural bounds | Initial 16:9 scale | Logical poster | Final scale | PNG |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| small | 6 / 6 | 2 / 2 | 292×306 | 1.000000 | 1920×1080 | 1.000000 | 3840×2160 |
| reference | 44 / 44 | 2 / 2 | 1924×434 | 0.964657 | 1920×1080 | 0.964657 | 3840×2160 |
| real-shape | 50 / 50 | 2 / 2 | 2144×562 | 0.865672 | 1920×1080 | 0.865672 | 3840×2160 |
| wide | 61 / 61 | 6 / 6 | 2664×296 | 0.696697 | 2356×1080 | 0.860360 | 4712×2160 |
| ultrawide | 80 / 80 | 7 / 7 | 3438×328 | 0.539849 | 3021×1080 | 0.860093 | 6042×2160 |
| both | 132 / 132 | 7 / 7 | 2862×1224 | 0.648498 | 2526×1185 | 0.860238 | 5052×2370 |
| unsupported | 93 / 93 | 8 / 8 | 4048×296 | 0.458498 | Incomplete | 0.731225 | Disabled |

**F/G.** The 44- and 50-Asset reference fixtures retain their complete 1920×1080
result, with all workloads, intermediate hosts and current Assets visible.

**H.** The wide fixture is a recorded forest of five independent fabrics with
18 parallel hosting branches, local two-member categories, a gateway branch and
an unconnected Asset. All 61 Assets are visible. This is structural width
pressure, not hundreds of repetitive leaves. Its first attempt fails the floor
at 16:9, then succeeds at the minimum 2356px width.

**I.** The near-2.8 fixture has six fabrics, 23 host branches and one five-member
category; all 80 Assets fit at 3021×1080 (2.7972:1), three logical pixels below the
ceiling. Subtracting one pixel from the selected width violates the floor.

**J.** The 93-Asset/28-branch forest requires more than the supported width.
At the 3024×1080 cap its scale would be .731225, below .86. The browser shows
Showcase incomplete with no SVG or export action. The older 182-Asset stress
fixture also remains unsupported; route-inclusive diagnostics now correctly
identify both width and height pressure rather than stopping at the first axis.

**K.** No collapse was attempted in small, reference, real-shape, wide,
ultrawide, both-axis or unsupported normal-size fixtures. The 132-Asset both-axis
fixture demonstrates that the full dimension envelope is attempted even above
100 Assets. The existing 236-Asset repetitive fixture retains its last-resort
four-member previews only after complete geometry exceeds the height envelope.

**L.** PNG IHDR dimensions exactly match each selected logical axis × 2. Checked
3840×2160, 3840×2332, 3840×2316, 3840×2700, 4712×2160, 6042×2160 and 5052×2370.
The existing export implementation already reads SVG viewBox dimensions and
needed no changes.

## Preview, topology compatibility and browser inspection (M–O/R)

**M.** Eight light scenes compare preview pixels at exact export resolution with
their PNGs. Wide mean RGB-channel difference: .000168; near-maximum: .000215;
both-axis: .000754 on a 0–255 scale. Strongly changed pixel fractions are below
.00000013, with zero strongly changed pixels in the near-maximum image.
Three light/dark PNG pairs are byte-identical. Exports work offline and make no
network requests. Browser resizing preserves item transforms and selected
aspect ratio; the complete scene stays within page width without internal
horizontal scrolling. Full accessible names and one icon/name line per Asset
remain; no operational metadata or logical Network/VLAN tile enters the scene.

**N.** All 29 existing Connectivity layout tests pass unchanged. New fixtures
compare rank, local same-position depth and parent identity with default
Connectivity geometry. Browser comparisons show all 44/50/61/80 Assets with
Networks off and local disclosure fully expanded. These complete renderer
fixtures deliberately bypass the real API's neighbourhood cap; the separate
unchanged regression harness exercises actual Python traversal and controls.

**O.** Platform content before/after Showcase is identical in all 13 successful
Showcase browser scenarios. Unit regressions preserve Platform inputs,
Connectivity routing and disclosure inputs. The separate unchanged topology
browser regression covers both light/dark themes at 1440, 1100 and 800px.

**R.** Visually inspected normal, wide and near-maximum scene screenshots and
their corresponding PNGs, both wide Connectivity comparison captures, an export
detail at original pixel resolution, and the unsupported state. Workload names
and icons are clear at logical/export size, category boxes stay with their
hosts, all branches are inside the poster and no +N is introduced by width.
Normal desktop previews scale the whole wider scene proportionally.

Artifacts are in `/tmp/atlas-adaptive-width-browser/`: `report.json`,
`reference-light-scene.png`, `wide-light-scene.png`,
`ultrawide-light-scene.png`, their `*-light-export.png` files,
`*-preview-at-export-resolution.png`,
`wide-connectivity-networks-off-expanded.png`,
`ultrawide-connectivity-networks-off-expanded.png`,
`ultrawide-export-detail.png` and `oversized-incomplete.png`.

## Executed validation (P/Q/S)

| Command | Result |
| --- | --- |
| `node --test tests/showcase.test.mjs tests/connectivity-layout.test.mjs tests/infrastructure-topology.test.mjs` | 69 passed: 28 Showcase, 29 Connectivity layout, 12 infrastructure topology. |
| `npm test` in `apps/web` | 243 passed. |
| `.venv/bin/python -m pytest tests/test_infrastructure_topology.py tests/test_topology_layers.py -q` in `apps/api` | 23 passed. |
| `npm run build` in `apps/web` | Production build passed; 38 pages generated. |
| `node scripts/check-showcase-browser.mjs` | 13 complete light/dark scenes plus unsupported/empty cases passed in production Chrome; PNG sizes, text, Networks-off, no collapse, resize and parity checked. |
| `node scripts/check-infrastructure-topology-browser.mjs` | Six light/dark scenarios passed at 1440/1100/800px, including real Python traversal, Network controls, disclosure, focus, inspector and Platform regressions. |
| `.venv/bin/alembic heads` in `apps/api` | Single existing head `20260921_0023`; no migration changes. |
| Relative documentation link check | 35 relative links across five affected documents passed. |
| `git diff --check` | Clean. |

Browser commands used local Chrome, offline-cached temporary Playwright tools,
`ATLAS_BROWSER_BASE_URL=http://127.0.0.1:3110`, and isolated authorized fixtures.
No live Atlas knowledge was changed. Logs are `/tmp/atlas-adaptive-width-*.log`.
The first topology regression invocation used its default port 3108 and failed
to connect; it was rerun against the local fixture server on 3110.

## Material files and boundaries

| File | Purpose |
| --- | --- |
| `apps/web/lib/showcase.mjs` | Bounds-based adaptive fitting and complete diagnostics. |
| `apps/web/components/showcase.js` | Existing header rule/text budget follow selected width; complete/incomplete diagnostics log only outside production. SVG/frame already preserve arbitrary dimensions. |
| `apps/web/tests/fixtures/showcase.mjs` | Wide forest, near-maximum category footprint and optional tall branch fixtures. |
| `apps/web/tests/showcase.test.mjs` | Dimensions, bounds, floor, visible tiles, ownership, determinism and upper-bound regressions. |
| `apps/web/scripts/check-showcase-browser.mjs` | Adaptive preview/export size and parity, full topology comparisons, unsupported stress, responsive preview and diagnostic artifacts. |
| `docs/architecture/showcase.md` | Dimension selection, limits, diagnostics and export contracts. |
| `docs/admin/showcase.md` | Operator guidance for proportional ultrawide posters. |
| `docs/product/feature-ledger.md` | Repository reality and current acceptance link. |
| `docs/testing/showcase-shared-geometry.md` | Retain historical geometry evidence while pointing to the new width envelope. |
| `docs/testing/showcase-adaptive-width.md` | This A–T completion record. |

No database migrations were required. Existing API routes, contracts,
authorization, customer/site headers, topology projection and relationship
semantics remain intact. Diagnostics count only the already authorized current
Site's Networks-off graph. Manual accepted knowledge remains first-class.

The user's actual homelab data was not available in these isolated tests.
A separate existing geometry limitation surfaced while probing a single fabric
with 20 host/workload branches: compact descendants can overlap between sibling
rows. Dense category variants can also fail shared orthogonal routing. Those
geometry changes are outside this width-only task and remain deferred; the
probe is recorded in `/tmp/atlas-adaptive-width-dense-probe.json`.

## Repository state (T)

No commit or push. `git status --short`:

```text
 M apps/web/components/showcase.js
 M apps/web/lib/showcase.mjs
 M apps/web/scripts/check-showcase-browser.mjs
 M apps/web/tests/fixtures/showcase.mjs
 M apps/web/tests/showcase.test.mjs
 M docs/admin/showcase.md
 M docs/architecture/showcase.md
 M docs/product/feature-ledger.md
 M docs/testing/showcase-shared-geometry.md
?? docs/testing/showcase-adaptive-width.md
```
