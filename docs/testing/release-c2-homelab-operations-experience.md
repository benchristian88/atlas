# C2.4 implementation and acceptance record

Date: 9 September 2026. **Implementation complete; automated validation complete;
live/manual acceptance pending.** This record concerns the uncommitted C2.4
working tree. It does not claim deployment, merge or live acceptance.

## Follow-up: compact Dashboard and sidebar refinements

Shared shell top padding is now 20px on desktop and 16px at widths up to 900px.
`PageHeader` omits an absent eyebrow instead of rendering its empty margin;
provided eyebrows remain visible. Sidebar selection retains its themed pill,
bold text, `aria-current` and focus ring, with the separate left border removed.

All four Dashboard totals have consistent icon tiles, large counts and the
truthful supporting line “Current recorded total”. Missing or inaccessible
totals retain a dash and explanatory text. No comparative analytics are inferred.
Knowledge attention adds small icons and compact actionable rows. Critical
Services reuse entity icons, recorded status (with visible text), managed
criticality and existing completeness meters, now inset in each card. Recent
changes use existing change types for decorative event icons (with a generic
fallback), and retain the recorded summary, entity name and timestamp.

Validation for this refinement:

- `cd apps/web && npm test` — 97 passed.
- `cd apps/web && npm run build` — passed; 34 pages generated.
- With that build served locally on port 3114, run from `apps/web`:
  `ATLAS_BROWSER_DASHBOARD_ONLY=1 ATLAS_WEB_TEST_ORIGIN=http://127.0.0.1:3114 ATLAS_BROWSER_OUTPUT=/private/tmp/atlas-c24-refinements node scripts/check-operations-browser.mjs`
  — passed against fixture API data in Chrome. Light and dark modes at 1600,
  1280, 900 and 390px verify title spacing, selected styling, equal card heights,
  truthful totals, all attention icons, status/completeness, event icons and
  timestamps, keyboard focus, and absence of content overflow/runtime exceptions.
  Existing appearance checks also pass. Screenshots were visually reviewed;
  evidence is in `/private/tmp/atlas-c24-refinements/dashboard-evidence.json`.
- `git diff --check` — clean.

Manual checks: select a populated Customer/Site, compare Dashboard totals with
their lists, follow attention and Critical Service links, and review recent
changes against Changes. Check the tighter title spacing on Dashboard, Knowledge
Graph and a page with an eyebrow such as My profile. Repeat in Light and Dark
at desktop, tablet and phone widths; hover and Tab through the sidebar, summary
cards and actionable rows. Confirm the selected pill has no left accent, long
names wrap, and recorded status/completeness remain readable.

No backend, schema, API, route or authorization changes; feature-ledger status
is unchanged. Live-data manual acceptance remains pending. This focused check
does not rerun the full graph analysis smoke described below.

## Follow-up: sidebar icons and independent theme mode

The sidebar now uses consistent 18px decorative inline SVGs for all available
destinations, including the existing Reference Data and Administration links.
No icon dependency was added. Permissions, destinations and layout are unchanged.

Profile → Appearance separates Theme mode (Light, Dark, System) from the retained
accent picker, hex input and presets. Save appearance persists both through
`PATCH /api/auth/profile`; reset selects System and the default accent. The
additive `theme_mode` response field reloads through login and `/api/auth/me`.
Migration `20260909_0015` adds the nullable, constrained preference; null means
System. The existing authenticated self-profile and audit boundary is retained.
No customer/site or graph authorization behavior changes.

`RootShell` resolves System with `matchMedia`, listens for device-mode changes,
and applies `data-theme` to the document root. Shared CSS tokens control surfaces
and native control colour schemes. Accent derivation leaves surface/sidebar
colours alone and computes readable text, soft highlights and focus rings for
either palette. Preference loading uses the existing server mechanism; there
is no new local-storage theme cache.

Follow-up validation:

- `apps/web`: `npm test` — 97 passed; `npm run build` — 34 pages built.
- `apps/api`: `.venv/bin/python -m pytest tests/test_auth.py -q` — 31 passed
  before adding the PostgreSQL persistence case.
- Full `.venv/bin/python -m pytest -q` with `ATLAS_TEST_DATABASE_URL` pointing
  to a fresh disposable PostgreSQL instance — 248 passed, no skips. This includes
  persistence through separate database sessions, logout/login, audit history,
  invalid values, omitted-field compatibility and self-profile authorization.
