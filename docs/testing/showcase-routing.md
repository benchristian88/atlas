# Showcase routing correction acceptance

Validated on `feature/topology-showcase`, starting at
`af13ece2bf197c330e4d7c02c769c91090114e29` with a clean working tree.
No commit or push. This correction changes routing only; poster fitting,
placement, managed Positions, categories and collapse policy are unchanged.

## Reproduced failure (A–C)

**A.** The realistic 44-Asset regression records an undirected `connects_to`
relationship in the `physical_network` family from **Task A 02** to
**Media Client**. The source is an Application Asset at managed **Workload**
Position (sort order 50), inside Platform A's Media & Photos category. The
target is a Device Asset at managed **Endpoint / Device** Position (sort order
60), outside a category. Canonical source/target keys remain unchanged.

The placed source is `(472, 283)` with a 112×22 card. Its normal bottom port is
`(472, 302)`. The target is `(336, 414)` with a 124×32 card; its top port is
`(336, 390)`. The normal exit and entry rails both have Y=382.

**B.** Task A 04's six-pixel-padded rectangle is
`[410, 534] × [298, 332]`. The source port lies inside this obstacle. The first
preferred vertical segment also crosses Task A 06's padded rectangle
`[410, 534] × [330, 364]`. All 65 normal X-track candidates retain that blocked
port. Changing the rail cannot fix it; the bounded search cannot leave an
attachment point inside an obstacle either. The cards themselves do not touch:
a 32px member row step leaves 10px between 22px cards, but an attachment 8px
outside the source enters the next card's required clearance.

The smaller fixed-coordinate regression reproduces exactly this blocked-port
condition, independently of placement. Default routing throws; opt-in fallback
succeeds without changing the input nodes, groups or relationship.

**C.** The realistic fixture fails on a neighbouring card, rather than an
impenetrable category perimeter. A separate regression covers a member's fixed
top port inside its own category title. Existing internal routing already permits
entry/exit through an endpoint's container, but cannot repair an attachment
inside its protected title. The fallback selects another clear port and repairs
this case locally. Unrelated containers and all card/title obstacles remain
protected.

The user's failing relationship UUID was supplied without its endpoint records
or full topology payload. These are verified synthetic reproductions of the
shared router failure, not a claim that the user's particular endpoints have
been identified. Non-production diagnostics now expose the necessary endpoint,
Position, membership, port, candidate and blocking-rectangle details for that
record. No user's UUID or name is used in fixture logic.

## Routing correction and safety (D–H)

**D/F.** Showcase explicitly enables `allowExteriorFallback`. Default
Connectivity routing remains unchanged, as do ordinary successful Showcase
routes. The option activates only after the existing preferred path, rail
candidates and bounded searches fail. Routing failures retain their own internal
reason and a routing-specific message, rather than claiming the poster is too
large. Detailed diagnostics are hidden from normal production UI.

**E.** Select clear existing card-side attachment candidates, or an existing
shared category connector boundary. For a port blocked by its own category
title, first search for a local repair. Otherwise compare exterior gutters to
the left, right, top and bottom of the occupied node/group bounds. Gutters sit
at least 16px beyond those bounds, including card clearance. Straight access
legs are preferred when clear; the existing bounded orthogonal search supplies
blocked access legs. Its fallback-only option adds already-padded obstacle
boundary tracks to find narrow safe corridors omitted by the default offset
grid. Choose the shortest valid candidate by Manhattan length with stable
point-sequence tie-breaking. No node or category is moved.

**G.** Every rendered segment is checked against six-pixel-inflated card
rectangles, category titles and unrelated category containers. Only the source
and target's own presentation containers may be entered/exited. Relationship
lines can cross or share tracks. Canonical endpoints/direction, group member
identities and every relationship identity remain represented. A test with an
endpoint completely buried inside an unrelated card still throws safely: the
router never solves impossible geometry by drawing through a card.

**H.** The existing `topologyBounds` receives the returned fallback routes
before fitting. Tests verify the bounds include the extended path. The existing
translation, scale, SVG viewBox and PNG export include that complete geometry.
No additional layout calculation or poster-sizing rule was introduced.

## Measured acceptance (I/J)

| Fixture | Assets / visible | Roots / components | Natural routed bounds | Logical poster | Scale | Exterior fallbacks | Collapse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Forced exterior | 10 / 10 | 1 / 1 | 420×404 | 1920×1080 | 1 | 3 | None |
| Dense host/workload categories | 39 / 39 | 1 / 1 | 1190×436 | 1920×1080 | 1 | 5 | None |
| Realistic difficult 44-Asset topology | 44 / 44 | 1 / 1 | 1776×494 | 1920×1080 | 1 | 3 | None |

All three layouts are complete. Default routing fails on their identical placed
compact geometry; Showcase's opt-in succeeds. Tests check unchanged input data,
canonical identities, complete relationship coverage, obstacle clearance,
route-inclusive bounds and deterministic output under reversed input order.
The 44-Asset fixture retains three platform hosts, a container host, storage,
backup, access switching, clients, wireless devices and all workloads.

## Compatibility and visual inspection (K/L/O)

