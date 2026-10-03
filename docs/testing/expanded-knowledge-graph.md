# Expanded Knowledge Graph — implementation and validation

## Repository state

Implemented on `feature/knowledge-graph-expanded-view`, based on
`62f577d3c49f57570fbf9f0778a028f4fd8695df`. Changes remain uncommitted.
No commit, push, merge, schema change or migration was performed.

## Architecture audit and delivered behavior

- The full `/knowledge-graph` page owns Focus, selection, filters and analysis.
  `ServiceLandscape` renders deterministic left-to-right HTML nodes and SVG
  connectors with native pan/scroll, zoom, Fit, progressive lane disclosure,
  dependency-group markers and a structured relationship list. It is also used
  by the compact dashboard. Expand is added only to the full page.
- `GraphInspector` is the existing shared persistent inspector. Expansion keeps
  the same mounted graph and inspector, including selection and local canvas
  state. A native application dialog is promoted to the top layer; the browser
  Fullscreen API is not used. Overview retains its existing depth-free meaning.
- The old generic API maximum was 2. The API now accepts `max_depth=0..3`, with
  422 for values outside that range. The structural builder entry point also
  validates `0..3`; its separate internal analysis entry point is unchanged.
- Traversal remains deterministic, cycle-safe, current-valid and authorized at
  every endpoint, with canonical directions preserved. Customer isolation and
  authorized Site-viewpoint behavior use the existing services. PostgreSQL
  remains authoritative; no knowledge or hypothetical state is written.
- Focus still defaults to 250 nodes, with an API maximum of 500. The existing
  generic graph has no separate edge or serialized-byte cap; no cap was removed
  or raised. Overview retains its 500-node/2,000-edge bounds. Analysis retains its
  independent bounds. Existing truncation warnings and progressive rendering
  remain visible. The 210-node/300-edge deterministic presentation regression
  still passes; live database throughput was not benchmarked.
- Embedded Focus offers 1/2; expanded Focus offers 1/2/3. Closing at 3 clamps
  immediately to 2 and replaces the current URL depth without adding history.
  Reopening stays at 2. An incoming depth-3 link renders at 2 while embedded and
  uses 3 when expanded. Back/forward remains functional. Next-integrated native
  history updates query state without requiring server navigation.
- Responses are reused by depth for the current focus and workspace during the
  page session. Focus, Customer, Site or retry clears that small cache. Expand
  alone makes no graph, inspector or icon requests. The analysis request no
  longer depends on the structural response, so depth changes reuse the same
  scenario while recomputing its presentation.
- Relationship filtering still uses the shared visible-graph projection before
  layout and inspector selection. Third-hop structural orphans disappear when
  their only visible path is hidden. Removed selections fall back to Focus;
  dependency markers retain only surviving members. Analysis retains its
  pre-existing explanation-context exception to structural pruning.
- Find retains the existing authorized Customer search and additionally offers
  matches in the visible graph for selection and location without changing
  Focus. Node location pans only the canvas, protecting the page scroll position.
- Shared `AssetIcon` preserves cached Asset → Asset Type → generic fallback.
  Services and Business Functions retain their semantic icons. No alternate
  image loader, layout, minimap or graph implementation was introduced.
- Desktop uses approximately 75% graph / 25% inspector; tablet retains a narrow
  inspector, and mobile stacks a scrollable inspector below the graph. The Close
  heading stays available when a short viewport needs internal scrolling.
- Close and Escape restore page styles, scroll coordinates and focus to Expand.
  The dialog makes obscured content inert and traps Tab; node keyboard controls,
  inspector semantics and structured relationships remain accessible. Pan and
  location changes are instant and add no motion animation. Fit reads the current
  viewport; ResizeObserver continues to measure it on expansion and collapse.

## Executed validation

Baseline, before edits:

- `cd apps/api && .venv/bin/python -m pytest tests/test_operational_graph.py -q`
  — **16 passed**.
- `npm test --prefix apps/web` — **126 passed**.

Final code:

- `cd apps/api && .venv/bin/python -m pytest -q` — **343 passed, 45 skipped**.
  Skips require an unconfigured disposable migrated PostgreSQL database
  (`ATLAS_TEST_DATABASE_URL`). Existing dependency deprecation warnings remain.
  Added checks cover API acceptance/rejection, third-hop cycles, both canonical
  directions and bidirectional traversal, shuffled-input determinism, node caps,
  non-disclosure and temporal exclusion at the third hop. Existing compatibility
  endpoints and dependency-analysis tests pass.