- `.venv/bin/alembic upgrade head` on that disposable database — passed through
  `20260909_0015`; `.venv/bin/alembic heads` — one head, `20260909_0015`.
- `.venv/bin/alembic upgrade 20260908_0014:head --sql` — additive column and
  correctly named check constraint inspected.
- Chrome: `ATLAS_WEB_TEST_ORIGIN=http://127.0.0.1:3105 node
  scripts/check-operations-browser.mjs` against Next development — full C2.4 and
  appearance checks passed, with no runtime exceptions.
- Chrome: `ATLAS_BROWSER_APPEARANCE_ONLY=1
  ATLAS_WEB_TEST_ORIGIN=http://127.0.0.1:3106 node
  scripts/check-operations-browser.mjs` against the standalone production build
  passed the focused sidebar/theme acceptance checks with no runtime exceptions.
  Evidence is saved separately
  to `/private/tmp/atlas-c24-browser/appearance-evidence.json`.
- The complete browser script against production still times out waiting for
  the graph **Preview unavailable** analysis scenario. The unchanged script also
  reproduces this on an isolated, untouched `cecbca1` source snapshot built with
  Webpack. This production smoke issue remains outside the sidebar/theme update;
  verify Preview unavailable manually on the deployed instance. No graph
  traversal or analysis behavior was changed to address it.
- `git diff --check` — clean.

Manual acceptance for this follow-up (against your normally migrated instance):

1. Open Profile → Appearance. Choose **Light**, select **Blue**, then **Save
   appearance**. With the device set to dark, confirm Atlas stays light.
2. Open Dashboard and Knowledge Graph; select an Asset to open the inspector.
   Check backgrounds, cards, graph lanes/nodes, controls and text in both pages.
3. Check icons beside each permitted sidebar destination. Hover links, navigate
   to one, and Tab through links to verify hover, selected and focus states.
4. Repeat steps 1–3 with **Dark** while the device is set to light. Try another
   preset and custom `#FFFFFF`/`#000000`; mode must remain unchanged and controls,
   links and focus rings must remain readable.
5. Refresh, return to Profile, then sign out and sign back in. Confirm both saved
   preferences reload. Tab to Theme mode, choose with arrow keys, and save using
   the keyboard.
6. Save **System**, then change the device appearance while Atlas is open.
   Confirm Atlas follows it. **Reset to Atlas default** should save System and
   the default teal accent.
7. Repeat at desktop, tablet and phone widths; check the Profile controls and
   sidebar remain usable and the Graph inspector remains accessible.

## A–I. Implementation and architecture

- **A — Delivered:** a compact operations Dashboard and visual Knowledge Graph
  over accepted Atlas knowledge, with fixed widgets, progressive disclosure,
  persistent inspector, Find, URL state and C2.3 analysis in the same graph.
- **B — Architecture:** PostgreSQL remains authoritative; the new batched landscape
  method reuses C2.1 temporal/authorization/metadata loaders. C2.2 groups are
  presentation objects, and the existing C2.3 engine owns every consequence.
- **C — Frontend dependency:** none added; manifest and lockfile unchanged. Custom
  DOM buttons and SVG connectors implement one deterministic horizontal layout.
- **D — API:** new `GET /api/operational-graph/landscape`; opt-in `site_viewpoint`
  on graph/analysis, opt-in `include_customer_wide` on summary/changes, and additive
  graph metadata. Existing defaults and compatibility routes remain intact.
- **E — Scope:** one Customer/Site viewpoint; directly relevant authorized remote
  providers may appear. Existing customer-wide and site-specific Services remain
  distinct scope choices. The user explicitly chose to retain those rules.
  No fundamental contradiction requiring a domain migration was found under
  that decision. Site-scoped grants do not gain customer-wide access.
- **F — Dashboard:** four metrics, fixed registry IDs/order, service landscape,
  knowledge attention, three Critical Service cards and six meaningful changes.
  Completeness reuses required satisfied/total, including explicit not-evaluated
  handling. Customer-wide changes/gaps are included only when authorized.
- **G — Graph:** Business Functions / Services / Assets lanes, Overview and depth
  1/2 Focus, type/relationship filters, search, pan/zoom/Fit, +N disclosure and
  dependency-group presentation. Main navigation uses `/knowledge-graph`;
  `/topology` remains available for legacy lenses.
