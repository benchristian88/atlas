# Asset icon cache: implementation and acceptance record

## Implementation report

- **Branch:** `feature/asset-icon-cache`
- **HEAD:** `99ec8379a0abc3b8ddbfd46087d25ae8455a6fcc`
- **Scope:** secure cached Asset artwork, shared across existing presentation.
  No commit, push or merge; no domain knowledge semantics changed.
- **Existing architecture:** `Asset.icon_url`, `AssetType.default_icon_url`, a
  shared browser-fetching AssetIcon, separate graph EntityMark, scoped Asset
  routes and cookie authentication. No media store or usable worker queue.
  PostgreSQL already has a persistent Docker volume; the worker is a heartbeat.
- **Schema/storage:** additive migration `20260912_0018`, one cache row per Asset,
  bounded PNG bytes and source/content hashes in PostgreSQL. Existing Asset rows
  are untouched. No source-tree files, extra data directory or volume required.
- **Serving/security:** `/api/assets/{asset_id}/icon`, authentication and
  `assets.view` Customer/Site scope, identical inaccessible/missing 404s,
  PNG/nosniff, private ETag revalidation before byte reuse.
- **SSRF:** public HTTPS/443 only; no credentials, proxies or forwarded cookies;
  all DNS answers and the actual TLS peer checked; validated numeric connection
  addresses prevent a second DNS lookup; every redirect checked, maximum three.
- **Formats/limits:** PNG/JPEG/WebP input; 2 MiB download; 2048 px per side and
  four million pixels; metadata-free static PNG output within 256×256 and
  512 KiB. SVG/HTML/XML/unsupported content rejected. Two-second connect/read,
  eight-second response total, ten-second redirect/download budget.
- **Invalidation/backfill:** successful unchanged URLs never refetch. Existing
  Assets populate on first authorized icon request, after the response is sent.
  Source changes permit a new attempt; previous bytes remain internal until
  validated replacement and are not served under the new source. Clear deletes
  cache; Asset delete cascades. Failures/corruption recover lazily with a
  five-minute attempt lease; no TTL/scheduler. Four fetch slots per API process.
- **Frontend:** one source resolver and AssetIcon; fixed boxes, contained images,
  hidden loading/failed image layers and existing generic fallback. Transparent
  images do not reveal the generic placeholder beneath them. List remains
  38 px, detail 58 px, graph/dashboard 32 px. Services, Business Functions,
  dependency markers, graph dimensions and semantics retain existing behavior.
  Type default images retain their previous external HTTPS behavior and CSP is
  unchanged. Browser API-base configuration is respected.
- **API compatibility:** additive icon metadata for Asset DTOs, graph Asset nodes
  and Service Asset dependency DTOs. Source URL and routes remain available;
  `resolved_icon_url` now resolves through the local lookup when configured.
- **Documentation:** README, administrator icon guide, cache architecture,
  authentication/CSP/deployment guidance and feature ledger updated.

## Files changed

Paths below are relative to the repository root.

