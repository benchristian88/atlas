# Infrastructure Topology interaction polish

21 September 2026. Isolated homelab-shaped API fixtures and the existing
disposable PostgreSQL database are used for acceptance. No live Atlas records
are changed.

## Pointer regression correction — 21 September 2026

The original acceptance below was insufficient: it used checkbox `check()` and
`uncheck()` helpers and did not click the visible category label, text or icon.
Its passing result did not establish that the entire visible option worked.
The following correction supersedes that interaction claim.

### Reproduction and exact cause

Branch `feature/infrastructure-topology-v0`, starting HEAD
`ed4f91e081d8dcc0908da42196a7e77ffcd1ca8d`, initially clean working tree.
The unmodified production build reproduced the failure with a normal Playwright
`row.click()` on Backup. Read-only event instrumentation recorded:

1. `pointerdown` and `mousedown` hit the label's text span inside the popover.
2. The initially focused checkbox blurred to the enclosing embedded `dialog`.
3. The filter root's React `onBlur` treated that temporary focus change as an
   exit and synchronously unmounted the popover.
4. `mouseup` landed on the underlying topology; no checkbox `click` or `change`
   occurred. The Filters count remained unchanged.

The document `pointerdown` containment check was correct. The failure was the
blur dismissal before native label activation, not an overlay or state reset.
Direct checkbox clicks worked in this reproduction, explaining why the former
acceptance missed the visible-row failure.

At 1440px/light before the fix, the popover bounds were approximately
`(894.67, 267.19, 380, 289)` and Backup's row was
`(1089.67, 341.69, 172, 30)`. Centre hit tests returned the intended input and text
span. The panel and controls had `pointer-events: auto`; the existing panel
`z-index` was 60, ancestor z-indices were auto, and no pseudo-element or
transparent overlay intercepted the option. Bounding boxes and hit tests were
recorded for every option. `account-dropdown` styling was not the cause.

### Scoped correction

`topology-category-filter.js` tracks whether a pointer interaction started
inside its root. Blur dismissal waits through that interaction so native label
activation can focus and toggle the checkbox. Pointer up/cancel and effect
cleanup clear the guard. Outside pointerdown still dismisses, without
preventing default events; ordinary keyboard focus departure still dismisses.
Unique IDs and explicit `htmlFor` associations supplement the native wrapping
labels. The entire compact row, text, icon and checkbox activate the same
native input. Existing pointer cursors, layout, scrolling and stacking remain.
No CSS or z-index adjustment was needed.

The controlled `choices` updater, `topologyCategorySelection`, managed defaults,
and view-entry initializer are unchanged. Checkbox changes retain local
overrides and immediately update both topology content and the changed count.
The existing suite continues checking active-tab retention, new-tab reset,
Expand/Refresh preservation, and managed-default changes after Refresh.

No database/migration, API, route, graph semantics, authorization or customer/site
boundary changed. Browser fixtures only supply already-authorized UI data; no
live Atlas records are modified. Feature-ledger classification remains valid.

### Stronger acceptance

The browser fixture now assigns PBS to Backup, so disabling Backup must remove
an actual Asset. Category interactions use normal Playwright clicks. Read-only
`evaluate` calls inspect geometry, computed styles, native checked state and
focus; none activates or changes a control.

In light/dark at 1440, 1100 and 800px, both embedded and expanded views test:

- Filters pointer opening, Backup row toggle and toggle back.
- Direct native checkbox, text, and empty row-padding clicks, each checking
  visible native checked state, Filters count and PBS removal/restoration.
- Compute icon clicks with PVE1 removal/restoration and count changes.
- Native Tab navigation and Space toggling, with the same topology checks.
- Reset after two overrides, restoring visible defaults, PBS and the count,
  and removing the default-hidden Uncategorized Asset.
- Outside click, Escape/focus return, and keyboard departure after pointer use.
- Every option's row/input/text/icon centre hit tests and computed pointer events;
  unrelated overlay interception fails the test. Unique input IDs and explicit
  label association are also checked.

The strengthened test was run against the original production build and failed
on its first Backup row click: “Inside interaction keeps the popover mounted”.
The previous production reproduction log is `/tmp/atlas-filter-repro.log`;
the failing regression log is `/tmp/atlas-filter-before.log`.

Validation commands run from `apps/web` unless indicated:

| Check | Result |
| --- | --- |
| `node --test tests/infrastructure-topology.test.mjs tests/presentation.test.mjs` | 12 passed before and after the fix. |
| `npm test` | 144 passed. |
| `npm run build` | Passed for reproduction and for the fixed production build. |
| `node scripts/check-infrastructure-topology-browser.mjs` | Six scenarios passed: light/dark at 1440, 1100 and 800px, with pointer/hit-test acceptance in both embedded and expanded views. |
| `node scripts/check-expanded-graph-browser.mjs` | Eight scenarios passed, light/dark at desktop and mobile widths. |
| `node --check scripts/check-infrastructure-topology-browser.mjs` | Passed. |
| `git diff --check` (repository root) | Clean. |

