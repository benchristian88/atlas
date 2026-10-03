# Infrastructure Topology presentation identity — completion evidence

Validated on 2026-09-21 using disposable PostgreSQL databases and isolated browser
API fixtures. No live knowledge was changed. No commit, push or merge was made.

## A–F: repository and existing design

- Branch: `feature/infrastructure-topology-v0`.
- HEAD: `97d016f3d82c49126442be077884c8d6319d7104` (unchanged).
- Working tree began clean; all listed changes belong to this task.
- Reused NavigationIcon's inline line icons, AssetIcon's cached Asset → type
  default → generic fallback, CrudScreen, existing layout and status tokens,
  and the `data-theme`/`color-scheme` theme system. The existing workspace
  hexadecimal branding accent remains separate from bounded record identity.
- Final accent keys: `blue`, `green`, `purple`, `orange`, `red`, `teal`, `cyan`,
  `amber`, `slate`, `rose`.
- Final icon keys: `infrastructure`, `server`, `cube`, `database`, `archive`,
  `network`, `switch`, `router`, `shield`, `bridge`, `cloud`, `device`, `home`,
  `application`.

## G–L: schema, migration and administration

Both models now persist non-null `icon_key`/`accent_key` strings. Existing APIs
accept the bounded keys, reject unsupported values and explicit null, and return
the metadata additively. Old callers may omit the fields. PATCH preserves omitted
values. No routes or permission keys changed. The same response schemas feed the
existing authorized topology projection. Category lifecycle protections and
Network customer/site checks remain in the existing routes.

Migration `20260921_0020` follows `20260921_0019`; it adds four columns without
changing existing IDs, names, assignments or Network fields. It applies these
one-time defaults:

| Existing category | Icon / accent |
| --- | --- |
| Compute | server / blue |
| Software, Workload | cube / green |
| Network | network / cyan |
| Storage | database / purple |
| Backup | archive / orange |
| Data | database / teal |
| Other, Uncategorized, unknown/custom categories | infrastructure / slate |

Existing and new Networks default to network/blue, independently of names or
VLAN IDs. New categories default to infrastructure/slate. Downgrade removes only
the presentation fields. Both create/edit screens use the same named icon radio
picker, ten accent choices and preview. List rows repeat the chosen icon tile.

## M–V: topology, themes and accessibility

| Surface | Implemented result |
| --- | --- |
| Overview | Four static Atlas metric identities; configured category tiles/tints and Network identities. Six AssetIcon previews and +N preserved. |
| Platform | Configured heading icons/accents, restrained card borders; children resolve their own category. AssetIcon, IP and containment behavior preserved. |
| Network & VLAN | Configured list/detail identity, visible VLAN/CIDR/member information and independent selected outline. |
| Connectivity Assets | Category tint/border with the existing AssetIcon. No Network-based Asset recolouring. |
| Connectivity Networks | Network icon/accent inside the node, VLAN/CIDR and interface count. |
| Multihoming | AdGuard retains Workload green across Management purple and Apps orange. |
| Membership edges | Network-accent dashed lines, existing readable labels; technical relationships retain their original style/direction. |
| Focus/selection | Heavier neutral focus border, outer selection ring, dashed keyboard focus; independent of blue or any other accent. |
| Light theme | Pale surfaces, coloured icon tiles, normal dark labels, no saturated card backgrounds. |
| Dark theme | Muted tints, readable icon foreground and labels, distinct focus/selection. |

Each accent defines foreground, tile, border, tint and emphasis tokens using
theme-aware CSS. Unit checks cover every palette entry: icon and text contrast
at least 4.5:1, membership emphasis at least 3:1. Browser checks also measure the
computed icon/tile contrast in both themes. Labels, native checked controls,
VLAN/CIDR and recorded status remain visible. Status colours are unchanged.
Unknown historical icons/accents render through safe generic/network/slate
fallbacks. A contract test prevents frontend/backend registry drift.

