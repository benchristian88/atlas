# Knowledge Graph edge routing refinement

Branch: `feature/dependency-semantics-ux`, starting from clean commit
`07bcf7ff00524805a82f256cdedc22500cf2db52`. No new branch, commit, push or PR.

## Inspection and implementation

Inspected `service-landscape.js`, `landscape-layout.mjs`,
`landscape-geometry.mjs`, the Knowledge Graph page, connector/card CSS,
normalization/presentation tests, dependency fixtures, and existing production
browser scripts. This is custom React/HTML card rendering over an SVG canvas;
there is no third-party graph library or layout engine to configure.

The hard-to-follow routing came from shared centre anchors, orthogonal H/V paths,
four repeatedly reused rail offsets, and a separately hard-coded angular group
trunk. Paths could look merged even though their underlying edges were distinct.

The change is limited to routing and traceability:

- Cross-lane edges use restrained cubic Bezier curves between side anchors.
  Equal-height endpoints produce a straight flow without an artificial loop.
- Service→Asset uses right→left anchors. Recorded Service→Business Function
  edges retain left→right card-side anchors and the recorded arrow direction;
  they are not reversed to match the illustrative mockup.
- Same-lane Service dependencies bend through the left gutter, distinct from
  Asset-provider routing on the right.
- Shared endpoints receive small ordered port offsets. Opposite endpoint
  position and durable edge key determine ordering, not API array order.
- Each multi-member group keeps one curved parent connector and separate
  outgoing member ports. Later groups' parent connectors use the outer gutter
  to avoid passing through earlier requirement markers.
- Singleton groups remain direct original relationships. No synthetic singleton
  node, altered membership, name, effect or requirement is introduced.
- Selected nodes subtly emphasize adjacent edges. Selecting a member includes
  its shared group's visible branches and trunk; selecting a group isolates
  emphasis to that group. Unrelated context remains visible. Existing analysis
  styling takes precedence.
- SVG marker IDs are unique per canvas; arrow tips coincide with path endpoints.
  Fit/zoom and ResizeObserver-driven layout remain the existing implementation.
- Node positions/order, lanes and cards were not redesigned. Left border accents
  on entity cards remain removed. Textual relationship details, keyboard actions
  and touch disclosure remain available.

## Files changed

- `apps/web/lib/landscape-layout.mjs`: cubic routes, group trunks, distributed
  ports and selection-edge calculation; existing node layout unchanged.
- `apps/web/components/service-landscape.js`: memoized routes, unique markers,
  group/edge emphasis and stable DOM identifiers for browser validation.
- `apps/web/app/knowledge-graph/page.js`: pass selected group identity.
- `apps/web/app/globals.css`: restrained selected/background connector styles.
- `apps/web/tests/edge-routing.test.mjs`: geometry, direction, grouping, fan-out,
  fan-in, selection, deterministic ordering, normalization and bounded cost.
- `apps/web/tests/fixtures/edge-routing.mjs`: isolated singleton, DNS HA/controller,
  and dense Home Connectivity fixtures.
- `apps/web/scripts/check-edge-routing-browser.mjs`: production-browser fixture
  navigation, endpoint attachment, selections, Fit/zoom, resize and screenshots.
- Architecture graph documentation, feature ledger and this validation record.

No database/schema/API changes or migrations. No authorization or tenant-scoping
changes. This operates exclusively on existing authorized graph projections and
does not change failure analysis or temporal knowledge.

## Fixtures and QA

The dense fixture contains Home Connectivity and Smart Home; DNS, DHCP, Firewall
Protection, Internet Access, Reverse Proxy and Home Automation; UDM-Pro, Atlas
DNS, both AdGuard providers, Nginx Proxy Manager and homeassistant. It includes a
shared UDM provider, DNS ANY group, optional/degraded direct Atlas DNS controller,
Service→Service links, and Business Function support relationships.

Browser APIs are intercepted; a bounded structural fixture response provides
Focus depth 1/2/3 neighborhoods. These fixtures do not write live knowledge and
do not substitute for backend traversal/authorization tests.

Validation completed:

- `npm test --prefix apps/web`: 202 tests passed, including five new routing
  tests.
- `npm run build --prefix apps/web`: production build passed.
- From `apps/api`, `.venv/bin/python -m pytest tests/test_operational_graph.py
  tests/test_dependency_semantics.py tests/test_dependency_analysis.py -q`:
  86 tests passed (540 dependency deprecation warnings).
- `git diff --check`: clean.

Browser checks used the production server at `http://127.0.0.1:3112`, started
with `npm run start --prefix apps/web -- --hostname 127.0.0.1 --port 3112`.
Commands (local Playwright/Chrome installations, no new framework dependency):

```bash
ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-impact-browser-tools/node_modules/playwright/index.mjs \
ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
node apps/web/scripts/check-edge-routing-browser.mjs

ATLAS_PLAYWRIGHT_MODULE=/tmp/atlas-impact-browser-tools/node_modules/playwright/index.mjs \
ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
ATLAS_BROWSER_BASE_URL=http://127.0.0.1:3112 \
ATLAS_BROWSER_OUTPUT=/tmp/atlas-edge-expanded-regression \
node apps/web/scripts/check-expanded-graph-browser.mjs
```

The routing script passed 126 checks across 1440px, 900px and 390px widths in
light and dark themes. The existing expanded-graph script passed eight scenarios
across desktop, tablet and two mobile heights in both themes. Routing checks
cover singleton depth 1/2, pure DNS HA, HA plus controller, dense depth 2/3,
DNS/AdGuard/Atlas DNS and group selection, keyboard/touch detail disclosure,
Focus/Overview, Fit, zoom and resize. SVG endpoint positions were checked
against actual card bounds after transforms. No uncaught browser errors occurred.
Local depth/selection/Fit/zoom/resize/Overview sequences took 351–618ms.

Visual screenshot review covered the desktop singleton, DNS HA plus controller,
full dense depth-3 Fit view (including Reverse Proxy→DNS), narrower-desktop HA
pair, and dark mobile DNS. The singleton has two direct aligned relationships
and no group marker. DNS has a short parent trunk and two distinct curved member
branches, with Atlas DNS separately attached. The dense overview retains clear
cards and emphasizes DNS paths, but shared-provider and Service-to-Service
crossings still require some tracing. Narrow views retain horizontal panning;
they do not squeeze all three lanes into unreadable cards. Interactive scenarios
above were automated browser QA; screenshot review was visual inspection, not
live-data manual acceptance.

Screenshot artifacts from this run are in `/tmp/atlas-edge-routing-browser/`:

- `light-1440-singleton-depth-1.png` and `light-1440-singleton-depth-2.png`
- `light-900-ha-pair.png` and `light-1440-dns.png`
- `light-1440-dense-depth-3-fit.png`
- `dark-390-dns.png`

The script also captures each main state in both themes at all three widths.

## Limits

Shared and cyclic relationships can still cross in dense graphs; this is not an
obstacle-avoiding routing engine. Curves and selection improve tracing without a
large layout rewrite or hidden context. Fit can reduce text size substantially
on mobile; native zoom/panning and textual details remain the readable access
paths. Browser interaction timings describe local fixture runs, not production
latency or measured frame rates. No live-data manual acceptance was performed.
