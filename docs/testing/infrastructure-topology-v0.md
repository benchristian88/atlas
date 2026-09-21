# Infrastructure Topology implementation and validation record

Date: 21 September 2026. This records local implementation and isolated validation,
not deployment or acceptance against a live homelab.

## A–C: Repository state

- Branch: `feature/infrastructure-topology-v0`
- HEAD: `45c3eb5d14b6ef2ba211785d7d5361a9143c05d4`
- Starting working tree: clean. No commit, push or merge was performed.
- Final working-tree paths are listed below.

## D–K: Managed Asset Categories

| Item | Result |
| --- | --- |
| D. Existing architecture | AssetType had a nullable indexed free-text category. Assets referenced stable Asset Type keys. |
| E. Hard-coded usages | Old topology hard-coded Asset Type/relationship sets. Current Assets already used dynamic Asset Type counts, with no category selector. Built-in category values were Other, Network, Compute, Software, Data, Storage and Backup; migration/discovery could add Migrated and discovered. |
| F. Schema | AssetCategory has UUID ID, immutable API key, name, description, sort order, active, show_in_topology and standard timestamps. AssetType has a required category FK. |
| G. Migration | Additive `20260921_0019`; exact distinct values preserved, deterministic UUIDs/keys, collisions resolved without merging, blanks fall back. Legacy column retained only as a frozen upgrade snapshot; rollback copies managed names back. Empty chain and representative upgrade/rollback passed. |
| H. Uncategorized | Protected stable fallback, active, hidden by default, available in Filters. Database/API protection prevents deletion and changing its identity/name or deactivating it. |
| I. Asset Type forms | Required managed dropdown; active choices in managed order, current inactive assignment retained. Free-text category writes rejected. |
| J. Assets filter | New managed category selector composes with existing type, search, completeness and pagination filters. |
| K. Reference Data | Add/edit, active checkbox, topology default, counts and conservative delete. Reuses global Asset Type permissions and existing audit/CRUD conventions. |

## L–X: Infrastructure Topology

| Item | Result |
| --- | --- |
| L. Reuse | `/topology` and `/api/topology` retained. Existing collections retained; category/type metadata and platform links added. Asset enrichment batched. |
| M. Overview | Authorized visible Asset/interface counts, Network count and represented categories; dynamic category summaries and recorded Network preview. |
| N. Platform | Category sections with responsive desktop cards, standalone Assets, compact children, search including children beyond the default preview, and navigable cycles. |
| O. Parent semantics | Canonical built-in keys: runs_on/member_of child→parent; hosts/contains/runs parent→child. No category-label or vendor-metadata inference. |
| P. Large parents | First eight compact children; Show all expands 20 without pagination. Four hosts and standalone appliances verified. |
| Q. Network & VLAN | Vertical master/detail, deterministic VLAN/name ordering, recorded purpose/CIDR/gateway/Site and connected interface rows. |
| R. Membership | Only AssetInterface.network_id; multihomed Assets appear in each recorded Network. No subnet or gateway inference. |
| S. Connectivity | Focused Asset/Network graph, canonical relationship labels, distinct interface edges, no Services/Business Functions duplicated. |
| T. Bounds/layout | Backend one/two-hop BFS, cycle-safe and deterministic, 25 nodes requested by UI, 150 edges. Edge clipping retains connection paths. Focus centred with readable fixed-size node text, viewport-fitting height and zoom. |
| U. Inspector | Shared visual conventions, icons, known fields, interfaces and canonical relationships. Open Asset and View in Knowledge Graph links. Selection outside the current neighbourhood becomes a new focus. |
| V. Filters | Dynamic categories; defaults follow show_in_topology, including hidden Uncategorized. Session/view-only choices; no accepted knowledge writes. |
| W. Expansion | Reused single-tree dialog pattern; no browser Fullscreen API. Tab, focus, selection, search, category choices, children and Network selection retained. Button/Escape closing and scroll lock verified; expansion alone causes no new API fetch. |
| X. Icons | Shared AssetIcon in summaries, Platform, Network rows, Connectivity and inspector. Cached Asset → type default → generic precedence retained. |