## W–AC: validation actually executed

| Check | Result |
| --- | --- |
| Baseline focused API tests | 54 passed; 8 PostgreSQL tests initially skipped before provisioning |
| Baseline `npm test` | 139 passed |
| Final focused category/Network API, topology, administration and migration tests | 72 passed, no skips |
| Full API `.venv/bin/pytest -q` with migrated disposable database | 415 passed, 2 skipped; the two empty-database migration tests passed in the focused run |
| `npm test` in `apps/web` | 142 passed |
| `npm run build` in `apps/web` | Passed |
| Empty database `alembic upgrade head` | Passed through all migrations |
| Upgrade from `20260921_0019`, backfills, preservation, downgrade/re-upgrade | Passed against real PostgreSQL |
| Existing legacy-category migration preservation | Passed against real PostgreSQL |
| `.venv/bin/alembic heads` | Single head: `20260921_0020` |
| Existing browser regression suite | Six scenarios passed before extending identity checks |
| Extended browser acceptance | Six scenarios passed: light/dark at 1440, 1100 and 800px |
| `git diff --check` | Passed |

Focused API command (from `apps/api`, with `ATLAS_TEST_DATABASE_URL`,
`ATLAS_TEST_MIGRATION_DATABASE_URL` and `ATLAS_TEST_PRESENTATION_MIGRATION_URL`
pointing to the disposable databases):

```bash
.venv/bin/pytest -q tests/test_presentation.py tests/test_presentation_postgres.py tests/test_presentation_migration_postgres.py tests/test_asset_category_migration_postgres.py tests/test_infrastructure_topology.py tests/test_infrastructure_topology_postgres.py tests/test_administration.py tests/test_crud.py
```

Browser command (from `apps/web`, using the installed temporary Playwright module,
local Chrome and the production build at port 3110):

```bash
node scripts/check-infrastructure-topology-browser.mjs
```

The browser script uses `ATLAS_PLAYWRIGHT_MODULE`, `ATLAS_CHROME_PATH`,
`ATLAS_BROWSER_BASE_URL` and `ATLAS_BROWSER_OUTPUT` for those local paths.
Screenshots are in `/tmp/atlas-identity-browser-results`. Logs are in
`/tmp/atlas-identity-api-focused-final.log`, `/tmp/atlas-identity-api-full.log`,
`/tmp/atlas-identity-web.log`, `/tmp/atlas-identity-browser.log` and
`/tmp/atlas-identity-build.log`. Temporary servers were stopped after validation.

## AD: exact acceptance results

All rows passed in both themes at all three tested widths.

| Acceptance case | Result |
| --- | --- |
| Compute blue/server | Saved via category edit; Overview, heading, filters and PVE1 category accent verified. |
| Workload green/cube | Saved via category edit; summaries, child tiles and AdGuard node verified with AssetIcon retained. |
| Management Network blue | Saved via Network edit; master/detail and Connectivity identity verified. Then reloaded as purple for the multihomed case. |
| IoT Network purple | Saved via edit; master/detail identity and CIDR verified. |
| Apps Network orange | Saved via edit; master/detail and Connectivity identity verified. |
| Infra Network red | Saved via edit; master/detail identity and CIDR verified. |
| Multihomed AdGuard | Green Asset category retained with Management purple and Apps orange; dashed membership accents and ordinary relationship styling verified. |
| Custom Home Automation | Created home/teal, assigned to a new Home Device Asset Type; fixture Asset appeared automatically in Overview, Platform and Connectivity. |
| Custom Network presentation | New form defaults checked; created cloud/rose; list, detail and Connectivity identity verified. |

Browser fixtures verify shared AssetIcon and Asset-specific image URLs using test
raster data, not live vendor artwork. Live-data manual acceptance was not performed.
API writes and tenancy were tested separately against real PostgreSQL. No known
implementation failures remain; dependency deprecation warnings remain unchanged.

## Material files changed

