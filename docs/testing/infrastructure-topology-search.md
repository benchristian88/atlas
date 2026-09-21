# Connectivity focus finder and compact toolbar

21 September 2026. Focused UI change on `feature/infrastructure-topology-v0`.

## A–C. Repository

Starting HEAD: `dc9e9d549261fc9ba4e94b821e0adfc3aa1c9c39`. The working tree was
clean. Branch and HEAD are unchanged; no commit, push or merge was performed.
Final status is recorded below.

## D–H. Search reproduction, cause and fix

Before editing production code, Chrome opened the existing production Next build
at `http://127.0.0.1:3112/topology` with the repository's isolated homelab fixtures.
With AdGuard Home focused, a real click and keyboard typing of `pve` changed the
input but left focus unchanged. There were zero new requests and zero listboxes.
Only the separate native Focus selector's options narrowed to AdGuard Home and
the PVE hosts (plus Networks). Selecting PVE1 there successfully recalculated the
graph. The before screenshot is `/tmp/atlas-search-before/before-search.png`.

The actual cause was incomplete interaction wiring: Connectivity's search value
was used only by `matchesSearch` to filter native Focus options. No results popup,
result-selection handler or keyboard result-navigation behavior existed. Input
state and matching worked. This was not a failed request, stale query parameter,
response mapping, debounce, authorization failure or overlay intercepting a
search result: no search request or result popup existed.

The new component matches the existing `/api/topology` projection immediately
after one non-whitespace character, with a deterministic maximum of ten results.
It uses Asset name, hostname and every visible AssetInterface IP, including
partial/case-insensitive matches. Legacy `Asset.ip_address` is excluded. Each
result shows the shared Asset icon, name, managed Type name, hostname and compact
interface IP where available. No health/status is invented.

No additional all-Assets fetch or search endpoint was introduced. The existing
backend projection applies `assets.view`, customer and site context; interface
addresses additionally require `networks.view`. Presentation category filters
are independent of this authorization. PostgreSQL tests exercise exact/partial
name, hostname and IP matching in the existing Asset list API and the authorized
source projection, missing matches, hidden Sites/customers, scoped grants, denied
focus and legacy-IP exclusion. Backend production code is unchanged.

## I–M. Toolbar

The former stacked Search Assets field and separate stacked Focus row are replaced
by a shared compact Search / inline Focus / hops / Networks row. Existing Atlas
field/button styles, accessible names and visible focus treatment are reused.
Fit, zoom and node counts remain inside the graph card.

At 1440 × 1000, both themes have a 38px toolbar and aligned control centres. The
graph card starts at y=341.1875 instead of y=450.6875: **109.5px higher**. Search is
360px and Focus is 240px. At 1100 and 800px the toolbar wraps to 67.5px, controls
remain usable, and the page has no horizontal overflow. Geometry JSON and
screenshots are under `/tmp/atlas-search-browser`.

## N–R. Interaction

Search selection uses the same `refocusConnectivity` handler and canonical
`focusId` as Focus, node double-click and inspector Focus. It clears search,
closes results, synchronizes the selector and requests the new graph. Hops,
category/Relationship Class choices and Networks are retained; refocus mounts
the existing fitted/recentred graph. Typing and empty matches leave it untouched.
The separate Focus selector no longer narrows while typing.

Searching a category hidden by presentation filters retains both that chosen
focus and the existing filter settings, with a message to enable its category.
When all categories are hidden, this message replaces the graph loading state.
Cross-view explicit navigation still initializes the requested category as before.
Entering another tab and returning resets transient state; Refresh and expansion
retain it. Source-loading/error handling uses the existing topology status/banner
and Refresh action; search is disabled on source-refresh failure, and current
focus remains unchanged.

Acceptance uses `page.mouse.move` and `page.mouse.click` at result centres, with
read-only `document.elementFromPoint` checks confirming the result/child receives
the pointer. It also covers Arrow Down/Up, wrapping, Enter, Escape, Tab and
reopening results after Escape. The final focused rerun passed the hidden-category
loading guard, Arrow Up reopening and empty-search modal Escape after these small
edge-case fixes; the full regression pass preceded those fixes. Expanded mode uses the same mounted component;
Escape dismisses the popup before the modal, and details hide/show, selection,
Fit and refocusing work. Search scenarios include AdGuard Home → `pve` → PVE1,
`adg`, interface `192.168.5.3`, hostname and no matches.

## S–X. Validation