## Y–Z: Truthfulness and security

No telemetry fields were invented or added. No CPU/memory/disk use, uptime,
throughput, PoE/client counts, backup freshness/success, latency, loss, bandwidth,
temperature or generated health states appear. Provider-specific VM identifiers
and arbitrary vendor facts/metadata are deliberately omitted because this surface
does not assign them a universal canonical meaning or freshness.

Authorization uses existing permissions and Customer/Site context. Both endpoints
must be visible as Assets and relationships; interfaces require a visible Asset
and applicable Network permission. Inaccessible Network IDs are redacted.
Counts, child lists, graph nodes and edges derive only from the resulting visible
records. A hidden/missing focus returns the same 404. No graph or layout state is
persisted, and discovery/reconciliation semantics remain unchanged.

## AA–AF: Commands and results

Run API commands from `apps/api`, web commands from `apps/web`.

| Validation | Executed command / result |
| --- | --- |
| Baseline API | `.venv/bin/pytest -q tests/test_administration.py tests/test_crud.py tests/test_entity_detail_access.py`: **71 passed**. |
| Baseline web | `npm test`: **128 passed**; `npm run build`: **passed**. |
| Full final API with PostgreSQL | `ATLAS_TEST_DATABASE_URL=... .venv/bin/pytest -q`: **399 passed, 1 skipped**. The skipped test requires its own empty migration database and was run separately. Existing deprecation warnings remain. |
| Focused final API | Category/topology unit and PostgreSQL tests: **11 passed**. |
| Empty migration chain | `DATABASE_URL=... .venv/bin/alembic upgrade head`: **passed** on a fresh UTF-8 PostgreSQL database. |
| Representative legacy migration | `ATLAS_TEST_MIGRATION_DATABASE_URL=... .venv/bin/pytest -q tests/test_asset_category_migration_postgres.py`: **1 passed**, including full pre-change chain, exact distinct/blank categories, preservation of Asset/Type IDs, downgrade and re-upgrade. |
| Alembic heads | `.venv/bin/alembic heads`: **20260921_0019 (head)**, one head. |
| Final web | `npm test`: **133 passed**. |
| Production build | `npm run build`: **passed**. |
| Topology browser | `node scripts/check-infrastructure-topology-browser.mjs`: **6 scenarios passed**, light/dark at 1440, 1100 and 800px, using isolated API fixtures and installed Chrome. Also submits category/type forms and verifies inactive current dropdown values and protected delete controls. |
| Existing Knowledge Graph browser | `node scripts/check-expanded-graph-browser.mjs`: **8 scenarios passed**, including desktop/narrow screens, state, focus and scroll behavior. |
| Documentation | Changed/new Markdown local-link check: all targets exist. |
| Whitespace | `git diff --check`: clean. |

The isolated PostgreSQL server used port 55439. Browser preview used localhost
3108. Playwright was installed under `/tmp`, not added to application dependencies.
Screenshot artifacts are under `/tmp/atlas-topology-browser-results`; existing
Knowledge Graph regression images are under `/tmp/atlas-expanded-graph-browser`.

## AG: Exact acceptance coverage

| Requested scenario | Result and evidence type |
| --- | --- |
| Custom Workload / Docker Compose | PostgreSQL API test creates Workload then Docker Compose, resolves the category name/key, rejects missing/null assignment, and exercises reassignment. Browser fixture submits a Docker Compose form with required Workload dropdown; Assets filter resolves it dynamically. |
| Uncategorized | PostgreSQL guards delete/deactivate/rename, verifies required fallback assignment and false default visibility. Browser enables the filter and visible Assets increase from 38 to 39, then returns to 38 when disabled. |
| PVE1 with ~20 children | Browser fixture: eight tiles initially, Show all 20 reveals all, Show fewer restores preview. Search for Workload 19 reveals the otherwise hidden match. |
| Multiple hosts | Browser fixture: PVE1/PVE2/PVE3/PVE4 with 20/4/3/3 children plus PBS, Synology, Switch and Router. Cards wrap with no horizontal page overflow. |
| Six-plus VLANs including VLAN 99 | Browser fixture: 14 Networks including Default, Main, IoT, Apps, Infra and Management VLAN 99. Vertical list, selected detail and multihomed AdGuard interface IPs verified. |
| AdGuard Connectivity | Browser fixture: AdGuard centred, PVE1 reached by recorded runs_on, Apps/Management by eth1/eth0. One/two hops, category pruning, canonical labels, inspector links, icons and expansion verified. PostgreSQL tests separately prove scoped real-record derivation and non-disclosure. |

