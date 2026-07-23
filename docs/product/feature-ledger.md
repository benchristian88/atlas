# Atlas product feature ledger

Last audited: 23 July 2026  
Repository state: `dev` at `09d2271` (`services foundation`)

## How this ledger was produced

This is an implementation audit, not a transcription of feature requests. The
audit reviewed:

- the primary Codex session transcript and its pasted specifications;
- all 39 commits from `531eb37` through `09d2271`;
- every FastAPI router registered in
  [`main.py`](../../apps/api/app/main.py), the SQLAlchemy model metadata in
  [`models.py`](../../apps/api/app/models.py), and all 13 Alembic revisions;
- every Next.js page, shared web component, and web test;
- API, plugin SDK, and Proxmox tests;
- repository documentation and repository-wide `TODO`, `FIXME`, `later`,
  `future`, `phase 2`, `follow-up`, `out of scope`, and related searches.

A prompt, transcript, document, model field, or commit title is only evidence
that a capability was considered. “Implemented” requires a working code path
and, where the feature stores data, corresponding schema or migration evidence.
Tests are cited where they exercise that path. There were no `TODO` or `FIXME`
comments in application/plugin code at the audit point; unresolved work is
instead documented as roadmap, non-goals, placeholders, compatibility code, or
missing layers.

Statuses have the following meanings:

- **Implemented** — the current repository contains the usable capability
  across the layers it needs. This does not mean production-hardening is
  complete.
- **Partially implemented** — meaningful layers exist, but the stated product
  journey is not end-to-end or an important requested behavior is still absent.
- **Planned but not implemented** — current roadmap/navigation/next-increment
  documentation names the capability, but no usable implementation exists.
- **Deferred** — an explicit MVP/C1 non-goal, “later” item, or intentionally
  postponed extension.
- **Abandoned** — a previous design or surface was deliberately superseded or
  rejected.
- **Unknown** — the repository mentions or structurally anticipates the
  capability, but contains neither an implementation nor a clear current
  commitment/deferral decision.

## Audit validation

The audit finished with these repository checks:

- API: `158 passed` from `pytest -q apps/api/tests`;
- web unit/regression suite: `14 passed` from `npm test`;
- plugin SDK and Proxmox: `27 passed`;
- Next.js 16.2.10 production build: passed, generating 32 static pages and
  successfully compiling the listed dynamic routes;
- Alembic: one head, `20260720_0013`;
- Markdown link targets and `git diff --check`: passed.

These checks validate the checked-in contracts and build. They do not substitute
for a live Docker/PostgreSQL/Proxmox acceptance run, and no such live result is
claimed by this ledger.

## Implemented

### Runtime, deployment, and platform foundation

| Feature | Concrete evidence |
| --- | --- |
| Monorepo runtime scaffold | Compose defines `api`, `web`, `worker`, `postgres`, and `redis` in [`docker-compose.yml`](../../infra/docker/docker-compose.yml). FastAPI exposes `/api/health`, Next.js has a landing/root route, and the worker logs readiness in [`worker/main.py`](../../apps/worker/worker/main.py). The scaffold originated in `531eb37`; the current web image uses a production Next.js start command. |
| PostgreSQL schema and additive upgrades | [`models.py`](../../apps/api/app/models.py) defines the current durable model and [`migrations/versions`](../../apps/api/migrations/versions) contains a linear 13-revision chain from `20260710_0001` to `20260720_0013`. Model/migration invariants are exercised by [`test_models.py`](../../apps/api/tests/test_models.py). |
| Single-origin `/api` deployment | [`main.py`](../../apps/api/app/main.py) mounts all API routers under `/api`; [`api-url.mjs`](../../apps/web/lib/api-url.mjs) defaults the browser to `/api`; Compose defaults `NEXT_PUBLIC_API_URL` to `/api`. [`test_auth.py`](../../apps/api/tests/test_auth.py) checks the namespaced health/docs paths and [`api-url.test.mjs`](../../apps/web/tests/api-url.test.mjs) covers relative and split-origin URL construction. Operator contracts are in [`single-origin.md`](../deployment/single-origin.md) and [`reverse-proxy-examples.md`](../deployment/reverse-proxy-examples.md). |
| Optional split-origin development | Configurable CORS, allowed headers, credentialed requests, and origin checks are in [`main.py`](../../apps/api/app/main.py). Absolute API overrides are tested in [`api-url.test.mjs`](../../apps/web/tests/api-url.test.mjs) and documented in the root [`README`](../../README.md). |
| Upgrade/backfill compatibility | Migration `20260714_0004` backfills default sites, managed type keys, legacy user access, and legacy relationship context without resetting the database. Later revisions add knowledge and Service records additively. The rules and rollback limits are documented in [`deployment-and-upgrades.md`](../architecture/deployment-and-upgrades.md). |

### Authentication, access, and account experience