- **H — Analysis:** unavailable/degraded/unknown/unaffected remain API states;
  namespaced canonical relationships and structured explanations are preserved.
  BF availability and structural Asset-to-Asset propagation are not invented.
- **I — Accessibility/responsiveness:** HTML buttons, explicit Enter/Space selection,
  focus rings, labelled controls/status/meters, semantic relationship list,
  independent inspector, reduced motion, system light/dark tokens and a full-width
  mobile inspector below a pannable graph.

Details and explicit bounds are in the
[architecture](../architecture/homelab-operations-experience.md).

## J. Performance evidence

The PostgreSQL fixture contains 40 Services, 150 Assets and 20 Business Functions,
with 230 relationships including a Service cycle and a remote provider. The
read executes under PostgreSQL `READ ONLY`; the test checks the node/edge counts,
selected Customer, no writes, bounded query count and site-grant non-disclosure.
It used 19 SQL statements and measured **36.2 ms** for the 210-node/230-edge
projection on the local test instance, independent of a per-Service fetch loop.
Measured local query/render timings are test observations, not product SLAs.

The frontend unit fixture uses 210 nodes and 300 edges, tests deterministic
presentation and full expansion, and initially displays 24 nodes with explicit
186-record disclosure. The browser fixture exercises 210 nodes and 230 edges,
asset-lane expansion, and pan/zoom/Fit with full-sized nodes.

Browser output and screenshots are generated outside the repository at
`/private/tmp/atlas-c24-browser/`; `evidence.json` records the final measured
navigation-to-visible-nodes time (**135 ms** in the final dense fixture run)
and zero runtime exceptions. These synthetic
browser responses validate presentation, not deployed API integration. Real
PostgreSQL tests separately validate the new query behavior.

## K–L. Commands and results

Commands executed from the indicated directories:

| Directory | Command | Result |
| --- | --- | --- |
| `apps/web` | `npm test` before edits | 81 passed |
| `apps/api` | `.venv/bin/python -m pytest tests/test_operational_graph.py tests/test_dependency_semantics.py tests/test_dependency_analysis.py tests/test_auth.py -q` before edits | 95 passed |
| `apps/web` | `npm test` after implementation | 95 passed |
| `apps/api` | `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://localhost:55424/atlas_c24 .venv/bin/python -m pytest -q` | 239 passed, including C2.1/C2.2/C2.3, auth, C2.4 and real PostgreSQL integration |
| `apps/web` | `node scripts/check-operations-browser.mjs` | Passed against isolated Chrome and synthetic fixtures; no runtime exceptions |
| `apps/web` | `npm run build` | Production build passed, 34 pages |
| `apps/api` | `.venv/bin/python -m compileall -q app` | Passed |
| `apps/api` | `.venv/bin/alembic heads` | Single head `20260908_0014` |
| `apps/api` | `DATABASE_URL=postgresql+psycopg://localhost:55424/atlas_c24 .venv/bin/alembic upgrade head` | Full existing migration history applied to a fresh temporary PostgreSQL database |
| repository | `git diff --check` | Clean |
| repository | Relative Markdown target check over changed documentation | 89 targets passed |

The repository has no configured frontend lint/format script, no ESLint config,
and no configured Python formatter/linter. No standalone lint result is claimed;
Next compilation, Python compilation, tests and whitespace checks were run.
Existing FastAPI/Starlette Python deprecation warnings remain; they do not fail
the suites. No schema migration was added. No generated/vendor artefacts were
added to source control. Plugin code and dependencies were unchanged; plugin
suites were not rerun for this UI/read-projection change.

## M. Files and documentation changed