| Files | Purpose |
| --- | --- |
| `apps/api/app/models.py`, `apps/api/app/schemas.py` | Add persisted fields and additive validated contracts. |
| `apps/api/app/presentation.py` | Bounded API key definitions. |
| `apps/api/migrations/versions/20260921_0020_presentation_identity.py` | Add columns, deterministic defaults and downgrade. |
| `apps/api/tests/test_presentation.py` | Valid/invalid keys, defaults, PATCH and registry parity. |
| `apps/api/tests/test_presentation_postgres.py` | Real API lifecycle, metadata projection, membership and scope isolation. |
| `apps/api/tests/test_presentation_migration_postgres.py` | Upgrade/backfill, identity preservation and rollback checks. |
| `apps/api/tests/test_asset_category_migration_postgres.py`, `apps/api/tests/test_models.py` | Update expected head and additive schema columns. |
| `apps/web/lib/presentation-registry.json`, `apps/web/lib/presentation.mjs` | Shared choices and safe resolution. |
| `apps/web/components/presentation-identity.mjs`, `apps/web/components/presentation-picker.js` | Reusable icon tiles, labels, accessible pickers and preview. |
| `apps/web/components/navigation-icon.mjs` | Extend existing SVG library for infrastructure choices. |
| `apps/web/components/crud-screen.js` | Small custom-field renderer hook used by both forms. |
| `apps/web/app/admin/asset-categories/page.js`, `apps/web/app/networks/page.js` | Form metadata and list previews. |
| `apps/web/app/presentation.css`, `apps/web/app/globals.css` | Central light/dark palette and restrained identity/focus styling. |
| `apps/web/lib/infrastructure-topology.mjs`, `apps/web/app/topology/page.js` | Resolve presentation once and apply it throughout the four views. |
| `apps/web/tests/presentation.test.mjs` | Registry/fallback rendering, contrast and multihoming tests. |
| `apps/web/scripts/check-infrastructure-topology-browser.mjs` | Extend browser regression coverage with all requested identity cases. |
| `docs/admin/asset-categories.md`, `docs/admin/networks.md`, `docs/admin/infrastructure-topology.md` | Administrator guidance. |
| `docs/architecture/infrastructure-topology.md` | Contract, migration, ownership and theme architecture. |
| `docs/README.md`, `docs/product/feature-ledger.md` | Documentation discovery and truthful implementation record. |
| `docs/testing/infrastructure-topology-identity.md` | This validation and completion record. |

## C: final repository state

`git status --short`:

```text
 M apps/api/app/models.py
 M apps/api/app/schemas.py
 M apps/api/tests/test_asset_category_migration_postgres.py
 M apps/api/tests/test_models.py
 M apps/web/app/admin/asset-categories/page.js
 M apps/web/app/globals.css
 M apps/web/app/networks/page.js
 M apps/web/app/topology/page.js
 M apps/web/components/crud-screen.js
 M apps/web/components/navigation-icon.mjs
 M apps/web/lib/infrastructure-topology.mjs
 M apps/web/scripts/check-infrastructure-topology-browser.mjs
 M docs/README.md
 M docs/admin/asset-categories.md
 M docs/admin/infrastructure-topology.md
 M docs/architecture/infrastructure-topology.md
 M docs/product/feature-ledger.md
?? apps/api/app/presentation.py
?? apps/api/migrations/versions/20260921_0020_presentation_identity.py
?? apps/api/tests/test_presentation.py
?? apps/api/tests/test_presentation_migration_postgres.py
?? apps/api/tests/test_presentation_postgres.py
?? apps/web/app/presentation.css
?? apps/web/components/presentation-identity.mjs
?? apps/web/components/presentation-picker.js
?? apps/web/lib/presentation-registry.json
?? apps/web/lib/presentation.mjs
?? apps/web/tests/presentation.test.mjs
?? docs/admin/networks.md
?? docs/testing/infrastructure-topology-identity.md
```