Commands ran in `apps/api` or `apps/web` as appropriate. API tests used the existing
disposable `atlas_positions_api` PostgreSQL database with `PGCLIENTENCODING=UTF8`
and `ATLAS_TEST_DATABASE_URL`; test fixtures roll back their records.

| Check | Command / result |
| --- | --- |
| Search, scope, Connectivity, positions, classes | `.venv/bin/pytest -q tests/test_infrastructure_topology.py tests/test_infrastructure_topology_postgres.py tests/test_topology_positions.py tests/test_topology_positions_postgres.py tests/test_topology_layers.py tests/test_topology_layers_postgres.py` — 42 passed |
| Auth, Asset CRUD, entity access | `.venv/bin/pytest -q tests/test_auth.py tests/test_crud.py tests/test_entity_detail_access.py` — 77 passed |
| Frontend | `npm test` — 153 passed |
| Focused production browser | `ATLAS_SEARCH_ONLY=1 node scripts/check-infrastructure-topology-browser.mjs` — six scenarios passed: both themes × 1440/1100/800px |
| Full production browser | `node scripts/check-infrastructure-topology-browser.mjs` — six scenarios passed: positions/layered layout, classes/categories, hops/Networks, selection/refocus, eight-child preview/+N, Fit and expanded details in both themes at three widths |
| Production build | `npm run build` — passed |
| Migration heads | `.venv/bin/alembic heads` — `20260921_0023 (head)` |
| Browser script syntax | `node --check apps/web/scripts/check-infrastructure-topology-browser.mjs` — passed |
| Documentation destinations | Local link check — 20 destinations checked, none missing |
| Whitespace | `git diff --check` — clean |

Chrome used installed Playwright via `ATLAS_PLAYWRIGHT_MODULE`, installed Chrome
via `ATLAS_CHROME_PATH`, and `ATLAS_BROWSER_BASE_URL=http://127.0.0.1:3112`.
Logs are `/tmp/atlas-search-{api,api-regression,web-tests,build,browser,browser-full}.log`.
The browser API fixtures execute the real Python Connectivity traversal; database
permissions and persistence are separately tested against PostgreSQL. Existing
FastAPI/Starlette deprecation warnings remain.

**Live homelab acceptance remains unverified:** no live URL/session was supplied.
These are production-build browser checks with realistic intercepted fixtures,
not a live-data session. No live operational records were changed.

## Files, compatibility and documentation

| Material file | Change |
| --- | --- |
| `apps/web/components/connectivity-asset-search.js` | Accessible bounded focus finder and pointer/keyboard popup interaction. |
| `apps/web/app/topology/page.js` | Single toolbar and shared focus-handler wiring; preserve category filters. |
| `apps/web/app/globals.css` | Compact wrapping row and anchored results styles. |
| `apps/web/lib/infrastructure-topology.mjs` | Deterministic ten-result matching helper. |
| `apps/web/tests/infrastructure-topology.test.mjs` | Fields, partial matches, bound, ordering and legacy-IP exclusion. |
| `apps/web/scripts/check-infrastructure-topology-browser.mjs` | Production pointer, keyboard, geometry, failure and expanded acceptance; adapt previous tests to dismiss the new popup. |
| `apps/api/tests/test_infrastructure_topology_postgres.py` | Asset-list/source-projection search and authorization regression tests. |
| `docs/admin/infrastructure-topology.md` | Explain search as focus finder and compact controls. |
| `docs/architecture/infrastructure-topology.md` | Correct existing refocus description; no new architecture. |
| `docs/product/feature-ledger.md` | Add focus-finder behavior to the implemented Connectivity entry. |
| `docs/testing/infrastructure-topology-search.md` | Reproduction and acceptance record. |

No database migration, API route/contract, traversal/domain semantics, accepted
knowledge or authorization implementation changed. PostgreSQL remains the system
of record. The existing local test server is stopped after validation.

## Final repository state

```text
 M apps/api/tests/test_infrastructure_topology_postgres.py
 M apps/web/app/globals.css
 M apps/web/app/topology/page.js
 M apps/web/lib/infrastructure-topology.mjs
 M apps/web/scripts/check-infrastructure-topology-browser.mjs
 M apps/web/tests/infrastructure-topology.test.mjs
 M docs/admin/infrastructure-topology.md
 M docs/architecture/infrastructure-topology.md
 M docs/product/feature-ledger.md
?? apps/web/components/connectivity-asset-search.js
?? docs/testing/infrastructure-topology-search.md
```
