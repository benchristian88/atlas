# Atlas Codex context

Current planning phase: Release C2.1 is next and is not yet implemented.

Read before C2 work:

- [`../product/development-roadmap.md`](../product/development-roadmap.md)
- [`../product/release-c2-plan.md`](../product/release-c2-plan.md)
- [`../architecture/operational-graph.md`](../architecture/operational-graph.md)
- [`../decisions/0001-shared-operational-graph.md`](../decisions/0001-shared-operational-graph.md)
- [`../testing/release-c2-operational-graph.md`](../testing/release-c2-operational-graph.md)
- [`c2-1-shared-operational-graph-codex-prompt.md`](c2-1-shared-operational-graph-codex-prompt.md)

## Product and repository

Atlas is an infrastructure knowledge, documentation, topology, and Service
operations platform for homelabs, internal IT teams, and MSPs. Preserve the
existing FastAPI, SQLAlchemy/Alembic, Next.js, PostgreSQL, Redis, worker, and
plugin-SDK architecture when extending it.

```text
apps/api       FastAPI API, SQLAlchemy models, Alembic migrations, pytest
apps/web       Next.js App Router UI and Node tests
apps/worker    Background worker boundary
plugins/sdk    Vendor-neutral discovery contracts
plugins/proxmox
infra/docker   Compose development/reference deployment
docs           Product, architecture, ADR, testing, and operator guidance
```

The normal workflow is local editing, commit/push, pulling on the Docker host,
then rebuilding with Compose. Do not replace working project conventions to
introduce a preferred framework.

## Implementation source of truth

[`../product/feature-ledger.md`](../product/feature-ledger.md) is the audited
implementation record at the commit named in that document. The roadmap and this
context describe planned work but do not prove it exists.

Before coding, check the current branch, commit, migration head, routes, models,
tests, and ledger audit point. Do not assume a past test count or commit remains
current.

The current ledger audit baseline is `dev` at `09d2271`, audited on 23 July
2026. Confirm whether the working branch is still at that baseline or contains
later changes. Treat later repository code as authoritative and report material
differences before implementation.

## Implemented foundation through C1

The current foundation includes:

- database-backed local users, password hashes, active/lock/forced-change state,
  profile editing, and password change/reset boundaries;
- expiring signed sessions in an `HttpOnly`, `SameSite=Lax` cookie;
- logout/password-change invalidation through `users.session_version`;
- explicit permissions, protected built-in roles, and global/customer/site role
  assignments;
- central FastAPI policy helpers and backend scope filters for inventory,
  topology, selectors, counts, Services, focused graphs, and administration;
- an active customer/site selector that is a preference, not proof of access;
- Customers, Sites, Assets, interfaces, Networks, and Asset relationships;
- managed Asset/Relationship Types, endpoint applicability, lifecycle controls,
  and typed custom fields;
- safe HTTPS icon URL metadata and fallback behavior;
- permission-gated read-only security/administration audit history;
- data sources, discovery simulation, evidence, assertions, reconciliation,
  entity-source links, complete-snapshot absence handling, and meaningful
  Knowledge Changes;
- configurable completeness requirements, current summaries, and Knowledge Gap
  lifecycle for Assets and Services;
- first-class Services, Service Types, Criticality Levels, recovery fields,
  temporal Service-to-Asset and Service-to-Service dependencies;
- lightweight Business Functions and temporal Service links;
- focused Service and Business Function graph endpoints;
- vendor-neutral plugin contracts and a Proxmox adapter;
- idempotent core discovery sync and generated Markdown storage; and
- a worker/Redis boundary that is not yet a complete production job system.

## Security and ownership invariants

Atlas ownership is:

```text
Instance / workspace
└── Customer
    ├── Site -> Assets, interfaces, Networks, and Asset relationships
    ├── Services -> customer-wide or Site-scoped
    └── Business Functions -> customer-wide or Site-scoped
```

Every interactive route must authenticate. Apart from documented
authentication/profile operations and the slim read-only `/api/context` selector,
application routes must:

1. enforce forced-password-change state;
2. require an explicit permission;
3. constrain the query or mutation to an authorized assignment;
4. validate object and relationship endpoint ownership; and
5. avoid revealing inaccessible IDs, labels, counts, totals, paths, or errors.

Never rely on navigation hiding, active-context headers, URL/query/body IDs, or
browser storage as proof of access.

New Asset relationships require distinct accessible endpoints in the same
customer and site. A migrated legacy cross-context edge is readable only when
both endpoint contexts are accessible and cannot be recreated.

Never return or log passwords, hashes, bootstrap credentials, session values,
cookies, authorization headers, Integration secrets, or full secret-bearing
request bodies. Avoid mass assignment of roles, access scope, identity state,
ownership, stable keys, or system flags.

## Knowledge invariants

Keep these concepts separate:

1. evidence — immutable raw observation;
2. assertions — sourced claims with source-current and accepted states;
3. reconciliation items — human decisions before discovered changes update the
   operational model;
4. accepted operational records — current model used by inventory and graphs;
5. Knowledge Changes — meaningful product history; and
6. Knowledge Gaps — absent, stale, or insufficient knowledge.

Do not place an unaccepted source-current assertion into the operational graph.
Do not use Audit Events as product change history or Knowledge Changes as a
security audit substitute.

No-op edits should not create duplicate assertions or changes. Temporal Service
links are ended, not deleted.

## C1 Service invariants

- A Service is an operational capability; an Asset is a technical implementation
  or dependency.