**Live/manual homelab acceptance was not performed.** No production database,
real infrastructure, user accounts or accepted knowledge were changed. The
fixtures are test evidence, not claimed observations of the user's environment.

## Material files changed

| File | Purpose |
| --- | --- |
| `README.md` | Current navigation, topology workflow and documentation links. |
| `apps/api/app/main.py` | Register category API. |
| `apps/api/app/models.py` | Category model/contracts and explicit topology projection contracts. |
| `apps/api/app/presenters.py` | Batch compatible Asset response enrichment for topology. |
| `apps/api/app/routes/asset_categories.py` | Category lifecycle, managed assignment/filtering or scoped topology API. |
| `apps/api/app/routes/assets.py` | Category lifecycle, managed assignment/filtering or scoped topology API. |
| `apps/api/app/routes/reference_data.py` | Category lifecycle, managed assignment/filtering or scoped topology API. |
| `apps/api/app/routes/topology.py` | Category lifecycle, managed assignment/filtering or scoped topology API. |
| `apps/api/app/schemas.py` | Category model/contracts and explicit topology projection contracts. |
| `apps/api/app/services/discovery_sync.py` | Use managed Uncategorized fallback for newly registered types. |
| `apps/api/app/services/infrastructure_topology.py` | Canonical platform semantics and bounded technical connectivity. |
| `apps/api/migrations/versions/20260921_0019_asset_categories.py` | Additive category migration, backfill and fallback protection. |
| `apps/api/tests/test_administration.py` | Behavioral/schema/navigation regressions and migration/authorization coverage. |
| `apps/api/tests/test_asset_category_migration_postgres.py` | Behavioral/schema/navigation regressions and migration/authorization coverage. |
| `apps/api/tests/test_infrastructure_topology.py` | Behavioral/schema/navigation regressions and migration/authorization coverage. |
| `apps/api/tests/test_infrastructure_topology_postgres.py` | Behavioral/schema/navigation regressions and migration/authorization coverage. |
| `apps/api/tests/test_models.py` | Behavioral/schema/navigation regressions and migration/authorization coverage. |
| `apps/web/app/admin/asset-categories/page.js` | Managed category UI/filter or four-view Infrastructure Topology surface. |
| `apps/web/app/admin/asset-types/page.js` | Managed category UI/filter or four-view Infrastructure Topology surface. |
| `apps/web/app/assets/page.js` | Managed category UI/filter or four-view Infrastructure Topology surface. |
| `apps/web/app/globals.css` | Existing-token desktop grids, network master/detail and connectivity layout. |
| `apps/web/app/topology/page.js` | Managed category UI/filter or four-view Infrastructure Topology surface. |
| `apps/web/components/crud-screen.js` | Optional singular form title for Asset category; other callers retain defaults. |
| `apps/web/components/expanded-graph-surface.js` | Reusable title while retaining existing expansion behavior. |
| `apps/web/components/navigation-icon.mjs` | Distinct topology destination and Asset Categories navigation. |
| `apps/web/lib/asset-list-filters.mjs` | Presentation grouping/layout and composable category filter state. |
| `apps/web/lib/infrastructure-topology.mjs` | Presentation grouping/layout and composable category filter state. |
| `apps/web/lib/navigation-model.mjs` | Distinct topology destination and Asset Categories navigation. |
| `apps/web/lib/system-navigation.mjs` | Distinct topology destination and Asset Categories navigation. |
| `apps/web/scripts/check-infrastructure-topology-browser.mjs` | Isolated production-browser acceptance checks. |
| `apps/web/tests/infrastructure-topology.test.mjs` | Behavioral/schema/navigation regressions and migration/authorization coverage. |
| `apps/web/tests/navigation-model.test.mjs` | Behavioral/schema/navigation regressions and migration/authorization coverage. |
| `apps/web/tests/system-lifecycle.test.mjs` | Behavioral/schema/navigation regressions and migration/authorization coverage. |
| `apps/web/tests/ui-polish.test.mjs` | Behavioral/schema/navigation regressions and migration/authorization coverage. |
| `docs/README.md` | Current navigation, topology workflow and documentation links. |
| `docs/admin/asset-categories.md` | User/admin category and topology guidance; Knowledge Graph distinction. |
| `docs/admin/infrastructure-topology.md` | User/admin category and topology guidance; Knowledge Graph distinction. |
| `docs/admin/knowledge-graph.md` | User/admin category and topology guidance; Knowledge Graph distinction. |
| `docs/architecture/architecture-v0.md` | Managed category schema, projection semantics, compatibility and scoping. |
| `docs/architecture/data-model-v0.md` | Managed category schema, projection semantics, compatibility and scoping. |
| `docs/architecture/homelab-operations-experience.md` | Managed category schema, projection semantics, compatibility and scoping. |
| `docs/architecture/infrastructure-topology.md` | Managed category schema, projection semantics, compatibility and scoping. |
| `docs/architecture/operational-graph.md` | Managed category schema, projection semantics, compatibility and scoping. |
| `docs/product/feature-ledger.md` | Repository implementation evidence and legacy-lens supersession. |
| `docs/testing/infrastructure-topology-v0.md` | Audit, validation evidence, acceptance limits and repository state. |