| Feature | Concrete evidence |
| --- | --- |
| Local email/password authentication | [`auth.py`](../../apps/api/app/auth.py) hashes/verifies passwords and validates signed sessions; [`routes/auth.py`](../../apps/api/app/routes/auth.py) implements login, logout, `/auth/me`, profile, and password change. [`test_auth.py`](../../apps/api/tests/test_auth.py) verifies Argon2 hashing, generic failures, disabled/locked users, session invalidation, and origin checks. |
| HttpOnly cookie sessions | Login writes `atlas_session` as `HttpOnly`/`SameSite=Lax`; the web client uses `credentials: "include"` in [`lib/api.js`](../../apps/web/lib/api.js). [`test_auth.py`](../../apps/api/tests/test_auth.py) checks cookie attributes and absence of an exposed token. |
| Bearer-token API compatibility | [`app/auth.py`](../../apps/api/app/auth.py) accepts either `HTTPBearer` credentials or the session cookie. This remains useful for API clients, although it is no longer the browser session design. |
| One-time administrator bootstrap | [`scripts/seed_admin.py`](../../apps/api/scripts/seed_admin.py) creates only the first forced-password-change global Master Administrator, hashes the password, optionally creates `Home / Homelab`, and treats existing users as a no-op. [`test_seed_admin.py`](../../apps/api/tests/test_seed_admin.py) covers idempotence, validation, hashing, safe errors, and the deprecated environment fallback. |
| Forced password change, profile, and password reset | The authorization layer limits forced-change users, [`profile/page.js`](../../apps/web/app/profile/page.js) provides display-name/password/appearance controls, and [`admin/users/page.js`](../../apps/web/app/admin/users/page.js) supports write-only temporary-password resets. Backend coverage is in [`test_auth.py`](../../apps/api/tests/test_auth.py) and [`test_administration.py`](../../apps/api/tests/test_administration.py). |
| Protected shell and stable session states | [`root-shell.js`](../../apps/web/components/root-shell.js), [`auth-context.js`](../../apps/web/components/auth-context.js), and [`session-state.mjs`](../../apps/web/lib/session-state.mjs) distinguish checking, authenticated, unauthenticated, error, and public states without showing protected content first. [`session-state.test.mjs`](../../apps/web/tests/session-state.test.mjs) covers 401, retry, network/server failures, cleanup, and public login behavior. |
| Scoped RBAC | `Role`, `Permission`, `RolePermission`, and `AccessAssignment` are migrated in `20260714_0004`; central enforcement is in [`authorization.py`](../../apps/api/app/authorization.py) and permission definitions in [`permissions.py`](../../apps/api/app/permissions.py). [`test_crud.py`](../../apps/api/tests/test_crud.py) and [`test_administration.py`](../../apps/api/tests/test_administration.py) verify global/customer/site scope, viewer read-only behavior, ID substitution, privilege boundaries, and last-master protections. |
| Customer/site context selection | [`routes/context.py`](../../apps/api/app/routes/context.py) returns only authorized contexts; [`workspace-context.js`](../../apps/web/components/workspace-context.js) and [`context-selector.js`](../../apps/web/components/context-selector.js) implement selection and revalidation. Scope-filter tests cover lists, totals, topology, and active-context overrides in [`test_crud.py`](../../apps/api/tests/test_crud.py). |
| User, role, assignment, and permission administration | [`routes/users.py`](../../apps/api/app/routes/users.py) and [`routes/roles.py`](../../apps/api/app/routes/roles.py) expose guarded APIs; `/admin/users` and `/admin/roles` provide current UI. Custom-role CRUD and protected built-in behavior are covered by administration tests. |
| User accent preference | Migration `20260717_0005`, `/auth/profile`, [`accent-theme.mjs`](../../apps/web/lib/accent-theme.mjs), and the Profile picker persist and apply a safe per-user color. Backend validation is in [`test_auth.py`](../../apps/api/tests/test_auth.py); preference and contrast behavior are covered by [`accent-preference.test.mjs`](../../apps/web/tests/accent-preference.test.mjs) and [`accent-theme.test.mjs`](../../apps/web/tests/accent-theme.test.mjs). |
| Account menu and initials avatar | [`account-menu.js`](../../apps/web/components/account-menu.js) makes the top-right identity area the profile/logout menu and [`user-avatar.js`](../../apps/web/components/user-avatar.js) provides safe initials/image fallback. [`account-menu.test.mjs`](../../apps/web/tests/account-menu.test.mjs) covers keyboard, responsive, profile, logout, and fallback behavior. |

### Inventory, reference data, and topology

