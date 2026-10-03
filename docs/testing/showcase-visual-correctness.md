# Showcase name and connector visual correctness

Validated against `e519d39` on `feature/topology-showcase`. This pass changes only
Showcase's local name rectangles and connector presentation. No commit or push.

## A. Previous truncation rule

Standalone Asset tiles were fixed at 124×32 with an 80px name budget; category
cells were fixed at 112×22 with an 84px budget. Names used one 15px Arial/600 line
and middle ellipsis, even for common names such as USW-Aggregation or Music
Assistant. The full name existed only in the accessible SVG title.

## B. New width rule

Measure each name using native canvas at the unchanged font. Standalone widths
are local and bounded at 124–240px; category cells are bounded at 112–220px.
Widths include existing icon/text padding and a 2px measurement guard, rounded
up to 4px. Each category uses its own maximum useful member width, preserving
the existing one-/two-column rule. The shared engine receives actual width and
height before placement and routing. Its algorithms and defaults are unchanged.
Node tests use calibrated Arial glyph/kerning metrics; unsupported characters
have a conservative fallback rather than an underestimated width.

## C. Two-line rule

Attempt the complete name on one line, then two lines at 15px/18px line height,
then ellipsis on the final line only if those two lines cannot contain it.
Prefer a word boundary, splitting a long single token only when necessary.
Two-line standalone tiles are 46px high. Category cells use the local maximum
22px or 40px height, plus the existing 10px row gap. No metadata was added.

## D. Names verified

Unit and browser coverage retains USW-Aggregation, USW-16-POE (Rack), US-8-60W
(Office), Dell Server 1/2, Proxmox Dell 1/2, AdGuard Home, Atlas Impact, HCR
Website, Roadcycling, Music Assistant, Nginx Proxy Manager and Uptime Kuma in
full. Proxmox Data Center Manager uses two complete lines. Exceptionally long
names exceeding two-line capacity have a tested final-line ellipsis.

## E. Exact reproduced dangling connector

The supplied image has no relationship UUID or API payload, so its live UUID
cannot be established from the image alone. The 44-Asset reproduction has the
same two separate Docker Inf children and reproduces the spur on:

- Fixture relationship: `relationship:00000000-0000-4000-8000-000000010016`.
- Canonical source: unpoller, `asset:00000000-0000-4000-8000-000000000117`.
- Canonical target: Docker Inf, `asset:00000000-0000-4000-8000-000000000113`.
- Type/class: Runs on (`runs_on`), platform; nongrouped exterior fallback.

These are synthetic fixture IDs, not asserted live record IDs.

## F. Cause and correction

Homarr and unpoller have different valid categories, so both remain standalone
tiles beneath Docker Inf. Neither child is hidden or suppressed by a category
group. Both canonical and rendered endpoints exist.

With the old compact rectangles, the raw fallback starts
`[425,408] → [425,542] → [425,508]`: it retraces the last 34px, leaving a visible
spur with no endpoint at its bottom. Showcase removes this redundant collinear
turn from the displayed polyline. It preserves all original router points for
diagnosis and does not calculate another route, move a node, change category
membership or invent a relationship.

## G. Endpoint remapping and group identity

Existing hosted-group deduplication remains intact: two eligible hosted siblings
have one legitimate shared group connector with both relationship IDs. The
child presentation endpoint resolves to the existing group boundary and the
parent to its visible tile. Independent physical/mixed edges remain individual.
Existing eight-pixel router clearance ports are connected to visible boundaries.
Category member cells have a subtle background so their attachment boundary is
visible. All displayed connectors carry explicit presentation endpoint keys.

## H. Endpoint invariant

Every source and target must resolve to a visible tile or legitimate category
anchor, and the first/last path point must terminate on its actual boundary.
Hidden members, missing groups and stale pre-group points fail with the original
relationship IDs, canonical endpoint keys, rendered endpoint, role and reason.
Checks run during presentation adaptation, before SVG rendering, and independently
against browser SVG rectangles. No displayed connector is accepted with a missing
endpoint. Unit coverage also checks fallback obstacle avoidance and orthogonality.

## I. Realistic 44-Asset result

All 44 Assets are visible, with the same ownership, managed Positions and category
rules, no collapse and no ellipsis. The large PVE1 group stays two columns, with
184×40px cells and 50px row spacing. Full-name geometry has natural bounds
1944×696, selecting 1920×1080 at scale 0.9547325103. The old fixed-name fixture
had bounds 1476×558 and scale 1.2574525745. The scale formula, 1.30 maximum,
0.86 floor, dimension selection and collapse rules are unchanged; different
measured input rectangles naturally change coordinates and selected scale.

## J. Connectivity

