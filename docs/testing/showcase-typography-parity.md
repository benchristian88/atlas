# Showcase preview / PNG typography parity

Narrow presentation correction against `e82e4ae` on `feature/topology-showcase`.
Placement, routing, grouping, adaptive poster sizing, name wrapping/truncation,
Platform and Connectivity remain unchanged. No commit or push.

## A. Cause reproduced

The preview and export both declared Arial/600 at 15px for Asset names. However,
`text-rendering: auto` produced scale-dependent SVG glyph metrics. The realistic
44-Asset scene was displayed at 1402 CSS pixels wide for its 1920px logical
poster; the exported SVG was rasterized at 3840px wide. Normalized logical
metrics differed despite identical declared font sizes:

| Text | Preview width / height | Export width / height |
| --- | --- | --- |
| USW-16-POE (Rack) | 142.96974 / 16.06417 | 143.06200 / 16.77290 |
| Music Assistant | 113.56445 / 15.77844 | 113.63621 / 16.75862 |
| Nginx Proxy Manager | 153.27953 / 16.06417 | 153.37247 / 16.77290 |

The previous pixel comparison enlarged the preview to export resolution before
comparing, which hid this difference. The standalone export also dropped inherited
line-height and other text properties that were outside its freeze list.

## B. Files changed

- `apps/web/lib/showcase-text.mjs`: one font family/weight/size/line-advance source,
  scale-independent text-rendering setting, and computed text properties to preserve.
- `apps/web/components/showcase.js`: consumes those existing typography values
  and sets `geometricPrecision` on the shared scene.
- `apps/web/lib/showcase-export.mjs`: freezes the complete preview typography
  context in the cloned SVG; logical dimensions and 2× output remain unchanged.
- `apps/web/scripts/check-showcase-browser.mjs`: compares actual serialized export
  styles, line breaks, text lengths/bounds and every rectangle/transform/route
  against the real preview, with fixture and DPR selection for focused runs.
- `docs/architecture/showcase.md`: documents the enforced rendering context.
- This acceptance record.

## C. Font loading

Font loading was not the reproduced cause. Both contexts used the same installed
Arial face, family, weight and size. The existing `document.fonts.ready` wait
before export is retained. Browser validation waits for fonts before capturing
metrics in both the preview and isolated exported SVG.

## D. Logical scaling

No logical font or scene scale changed. The 44-Asset scene keeps natural bounds
1944×696, logical poster 1920×1080, final scale 0.9547325103 and PNG 3840×2160.
The export's original 2× density was correct; the different viewport scales
exposed automatic text rendering drift. Device pixel ratio is not applied to
PNG dimensions. Rectangles, icon/text transforms, padding, route paths and line
breaks are copied directly from the displayed SVG.

## E. Parity enforcement

`geometricPrecision` keeps SVG glyph geometry stable across rendering scales.
The same scene supplies the family, weight, sizes and explicit 18px tspan advance.
Export freezes computed font style/stretch/kerning/features/variants/synthesis,
line-height, letter/word spacing, text rendering, text-size adjustment and
smoothing, together with its existing palette and baseline/anchor properties.
It retains the existing viewBox and scene transform and rasterizes at 2×.
There is no second layout, export-only wrap decision, font shrink or DPR multiplier.

## F. Validation

The original browser reproduction and a one-setting experiment are recorded in
`/tmp/atlas-typography-before/typography-metrics.json` and
`/tmp/atlas-typography-precision/typography-metrics.json`. Changing only
`text-rendering` eliminated the logical text width/height differences (maximum
delta zero), confirming the correction before implementation.

Executed successfully:

- `npm test` in `apps/web`: all 261 tests pass.
- `npm run build` in `apps/web`: production build succeeds.
- Direct HEAD comparison: all name layouts and complete scene results for 12
  fixtures match exactly. The layout, route adapter, shared geometry, operational
  helpers, topology page and fixtures are byte-identical to HEAD.

Production browser acceptance passes all 17 complete scenes, plus empty and
unsupported states, with no browser errors. It compares the Site title, top-level
names, category headings, every workload and two-line names. Text styles and line
breaks match exactly; no additional truncation or clipping occurs. Sixteen scenes
have zero maximum metric delta. The enormous-site fixture's centered `+96` badge
has 1/64px metric quantization; the check allows at most 1/32px, still rejecting
the original near-1px height drift. Every exported rectangle/transform/route
matches its preview. Platform before/after comparisons and complete Networks-off
Connectivity checks pass.

The realistic 44-Asset fixture has zero metric delta across all 94 text/tspan
elements at DPR 1 and DPR 2. Both produce byte-identical 3840×2160 PNGs. Its
preview/export pixel comparison at equal export resolution has mean channel
difference 0.00027963 and changed-pixel fraction 0.000000121. Normal preview and
PNG shown at the same 1402px CSS width were also visually inspected. Raster
resampling/antialiasing can differ at reduced display sizes; font geometry and
layout are identical.

Browser commands (in `apps/web`, using local Playwright and Chrome):

```bash
ATLAS_BROWSER_BASE_URL=http://127.0.0.1:3110 \
ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-shared-browser-tools/node_modules/playwright/index.mjs \
ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
ATLAS_BROWSER_OUTPUT=/tmp/atlas-typography-after \
node scripts/check-showcase-browser.mjs

ATLAS_BROWSER_CASES=readable ATLAS_BROWSER_DPR=2 \
ATLAS_BROWSER_BASE_URL=http://127.0.0.1:3110 \
ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-shared-browser-tools/node_modules/playwright/index.mjs \
ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
ATLAS_BROWSER_OUTPUT=/tmp/atlas-typography-dpr2 \
node scripts/check-showcase-browser.mjs
```

Inspected screenshots under `/tmp/atlas-typography-after`:

- `readable-light-scene.png`: normal-width preview, including title, host names,
  category headings and every workload.
- `readable-export-at-preview-width.png`: PNG displayed at the same CSS width,
  with matching apparent type scale, line breaks and composition.
- `readable-workload-names.png`: readable one-/two-line names without clipping.
- `readable-light-export.png`: crisp high-resolution poster with the same geometry.

Results are `/tmp/atlas-typography-after/report.json` and
`/tmp/atlas-typography-dpr2/report.json`; per-scene typography JSON includes the
complete before/after styles and logical metrics. Test/build logs are
`/tmp/atlas-typography-tests.log` and `/tmp/atlas-typography-build.log`.

This frontend presentation fix requires no database migration, API change or
authorization/customer/site scoping change. The feature ledger already describes
same-scene export and needs no capability/status change. Browser evidence is
local Chrome; no other browser engine is claimed as tested.

## G. Diff check

`git diff --check` passes.

## H. Repository state

Final `git status --short`. No commit or push:

```text
 M apps/web/components/showcase.js
 M apps/web/lib/showcase-export.mjs
 M apps/web/lib/showcase-text.mjs
 M apps/web/scripts/check-showcase-browser.mjs
 M docs/architecture/showcase.md
?? docs/testing/showcase-typography-parity.md
```