| Feature | Concrete evidence |
| --- | --- |
| Customer and Site persistence/CRUD | Models and migrations establish ownership; [`routes/customers.py`](../../apps/api/app/routes/customers.py) and [`routes/sites.py`](../../apps/api/app/routes/sites.py) implement list/create/get/update/guarded delete. `/customers`, `/sites`, `/admin/customers`, and `/admin/sites` use the real API. Scope and CRUD behavior are covered in [`test_crud.py`](../../apps/api/tests/test_crud.py). |
| Manual Asset CRUD and detail/edit UI | [`routes/assets.py`](../../apps/api/app/routes/assets.py) implements scoped list/summary/create/get/update/delete; `/assets`, `/assets/[id]`, and `/assets/[id]/edit` use PostgreSQL-backed APIs and typed custom values. Manual edits also emit accepted declarations and changes. CRUD and assertion behavior are covered in [`test_crud.py`](../../apps/api/tests/test_crud.py) and [`test_knowledge_foundation.py`](../../apps/api/tests/test_knowledge_foundation.py). |
| Managed Asset Types | `AssetType` is a stable-key reference table created by `20260714_0004`; [`routes/reference_data.py`](../../apps/api/app/routes/reference_data.py) and `/admin/asset-types` implement lifecycle-safe management. Tests cover inactive types, safe deletion, icon resolution, and scoped usage counts in [`test_administration.py`](../../apps/api/tests/test_administration.py). |
| Managed Relationship Types and endpoint applicability | `RelationshipType` plus C1 `RelationshipTypeApplicability` support labels, direction, Asset-type constraints, and typed `asset→asset`, `service→asset`, `service→service`, and `service→business_function` applicability. APIs/UI are in [`reference_data.py`](../../apps/api/app/routes/reference_data.py) and `/admin/relationship-types`; tests are in [`test_administration.py`](../../apps/api/tests/test_administration.py) and [`test_services.py`](../../apps/api/tests/test_services.py). |
| Typed custom enrichment fields | The definition/applicability/option/value tables are migrated in `20260714_0004`; [`services/custom_fields.py`](../../apps/api/app/services/custom_fields.py) and [`routes/custom_fields.py`](../../apps/api/app/routes/custom_fields.py) validate supported data types, options, applicability, and the 10-field limit. `/admin/custom-fields` and the Asset form expose the feature. [`test_administration.py`](../../apps/api/tests/test_administration.py) covers type, precision, option, lifecycle, and limit rules. |
| Asset/type icons and Atlas branding | Safe HTTPS non-SVG icon validation and fallback are implemented in backend presenters and [`asset-icon.js`](../../apps/web/components/asset-icon.js). Committed Atlas SVG/PNG assets and [`atlas-brand.mjs`](../../apps/web/components/atlas-brand.mjs) brand both shell and login. [`test_administration.py`](../../apps/api/tests/test_administration.py) and [`atlas-brand.test.mjs`](../../apps/web/tests/atlas-brand.test.mjs) cover these paths. |
| Networks/VLAN CRUD | `Network` and migration `20260714_0003` store customer/site, type, VLAN, CIDR, gateway, purpose, zone, and notes. [`routes/networks.py`](../../apps/api/app/routes/networks.py) validates addresses and ownership; `/networks` lists, creates, edits, and deletes through the real API. |
| Asset Interfaces | `AssetInterface` and migration `20260714_0003` persist interface name, network, IP, MAC, primary state, and notes. [`routes/asset_interfaces.py`](../../apps/api/app/routes/asset_interfaces.py) implements list/create/update/delete; Asset detail provides add/list/delete UI and topology consumes interfaces. |
| Asset Relationships | [`routes/asset_relationships.py`](../../apps/api/app/routes/asset_relationships.py) implements scoped CRUD, same-context and non-self validation, readable endpoint names, managed-type validation, and legacy edge handling. Asset detail provides add/list/delete UI. Relationship and scope behavior is tested in [`test_crud.py`](../../apps/api/tests/test_crud.py). |
| Topology API and v2 Knowledge Graph lenses | [`routes/topology.py`](../../apps/api/app/routes/topology.py) returns authorized customers, sites, assets, relationships, networks, and interfaces. [`topology/page.js`](../../apps/web/app/topology/page.js) implements Physical, Platform, Network/VLAN, Dependency, and All Relationships lenses, filters, one-hop focus, interface-based network grouping, and stable empty states. Backend scoping is tested in [`test_crud.py`](../../apps/api/tests/test_crud.py); frontend navigation/selector behavior is covered by web tests. |
| Live Dashboard summaries | [`routes/context.py`](../../apps/api/app/routes/context.py) computes scoped inventory, relationship, network, Service, Business Function, and completeness totals. [`dashboard/page.js`](../../apps/web/app/dashboard/page.js) renders live counts, reconciliation state, changes, and feature links with permission-aware errors. |

### Knowledge, discovery simulation, and reconciliation