| Files | Purpose |
| --- | --- |
| `apps/api/app/services/asset_icons.py` | Secure retrieval, normalization, source resolution, integrity checks and atomic leased cache updates. |
| `apps/api/app/models.py`, `apps/api/migrations/versions/20260912_0018_asset_icon_cache.py` | Separate bounded cache table with deletion cascade. |
| `apps/api/app/routes/assets.py` | Scoped icon endpoint, background retrieval and URL-clear cleanup. |
| `apps/api/app/presenters.py`, `apps/api/app/schemas.py`, `apps/api/app/services/operational_graph.py`, `apps/api/app/routes/services.py` | Shared additive icon metadata on authorized existing DTOs. |
| `apps/api/requirements.txt` | Pinned aiohttp and Pillow dependencies. |
| `apps/api/tests/test_asset_icons.py`, `apps/api/tests/test_asset_icons_postgres.py` | Retrieval/security, cache lifecycle, tenancy and concurrency tests. |
| `apps/api/tests/test_administration.py`, `apps/api/tests/test_models.py` | Updated existing resolution/schema expectations. |
| `apps/web/lib/asset-icon.mjs`, `apps/web/components/asset-icon.js`, `apps/web/app/globals.css` | Shared resolution and fixed, themed, failure-safe image rendering. |
| `apps/web/app/assets/page.js`, `apps/web/app/assets/[id]/page.js`, `apps/web/components/asset-form.js` | List/detail integration and safe saved-image form preview/help. |
| `apps/web/components/service-landscape.js`, `apps/web/components/graph-inspector.js`, `apps/web/app/topology/page.js` | Knowledge Graph/dashboard/shared inspector/topology rendering. |
| `apps/web/components/entity-detail.js`, `apps/web/app/services/[id]/page.js` | Consistent Asset relationship card artwork. |
| `apps/web/tests/asset-icon.test.mjs`, `apps/web/scripts/check-asset-icons-browser.mjs` | Source precedence and real browser surface/failure/theme tests. |
| `README.md`, `docs/admin/asset-icons.md`, `docs/architecture/asset-icon-cache.md`, `docs/architecture/authentication-and-access-control.md`, `docs/architecture/deployment-and-upgrades.md`, `docs/product/feature-ledger.md`, `docs/testing/asset-icon-cache.md` | User/admin/technical guidance, truthful implementation ledger and validation record. |

## Executed validation

Backend commands used `apps/api/.venv`; PostgreSQL checks used an isolated
UTF-8 database on a temporary local PostgreSQL 17 instance, not application data.

| Command/check | Result |
| --- | --- |
| Baseline `python -m pytest tests/test_administration.py tests/test_operational_graph.py -q` | 43 passed. |
| Baseline `npm test` in `apps/web` | 123 passed. |
| `python -m pytest tests/test_asset_icons.py -q` | 49 passed. |
| `python -m pytest tests -q` without integration database | 329 passed, 45 skipped for database requirements. |
| `ATLAS_TEST_DATABASE_URL=… python -m pytest tests -q` | 374 passed, no skips. |
| Focused fetcher/administration/graph rerun | 92 passed. |
| PostgreSQL cache tests after final lock-order adjustment | 8 passed. |
| `npm test` | 126 passed. |
| `npm run build` | Production build passed. |
| `alembic upgrade head` on empty PostgreSQL | Entire migration chain passed. |
| `alembic heads` | Single head: `20260912_0018`. |
| `alembic check` | Existing unique-constraint/index drift in `criticality_levels`, `knowledge_requirement_definitions`, `service_types`; no cache-table mismatch. Those unrelated definitions were not changed. |
| Live `fetch_icon` against public python.org PNG | DNS/TLS peer/download/normalization succeeded, 4236 PNG bytes. |
| `node scripts/check-asset-icons-browser.mjs` against production build | 48 checks passed: light/dark cached, failed, corrupt, cleared, missing-type and broken-type behavior across four surfaces; version replacement and no external Asset-source request checked. |
| Changed-document relative Markdown links | Passed. |
| `git diff --check` | Clean. |

The browser script uses API fixtures named AdGuard Home, Nginx Proxy Manager and
PVE1. Backend tests separately exercise the real FastAPI routes and PostgreSQL
cache lifecycle. A live external fetch checks the real transport. This is not a
claim that a user's deployed homelab has been manually modified or verified.
Existing framework deprecation warnings remain.

Run the browser check with `ATLAS_PLAYWRIGHT_MODULE` pointing to Playwright when
it is not installed locally, `ATLAS_CHROME_PATH` for Chrome and
`ATLAS_BROWSER_BASE_URL` for a running production build. Its screenshots default
to `/tmp/atlas-asset-icon-browser` and are not committed.

## Exact manual acceptance checklist

Use a test Customer/Site and authorized operator. Have AdGuard Home, Nginx Proxy
Manager and PVE1 Assets available; retain any existing source URL before editing.
Apply migrations and run the updated API/web first. Use browser Network tools
with **Preserve log**, leaving normal browser caching enabled.

