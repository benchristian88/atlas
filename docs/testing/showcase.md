# Showcase v1 implementation and acceptance

> Historical acceptance record. Layout descriptions and measurements below are
> superseded by [shared Connectivity geometry](showcase-shared-geometry.md).

Historical implementation record. The compact renderer and adaptive poster
correction supersede the fixed geometry and name/Type presentation below; see
[the current correction and validation record](showcase-compact-poster.md).

Validated on 30 September 2026, on `feature/topology-showcase` at base HEAD
`15a696e871558a4241b0098ae45dacbd22ddb24f`. Work is uncommitted; no push or merge.

## Delivered behavior

| Area | Implementation and evidence |
| --- | --- |
| Navigation | Fifth tab at Topology → Showcase on `/topology`, after Connectivity. Browser checks load it from the real production route. |
| Whole current Site | Reuses the existing unpaginated, authorized `/api/topology` result and current workspace headers. No focus or hop query, category visibility filtering, or Connectivity traversal limits. Fixtures represent all 6, 43 and 236 Assets exactly once, explicitly or in counts. |
| API change | Additive `structural_edges` on the existing response, using the existing `ConnectivityEdge` contract. No new endpoint. Backend resolves structural classes, canonical direction, hosting parent and interface membership. |
| Model/database | No persisted concept, schema change or migration. Existing migration chain reaches one head: `20260921_0023`. PostgreSQL remains authoritative. |
| Authorization | Existing permission/context SQL filtering remains authoritative. Both Asset endpoints must be visible, relationship access is independent, hidden Network IDs are redacted. PostgreSQL tests check foreign customers/sites, hidden endpoints, counts and lack of membership/relationship permission. |
| Scene | One 1920×1080 light SVG. Browser width changes only CSS scale; node transforms and network request counts remain identical on resize. No alternate export layout. |
| Header | Current Site name and existing `atlas-impact-lockup-light.svg`; no title override, timestamp, address or operational summary. |
| Cards | Cached/type/fallback icon, Asset name and Asset Type, plus subtle managed Position label. Fixed measured label widths avoid overlaps; accessible titles retain full names. No operational metadata. |
| Positions and hierarchy | Managed names and ordering; physical relationships preserve same-position switch depth. Explicit hosting takes priority, including intermediate hosts. Cycles and extra/shared connections remain represented. |
| Workload categories | Category groups belong to a specific recorded host. Both Platform Host A and B retain their own Media & Photos and Infrastructure groups. Tests verify every grouped member's actual parent. No cluster inference. |
| Endpoints | Type-based local collapse, up to four previews, truthful total and +N. The five-AP fixture displays four previews and +1 with one consolidated connector. Camera and IoT groups behave similarly. |
| Disconnected | Explicit Unconnected / Other presentation without invented edges. Disconnected endpoint Type groups also preserve exact counts. |
| Compaction | Endpoint grouping, workload collapse, other repetitive Automatic leaf collapse, tighter spacing, modest card/scale compaction. Structural parents and named structural positions stay explicit. |
| Readability | Minimum permitted scale .86; 14px secondary text has a 12.04px logical floor. Medium/large fixtures actually use .903353 scale and 12.6469px secondary text. A structurally oversized fixture returns non-exportable Showcase incomplete. |
| Routing | Existing obstacle-aware `orthogonalDetour` reused unchanged. All tested routes are orthogonal and avoid cards. Consolidated edges retain their source relationship IDs in the scene model. |
| Icons | Existing `assetIconSources` hierarchy; successful authenticated cached icon, successful CORS Type fallback and failing optional cached/Type icons exercised. URL deduplication, bounded workers and deadline; embedded resources, with local managed fallback. |
| PNG | Exactly 3840×2160, Site-derived sanitized filename, only the displayed SVG composition. The browser opens each exported PNG for inspection. Export succeeds offline with no network requests. |
| Theme parity | Medium light/dark PNG bytes are identical. Dark Atlas chrome surrounds an unchanged light preview. |
| Preview parity | A browser screenshot of the displayed SVG at 3840×2160 is compared with the export. Mean channel difference: 0.001832 / 255; pixels with significant difference: 0.00146%. Minor rasterization variation only. |
| Compatibility | Existing Platform/Connectivity functions and contracts retain behavior; Platform browser content before and after Showcase is identical. No Showcase category grouping is added to Connectivity. Overview and Network & VLAN remain operational. |
| Controls | Export PNG outside the image. No Focus, hops, search, category/class filter, inspector, fullscreen, drill-down, editing, drag/drop, expansion or regeneration. |

## Commands and results

Commands run from `apps/web` unless stated otherwise. Browser tests use installed
Chrome with `ATLAS_CHROME_PATH` and the existing temporary Playwright installation
via `ATLAS_PLAYWRIGHT_MODULE`. They intercept API calls with generic isolated
fixtures and never write to live Atlas records.