| Feature | Concrete evidence |
| --- | --- |
| Data Sources and simulated discovery | `DataSource` and the expanded `DiscoveryRun` model were added in `20260719_0006`; [`routes/knowledge.py`](../../apps/api/app/routes/knowledge.py) implements Data Source list/create, run list/detail, and `/discovery/simulate`. `/discovery/simulate` and `/discovery-runs` provide usable UI. Core behavior is covered extensively by [`test_knowledge_foundation.py`](../../apps/api/tests/test_knowledge_foundation.py). |
| Evidence, assertions, and reconciliation | `EvidenceRecord`, `KnowledgeAssertion`, and `ReconciliationItem` are durable tables. The knowledge router exposes assertion and reconciliation list/detail/decision APIs; `/reconciliation` provides stable queues and accept/reject/defer/lifecycle decisions. Tests cover asset/fact/relationship acceptance, rejection, deferral, contradictions, and unresolved endpoints. |
| External identity matching and relationship endpoint resolution | `EntitySourceLink` was added in `20260719_0007`; [`entity_resolution.py`](../../apps/api/app/services/entity_resolution.py), [`simulated_discovery.py`](../../apps/api/app/services/simulated_discovery.py), and [`reconciliation.py`](../../apps/api/app/services/reconciliation.py) perform exact/manual matching and preserve resolution metadata. Regression cases for duplicate avoidance, ambiguity, linking, and relationships are in [`test_knowledge_foundation.py`](../../apps/api/tests/test_knowledge_foundation.py). |
| JSON-safe persisted knowledge metadata | [`utils/json_values.py`](../../apps/api/app/utils/json_values.py) centralizes FastAPI `jsonable_encoder` normalization at assertion, evidence, reconciliation, audit, and change boundaries. Nested UUID/datetime/Enum/Pydantic and rollback regressions are tested in [`test_knowledge_foundation.py`](../../apps/api/tests/test_knowledge_foundation.py). |
| Safe Discovery Run and Assertion lifecycle | Migration `20260719_0008`, [`knowledge_lifecycle.py`](../../apps/api/app/services/knowledge_lifecycle.py), run detail/list UI, and [`assertions-panel.js`](../../apps/web/components/assertions-panel.js) provide archive/restore, dependency-aware deletion, and reasoned retraction without removing accepted operational data. Backend and responsive UI tests are in [`test_knowledge_lifecycle.py`](../../apps/api/tests/test_knowledge_lifecycle.py) and [`knowledge-lifecycle-ui.test.mjs`](../../apps/web/tests/knowledge-lifecycle-ui.test.mjs). |
| Historical assertion read resilience | [`routes/knowledge.py`](../../apps/api/app/routes/knowledge.py) and response schemas tolerate missing optional provenance and structured JSON values. The exact historical `docker01` regression and unaffected other-asset path are in [`test_assertion_list.py`](../../apps/api/tests/test_assertion_list.py). |
| Complete-snapshot coverage and “no longer observed” | `RunObservedEntity`, coverage keys, complete-snapshot state, and `KnowledgeChange` were added in `20260719_0009` and UUID defaults repaired by `20260719_0010`. [`discovery_observations.py`](../../apps/api/app/services/discovery_observations.py) detects absence only against a valid baseline and resolves re-observation. Tests cover complete/partial/failed/different coverage, idempotence, lifecycle decisions, and retired assets. |
| Meaningful Changes timeline and Asset fact history | [`knowledge_changes.py`](../../apps/api/app/services/knowledge_changes.py) records semantic changes; [`routes/changes.py`](../../apps/api/app/routes/changes.py) provides scoped list/summary/Asset fact history; `/changes` and Asset history render compact timelines. [`knowledge-v2-ui.test.mjs`](../../apps/web/tests/knowledge-v2-ui.test.mjs) and knowledge tests cover the path. |
| Source-current versus accepted knowledge | Migration `20260719_0011`, [`predicate_definitions.py`](../../apps/api/app/services/predicate_definitions.py), and [`knowledge_summary.py`](../../apps/api/app/services/knowledge_summary.py) separate latest source observations from canonical accepted assertions and enforce single-valued cardinality. Asset detail defaults to a predicate roll-up while retaining history/raw assertions. Regression tests cover manual declarations, conflicts, unresolved values, supersession, and provenance gaps. |
| Configurable Asset knowledge profiles and completeness | Migration `20260720_0012` adds requirement, gap, and summary tables. [`knowledge_completeness.py`](../../apps/api/app/services/knowledge_completeness.py) evaluates structured database-defined rules, triggers reevaluation, and records stable summaries. `/admin/asset-types/[id]/knowledge-profile`, Asset detail, Asset list, and Dashboard consume it. [`test_knowledge_completeness.py`](../../apps/api/tests/test_knowledge_completeness.py) covers rules, references, lifecycle, idempotence, and evaluator failure isolation. |
| Dedicated Knowledge Gaps workflow | [`routes/knowledge_completeness.py`](../../apps/api/app/routes/knowledge_completeness.py) supports list/summary/defer/exception/reopen/assign/resolve. `/knowledge-gaps` has URL-backed filters, compact cards, permissions, and links; it is separate from reconciliation. [`knowledge-completeness-ui.test.mjs`](../../apps/web/tests/knowledge-completeness-ui.test.mjs), [`knowledge-gap-filters.test.mjs`](../../apps/web/tests/knowledge-gap-filters.test.mjs), and [`reconciliation-navigation.test.mjs`](../../apps/web/tests/reconciliation-navigation.test.mjs) verify the separation and UI. |

### Services and capabilities