| Files | Purpose |
| --- | --- |
| `apps/api/app/services/operational_graph.py` | Batched authorized landscape and inspector metadata |
| `apps/api/app/schemas.py` | Optional explicit graph-node metadata |
| `apps/api/app/routes/operational_graph.py`, `apps/api/app/routes/dependency_analysis.py` | Landscape route and opt-in Site viewpoint |
| `apps/api/app/routes/context.py`, `apps/api/app/routes/changes.py` | Opt-in customer-wide gaps/completeness/changes |
| `apps/api/tests/test_operations_experience.py` | Projection, scope, metadata, API and PostgreSQL regressions |
| `apps/web/app/dashboard/page.js` | Fixed registry-rendered operations Dashboard |
| `apps/web/app/knowledge-graph/page.js` | Overview/Focus/Analysis route, controls, search and URL state |
| `apps/web/components/service-landscape.js` | Shared accessible lane presentation, groups, disclosure and viewport |
| `apps/web/components/graph-inspector.js` | Recorded entity details and structured scenario explanations |
| `apps/web/components/operations-primitives.js`, `apps/web/app/globals.css` | Compact theme, cards, status, completeness and responsive primitives |
| `apps/web/lib/operations-experience.mjs` | Registry, presentation transforms, URL parsing and API overlays |
| `apps/web/lib/workspace-selection.mjs`, `apps/web/components/workspace-context.js`, `apps/web/components/context-selector.js` | Explicit authorized Customer/Site selection |
| `apps/web/lib/navigation-model.mjs` | Reachable new graph navigation with legacy route active matching |
| `apps/web/lib/record-context.mjs`, `apps/web/components/service-form.js` | Preserve explicit record scope when editing from a Site viewpoint |
| `apps/web/app/services/new/page.js`, `apps/web/app/services/[id]/edit/page.js`, `apps/web/app/services/[id]/page.js`, `apps/web/app/business-functions/page.js` | Narrow customer-wide form/provider-picker compatibility; no detail redesign |
| `apps/web/tests/operations-experience.test.mjs` | C2.4 presentation, URL, accessibility contract and scale coverage |
| `apps/web/tests/knowledge-completeness-ui.test.mjs`, `apps/web/tests/knowledge-v2-ui.test.mjs` | Replace superseded Dashboard count/reconciliation assertions with requested behavior |
| `apps/web/scripts/check-operations-browser.mjs` | Dependency-free optional Chrome interaction/theme/responsive fixture checks |
| `README.md`, `docs/README.md` | Current release state and documentation entry points |
| `docs/product/development-roadmap.md`, `docs/product/release-c2-plan.md`, `docs/product/feature-ledger.md` | C2.4 implementation/pending manual gate; C2.5 sequence, IP cleanup and deferrals |
| `docs/architecture/operational-graph.md`, `docs/architecture/authentication-and-access-control.md` | Link current graph experience and document viewpoint vs authorization |
| `docs/architecture/homelab-operations-experience.md` | C2.4 design, API, scope, UX, dependency decision and limitations |
| `docs/testing/release-c2-homelab-operations-experience.md` | This implementation/validation/manual acceptance record |

## N. Deferred work and practical limitations

Live acceptance is the remaining release gate. Browser checks use fixtures; no
claim is made that the user's deployed topology or actual devices were tested.
Screen-reader/device acceptance remains part of the manual checklist.

Service/BF detail redesign is C2.5. Interface-owned IP cleanup must preserve
existing data and update discovery/importers later. The existing duplicate Asset
IP did not block C2.4: inspector networking reads interfaces and does not add a
second IP rule. BF completeness remains explicitly unsupported.

Enterprise scale, minimap, alternate layouts, saved perspectives, Workloads(N)
clustering, dashboard customization/drag-drop/named/per-Site dashboards, network
lane, BF impact, Asset-to-Asset failure propagation and richer/full enterprise
Impact Analysis remain deferred. Search returns up to eight matches per type;
refine the query for further matches. Output truncation has a generic warning,
not invented exact counts. Fit preserves a readability floor on small screens.

## O. Exact manual acceptance checklist (pending)

1. Run the branch in your normal test deployment without merging. Confirm
   Alembic remains at `20260908_0014`. Sign in as your usual homelab administrator.
2. Confirm one explicit Customer/Site is selected, no aggregate option is offered,
   changing Customer selects only its accessible Sites, and refresh restores
   selection. Check a customer with no Sites can still reach administrative setup.
3. Open Dashboard. Verify exactly four metrics, Environment Overview and Knowledge
   attention, then Critical Services and recent changes. Compare counts and
   completeness to existing API/detail data; statuses must say recorded status.
4. Use All/Critical/With gaps and expand a +N control. Click a Dashboard entity;
   confirm `/knowledge-graph?focus=<type>:<id>` and the matching inspector.