Browser commands use `ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-topology-browser/node_modules/playwright/index.mjs`,
`ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'`,
and `ATLAS_BROWSER_BASE_URL=http://127.0.0.1:3112`.
`ATLAS_BROWSER_OUTPUT` is `/tmp/atlas-filter-browser` for topology and
`/tmp/atlas-filter-expanded` for Knowledge Graph. Topology output includes
per-option hit-test JSON and before-reset/after-reset screenshots. Light and
dark screenshot review confirms native checkbox visibility and changed counts.
Logs: `/tmp/atlas-filter-{focused,tests,build,browser,expanded}.log`.

Material files for this correction only:

- `apps/web/components/topology-category-filter.js`: pointer/focus lifecycle
  correction and explicit native label associations.
- `apps/web/scripts/check-infrastructure-topology-browser.mjs`: real pointer
  acceptance, Backup Asset fixture, hit-test evidence and screenshots.
- `docs/testing/infrastructure-topology-interactions.md`: correct the earlier
  acceptance claim and record reproduction and validation.

No commit, push, merge or branch change. Repository state:

```text
 M apps/web/components/topology-category-filter.js
 M apps/web/scripts/check-infrastructure-topology-browser.mjs
 M docs/testing/infrastructure-topology-interactions.md
```

---

The remainder records the preceding implementation and its original validation.

## A–C: Repository

- Branch: `feature/infrastructure-topology-v0`.
- HEAD: `294c84453826d41bc69dc5de8bbc26ff382ff738`.
- Started with a clean working tree. No commit, push, merge or branch change.
- Final working-tree paths are recorded below.

## D–I: Filters

The previous implementation conditionally inserted a full-width fieldset below
the toolbar, with outlined category labels. It shared its open state across
views and had no reset action or changed-filter count.

`TopologyCategoryFilter` now anchors an absolutely positioned dropdown to the
existing Filters button. It reuses Atlas's `account-dropdown` styling, theme
tokens, shared `PresentationIdentity`, and outside-click/focus conventions.
There is no new component library. The panel is 380px wide, constrained to the
viewport, with two compact checkbox columns and 22px category icons. At widths
below 400px the choices stack. It can open above the button and scroll within
the available height. The topology content does not move when it opens.

All managed categories, including custom and inactive categories, remain
available. Changes apply immediately. `topologyCategorySelection` resolves
choices from current managed `show_in_topology` values plus local overrides.
The button shows `Filters · N` only when N values differ from those defaults;
enabled defaults do not contribute to the count. Reset clears overrides and
keeps the popover open. No Reference Data write occurs.

The button has `aria-expanded` and `aria-controls`. The popover is non-modal,
with a labelled fieldset and native checkboxes. Opening focuses the first
checkbox; Tab follows normal control order and closes on leaving. Escape closes
and returns focus to Filters; it does not close the enclosing expanded view.
Outside clicks dismiss it. Names and checkmarks supplement category accents.

## J–R: View state and navigation

One `enterView` initializer resets transient state when a different tab is
clicked. It retains the existing individual state controls rather than adding
a persistent per-view state cache. All four views use the same managed category
default calculation. Clicking the already-active tab preserves state.

| View | Fresh defaults |
| --- | --- |
| Overview | Managed category defaults, no search, no inspector selection, closed Filters, normal scroll. |
| Platform | Managed defaults, blank search, no parent focus or Asset selection, eight-child previews, existing name/ID order, closed Filters. |
| Network & VLAN | Managed defaults, blank search, no Asset inspector, first visible Network in existing VLAN/name/ID order, closed Filters. |
| Connectivity | Managed defaults, blank search, one hop, Networks enabled, first visible Asset in name/ID order, no selected node beyond focus, fitted viewport, closed Filters. |

Customer, Site, authentication and theme are outside this initializer.
Expand/collapse retains the same mounted tree, controls, child expansion,
selection, graph zoom and pan. Viewport measurement ignores the brief hidden
dialog transition; user pan is retained relative to the graph centre during
resize. Fit clears zoom and pan.

Refresh retains the current projection while fetching its replacement, keeping
valid controls and the unchanged graph mounted. A response that removes a graph
entity invalidates that old graph before the replacement connectivity result is
rendered. Existing fallback behavior handles removed Asset/Network selections.

Explicit inspector **Focus Connectivity** and Network navigation supply fresh
initial context. A requested Asset's category is enabled if necessary; unrelated
overrides are cleared. Subsequent ordinary tab entry returns to managed defaults.
The source audit found no existing topology URL/query-state or Asset-detail
deep-link contract. None was added or removed. Existing focused Knowledge Graph
links are preserved. Temporary filters and tab clicks do not write history.