| Feature | Concrete evidence |
| --- | --- |
| First-class Service records | Migration `20260720_0013` creates `services`; [`routes/services.py`](../../apps/api/app/routes/services.py) implements scoped list/summary/create/get/update/archive/restore; `/services`, `/services/new`, `/services/[id]`, and `/services/[id]/edit` provide the full current UI. Service validation/routing contracts are tested in [`test_services.py`](../../apps/api/tests/test_services.py) and frontend flows in [`services-ui.test.mjs`](../../apps/web/tests/services-ui.test.mjs). |
| Service Types and Criticality Levels | `service_types` and `criticality_levels` are seeded and managed through [`service_reference_data.py`](../../apps/api/app/routes/service_reference_data.py), `/admin/service-types`, and `/admin/criticality-levels`. Suggested RTO/RPO minutes and criticality-based rules are implemented without overwriting explicit targets. |
| Service recovery and simple ownership fields | Service schema/UI persist purpose, owner/contact/support labels, exact-minute RTO/RPO, backup/recovery notes, runbook URL, documentation URL, lifecycle, and operational state. Validation is in [`schemas.py`](../../apps/api/app/schemas.py); form conversion is tested in [`services-ui.test.mjs`](../../apps/web/tests/services-ui.test.mjs). |
| Temporal Service dependencies | `ServiceAssetDependency`, `ServiceDependency`, and `ServiceBusinessFunction` preserve `valid_from`/`valid_to`. The Services router implements list/create/update/end for all three and records assertions, changes, and completeness reevaluation. Detail UI supports typed Service→Asset, Service→Service, and Service→Business Function links. |
| Lightweight Business Functions | Migration `20260720_0013`, [`routes/business_functions.py`](../../apps/api/app/routes/business_functions.py), `/business-functions`, and `/business-functions/[id]` implement scoped create/list/detail/edit, criticality/owner fields, supporting Services, and affected Assets. |
| Service provenance and completeness | Manual Service fields/links create accepted assertions and meaningful changes. Service requirement APIs/evaluation and `/admin/service-types/[id]/knowledge-profile` extend the existing completeness engine; Service detail and `/knowledge-gaps` surface the results. |
| Focused Service/Business Function graphs | `/services/{id}/graph` and `/business-functions/{id}/graph` return authorized, navigable Service/Asset/Business Function projections; their detail pages render the edges. The bounded graph behavior and intentional non-recursion are documented in [`service-dependencies.md`](../architecture/service-dependencies.md). |

### Plugin and discovery components

| Feature | Concrete evidence |
| --- | --- |
| Vendor-neutral plugin SDK | Protocols for `validate_connection`, `discover`, `normalize`, and `sync`, plus safe data contracts, are in [`plugins/sdk`](../../plugins/sdk). [`test_contracts.py`](../../plugins/sdk/tests/test_contracts.py) verifies structural conformance, credential-safe representation, raw/normalized separation, and trusted sync context. |
| Proxmox API-token connection adapter | [`connection.py`](../../plugins/proxmox/atlas_proxmox/connection.py) and [`client.py`](../../plugins/proxmox/atlas_proxmox/client.py) validate HTTPS endpoints using Proxmox token headers with TLS verification and sanitized failures. [`test_connection.py`](../../plugins/proxmox/tests/test_connection.py) covers success, permissions, timeouts, unsafe URLs, and secret handling. |
| Proxmox discovery and normalization adapter | [`discovery.py`](../../plugins/proxmox/atlas_proxmox/discovery.py) collects nodes, QEMU VMs, LXCs, storage pools, and bridges; [`normalization.py`](../../plugins/proxmox/atlas_proxmox/normalization.py) creates stable vendor-neutral Assets, facts, and relationships. [`test_discovery.py`](../../plugins/proxmox/tests/test_discovery.py) verifies the contract and sanitization. |
| Idempotent core sync component | [`discovery_sync.py`](../../apps/api/app/services/discovery_sync.py) validates integration tenancy, stores raw payloads, upserts Asset/fact/relationship identities, updates `last_seen_at`, and marks missing Assets stale. [`test_discovery_sync.py`](../../apps/api/tests/test_discovery_sync.py) verifies repeat sync, raw retention, staleness, and scope. This component is implemented even though automatic worker dispatch is not. |
| Generated Markdown component | [`markdown_docs.py`](../../apps/api/app/services/markdown_docs.py) renders sanitized deterministic Asset Markdown and core sync upserts `Document` rows. [`test_markdown_docs.py`](../../apps/api/tests/test_markdown_docs.py) covers content, relationship rendering, determinism, and injection resistance. A user-facing document surface is separately classified as partial below. |

### Application shell and UX consolidation

| Feature | Concrete evidence |
| --- | --- |
| Permission-aware product navigation | [`navigation-model.mjs`](../../apps/web/lib/navigation-model.mjs) groups implemented routes under Overview, Knowledge, Operations, Connections, and System and never renders `available: false` roadmap entries. [`navigation-model.test.mjs`](../../apps/web/tests/navigation-model.test.mjs) verifies role visibility, active deep links, roadmap hiding, context, profile access, and logout. |
| Root redirect and authenticated shell | `/` delegates to the session-aware shell and routes authenticated users to their permitted home while `/login` stays public. The global shell supplies context, account identity, and logout to protected pages. Session tests cover loop/error behavior. |
| Changes/Assets/Knowledge Gaps UI polish | Shared filter/timeline components, URL-backed query helpers, Asset Type quick filters, responsive assertions, completeness spacing, and compact Knowledge Gap cards are present in the current pages/components. [`ui-polish.test.mjs`](../../apps/web/tests/ui-polish.test.mjs), [`knowledge-gap-filters.test.mjs`](../../apps/web/tests/knowledge-gap-filters.test.mjs), and lifecycle/account/brand tests cover the requested regressions. |

## Partially implemented

