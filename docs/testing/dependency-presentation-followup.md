# Dependency presentation and homepage regression follow-up

Work continues on `feature/dependency-semantics-ux`, starting from clean commit
`4e17459a1115f90a89cefd1c0fd5406dd4ff8700`. No new branch, commit, push or PR.

## Homepage root cause

The new `Attention` relationship list read `edge.source.entity_id`,
`edge.source.name` and `edge.target.name` on the raw `/operational-graph/landscape`
response. That API returns endpoint keys, not endpoint objects. In fact its
optional `source` field is provenance text. `DashboardPage` stored that raw
response, while `ServiceLandscape` normalized only its own copy. An attention
relationship therefore reached rendering with no resolved endpoint objects.

The fix normalizes at dashboard ingestion before any widget uses the graph.
Attention counts and links share a dependency-only selector over that normalized
set. Missing effects on legacy dependencies are Unknown. Missing or malformed
records and dangling/inaccessible endpoints are omitted; no hidden entity is
looked up or fabricated. Summary Knowledge Gap totals retain their separate
summary API source, and Critical Services with gaps retain their node criteria.
There are no API response/schema changes on this branch.

## Authentication and favicon

`checkSession` already maps `/auth/me` 401 to unauthenticated; `RootShell` sends
that state to `/login` without rendering protected children. `apiRequest` sends
credentials and the session probe disables its generic redirect in favor of
RootShell's handler. These files and cookie/auth behavior were not changed.
Browser fixtures verify both accepted sessions and missing/expired-session 401
responses on direct `/`, refresh and dashboard navigation. No uncaught exception
occurred in those paths. This establishes correct frontend behavior; it does not
establish why a particular deployed user's cookie was missing or expired.
Real session persistence remains covered by the existing API tests that can run
in this environment; opt-in PostgreSQL integration tests were skipped.

The app metadata correctly references existing `/branding/favicon.svg`, PNG and
ICO assets. No app reference to a missing `/favicon.ico` was found. The console
404 for that conventional browser path is independent of the dashboard error;
no unrelated favicon or authentication change was made.

## Graph and names

- Connected Service/provider blocks replace independent alphabetical columns.
  Shared Assets retain one card and all recorded edges.
- Multi-member groups remain subordinate markers; singleton semantics remain on
  direct relationships. Semantic direction, IDs, grouping and analysis do not
  change.
- Separate routing space for Service→Service edges, tighter row spacing and
  packing of Services without Asset providers reduce crossings and wasted space.
- Stronger card typography, lane headers and entity borders distinguish entities
  from requirements. Group details remain selectable and touch accessible.
- New generated names use Service/dependency context with deterministic numeric
  collision suffixes. Existing UUID/internal-ID-style names get a friendly label
  at display time. Readable authored names and stored history are preserved.
- Normal relationship text and graph labels use the shared friendly-label helper;
  raw historical names remain only in explicit advanced/technical disclosures.

The new `dependency-refinement.mjs` fixture contains two Business Functions, five
Services, eight Assets, ANY/ALL groups, optional/required singletons, unclassified
relationships, Service dependencies and historical generated UUID names. The
browser fixture returns raw API-shaped edges with provenance strings, not
pre-normalized endpoints. Partial mode adds null records, a dangling edge and a
valid legacy relationship. Depth-2 requests use this shared presentation fixture;
actual traversal-depth semantics remain covered by backend tests.

## Validation

- `npm test --prefix apps/web`: **197 passed**.
- `npm run build --prefix apps/web`: **passed**, including production static page generation.
- From `apps/api`, `.venv/bin/python -m pytest -q`: **375 passed, 79 skipped**.
  Skipped tests require opt-in disposable PostgreSQL/migration database URLs,
  which were not configured. Existing executable auth, authorization, tenancy,
  graph, dependency semantics and analysis regressions passed.
- From `apps/api`, `.venv/bin/alembic heads`: **20260921_0023**, one head.
- `git diff --check`: **passed**.

Production browser server:

```bash
npm run start --prefix apps/web -- --hostname 127.0.0.1 --port 3112
```

Browser commands used these environment values:

```bash
export ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-impact-browser-tools/node_modules/playwright/index.mjs
export ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
export ATLAS_BROWSER_BASE_URL=http://127.0.0.1:3112
node apps/web/scripts/check-dependency-refinement-browser.mjs
ATLAS_BROWSER_OUTPUT=/tmp/atlas-refinement-impact-regression node apps/web/scripts/check-dependency-impact-browser.mjs
ATLAS_BROWSER_OUTPUT=/tmp/atlas-refinement-expanded-regression node apps/web/scripts/check-expanded-graph-browser.mjs
```

- **66 dashboard/graph assertions passed**, at 1440, 900 and 390 pixels:
  direct homepage redirect, refresh, navigation from the graph, all four attention
  counts, actionable relationship links, no attention records, partial/legacy
  records, dangling endpoints, 401 redirects from root and dashboard, Overview
  and focused depth-2 graphs, generated friendly labels, no internal IDs in
  normal relationship text, and mobile focus visibility after width measurement.
- **51 existing dependency-workflow assertions passed**: singleton/group editing,
  required/optional, keyboard and touch details, read-only behavior and previews.
- **8 existing expanded-graph scenarios passed**: desktop/tablet/mobile in light
  and dark themes, focus, expansion, filters, fit, search and analysis behavior.
- No uncaught browser exceptions occurred in those checks.

Screenshot artifacts are in `/tmp/atlas-dependency-refinement-browser`:
`dashboard-{width}.png`, `graph-overview-{width}.png`,
`graph-focus-depth-2-{width}.png`, and expanded equivalents. Desktop Overview,
expanded Overview and mobile dashboard/Focus screenshots were visually reviewed.
Review led to narrower routing gutters (all three lanes fit the checked embedded
1440px desktop view), denser packing of Services without Assets, and positioning
the focused card after viewport measurement on narrow screens.

## Material files changed

- `apps/web/app/dashboard/page.js`: normalize graph ingestion; use consistent
  attention counts/links and an explicit empty classification state.
- `apps/web/lib/dependency-attention.mjs`: dependency-only attention selector.
- `apps/web/lib/operational-graph.mjs`: validate usable identities/endpoints;
  handle null/partial collections and provide a readable legacy label fallback.
- `apps/web/lib/landscape-layout.mjs`: deterministic connected placement, provider
  clustering, compact vertical packing and connector routing.
- `apps/web/components/service-landscape.js`: consume the shared layout, friendly
  group labels and corrected narrow-screen focus positioning.
- `apps/web/app/globals.css`: lane/card hierarchy, subordinate group markers and
  cleaner relationship details.
- `apps/web/lib/dependency-semantics.mjs`: friendly historical display labels and
  collision-safe domain names for generated groups.
- `apps/web/components/dependency-impact.js`: use those names for creation and
  normal group presentation without automatically renaming existing records.
- `apps/web/components/graph-inspector.js` and
  `apps/web/lib/dependency-analysis.mjs`: friendly names in normal inspection and
  explanation text, with technical evidence retained.
- `apps/web/tests/dashboard-attention.test.mjs`,
  `apps/web/tests/landscape-layout.test.mjs`,
  `apps/web/tests/fixtures/dependency-refinement.mjs`, and
  `apps/web/scripts/check-dependency-refinement-browser.mjs`: new regression,
  layout, naming and browser evidence.
- `apps/web/tests/dependency-impact.test.mjs`,
  `apps/web/tests/operations-experience.test.mjs`, and
  `apps/web/tests/visible-graph.test.mjs`: update existing assertions for friendly
  naming and extracted presentation layout.
- Architecture documentation for operational graph/dependency analysis, the
  feature ledger and this validation record: updated contract, presentation and
  test evidence.

No database migration, schema, API route/response contract or authorization
change. The graph remains a presentation of authorized backend knowledge.
No authentication/cookie or favicon configuration change.

## Remaining limits

This is deterministic lane layout, not a general crossing-minimizing graph
solver. Shared providers and cyclic Service relationships may still cross.
Dense graphs retain vertical scrolling, and narrow screens retain canvas panning.
Acquired authorized membership still bounds presentation group cardinality.
No live data was mutated during browser QA, and no deployed user's session was
available for diagnosing their particular 401. Database-dependent integration
coverage requires the disposable database environments listed in the test skips.