## S–V: Validation

Commands are run from `apps/web` except the API/migration checks (`apps/api`) and
Git checks (repository root).

| Check | Result |
| --- | --- |
| Baseline `node --test tests/infrastructure-topology.test.mjs tests/presentation.test.mjs` | 11 passed before implementation. |
| Baseline `node scripts/check-infrastructure-topology-browser.mjs` | Six production-browser scenarios passed before implementation. |
| Final focused frontend command above | 12 passed. |
| `npm test` | 144 passed. |
| `npm run build` | Passed. |
| `.venv/bin/pytest -q tests/test_infrastructure_topology.py tests/test_infrastructure_topology_postgres.py` | 18 passed with the disposable PostgreSQL test URL; no skips. Existing deprecation warnings remain. |
| `.venv/bin/alembic heads` | Single head `20260921_0020`; no migration required. |
| `node scripts/check-expanded-graph-browser.mjs` | Eight Knowledge Graph regression scenarios passed, both themes including narrow/mobile viewports. |
| Final `node scripts/check-infrastructure-topology-browser.mjs` | Six scenarios passed: light/dark at 1440, 1100 and 800px, including all new interaction checks. |
| Browser script syntax and `git diff --check` | Passed. |

The topology script includes popover geometry/no-layout-shift checks, all dynamic
choices, immediate filtering, icon/accent contrast, reset and changed-count
behavior, keyboard/outside dismissal, all four destination defaults, unchanged
workspace context, updated managed defaults after refresh, active-tab retention,
Expand/Refresh preservation, graph zoom/pan and explicit navigation including a
default-hidden Asset. Existing topology and Reference Data checks remain.

Browser execution uses installed Chrome, Playwright from
`/tmp/atlas-topology-browser/node_modules/playwright/index.mjs`, and the production
frontend at `http://127.0.0.1:3112`. Screenshots are written to
`/tmp/atlas-interaction-browser`; logs use `/tmp/atlas-interaction-*.log`.
Baseline screenshots are in `/tmp/atlas-interaction-baseline`.

The first new browser run exposed a transient zero-width measurement on expand;
the viewport guard fixes it. Fixture assertions were also corrected to select
a Network present in the Overview preview and to check Network icon contrast
on graphs that contain Network nodes, independently of the now-closed filters.
The outside-click target uses the uncovered heading at tablet width, where the
popover overlays the search field. Light/dark screenshots were visually reviewed.
The initial API run skipped PostgreSQL tests before the fixture server started;
the verified fixture database run passed all 18.
Temporary frontend and PostgreSQL validation services were stopped afterward.

## Compatibility, documentation and material files

No database migration, API contract, route, taxonomy, Network metadata, traversal
or backend authorization/scoping change. PostgreSQL remains authoritative. The
existing workspace remount and authorized API projections remain in use.

| File | Purpose |
| --- | --- |
| `apps/web/app/topology/page.js` | Shared view-entry reset, explicit navigation, retained Refresh graph and viewport state. |
| `apps/web/components/topology-category-filter.js` | Compact accessible temporary category selector. |
| `apps/web/lib/infrastructure-topology.mjs` | Shared managed selection/default-difference calculation. |
| `apps/web/app/globals.css` | Compact responsive popover layout. |
| `apps/web/app/presentation.css` | Remove obsolete outlined category-filter styling. |
| `apps/web/tests/infrastructure-topology.test.mjs` | Managed defaults, differences, reset and changed-reference-data regression. |
| `apps/web/scripts/check-infrastructure-topology-browser.mjs` | Interaction acceptance alongside existing homelab and presentation checks. |
| `docs/admin/infrastructure-topology.md` | User interaction behavior and defaults. |
| `docs/architecture/infrastructure-topology.md` | State lifecycle and truthful navigation contract. |
| `docs/testing/infrastructure-topology-interactions.md` | This implementation/validation record. |

The feature ledger already classifies these four views and managed filters as
implemented; this polish does not change their classification. Live manual
homelab acceptance remains separate from these isolated production-browser tests.

## Repository state

```text
 M apps/web/app/globals.css
 M apps/web/app/presentation.css
 M apps/web/app/topology/page.js
 M apps/web/lib/infrastructure-topology.mjs
 M apps/web/scripts/check-infrastructure-topology-browser.mjs
 M apps/web/tests/infrastructure-topology.test.mjs
 M docs/admin/infrastructure-topology.md
 M docs/architecture/infrastructure-topology.md
?? apps/web/components/topology-category-filter.js
?? docs/testing/infrastructure-topology-interactions.md
```