| Feature | Implemented evidence | Missing evidence / reason for classification |
| --- | --- | --- |
| Integration management and Proxmox connection setup | `Integration` is a scoped SQLAlchemy/Alembic table with plugin URL, token ID, secret reference, TLS, and status fields; permissions and navigation exist. The standalone Proxmox validator works. | No Integration router is registered in [`main.py`](../../apps/api/app/main.py), and [`integrations/page.js`](../../apps/web/app/integrations/page.js) imports [`mock-data.js`](../../apps/web/lib/mock-data.js). There is no create/edit/test-connection web journey or credential-reference resolver. |
| End-to-end Proxmox discovery | Plugin discovery/normalization, core persistence, raw payload retention, stale marking, and Markdown generation are independently implemented and tested. | No API/worker path loads an Integration, resolves its secret, invokes `ProxmoxPlugin`, and dispatches `AtlasDiscoverySync`. Current usable discovery is the JSON simulation path, not a configured Proxmox run. |
| Redis-backed worker orchestration | Compose runs Redis and a worker container and passes both database/Redis URLs. | [`worker/main.py`](../../apps/worker/worker/main.py) only logs readiness and sleeps; repository search finds no Redis client, queue producer/consumer, scheduler, retry, cancellation, or job-status implementation. The limitation is explicit in the root README. |
| Generated Documentation product surface | `Document` rows, safe Markdown generation, and discovery-run linkage exist and are tested. | There is no documents router, no document list/detail page, and navigation marks Documentation unavailable. Users cannot browse or edit generated pages through Atlas. |
| Interface-first IP-address UX | Networks/interfaces are durable; Asset detail manages interfaces; topology prefers interface IPs and groups by explicit network. `Asset.ip_address` remains optional for compatibility. | The later polish request said to remove/de-emphasize direct Asset IP in forms/tables, but [`asset-form.js`](../../apps/web/components/asset-form.js) still renders “Primary IP address,” sends `ip_address`, and [`assets/page.js`](../../apps/web/app/assets/page.js) displays `asset.ip_address` before hostname. The migration is therefore incomplete outside topology/detail. |
| Impact analysis | Focused Service and Business Function graphs show directly connected Services/Assets and Business Function affected Assets; the Asset topology Dependency lens offers one-hop focus. | There is no recursive traversal, path scoring, outage simulation, confidence-qualified impact engine, or dedicated `/impact-analysis` route. The navigation entry is unavailable and Service architecture explicitly limits C1 to focused projections. |
| Business Function knowledge lifecycle | Business Functions have durable scope, criticality, Service links, graph projection, and open Service-gap counts. | There are no Business Function assertions, requirement profiles, completeness summaries/gaps, or Business Function change-history page. The generic completeness design anticipated additional entity types, but current evaluators/routes support Assets and Services only. |
| Discovery-run lifecycle state machine | Runs support pending/running/completed/failed/cancelled schema values, archive/restore, safe deletion, complete snapshots, and result history. | There is no start/cancel/retry operational job API because worker dispatch is absent. `cancelled` is a stored allowed state rather than a usable cancellation workflow. |

## Planned but not implemented

These are affirmative roadmap or “recommended next increment” items, not merely
schema extension points.

| Feature | Concrete evidence that it is planned and absent |
| --- | --- |
| People & Teams and structured Service ownership | [`navigation-model.mjs`](../../apps/web/lib/navigation-model.mjs) reserves an unavailable `people-teams` entry; the root README names it as roadmap. [`service-model.md`](../architecture/service-model.md) says current labels should migrate later to Person/Team role assignments. There are no Person, Team, membership, or ownership-assignment models/routes/pages. |
| Full Impact Analysis | Navigation reserves an unavailable `impact-analysis` item, the MVP brief recommends deeper traversal next, and [`service-dependencies.md`](../architecture/service-dependencies.md) calls focused graphs its foundation. There is no route/page/engine beyond the partial projections above. |
| Backup & Recovery workflow | Navigation and README reserve `Backup & Recovery`; Service records already carry RTO/RPO and backup/recovery notes. There is no backup-policy, backup-run, recovery-test, restore, or dedicated workflow model/router/page. |
| Formal Documentation / Knowledge Objects | Navigation reserves `Documentation`; [`service-model.md`](../architecture/service-model.md) explicitly anticipates a future Knowledge Object association for runbooks/documents. Only generated `Document` storage exists; no Knowledge Object model or usable documentation page exists. |
| SSO/OIDC/SAML and MFA | The MVP brief’s recommended next increment names SSO/MFA after worker orchestration. `User.auth_provider`, `external_subject`, and `mfa_enabled` are extension fields, but the only authentication routes implement local passwords and no issuer/callback/enrollment/challenge flow exists. |
| External append-only audit export | The MVP brief recommends external audit export before production hardening and the security architecture describes it as necessary for tamper evidence. Current code only stores read-only application audit rows in PostgreSQL; there is no exporter/sink. |
| Plugin ingestion permissions and worker identity | The current Codex context recommends connecting plugin discovery/ingestion permissions to worker orchestration. Existing permissions cover interactive Integration/discovery operations, but no service identity, queued-job authorization envelope, or plugin-installed permission workflow exists. |
| Deliberate legacy Asset-to-Service association workflow | [`service-model.md`](../architecture/service-model.md) says first-class Services and the managed Asset Type “Service” remain distinct and that automated association/migration comes later. No association/migration assistant exists. |

## Deferred