**K.** All 29 existing Connectivity layout tests pass unchanged. A direct
comparison with the starting commit also confirms identical default Connectivity
placement, groups, routes and bounds across six fixtures: ordinary medium,
44-Asset reference, 50-Asset real shape, and the three new routing fixtures.
The unchanged topology browser harness passes six light/dark scenarios at
1440, 1100 and 800px, exercising real Python traversal, controls, disclosure,
focus, inspectors and Platform. The subsequent fallback-only boundary-track
addition is covered by the final tests and the default-output comparison.

**L.** Platform content before/after opening Showcase is identical in all 16
successful Showcase browser scenarios. Platform implementation and inputs were
not changed. Its separate topology browser regressions also pass.

**O.** Visually inspected the final production screenshots:

- `/tmp/atlas-routing-browser/reference-light-scene.png`: ordinary routing.
- `/tmp/atlas-routing-browser/exterior-light-scene.png`: forced outer gutters.
- `/tmp/atlas-routing-browser/dense-routing-light-scene.png`: dense categories.
- `/tmp/atlas-routing-browser/live-routing-light-scene.png`: all 44 Assets.

The fallback leaves cards clear, uses nearby gutters and retains readable
connections and existing placements. The difficult secondary relationships
share some tracks; no large poster-wide detour is required. Rendered SVG paths
match the calculated routes. All three new scenes export at 3840×2160, with
preview/export mean RGB-channel differences below .000086 on a 0–255 scale.
The strongly changed pixel fraction is about .000000121 in each. Browser checks
also retain responsive transforms, offline export, full accessible names,
Networks-off eligibility and absence of collapse or production diagnostics.

## Executed validation (M/N/P)

| Command/check | Result |
| --- | --- |
| `node --test apps/web/tests/showcase-routing.test.mjs apps/web/tests/showcase.test.mjs apps/web/tests/connectivity-layout.test.mjs apps/web/tests/infrastructure-topology.test.mjs` | 77 passed: 8 new routing, 28 Showcase, 29 Connectivity, 12 infrastructure topology. |
| `npm test` in `apps/web` | 251 passed. |
| `.venv/bin/python -m pytest tests/test_infrastructure_topology.py tests/test_topology_layers.py -q` in `apps/api` | 23 passed. |
| `npm run build` in `apps/web` | Production build passed; 38 pages generated. |
| `node scripts/check-showcase-browser.mjs` in `apps/web` | 16 complete scenes plus unsupported and empty cases passed in production Chrome. |
| `node scripts/check-infrastructure-topology-browser.mjs` in `apps/web` | Six light/dark responsive topology scenarios passed. |
| Starting-commit default Connectivity output comparison | Identical geometry/groups/routes/bounds across six fixtures. |
| `.venv/bin/alembic heads` in `apps/api` | Existing single head `20260921_0023`; no migrations. |
| Relative links in affected documentation | Verified against existing files. |
| `git diff --check` | Clean. |

Browser checks used the local production server at `http://127.0.0.1:3110`,
local Chrome, temporary cached Playwright tools and isolated authorized fixtures.
Artifacts include `/tmp/atlas-routing-browser/report.json`, scene screenshots,
PNG exports and exact-export-resolution preview captures. Logs are
`/tmp/atlas-routing-{focused,full-tests,build,backend,browser,topology}.log`.
No live Atlas knowledge was changed.

## Files and repository state (Q)

| File | Purpose |
| --- | --- |
| `apps/web/lib/topology-geometry.mjs` | Opt-in safe fallback, bounded boundary tracks and structured failure diagnostics. |
| `apps/web/lib/showcase.mjs` | Enable fallback, propagate diagnostics and distinguish routing/size failures. |
| `apps/web/components/showcase.js` | Restrict the temporary diagnostic panel to non-production and show routing detail. |
| `apps/web/tests/fixtures/showcase.mjs` | Forced, dense and realistic recorded-relationship fixtures. |
| `apps/web/tests/showcase-routing.test.mjs` | Blocked ports, group titles, corridor search, safety, identities, bounds and acceptance regressions. |
| `apps/web/scripts/check-showcase-browser.mjs` | Screenshot, full visibility, route parity, production diagnostics and export checks. |
| `docs/architecture/showcase.md` | Routing option, algorithm, safety and diagnostic contracts. |
| `docs/admin/showcase.md` | Operator guidance on difficult routes and distinct failures. |
| `docs/product/feature-ledger.md` | Current implementation and acceptance evidence. |
| `docs/testing/showcase-adaptive-width.md` | Preserve the prior report and link the routing correction. |
| `docs/testing/showcase-routing.md` | This acceptance record. |

No database/schema, backend, API, authorization or customer/site boundary
changes. Whole-site data, Networks-off semantics, icon/name cards, category
rules, managed Positions, host ownership, dimensions, scale floor and collapse
behavior are preserved. Existing overlapping geometry described in the prior
width report remains outside this routing task. The user's live payload still
requires live acceptance; synthetic 44-Asset acceptance is complete.

No commit or push. Final `git status --short`:

```text
 M apps/web/components/showcase.js
 M apps/web/lib/showcase.mjs
 M apps/web/lib/topology-geometry.mjs
 M apps/web/scripts/check-showcase-browser.mjs
 M apps/web/tests/fixtures/showcase.mjs
 M docs/admin/showcase.md
 M docs/architecture/showcase.md
 M docs/product/feature-ledger.md
 M docs/testing/showcase-adaptive-width.md
?? apps/web/tests/showcase-routing.test.mjs
?? docs/testing/showcase-routing.md
```