| Command | Result |
| --- | --- |
| `node --test tests/showcase.test.mjs` | 9 passed: complete small/medium/large scenes, deterministic input permutation, host-local counts, node/route geometry, same-position hierarchy, cycles/shared hosts/membership, scoping defence, unsupported states, filenames and operational projection regression. |
| `npm test` | 224 passed, including all existing frontend topology and Connectivity layout tests. |
| `npm run build` | Production build passed. |
| `node scripts/check-showcase-browser.mjs` | 4 scenarios passed: small/light, medium/light, large/light, medium/dark. Includes resize invariance, text bounds, icons/fallback, empty state, offline export, dimensions, filename, pixel comparison and Platform before/after regression. No browser page errors. |
| `node scripts/check-infrastructure-topology-browser.mjs` | 6 existing regression scenarios passed: light/dark at 1440, 1100 and 800px, including Platform, Connectivity, search, classes, same-position layout, disclosure, inspector, fullscreen and reference-data presentation. |
| API: `.venv/bin/pytest -q tests/test_showcase_projection.py tests/test_infrastructure_topology.py tests/test_topology_layers.py tests/test_topology_positions.py tests/test_infrastructure_topology_postgres.py tests/test_topology_layers_postgres.py tests/test_topology_positions_postgres.py` | 55 passed against a disposable PostgreSQL database with `ATLAS_TEST_DATABASE_URL`; includes the additive projection and whole-site results above 100 Assets. |
| API: `.venv/bin/pytest -q tests/test_entity_detail_access.py tests/test_administration.py` | 55 passed. Existing dependency deprecation warnings remain. |
| API: `.venv/bin/alembic upgrade head` and `.venv/bin/alembic heads` | Existing chain applied to the disposable database; single head `20260921_0023`. No new migration. |
| `git diff --check` | Clean. |
| Local Markdown link validation | All relative links in the new Showcase documents and linked topology guides resolve. |

## Browser artifacts

Artifacts are local at `/tmp/atlas-showcase-browser/`:

- `small-light.png`, `medium-light.png`, `large-light.png`: complete app screenshots.
- `small-light-scene.png`, `medium-light-scene.png`, `large-light-scene.png`: composition-only previews.
- `medium-dark.png`: dark application with light composition.
- `*-host-local-category.png`: separate host-local category examples.
- `*-wireless-group.png`: five APs, four previews and +1.
- `*-export.png`: original 3840×2160 PNG exports.
- `*-export-opened.png`: exported PNGs opened in the browser.
- `preview-at-export-resolution.png`: displayed SVG at export pixel dimensions.
- `report.json`: scenario dimensions, error lists and pixel comparison metrics.

The small, medium, large, dark-application, host-local category, AP-group and
exported-PNG artifacts were visually inspected. Initial inspection caught long
labels crowding their text areas; fixed text measurement now passes browser bounds
checks. No scene layout depends on browser width or theme.

## Material files

| File | Purpose |
| --- | --- |
| `apps/api/app/services/infrastructure_topology.py` | Complete structural-edge domain projection; legacy Platform and Connectivity functions unchanged. |
| `apps/api/app/routes/topology.py` | Adds authorized structural edges to the existing result. |
| `apps/api/app/schemas.py` | Additive typed response field. |
| `apps/api/tests/test_showcase_projection.py` | Structural class, parent/direction, completeness and endpoint filtering tests. |
| `apps/api/tests/test_infrastructure_topology_postgres.py` | Scoped structural-edge and >100-Asset completeness assertions. |
| `apps/web/app/topology/page.js` | Showcase tab, current-Site component integration, separate control surface. |
| `apps/web/app/globals.css` | Fixed-aspect preview and external export toolbar. |
| `apps/web/components/showcase.js` | Light SVG scene, text/icons, resource readiness and export interaction. |
| `apps/web/lib/showcase.mjs` | Deterministic forest, local grouping, complete compaction, geometry and filename. |
| `apps/web/lib/showcase-export.mjs` | Resource embedding and same-SVG 4K PNG export. |
| `apps/web/lib/infrastructure-topology.mjs` | Exports the existing orthogonal detour helper without changing it. |
| `apps/web/tests/fixtures/showcase.mjs` | Generic small/medium/large site fixtures. |
| `apps/web/tests/showcase.test.mjs` | Layout, semantics, completeness, geometry and regression coverage. |
| `apps/web/scripts/check-showcase-browser.mjs` | Production-browser and PNG acceptance. |
| `docs/admin/showcase.md` | User guide and supported presentation boundaries. |
| `docs/architecture/showcase.md` | Data contract, grouping, geometry and resource/export design. |
| `docs/admin/infrastructure-topology.md` | Adds Showcase navigation; limits operational filters/Refresh wording to operational tabs. |
| `docs/architecture/infrastructure-topology.md` | Links the separate projection and additive contract. |
| `docs/product/feature-ledger.md` | Records implemented Showcase behavior and operational-view compatibility. |
| `docs/testing/showcase.md` | This completion and validation record. |

## Boundaries

An arbitrarily large collection of independently named infrastructure branches
cannot fit one readable fixed-size poster. Showcase refuses export when its final
complete scene exceeds the explicit readability boundary. This is intentional;
there is no silent truncation. Tests and screenshots use generic data, not the
user's live homelab. No public share hosting or persistent layout is introduced.