| Feature | Concrete evidence for deferral and current absence |
| --- | --- |
| Billing or commercial tenancy above an Atlas instance/workspace | Listed under “Non-goals for this MVP” in [`mvp-brief.md`](mvp-brief.md). `Workspace` exists, but there is no billing, subscription, reseller, tenant-switching, or commercial account surface. |
| Recovery codes, forgotten-password email, and per-device session management | Explicitly absent in the security limitations of [`authentication-and-access-control.md`](../architecture/authentication-and-access-control.md). Current auth has password change/admin reset and a per-user session generation only; no mailer, recovery token, recovery-code, or device-session table/routes exist. |
| Break-glass account recovery command | [`deployment-and-upgrades.md`](../architecture/deployment-and-upgrades.md) explicitly says it does not yet exist and recommends backups/two Master Administrators. The bootstrap command refuses to reset an existing user. |
| Arbitrary per-record policy and delegated role administration | Explicit MVP non-goals in [`mvp-brief.md`](mvp-brief.md). Authorization supports global/customer/site assignments; there is no record ACL/policy expression or delegated role-management scope. |
| Customer-specific Asset/Relationship Types and Custom Field definitions | Explicitly “deliberately deferred” in [`authentication-and-access-control.md`](../architecture/authentication-and-access-control.md). Current reference definitions are global and have no `customer_id`. |
| New cross-site or cross-customer relationships | Explicit MVP non-goal and enforced rejection. [`test_crud.py`](../../apps/api/tests/test_crud.py) proves new cross-context edges fail; only flagged migrated legacy rows remain readable when both endpoints are authorized. |
| Uploaded icon/media library and server-side icon proxy | Explicit MVP non-goals. Current schema stores HTTPS metadata only, rejects remote SVG, and intentionally performs no server fetch; there is no blob/media table or upload/proxy route. |
| Runtime/customer-specific branding | The branding specification explicitly excluded configurable customer branding/file uploads. Current assets are committed at build time and changing them requires a rebuild; there is no branding settings model/UI. |
| User avatar/photo upload | The account-menu work explicitly prepared `UserAvatar` for a later backend field but excluded upload. `User`/response schemas have no avatar column and no media endpoint exists. |
| Additional discovery plugins | The MVP brief defers plugins beyond Proxmox. `DataSource.source_type` reserves PBS, Docker, UniFi, NetBox, imported-file, and inference labels, but there are no corresponding plugin packages or operational adapters. |
| Full production scheduler/queue control plane | Explicit MVP non-goal. The worker/Redis boundary is partial, with no schedule, queue administration, concurrency control, retry policy, or production job controls. |
| Bulk reconciliation acceptance | The Knowledge Foundation v2 specification explicitly excluded bulk accept. Current reconciliation decisions are per item; no bulk endpoint/UI exists. |
| Automatic rollback of accepted discovery changes | The discovery lifecycle specification defers this to a separate reconciliation/reversal workflow. Current run deletion intentionally never reverses operational Assets or relationships. |
| Automatically deleting Assets absent from discovery | Explicitly rejected by [`codex-system-instructions.md`](../prompts/codex-system-instructions.md), the MVP brief, and discovery code. Current implementations either create a reviewable `not_observed` episode or mark plugin-synced Assets stale. |
| Arbitrary executable completeness expressions | Explicitly excluded from Knowledge Completeness v1. Current requirement rules are a bounded structured vocabulary validated in [`knowledge_requirement_references.py`](../../apps/api/app/services/knowledge_requirement_references.py). |
| Asset ownership editor/`owner_exists` completeness rule | [`knowledge-completeness.md`](../architecture/knowledge-completeness.md) states `owner_exists` is deliberately disabled until an ownership model exists. Assets have no Person/Team owner relation or ownership editor. |
| Enterprise Business Function/process hierarchy | [`service-dependencies.md`](../architecture/service-dependencies.md) says Business Function is not a process hierarchy, portfolio, organization, or enterprise capability taxonomy. Current model is intentionally a flat lightweight capability. |
| SLO/SLA, incident, catalog, on-call, escalation, and ITSM workflows | Explicitly outside C1 in [`service-model.md`](../architecture/service-model.md) and later-release work in [`mvp-brief.md`](mvp-brief.md). No corresponding models, migrations, routers, pages, or tests exist. |
| AI-generated remediation | Explicit MVP non-goal in [`mvp-brief.md`](mvp-brief.md). Knowledge Gaps use administrator-authored remediation hints; there is no model call or AI service. |
| Deep global graph traversal/path scoring/outage simulation | Explicitly excluded from C1 in [`service-dependencies.md`](../architecture/service-dependencies.md). Current graphs are bounded focused projections and Asset topology is a client-rendered lens. |
| Automatic conversion of legacy “Service” Assets | C1 explicitly retains the managed Asset Type and forbids silent conversion/duplicate creation. No migration changes those Assets; operators create and link first-class Services deliberately. |

## Abandoned or superseded