- The legacy managed Asset Type named Service remains distinct from the
  first-class Service model.
- Do not auto-convert or duplicate legacy Service-type Assets.
- C1 plain-text owner/contact/support fields remain valid until C3 deliberately
  adds structured ownership.
- `runbook_url` and `documentation_url` remain valid until C4 deliberately adds
  formal Knowledge Objects.
- RTO and RPO are objectives in exact minutes. They are not restoration
  estimates or proof of recoverability.
- Legitimate cycles between different Services are allowed.
- Current focused graph endpoints are structural projections, not impact
  analysis.

## Release C2.1 objective

Implement one shared API-owned operational graph projection over accepted
operational records.

C2.1 should:

- use namespaced node keys such as `asset:<uuid>` and `service:<uuid>`;
- use namespaced edge keys by source table/family;
- preserve semantic source/target direction;
- return API-provided Relationship Type labels;
- support authorized Asset, Service, and Business Function focus;
- apply current and optional `as_of` temporal rules where the source model
  supports them;
- be cycle-safe, deterministic, bounded, and explicit about truncation;
- batch-load metadata to avoid obvious N+1 queries;
- preserve existing Service and Business Function graph contracts through
  adapters; and
- add API, IDOR, temporal, compatibility, performance, and web tests.

C2.1 must not:

- introduce a graph database or graph persistence table;
- mutate accepted operational records for a read graph;
- calculate outage propagation, impact severity, recovery paths, restoration
  estimates, or planned-change safety;
- invent a global confidence percentage;
- add hypothetical scenario state to current Asset or Service records;
- bypass existing permissions with a broad graph permission for convenience;
- redesign every roadmap screen in the same change;
- implement Integration CRUD, secret resolution, worker dispatch, or live
  Proxmox runs;
- add a Documents API or Documents UI;
- remove or redesign legacy `Asset.ip_address` handling;
- automatically or interactively convert legacy Service-type Assets.

## Recommended C2.1 code shape

Follow existing flat application conventions unless the current codebase has
changed:

```text
apps/api/app/services/operational_graph.py
apps/api/app/routes/operational_graph.py
apps/api/app/schemas.py
apps/api/app/main.py
apps/api/tests/test_operational_graph.py
```

Possible web support:

```text
apps/web/lib/operational-graph.mjs
apps/web/components/operational-graph-view.js
apps/web/tests/operational-graph.test.mjs
```

The domain builder must not depend on browser state or become a frontend-only
service. It may accept the authenticated principal/request context and explicit
projection parameters.

## C2.1 compatibility sequence

1. Add graph identity helpers and schemas with tests.
2. Add typed source loaders and the shared builder.
3. Reproduce the current Service graph result through the builder.
4. Refactor `/api/services/{id}/graph` using an adapter.
5. Refactor `/api/business-functions/{id}/graph` using an adapter.
6. Add the generic `/api/operational-graph` route.
7. Add authorization, temporal, cycle, truncation, and query-regression tests.
8. Add shared web utilities only after the API contract is stable.
9. Run all supported tests and builds.
10. Re-audit the feature ledger at the delivered commit.

Do not combine C2.1 with the C2.2 dependency-group migration unless the release
plan is deliberately changed and documented.

## C2.2 and C2.3 boundaries

C2.2 later adds explicit dependency semantics such as:

- all/any/minimum groups;
- quorum or `minimum_available`;
- unavailable/degraded/warning/manual failure effect; and
- completeness gaps for unknown critical semantics.

C2.3 later adds:

- recursive analysis traversal;
- dependency-group evaluation;
- unavailable/degraded/potentially affected/unknown states;
- explanation paths and reason codes;
- confidence qualification; and
- analysis engine/schema versioning.

Do not implement these implicitly in C2.1 UI code.

## Data and migration conventions

Use SQLAlchemy models and Alembic; do not drop/recreate databases for schema
changes. Seed permissions, roles, and protected managed types idempotently
without overwriting administrator customizations.

C2.1 is expected to need no graph persistence migration. If a migration becomes
necessary, explain why, keep it additive, test existing data, and update the
architecture/ADR if the decision changes.

Used/system types, definitions, options, Services, dependencies, assertions,
changes, and gaps must preserve history and restrictive lifecycle behavior.

## Running and testing

Use the commands supported by the repository at the current commit.

```bash
cp .env.example .env
# Set AUTH_SECRET_KEY and, only for an empty users table, all bootstrap values.
docker compose --env-file .env -f infra/docker/docker-compose.yml up -d --build
```

API:

```bash
cd apps/api
pip install -r requirements-dev.txt
pytest
alembic current
alembic heads
```

Web under Node.js 22+:

```bash
cd apps/web
npm install
npm test
npm run build
```

Plugins when relevant:

```bash
python3 -m pytest plugins/sdk
PYTHONPATH=plugins/sdk:plugins/proxmox python3 -m pytest plugins/proxmox/tests
```

Do not claim Docker, migration, build, or test success unless the corresponding
command completed. `docker compose down` preserves named volumes. Never suggest
`docker compose down -v` without an explicit warning that it destroys the
PostgreSQL data volume.

## Current limitations and later work

The repository does not yet provide the complete live Integration/worker
journey, SSO/MFA, external append-only audit retention, structured People/Team
ownership, formal Knowledge Objects, validated backup/recovery, full Impact
Analysis, intended-state simulation, or production/community packaging.

Keep planned navigation entries hidden or clearly unavailable until usable. Do
not turn concept-screen text into hard-coded claims unsupported by current data.