## Git status

Output of `git status --short`:

```text
 M README.md
 M apps/api/app/main.py
 M apps/api/app/models.py
 M apps/api/app/presenters.py
 M apps/api/app/routes/assets.py
 M apps/api/app/routes/reference_data.py
 M apps/api/app/routes/topology.py
 M apps/api/app/schemas.py
 M apps/api/app/services/discovery_sync.py
 M apps/api/tests/test_administration.py
 M apps/api/tests/test_models.py
 M apps/web/app/admin/asset-types/page.js
 M apps/web/app/assets/page.js
 M apps/web/app/globals.css
 M apps/web/app/topology/page.js
 M apps/web/components/crud-screen.js
 M apps/web/components/expanded-graph-surface.js
 M apps/web/components/navigation-icon.mjs
 M apps/web/lib/asset-list-filters.mjs
 M apps/web/lib/navigation-model.mjs
 M apps/web/lib/system-navigation.mjs
 M apps/web/tests/navigation-model.test.mjs
 M apps/web/tests/system-lifecycle.test.mjs
 M apps/web/tests/ui-polish.test.mjs
 M docs/README.md
 M docs/admin/knowledge-graph.md
 M docs/architecture/architecture-v0.md
 M docs/architecture/data-model-v0.md
 M docs/architecture/homelab-operations-experience.md
 M docs/architecture/operational-graph.md
 M docs/product/feature-ledger.md
?? apps/api/app/routes/asset_categories.py
?? apps/api/app/services/infrastructure_topology.py
?? apps/api/migrations/versions/20260921_0019_asset_categories.py
?? apps/api/tests/test_asset_category_migration_postgres.py
?? apps/api/tests/test_infrastructure_topology.py
?? apps/api/tests/test_infrastructure_topology_postgres.py
?? apps/web/app/admin/asset-categories/
?? apps/web/lib/infrastructure-topology.mjs
?? apps/web/scripts/check-infrastructure-topology-browser.mjs
?? apps/web/tests/infrastructure-topology.test.mjs
?? docs/admin/asset-categories.md
?? docs/admin/infrastructure-topology.md
?? docs/architecture/infrastructure-topology.md
?? docs/testing/infrastructure-topology-v0.md
```
