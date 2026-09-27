# Dependency impact UX validation

The shared fixture `apps/web/tests/fixtures/dependency-impact.mjs` includes Home
Connectivity, Home Automation with a required homeassistant singleton, DNS with
two AdGuard providers in an ANY group, optional/degraded Atlas DNS control plane,
File Sharing with a two-member ALL group, Reverse Proxy depending on DNS, Home
Automation depending on DNS as well as Assets, and an unclassified Asset edge.
No fixtures modify real accepted knowledge.

Automated unit tests cover singleton POST/PATCH mapping, Unknown classification,
required/optional values, preserving existing singleton strategy and identity,
graph normalization, singleton/group sizes, mixed graph density, presentation
filtering and natural explanations with unresolved and satisfied alternatives.
The browser script exercises the actual production UI against intercepted API
fixtures at 1440, 900 and 390 pixels. These are browser QA checks, not live database
acceptance; API correctness and isolation are covered separately by backend tests.

Commands and execution results are recorded below after validation.

## Executed validation

Branch: `feature/dependency-semantics-ux` (already checked out with a clean tree
at task start). No commit, push, merge or PR was created.

- `npm test --prefix apps/web`: **190 passed**.
- `npm run build --prefix apps/web`: **passed**, including static page generation.
- From `apps/api`, `.venv/bin/python -m pytest tests/test_dependency_semantics.py tests/test_operational_graph.py tests/test_dependency_analysis.py tests/test_dependency_analysis_postgres.py -q`:
  **86 passed, 1 skipped**. The skip requires `ATLAS_TEST_DATABASE_URL` pointing
  to a disposable migrated PostgreSQL database; none was configured. Existing
  scope, permission, temporal and unchanged analysis-result tests passed.
- From `apps/api`, `.venv/bin/alembic heads`: **20260921_0023 (single head)**.
- `git diff --check`: **passed**.

Browser validation used the production build served with
`npm run start --prefix apps/web -- --hostname 127.0.0.1 --port 3112`:

```bash
ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-impact-browser-tools/node_modules/playwright/index.mjs \
ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
node apps/web/scripts/check-dependency-impact-browser.mjs
```

**51 browser assertions passed** across 1440, 900 and 390 pixel widths. Checks
include singleton creation from Unknown, editing, canonical optional requirement,
keyboard effect activation, combining Asset and Service dependencies, ANY/ALL
editing, advanced renaming, read-only controls, mixed singleton/HA rendering,
depth 1/2, touch and keyboard semantic disclosure, page overflow, and natural
singleton/one-HA-provider preview explanations with technical details preserved.

```bash
ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-impact-browser-tools/node_modules/playwright/index.mjs \
ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
ATLAS_BROWSER_BASE_URL=http://127.0.0.1:3112 \
ATLAS_BROWSER_OUTPUT=/tmp/atlas-impact-expanded-regression \
node apps/web/scripts/check-expanded-graph-browser.mjs
```

**8 existing expanded-graph browser scenarios passed**: light/dark themes at
1440×1000, 900×1000, 390×844 and 390×600. This checks existing expansion, focus,
filters, depth, search, fit and analysis interactions alongside the refinement.

Screenshots are local artifacts in `/tmp/atlas-dependency-impact-browser`:
`service-home-{width}.png`, `service-dns-{width}.png`,
`graph-dns-depth-{1|2}-{width}.png`, and `graph-dense-{width}.png`.
Desktop dense graph and mobile graph/Service screenshots were visually reviewed.
These depict the mixed fixture described above, not production records.

## QA coverage and limits