5. Switch Overview/Focus, select with one click and Enter/Space, double-click a
   node, use Find, and change depth 1/2. Confirm selection alone does not navigate
   or reset pan/zoom. Test Fit and scroll/drag panning.
6. Toggle each node and relationship filter. Structural Asset relationships start
   off. Open a dependency group and compare Required/Optional, All/Any, effect
   and visible members with the existing Service dependency editor.
7. Inspect an Asset, Service and Business Function. Verify interface IP/VLAN,
   criticality, completeness, recorded relationships and Open actions. BF must
   show no invented completeness percentage or availability state.
8. Preview AdGuard unavailable using your known topology. With explicit DNS
   Provider/Core Operation unavailable effects, confirm DNS unavailable directly
   at one hop and Reverse Proxy unavailable downstream at two hops. Check
   structured reasons and path labels against the existing C2.3 results.
9. Preview PVE1 unavailable. Its structural Runs on relationship must not by
   itself imply AdGuard or Service failure. BF nodes remain context. Review
   degraded, unknown, unaffected and Any behavior if genuine topology supports
   them; do not add fictitious production knowledge merely to pass acceptance.
10. Exit analysis and confirm the same Focus context. Copy a Focus+Analysis URL,
    refresh it, then use Back/Forward through depth/filter/scenario transitions.
11. With two Sites in one Customer, use a customer-wide Service provided by an
    Asset at the other Site. Confirm its Site badge, relevant provider inclusion,
    and complete authorized analysis; unrelated remote infrastructure is absent
    from Overview. Confirm existing site-specific link restrictions still apply.
12. Test a site-restricted viewer and another-Customer user. Verify no hidden
    entity names/counts/search results/explanations appear, and inaccessible deep
    links retain Record not found. Test mixed Service and Asset permissions.
13. Create/edit a customer-wide Service and BF while a Site is selected. Verify
    scope is preserved and authorized remote providers remain selectable for
    customer-wide Services. Reopen the record to check persistence.
14. Review system light and dark themes, desktop/tablet/phone widths, keyboard
    focus, status labels, semantic relationship list and inspector reading order.
    Mobile must retain readable nodes and all core actions.
15. Review an empty and a partly modeled environment; simulate a read failure
    safely in development and retry. Review your dense homelab and +N disclosure.
    Record actual live acceptance separately before any merge.

## Repository and database state

- Branch: `feature/c2-4-homelab-operations-experience`.
- HEAD: `69c9a9a8ee3ca9d8b49d281cb9adf031c806e431`.
- Working tree: C2.4 changes listed above, uncommitted.
- Migration head: `20260908_0014`; no schema migration added.
- No commit, push, merge or release was performed.

Final `git status --short` (no commits made):

```text
 M README.md
 M apps/api/app/routes/changes.py
 M apps/api/app/routes/context.py
 M apps/api/app/routes/dependency_analysis.py
 M apps/api/app/routes/operational_graph.py
 M apps/api/app/schemas.py
 M apps/api/app/services/operational_graph.py
 M apps/web/app/business-functions/page.js
 M apps/web/app/dashboard/page.js
 M apps/web/app/globals.css
 M apps/web/app/services/[id]/edit/page.js
 M apps/web/app/services/[id]/page.js
 M apps/web/app/services/new/page.js
 M apps/web/components/context-selector.js
 M apps/web/components/service-form.js
 M apps/web/components/workspace-context.js
 M apps/web/lib/navigation-model.mjs
 M apps/web/tests/knowledge-completeness-ui.test.mjs
 M apps/web/tests/knowledge-v2-ui.test.mjs
 M docs/README.md
 M docs/architecture/authentication-and-access-control.md
 M docs/architecture/operational-graph.md
 M docs/product/development-roadmap.md
 M docs/product/feature-ledger.md
 M docs/product/release-c2-plan.md
?? apps/api/tests/test_operations_experience.py
?? apps/web/app/knowledge-graph/
?? apps/web/components/graph-inspector.js
?? apps/web/components/operations-primitives.js
?? apps/web/components/service-landscape.js
?? apps/web/lib/operations-experience.mjs
?? apps/web/lib/record-context.mjs
?? apps/web/lib/workspace-selection.mjs
?? apps/web/scripts/
?? apps/web/tests/operations-experience.test.mjs
?? docs/architecture/homelab-operations-experience.md
?? docs/testing/release-c2-homelab-operations-experience.md
```