| Superseded feature/design | Concrete evidence |
| --- | --- |
| Browser `localStorage` bearer-token sessions | Commit `ed4858d` introduced the bearer flow, but `c9141ba` replaced the browser design with HttpOnly cookies. [`auth-token.js`](../../apps/web/lib/auth-token.js) only deletes legacy `atlas_access_token`; current docs/tests require that no live token is stored in browser storage. Bearer API compatibility remains, but the browser session feature is abandoned. |
| Split-origin as the default production architecture | The early scaffold used independent browser/API origins. Commit `09a71a4` moved every route to `/api`; current Compose/web defaults and deployment docs define a single origin. Absolute split-origin remains an explicit development compatibility mode, not the product default. |
| “Missing Knowledge” as a Reconciliation queue | Commit `078ba9d` moved it to the dedicated `/knowledge-gaps` route. [`reconciliation-queues.mjs`](../../apps/web/lib/reconciliation-queues.mjs) intentionally contains no Knowledge Gaps queue and its test asserts that separation. |
| Old generic Hierarchy/Relationships topology tabs | Commit `8324d18` replaced the earlier generic view with Physical, Platform, Network/VLAN, Dependency, and All Relationships lenses. No independent hierarchy tab remains in [`topology/page.js`](../../apps/web/app/topology/page.js). |
| Standalone Profile sidebar navigation | Commit `7f568cb` made the top-right account menu primary and removed Profile from [`navigation-model.mjs`](../../apps/web/lib/navigation-model.mjs). `/profile` remains a valid destination through “My profile”; only the standalone navigation placement was superseded. |
| Visible “coming soon”/placeholder roadmap links | The future-facing navigation request explicitly rejected broken placeholders. `available: false` entries remain representable in the model but [`visibleNavigationGroups`](../../apps/web/lib/navigation-model.mjs) filters them out, verified by `navigation-model.test.mjs`. |
| Role-name-only authorization and browser-only route protection | Current backend checks stable permission keys and database assignments in [`authorization.py`](../../apps/api/app/authorization.py); navigation is explicitly only a usability filter. Earlier simpler protection designs no longer define access. |
| Recurring environment-backed admin seed/reset | Current bootstrap exits when any user exists and deprecated `ATLAS_ADMIN_*` names are only an empty-table compatibility fallback. Environment values are not a recurring user creation or password reset feature. |
| Treating every knowledge gap as a reconciliation item | Knowledge Completeness deliberately introduced separate `KnowledgeGap` records and `/knowledge-gaps`. The architecture and tests assert that absence/insufficiency is not duplicated into `ReconciliationItem`. |
| Hard-coded fixed Asset/Relationship enums as the authoritative taxonomy | Migration `20260714_0004` made both taxonomies database-managed stable-key records. Seed lists and UI helpers remain defaults/compatibility aids, but administrators can manage records and the database foreign keys are authoritative. |

## Unknown

These items are mentioned or implied, but the repository does not record a
clear product decision.

| Feature | Why status is unknown |
| --- | --- |
| Favicon/application icon refresh | The branding request made this conditional and allowed it as a follow-up. The repository has Atlas wordmark PNG/SVG assets and layout metadata, but no committed Next.js favicon/app icon, no favicon test, and no roadmap/non-goal entry deciding whether it should be added. |
| Integration secret-store implementation | `Integration.secret_reference` implies an external or indirect secret source and the architecture requires secret hygiene, but there is no resolver/provider interface, supported secret-store documentation, API, or migration describing where references point. The intended storage backend is not decided in current repository evidence. |
| Discovery-run cancellation UX | `DiscoveryRun.status` permits `cancelled`, but no cancel endpoint/page/action/test exists. Documentation does not say whether cancellation is a committed worker feature, deferred, or merely a reserved state. |
| Safe CIDR-based network membership suggestions | The Networks/VLAN request allowed a non-destructive suggestion when an Asset IP matched exactly one same-context CIDR. Current topology uses explicit `AssetInterface.network_id` and does not infer membership; no document records whether suggestion UI is still desired. |
| Second-hop topology focus | The topology request made second-hop display optional. Current focus mode shows the selected Asset plus direct neighbors. There is no documented decision whether configurable depth will be added with impact analysis or intentionally omitted. |

## Evidence map and maintenance rules

The principal implementation commits are:

- `531eb37` — scaffold, initial schema, SDK, Proxmox components, sync, Markdown;
- `352058a`–`8324d18` — manual inventory, Networks/Interfaces, topology;
- `c9141ba` — current authentication/RBAC/context/administration foundation;
- `09a71a4`–`214a7e1` — single-origin API and stable session shell;
- `25f302e`–`b052da4` — accent, branding, and future-facing navigation;
- `6d3acb6`–`49a1f4f` — knowledge foundation, reconciliation, lifecycle,
  coverage, changes, and assertion roll-up;
- `3ffbf0b`–`6cc1a0b` — completeness, Knowledge Gaps, and UI refinement;
- `09d2271` — first-class Services, Business Functions, typed dependencies,
  Service completeness, and focused graphs.

When updating this ledger:

1. Do not move an item to **Implemented** based only on a prompt, type hint,
   schema placeholder, mock page, or roadmap link.
2. For a durable feature, require a migration/model plus a reachable service or
   route; for an interactive feature, also require a usable current page.
3. Keep separately implemented components and incomplete end-to-end journeys
   separate, as with the Proxmox adapter versus operational worker discovery.
4. Record superseded behavior under **Abandoned** instead of silently deleting
   its history.
5. Move an **Unknown** item only when code or an explicit product decision
   resolves it.