| Requested scenario | Evidence |
| --- | --- |
| Home Automation / homeassistant singleton | Real UI classification/editing and singleton preview against fixtures; mixed Service page also includes unrelated dependencies |
| DNS with two ANY providers | Service controls, graph group, alternate-provider explanation |
| DNS HA plus optional Atlas DNS | Direct singleton rendering and inspectable optional/degraded detail |
| Several unrelated Asset dependencies | Mixed Home Automation and File Sharing fixture; ALL group remains visible |
| Asset and Service dependencies together | Home Automation fixture and creation of a group spanning both kinds |
| Dense depth-2 graph | Mixed focused graph at both depths and dense overview |
| Desktop/mobile Service and graph | 1440/900/390 browser runs and screenshot inspection |
| Singleton preview | Natural unavailable consequence plus original engine details |
| One member of HA unavailable | Remaining AdGuard provider satisfies requirement; no whole-Service health claim |
| All HA members unavailable | Wording unit test and existing engine tests; not exercised through UI because current preview accepts one focus only |
| MINIMUM/quorum | Not implemented by current domain, deliberately not offered or simulated |

Browser APIs are intercepted and depth requests are tested against the shared
presentation fixture; actual depth-bound acquisition is covered by backend
traversal tests. No live PostgreSQL mutation or live-data manual acceptance was
performed. The opt-in PostgreSQL test remains unrun.

Dense lane layouts still have crossing edges, especially Service→Service routes
beside Asset connectors. This work removes unnecessary singleton nodes without
replacing the layout algorithm. Native canvas scrolling remains necessary on
narrow screens; the relationship disclosure and inspector provide readable text
without hover. No page-level horizontal overflow was found at checked widths.

The graph cannot establish total membership outside its authorized, bounded
input. Known multi-member groups remain expanded after presentation filters,
but an acquired projection containing only one member renders directly. A future
API refinement could expose an authorization-safe presentation completeness hint
if that distinction needs stronger UI treatment; this change does not add one.

Dashboard cards still navigate to the general Knowledge Graph. An inline
**Relationships needing dependency-impact classification** disclosure now lists
known affected relationships and links directly to their Service editor. A
future small follow-up could preserve an attention filter in graph URL state.

## Changed files and compatibility

- `apps/web/components/dependency-impact.js`: new singleton and multi-provider
  workflow, optional group names, advanced membership editing, read-only view.
- `apps/web/app/services/[id]/page.js`: replaces the old primary editor; reduces
  duplicate semantics in relationship rows; refreshes after edits without
  replacing the whole page with a loading screen.
- `apps/web/app/globals.css`: responsive effect controls, selected checkmark/outline,
  touch targets and readable relationship disclosure.
- `apps/web/lib/dependency-semantics.mjs`: existing-API singleton mapping and shared
  relationship detail labels.
- `apps/web/lib/operational-graph.mjs`: presentation member counts retained through
  normalization, without deleting semantic fields or changing graph identity.
- `apps/web/components/service-landscape.js`: singleton collapse, group retention,
  accessible semantic disclosure and Service review links.
- `apps/web/lib/dependency-analysis.mjs`,
  `apps/web/components/dependency-analysis-panel.js`, and
  `apps/web/components/graph-inspector.js`: human explanations with original
  engine details retained; no engine result changes.
- `apps/web/app/dashboard/page.js`: actionable classification relationship list.
- `apps/web/tests/dependency-impact.test.mjs` and
  `apps/web/tests/fixtures/dependency-impact.mjs`: new semantic and density fixtures.
- `apps/web/tests/dependency-semantics.test.mjs`, `entity-detail.test.mjs`,
  `operations-experience.test.mjs`, and `visible-graph.test.mjs`: update existing
  source-contract assertions for the replacement component and presentation rule.
- `apps/web/scripts/check-dependency-impact-browser.mjs`: reproducible fixture QA.
- `docs/architecture/operational-graph.md`,
  `docs/architecture/dependency-analysis.md`, `docs/product/feature-ledger.md`, and
  this file: domain/presentation distinction, workflow mapping and honest validation.

No migrations, schema changes, API contract changes or backend authorization
changes. All writes use the existing permission-checked endpoints and temporal
replacement workflow. The browser works only with authorized responses; it does
not request hidden membership or add a parallel tenancy model. Effects remain
unavailable/degraded/unknown and required/optional remains canonical at the group
layer for grouped dependencies, and relationship layer for ungrouped dependencies.