- `npm test --prefix apps/web` — **128 passed**, including added depth-3 URL and
  structural-orphan/inspector regression cases.
- `npm run build --prefix apps/web` — **passed**.
- `cd apps/api && .venv/bin/python -m alembic heads` — one head,
  **`20260912_0018`**. No migrations required.
- `git diff --check` — **passed**.

Browser commands used a local production server on port 3108 and the existing
external Playwright installation (no dependency added):

```bash
ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-c26-browser/node_modules/playwright/index.mjs \
ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
node apps/web/scripts/check-expanded-graph-browser.mjs

ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-c26-browser/node_modules/playwright/index.mjs \
ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
node apps/web/scripts/check-asset-icons-browser.mjs
```

- Expanded graph: **8 scenarios passed**, light/dark at 1440×1000, 900×1000,
  390×844 and 390×600. Includes same-canvas identity, no requests on Expand,
  Close/Escape, focus trap/return, body lock and exact scroll restoration,
  persistent selection/filters/Focus, visible Find, depth-3 requests, pruning,
  stale-selection fallback, depth-2 reuse, analysis explanation preservation,
  Overview, copied depth-3 URLs and back/forward.
- Existing Asset icon regressions: **48 checks passed**, plus URL replacement
  and no external Asset-source requests. Includes graph, dashboard and Asset
  surfaces, both themes and fallback cases.
- Screenshots were generated under `/tmp/atlas-expanded-graph-browser` and
  `/tmp/atlas-asset-icon-browser`. Desktop, tablet and mobile screenshots were
  visually inspected. Chrome was exercised; Safari was not tested.

## Exact manual acceptance status

No authenticated live homelab browser session was available in this workspace.
The browser regressions intercept API requests with explicit synthetic fixtures;
they do not read or change live accepted knowledge. The fixture Cluster and its
relationships are test inputs, not claims about the user's actual environment.

| Requested acceptance | Fixture browser result | Live homelab result |
| --- | --- | --- |
| DNS Resolution and Filtering, depth 2, Expand/Escape | Focus, filters, inspector and valid AdGuard selection preserved; no expansion requests; scroll restored | Not run |
| AdGuard Home inspection/artwork | Shared icon mechanism retained; inspector selection survives expansion; separate icon fallback suite passed | Not run |
| PVE1 with structural relationships ON | Visible at second hop | Not run |
| Depth 2 versus depth 3 | Fixture Cluster appears only at depth 3; close removes it and displays 2; re-expansion stays at 2 | Not run |
| Structural Asset relationships OFF | PVE1 and Cluster disappear; DNS and AdGuard remain; hidden selection falls back to DNS | Not run |
| Expanded Preview unavailable | Existing scenario and Reverse Proxy explanation remain through close; no extra analysis request; Exit analysis works | Not run |

Outstanding acceptance is live homelab verification and Safari testing. No
missing or additional live relationships were inferred or fabricated.

## Material files changed

| File | Purpose |
| --- | --- |
| `apps/api/app/routes/operational_graph.py` | Allow bounded depth 3 |
| `apps/api/app/services/operational_graph.py` | Validate structural builder depth |
| `apps/api/tests/test_operational_graph.py` | Depth-3 traversal, API and safety regressions |
| `apps/web/app/knowledge-graph/page.js` | Expansion state, bounded UI depth, session reuse, selection and search |
| `apps/web/components/expanded-graph-surface.js` | Same-tree modal surface, focus and scroll lifecycle |
| `apps/web/components/service-landscape.js` | Locate visible matches and confine panning to canvas |
| `apps/web/components/navigation-icon.mjs` | Expand/Close in the existing icon family |
| `apps/web/app/globals.css` | Expanded layout, themes and responsive inspector |
| `apps/web/lib/operations-experience.mjs` | Depth-3 URL parsing and serialization |
| `apps/web/tests/operations-experience.test.mjs` | Depth-3 URL regression |
| `apps/web/tests/visible-graph.test.mjs` | Third-hop pruning and inspector regression |
| `apps/web/scripts/check-expanded-graph-browser.mjs` | Repeatable production-browser acceptance fixtures |
| `docs/admin/knowledge-graph.md` | User-facing instructions without release identifiers |
| `docs/README.md` | Guide discoverability |
| `docs/architecture/operational-graph.md` | Current structural depth contract |
| `docs/architecture/homelab-operations-experience.md` | Modal/state/presentation architecture |
| `docs/product/feature-ledger.md` | Implemented capability and pending live acceptance |
| `docs/testing/expanded-knowledge-graph.md` | This audit and validation record |
