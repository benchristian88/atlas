# UI system acceptance

UI work follows [the canonical UI architecture guide](../architecture/ui-architecture.md).
The [September review](../history/product-reviews/atlas-ui-system-review-2026-09.md)
is historical rationale. This document describes repeatable acceptance checks.

From `apps/web`, run `npm test` and `npm run build`. There is currently no lint
script or ESLint configuration; the production compiler and component tests
provide the available frontend checks. Do not describe those as a lint run.

Start the production build locally, then run:

```bash
ATLAS_BROWSER_BASE_URL=http://127.0.0.1:3125 \
ATLAS_PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
ATLAS_CHROME_PATH=/absolute/path/to/chrome \
node scripts/check-ui-system-browser.mjs
```

Playwright may be supplied by the local test environment. It is not a production
dependency. The script intercepts API requests and uses isolated fixtures; it
never seeds or mutates live knowledge. Its matrix covers Dashboard, Assets,
Asset detail, Services, Business Functions, Networks, Knowledge Graph, Topology,
Service Types, Profile and Login at 1440/1024/800/390 px in light/dark modes with
default/blue/purple accents. It checks local font loading, heading scale, focus,
identity/status separation, responsive overflow and production copy. Screenshots
and JSON evidence go to `ATLAS_BROWSER_OUTPUT` or `/tmp/atlas-ui-system-browser`.

Also run the existing focused scripts:

- `check-asset-icons-browser.mjs`: cached/type/bounded fallback, fixed optical
  boxes, URL replacement and no external Asset-source requests.
- `check-entity-detail-browser.mjs`: relationships, disclosures, permissions,
  retained edit payloads, current dependency-group editor and graph navigation.
- `check-operations-browser.mjs`: shell, appearance, Dashboard and graph
  selection/filter/analysis behaviour. `ATLAS_WEB_TEST_ORIGIN` selects the server.
- `check-infrastructure-topology-browser.mjs`: presentation picker, topology
  views, connectivity, sorting, responsive layout and layout invariants.

Inspect representative desktop/mobile screenshots as well as assertions.
Browser fixtures verify frontend behaviour; they do not replace PostgreSQL
integration tests or live authorization acceptance.

From `apps/api`, run the presentation, Service and operational-graph tests, plus
`alembic heads`. The entity presentation migration is `20261004_0024`; apply it
before deploying the updated API. It adds three nullable columns without
rewriting historical values. An offline SQL review can be generated with:

```bash
alembic upgrade 20260921_0023:head --sql
```

Live migration and scoped presentation-write tests require explicitly configured
disposable PostgreSQL databases. Keep their skip results visible when those
environments are unavailable.