All 29 existing Connectivity layout tests remain unchanged and pass. Default
geometry, position groups, routes and bounds for eight fixtures were compared
directly with the HEAD module and are identical, with all eight routing
successfully. The shared engine, operational helper module and topology page are
byte-identical to HEAD. Browser checks fully expand the 44-Asset fixture with
Networks off, confirm all 44 Assets and no remaining disclosure controls, and
capture the operational view. Its renderer, controls, cards and routing are untouched.

## K. Platform

Production browser acceptance records Platform content before entering Showcase
and compares it after returning for every complete scene. All comparisons pass.
No Platform source file changed. API contracts, authorization, customer/site
scoping, database models and migrations are untouched.

## L. Tests, build and browser evidence

Commands executed successfully:

- `node --test apps/web/tests/showcase.test.mjs apps/web/tests/showcase-routing.test.mjs`: 39 pass.
- `node --test apps/web/tests/showcase-visual.test.mjs`: seven focused regressions pass.
- `npm test` in `apps/web`: 261 pass.
- `npm run build` in `apps/web`: production build succeeds, 38 pages.
- Production `check-showcase-browser.mjs` with local Chrome/Playwright: 17
  complete scenes pass, plus empty and unsupported states. Every displayed
  connector has two valid SVG endpoints. Resize leaves logical geometry intact;
  names/icons stay within poster margins; export works offline; light/dark
  PNGs are identical for repeated fixtures; no browser errors.
- Preview/PNG parity passes for 12 fixtures. The named 44-Asset PNG is
  3840×2160, with mean channel difference 0.00027963 and changed-pixel fraction
  0.000000121 against the preview at export resolution.

Screenshots visually inspected, in addition to the supplied live image:

- `/tmp/atlas-visual-browser/readable-light-scene.png`: full 44-Asset preview,
  readable names, composed beneath the header, no dangling spur or clipping.
- `/tmp/atlas-visual-browser/readable-workload-names.png`: local two-column
  names, including the complete two-line Proxmox name.
- `/tmp/atlas-visual-browser/readable-light-export.png`: exported poster with
  the same complete names and connectors.
- `/tmp/atlas-visual-browser/exterior-light-scene.png`: fallback connections
  resolve visible tiles/groups without obscuring names.

Browser results are `/tmp/atlas-visual-browser/report.json`; test/build logs are
`/tmp/atlas-visual-all-tests.log` and `/tmp/atlas-visual-build.log`.
The first browser run stopped at the harness's old hard-coded Site download
filename; the harness now uses the existing `showcaseFilename` function and the
complete rerun passes. No production filename behavior changed.

## M. Diff and files

Material files:

- `apps/web/lib/showcase-text.mjs`, `showcase-font-metrics.mjs`: measured local
  Asset name sizing and one-/two-line labels.
- `apps/web/lib/showcase-routes.mjs`: rendered endpoint resolution, invariant
  and redundant spur removal, preserving canonical identity and raw routes.
- `apps/web/lib/showcase.mjs`: supplies measured rectangles to existing geometry
  and uses validated presentation routes for route-inclusive bounds.
- `apps/web/components/showcase.js`: renders those names/rectangles and route
  endpoint keys; adds endpoint failures to the existing test diagnostic panel.
- `apps/web/tests/fixtures/showcase.mjs`: named 44-Asset fixture and width-boundary
  fixture label adjustment so its test remains about structural width.
- `apps/web/tests/showcase-visual.test.mjs`: seven focused visual regressions.
- `apps/web/tests/showcase.test.mjs`, `showcase-routing.test.mjs`: actual local
  rectangle expectations, original router-point parity and unchanged fitting rules.
- `apps/web/scripts/check-showcase-browser.mjs`: full names, rendered endpoints,
  realistic fixture, preview/export checks and Site-derived filename expectation.
- `docs/architecture/showcase.md`, `docs/admin/showcase.md`,
  `docs/product/feature-ledger.md`: current name/route presentation behavior.
- This acceptance record.

`git diff --check` passes. All 37 local links in the changed documentation resolve.
No schema/migration, API, domain-semantic, authorization or operational view
changes were required. The only unresolved identification is the live UUID,
which is absent from the supplied screenshot; the regression mechanism and
synthetic relationship identity are explicitly covered above.

Final `git status --short`:

```text
 M apps/web/components/showcase.js
 M apps/web/lib/showcase.mjs
 M apps/web/scripts/check-showcase-browser.mjs
 M apps/web/tests/fixtures/showcase.mjs
 M apps/web/tests/showcase-routing.test.mjs
 M apps/web/tests/showcase.test.mjs
 M docs/admin/showcase.md
 M docs/architecture/showcase.md
 M docs/product/feature-ledger.md
?? apps/web/lib/showcase-font-metrics.mjs
?? apps/web/lib/showcase-routes.mjs
?? apps/web/lib/showcase-text.mjs
?? apps/web/tests/showcase-visual.test.mjs
?? docs/testing/showcase-visual-correctness.md
```