1. **A — Initial caching:** Set AdGuard Home's icon URL to a valid public HTTPS
   PNG/JPEG/WebP and save. Open its detail to trigger retrieval. A normal fallback
   may appear first; reload after retrieval. Verify the image on Asset list,
   Asset detail, Knowledge Graph and dashboard Environment Overview. Confirm
   image requests go to Atlas `/api/assets/{id}/icon`, not the source host.
2. **B — Reuse:** Reload all four surfaces several times. Confirm local 200/304
   image responses, no Asset-source-host requests, stable row/node dimensions,
   no graph relayout and usable rendering while the external host is unavailable.
   Restart the API/container and verify the same cached image remains available.
3. **C — Replacement:** Change to a different valid public HTTPS raster URL.
   Confirm the saved Asset remains usable, the fallback appears while pending,
   and the new artwork appears on all four surfaces after retrieval/reload.
   Verify repeated reloads do not trigger further origin retrieval.
4. **D — Blocked/failing source:** Change to `https://127.0.0.1/icon.png`, then a
   public URL returning invalid content. Confirm safe fallback on all surfaces,
   no stale artwork presented as current, no broken-image glyph, no private
   HTTP request, and no source/query secrets in API logs. The Asset save remains
   successful for syntactically accepted URLs. HTTP/SVG syntax is rejected by
   existing form/API validation; it does not start retrieval.
5. **E — Clear/fallback:** Clear the Asset URL and save. Verify the Asset Type
   default on all surfaces. Test a type without a default (and a broken default)
   and verify the existing generic icon. Restore original configuration if needed.
6. **Consistency:** Repeat using Nginx Proxy Manager and PVE1; inspect light/dark
   mode and narrow screens. Verify contained aspect ratio and fixed dimensions;
   Service/BF semantic icons and dependency markers remain unchanged.
7. **Access:** As a user without this Asset's Customer/Site scope, request its
   icon URL, also with a previously captured ETag. Expect the same 404 body as an
   unknown Asset. Without authentication expect 401; lacking `assets.view`, 403.
8. **Recovery/lifecycle:** In a disposable test database, remove/damage its cache
   row. Reload after the attempt lease permits retry and verify recovery. Archive
   an Asset and verify authorized display still works; delete an eligible Asset
   and verify the icon returns 404 and its cache row is gone.

## Remaining observations

No task-specific implementation blocker remains. Manual acceptance on a deployed
homelab remains an operator checklist. The unrelated pre-existing Alembic index
drift is recorded above, not repaired as part of this feature. General media
uploads, cached type-default images and scheduled refresh remain outside scope.

## Repository state at completion

`git status --short` (all changes remain uncommitted):

```text
 M README.md
 M apps/api/app/models.py
 M apps/api/app/presenters.py
 M apps/api/app/routes/assets.py
 M apps/api/app/routes/services.py
 M apps/api/app/schemas.py
 M apps/api/app/services/operational_graph.py
 M apps/api/requirements.txt
 M apps/api/tests/test_administration.py
 M apps/api/tests/test_models.py
 M apps/web/app/assets/[id]/page.js
 M apps/web/app/assets/page.js
 M apps/web/app/globals.css
 M apps/web/app/services/[id]/page.js
 M apps/web/app/topology/page.js
 M apps/web/components/asset-form.js
 M apps/web/components/asset-icon.js
 M apps/web/components/entity-detail.js
 M apps/web/components/graph-inspector.js
 M apps/web/components/service-landscape.js
 M docs/architecture/authentication-and-access-control.md
 M docs/architecture/deployment-and-upgrades.md
 M docs/product/feature-ledger.md
?? apps/api/app/services/asset_icons.py
?? apps/api/migrations/versions/20260912_0018_asset_icon_cache.py
?? apps/api/tests/test_asset_icons.py
?? apps/api/tests/test_asset_icons_postgres.py
?? apps/web/lib/asset-icon.mjs
?? apps/web/scripts/check-asset-icons-browser.mjs
?? apps/web/tests/asset-icon.test.mjs
?? docs/admin/asset-icons.md
?? docs/architecture/asset-icon-cache.md
?? docs/testing/asset-icon-cache.md
```
