# Showcase presentation upscale acceptance

Starting branch: `feature/topology-showcase`; HEAD:
`0100f6402d4cb5593007eb1eaef21d1dcd68e958`; working tree initially clean.
No commit or push.

The existing route-inclusive bounds now select a uniform presentation scale of
`min(SHOWCASE_MAX_UPSCALE, availableWidth / bounds.width, availableHeight / bounds.height)`.
`SHOWCASE_MAX_UPSCALE` is **1.30**. Poster dimension selection, adaptive width,
the 0.86 floor and collapse eligibility are unchanged. The scene remains centred
horizontally and starts at the existing 100px content top, beneath the header.
No geometry, route, relationship, group, Position, font size or text budget changes.
The existing middle ellipsis and icon + Asset name presentation are preserved.

## Scale and composition

| Case | Natural bounds | Old scale | New scale | Presented bounds | Logical poster |
| --- | ---: | ---: | ---: | ---: | ---: |
| Supplied live diagnostics | 1364×552 | 1 | 1.30 | 1773.2×717.6 | 1920×1080 |
| Realistic 44-Asset routing fixture | 1776×494 | 1 | 1.045045 | 1856×516.252 | 1920×1080 |
| Dense 39-Asset fixture | 1190×436 | 1 | 1.30 | 1547×566.8 | 1920×1080 |
| Small six-Asset fixture | 292×306 | 1 | 1.30 | 379.6×397.8 | 1920×1080 |
| Existing 44-Asset reference | 1924×434 | .964657 | .964657 | 1856×418.661 | 1920×1080 |
| Wide forest | 2664×296 | .860360 | .860360 | 2292×254.667 | 2356×1080 |

The supplied live result is calculated from the user's diagnostic extents; the
live payload was not available locally. It fits inside the unchanged 1856×948
content area, with horizontal bounds 73.4–1846.6 and vertical bounds 100–817.6.
Names remain 15px before transformation and become 19.5 logical poster pixels
at the cap; icons enlarge by the same factor.

The realistic 44-Asset fixture has less spare width, so it correctly stops below
the cap at 1.045045. Its presented width increases by 80px, reaching the available
1856px. The measured scene's top moves from 327 to 100 logical pixels. Its
canonical geometry, all 44 tiles and every routed relationship remain identical.

## Executed validation and inspected artifacts

- `node --test apps/web/tests/showcase.test.mjs apps/web/tests/showcase-routing.test.mjs`:
  **39 passed**, including small-scene enlargement, maximum cap, near-width
  limitation, unchanged shrink scales and collapse decisions.
- `npm test` in `apps/web`: **254 passed**, including existing Connectivity and
  Platform regression coverage.
- `npm run build` in `apps/web`: production build passed; **38 pages** generated.
- Direct comparison with starting HEAD across ten small, ordinary, realistic,
  dense, wide, ultrawide, both-axis, unsupported and collapsed fixtures: identical
  geometry, items, routes, edges, represented Assets, poster dimensions, outcome
  and collapse decisions. Every previously shrinking scale stays identical.
- `node scripts/check-showcase-browser.mjs`: **16 complete scenes** plus empty
  and unsupported cases passed in local production Chrome. Checks cover the
  same scene transform, measured card/route content inside existing margins,
  unchanged 15px name fonts, middle ellipsis retaining both name ends, responsive
  preview, offline PNG export, Connectivity and identical Platform content before
  and after Showcase.
- The 44-Asset PNG remains **3840×2160**. Its exact-resolution preview/export
  mean RGB-channel difference is .0002434 on a 0–255 scale, with strongly changed
  pixel fraction .000000121. The cap-scale dense fixture also passes parity.
- Visually inspected the previous 44-Asset scene, the new
  `/tmp/atlas-upscale-browser/live-routing-light-scene.png`, its
  `live-routing-light-export.png`, and `dense-routing-light-scene.png`.
  The scene sits directly beneath the header; enlarged names/icons and existing
  middle ellipses stay readable, with no clipped cards or routes.
- Relative documentation links verified; `git diff --check` clean.

Browser artifacts are in `/tmp/atlas-upscale-browser/`; comparison measurements
are `/tmp/atlas-upscale-comparison.json`. Test/build/browser logs are
`/tmp/atlas-upscale-{focused,tests,build,browser}.log`.

## Files and compatibility

`apps/web/lib/showcase.mjs` changes the scale cap and final vertical translation.
`apps/web/tests/showcase.test.mjs` adds presentation regressions;
`apps/web/tests/showcase-routing.test.mjs` updates the old unit-scale expectation.
`apps/web/scripts/check-showcase-browser.mjs` verifies enlarged scene bounds,
unchanged typography and ellipsis behavior. Architecture, operator guidance and
the feature ledger describe the new presentation behavior; this file records
acceptance.

No migrations, schema/API/backend changes or authorization/tenancy changes.
Platform, Connectivity, shared geometry/routing and the renderer are untouched.
No live knowledge was modified.

Final `git status --short`:

```text
 M apps/web/lib/showcase.mjs
 M apps/web/scripts/check-showcase-browser.mjs
 M apps/web/tests/showcase-routing.test.mjs
 M apps/web/tests/showcase.test.mjs
 M docs/admin/showcase.md
 M docs/architecture/showcase.md
 M docs/product/feature-ledger.md
?? docs/testing/showcase-upscale.md
```
