# Atlas

Atlas is an infrastructure knowledge, documentation, and topology platform for
homelabs, internal IT teams, and MSPs. It combines a customer/site-scoped asset
and Service inventory with managed dependencies, reference data, enrichment
fields, knowledge completeness, and an auditable administration foundation.

## Repository layout

```text
apps/
  api/                 FastAPI application
  web/                 Next.js application
  worker/              Python background worker placeholder
plugins/
  sdk/                 Vendor-neutral discovery plugin contracts
  proxmox/             Tested Proxmox discovery adapter (not yet wired end-to-end)
infra/
  docker/              Docker Compose configuration
docs/                   Product and architecture documentation
```

## Prerequisites

- Docker with Docker Compose v2

Node.js 22+ and Python 3.12+ are only required if you want to run an individual
service outside Docker.

## Browser and API routing

Atlas defaults to a single browser origin. The web UI uses the relative API
base `/api`; an operator-selected reverse proxy forwards `/api/*` unchanged to
FastAPI and all other paths to Next.js. No public hostname is compiled into
Atlas, and normal production browser traffic does not depend on CORS.
The reference web image runs the Next.js standalone production server, not the
development/HMR server.

See [single-origin deployment](docs/deployment/single-origin.md),
[reverse-proxy examples](docs/deployment/reverse-proxy-examples.md), and the
[split-origin migration guide](docs/deployment/split-origin-migration.md).

## Start the local stack

1. Create your local environment file:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` before starting. Always replace `AUTH_SECRET_KEY` with at least
   32 random characters. For example:

   ```bash
   openssl rand -hex 32
   ```

   On the first start of an empty database, set all three one-time bootstrap
   values:

   ```dotenv
   ATLAS_BOOTSTRAP_ADMIN_EMAIL=admin@example.com
   ATLAS_BOOTSTRAP_ADMIN_PASSWORD=replace-with-a-long-random-password
   ATLAS_BOOTSTRAP_ADMIN_NAME=Atlas Administrator
   ```

   They are optional after an account exists and are never the application's
   permanent login configuration. To use the exposed development ports without
   a reverse proxy, explicitly select split-origin development:

   ```dotenv
   NEXT_PUBLIC_API_URL=http://localhost:8000/api
   CORS_ORIGINS=http://localhost:3000
   ```

   Keep the default `NEXT_PUBLIC_API_URL=/api` for a same-origin reverse-proxy
   deployment. An absolute override is only needed when browser origins are
   intentionally split.

2. Build and start all services:

   ```bash
   docker compose --env-file .env -f infra/docker/docker-compose.yml up --build
   ```

   API startup applies pending Alembic migrations, seeds protected system
   definitions idempotently, and then runs the optional bootstrap check.

3. Open the services:

   - Web: <http://localhost:3000>
   - Login: <http://localhost:3000/login>
   - Direct API health check: <http://localhost:8000/api/health>

The API health endpoint returns `{"status":"ok"}`. The worker logs
`Atlas worker is ready` once it starts.

4. Sign in with the temporary bootstrap credentials, change the password when
   prompted, remove the three `ATLAS_BOOTSTRAP_ADMIN_*` entries from `.env`,
   and restart the API. Leaving a bootstrap password in deployment
   configuration needlessly exposes it to anyone who can inspect the
   environment, even though Atlas will not reuse it.

## Bootstrap the first administrator

Atlas does not expose public registration. The startup command creates one
Master Administrator only when the entire `users` table is empty and all three
valid bootstrap values are present. The password is hashed, the account is
assigned the global Master Administrator role, and the account must change its
password at first login.

On a truly context-free fresh installation, the same bootstrap creates the
starter `Home / Homelab` customer and site. It never adds that sample context
when a customer already exists.

If any user already exists, bootstrap is a no-op: it never creates a second
user, overwrites an account, or resets a password. Supplying only some bootstrap
values, an invalid email, or a password that fails the server policy while the
users table is empty is a configuration error. With no bootstrap values, the API
may start without creating a user; this is useful for an already-initialised
deployment.

To run the same safe check manually:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml exec api \
  python -m scripts.seed_admin
```

Bootstrap messages never contain the password. Bootstrap is not an account
recovery or password-reset mechanism.

For a transition from an older empty installation, the seed command recognizes
deprecated `ATLAS_ADMIN_EMAIL`, `ATLAS_ADMIN_PASSWORD`, and
`ATLAS_ADMIN_DISPLAY_NAME` only when no user exists and the preferred bootstrap
group is absent. It emits a deprecation warning and treats them as the same
one-time bootstrap input, never as live credentials. Replace/remove them
immediately. If a database user exists, even those legacy values are ignored.
The reference Compose file forwards only the new names, so rename legacy keys
in `.env` before a Compose upgrade rather than relying on the fallback.

## Authentication and profile

User accounts and password hashes live in PostgreSQL. Successful login creates
an expiring `HttpOnly`, `SameSite=Lax` session cookie; the web application does
not put an access token in `localStorage` or expose it to JavaScript. Requests
include the cookie and the API remains authoritative for every permission and
scope decision.

The profile menu shows the login email, editable display name, assigned roles,
available customer/site scope, and an Appearance control. Each user can choose
an accent with the colour picker, enter a six-digit hex value, select a preset,
or reset to the Atlas default. The preference is stored on the user account, so
it follows that user across browsers and devices. It changes the primary accent
family and derived sidebar treatment while success, warning, error, and neutral
status colours remain semantic. Derived text and focus colours are selected for
accessible contrast.

Password changes require the current password and a policy-compliant confirmed
replacement. Logout and password changes advance the user's session version,
invalidating previously issued sessions; disabling a user also prevents
authentication. Passwords, hashes,
cookies, and session tokens are excluded from API responses and audit details.

For local HTTP development, `.env.example` sets `AUTH_COOKIE_SECURE=false`.
Production deployments must terminate HTTPS and set it to `true`. Leave
`CORS_ORIGINS` blank for normal same-origin operation; for intentional
split-origin development, restrict it to the exact web origins. Treat
`AUTH_SECRET_KEY` as a production secret; rotating it invalidates all sessions.

## Branding assets

Atlas Impact artwork is organised under `apps/web/public/branding`: full-brand
SVG and PNG artwork lives in `lockups`, while compact artwork lives in `marks`.
The shared brand component uses the supplied light- or dark-background lockup
according to the sidebar treatment and uses the dark-background lockup on the
login screen. SVG is preferred for sharp rendering, with the corresponding PNG
as a fallback and accessible Atlas Impact text as the final fallback.

The browser favicon set, 192px and 512px installed-app icons, and 180px Apple
touch icon are also served from `apps/web/public/branding`. The canonical Web
App Manifest is `apps/web/app/manifest.webmanifest`; application and Apple web
app metadata are declared in `apps/web/app/layout.js`.

Branding assets are included at web-image build time. Runtime replacement,
customer-specific white labelling, uploads, and externally hosted logo URLs are
not supported by the MVP.

## Roles, permissions, and access scope

Roles grant explicit permission keys; separate role assignments say where
those permissions apply. An assignment can be global, customer-scoped, or
site-scoped, and a user can hold different roles at different scopes.

| Built-in role | Intended access |
| --- | --- |
| Master Administrator | Every permission across the instance. The bootstrap account receives this role at global scope. |
| Administrator | Broad administration and operations according to its assignment scope, without the Master-only platform settings implicitly granted. |
| Customer Administrator | Manage assets, relationships, networks, sites, integrations, and applicable metadata inside assigned customers/sites; no access to another customer. |
| Viewer | Read-only inventory, topology, and reference-data access inside assigned scope. |

The built-in roles are protected definitions. Authorization is based on
permission keys such as `assets.edit`, `users.assign_roles`, and `audit.view`,
not on role-name checks alone. Navigation and action buttons use the same
effective permissions for usability, but hiding a control is never the
security boundary. Direct ID, URL, query, and request-body substitutions are
checked by the API and rejected with `403` (or a non-disclosing not-found
response where appropriate).

## Navigation domains

The authenticated sidebar is organised around stable product domains rather
than one link per technical page:

- **Overview:** Dashboard and the meaningful Changes timeline.
- **Knowledge:** Assets, Networks, first-class Services, lightweight Business
  Functions, and Knowledge Graph. Knowledge Graph is the user-facing name for
  the existing `/topology` capability; topology remains a technical lens within
  that graph.
- **Operations:** Discovery run activity and simulation, plus Reconciliation
  for reviewing sourced changes before they enter the operational model.
- **Connections:** Integrations.
- **System:** permission-filtered Users & Access, Reference Data, and an
  Administration landing page linking to available administration sections.
- **Profile:** kept separate because it contains user-specific identity,
  password, access-summary, and appearance preferences.

The configuration reserves the following roadmap positions without rendering
links or placeholder pages:

```text
OVERVIEW       Dashboard; Changes
KNOWLEDGE      Knowledge Graph; Assets; Services; Business Functions;
               People & Teams (roadmap); Networks
OPERATIONS     Discovery; Reconciliation; Impact Analysis (roadmap);
               Backup & Recovery (roadmap); Documentation (roadmap)
CONNECTIONS    Integrations
SYSTEM         Users & Access; Reference Data; Administration
PROFILE        Profile
```

Future usable features should be enabled within these domains rather than
added as arbitrary top-level links.

## Customer and site context

Atlas always models inventory as `Customer -> Site -> assets/relationships`,
including a single homelab (for example, `Home -> Homelab`). An
MSP user can be assigned multiple customers or selected sites. The header
selector contains only authorized customers/sites, filters sites after a
customer selection, and drives inventory, topology, dashboards, and creation
forms. A sole accessible customer/site is selected automatically.

Global users can inspect all authorized records, but creating an asset still
requires a concrete customer and site. New assets inherit the active context.
New relationships require both endpoints in that same customer and site. The
API validates context independently of browser state and rejects stale or
unauthorized selections.

## System administration and managed data

The permission-aware **System** navigation group deep-links into the existing
administration routes and shows only the domains available to the current user:

- Users, roles, permissions, and global/customer/site assignments.
- Customers and sites, including activation/deactivation and guarded deletion.
- Asset and relationship types.
- Custom asset fields and dropdown options.
- A read-only, filterable audit log.
- Protected system settings for global Master Administrators.

User administration accepts write-only temporary passwords and can require a
change at next login; it never reveals an existing password. Atlas rejects a
change that would remove or disable the final usable global Master
Administrator.

Asset and relationship types are managed records with stable keys. Only active
types are offered for new records. An inactive type remains readable on old
records; a referenced type cannot be deleted; and a system-defined type cannot
be deleted even when unused. Deactivation is the safe retirement path.

Custom fields support single-line text, multiline text, number, date, boolean,
absolute HTTP/HTTPS URL, and dropdown values. Definitions can be global or
applicable to selected asset types. The total active fields applicable to any
one asset type is limited to 10, including global fields. Keys remain stable
after use, typed values are validated by the API, and deactivation preserves
existing values.

Asset types can define an HTTPS icon URL and an asset can override it. Atlas
resolves `asset override -> type default -> generic fallback`. Remote SVG URLs
and non-HTTPS URLs are rejected. The API validates and stores the URL but does
not fetch it; the user's browser fetches the image and falls back safely if it
fails.

For example, an operator can configure externally hosted Proxmox, Home
Assistant, or UniFi artwork for a type or specific asset. Atlas does not bundle
third-party copyrighted logos; verify the URL's licensing and availability.

Audit events capture authentication, password, user/assignment, customer/site,
and managed-reference-data changes without storing credentials or tokens. The
application exposes audit records read-only to users with `audit.view`.

The detailed design is documented in
[authentication and access control](docs/architecture/authentication-and-access-control.md)
and the [Mermaid data model](docs/architecture/data-model-v0.md).

The authenticated API surface is canonical beneath `/api` and includes:

- `/api/auth`, `/api/context`, and `/api/dashboard/summary`
- `/api/users`, `/api/roles`, and `/api/permissions`
- `/api/customers`
- `/api/sites`
- `/api/assets`
- `/api/asset-relationships`
- `/api/services`, `/api/service-types`, and `/api/criticality-levels`
- `/api/service-asset-dependencies` and `/api/service-dependencies`
- `/api/business-functions` and `/api/service-business-functions`
- `/api/topology`
- `/api/networks`
- `/api/asset-interfaces`
- `/api/asset-types` and `/api/relationship-types`
- `/api/data-sources`, `/api/discovery-runs`, and `/api/discovery/simulate`
- `/api/assertions`, `/api/reconciliation-items`, and `/api/changes`
- `/api/assets/<id>/fact-history`
- `/api/assets/<id>/knowledge-summary`
- `/api/custom-fields` and asset custom-field values
- read-only `/api/audit-events`
- protected `/api/system-settings`

Collection routes support `GET` and `POST`; resource routes support `GET`,
`PATCH`, and `DELETE` where applicable; audit events intentionally have no
mutation route. The corresponding web screens include
`/customers`, `/sites`, `/assets`, `/assets/<id>`, and `/topology`, together
with profile and permitted administration pages. `/api/manual-assets` remains a
compatibility route for earlier clients and is subject to the same authorization
policy.

## Homelab Services

Release C1 makes an operational **Service** distinct from the technical Assets
that implement it. For example, Authentik can be a Service that provides
identity and access, while `authentik-lxc`, its database, reverse proxy, DNS,
and backup system remain supporting Assets or Services. Typed dependency links,
Business Functions, recovery targets, assertions, Knowledge Changes, and
configuration-driven completeness all use the existing Atlas scope and
provenance foundations.

The managed Asset Type named **Service** is retained for compatibility. It is
not the first-class Service model, and Atlas does not automatically convert or
duplicate existing Application/Service Assets. Create and link operational
Services deliberately.

See the [Service model](docs/architecture/service-model.md),
[dependency model](docs/architecture/service-dependencies.md),
[administrator guide](docs/admin/service-types-and-criticality.md), and
[C1 test plan](docs/testing/homelab-service-mvp.md).

## Current product sequence

**C2.1 — Shared Operational Graph is implemented and merged. C2.2 — Lean
Dependency Semantics and C2.3 — Explainable Dependency Analysis are implemented
with live LXC acceptance complete for their respective scopes.** Atlas's near-term
product target is a polished, secure, publicly usable **Homelab Ready Release**.
C2.4 Homelab Operations Experience is next/planned, followed by F1-lite Homelab
Documentation, B2-lite Live Proxmox Discovery, and contained release hardening.

Manual and curated operational knowledge remains first-class. People/Teams,
formal Knowledge Objects, advanced recovery evidence, richer dependency rules,
full enterprise Impact Analysis, intended-state simulation, production-scale
orchestration, and multiple plugins remain additive later evolution rather than
Homelab Ready prerequisites. Discovery evidence and accepted operational
knowledge remain separate regardless of whether knowledge begins as a manual
declaration, simulation, or future live plugin observation.

See the [development roadmap](docs/product/development-roadmap.md),
[C2 release plan](docs/product/release-c2-plan.md), and
[feature ledger](docs/product/feature-ledger.md).

## Knowledge provenance and reconciliation

Discovery observations do not silently overwrite accepted inventory. Atlas
stores their raw evidence, source-current assertions, accepted assertions, and reviewable
reconciliation items alongside the existing Asset and AssetRelationship tables.
Only accepting a supported reconciliation item creates or updates the
operational model used by topology; reject and defer leave it unchanged.
Durable entity-source links map each data source's external asset ID to exactly
one same-customer/site Atlas asset. Exact normalized name/type matches can be
linked automatically; ambiguous matches require the explicit **Link asset**
action and are never silently merged.

`is_source_current` means “latest valid claim from this source”; `is_accepted`
means “canonical Atlas knowledge.” Single-valued predicates can have only one
accepted value, while interfaces, memberships, relationships, owners, and
dependencies may have several. Manual asset edits create accepted **Declared**
assertions and meaningful history without deleting conflicting observations.

Use **Discovery → Simulate discovery** to exercise this pipeline before a live
integration is configured. Paste a customer/site-scoped JSON observation, run
it, then review the generated items under **Reconciliation**. Asset detail pages
show a rolled-up Knowledge Summary by default, a human history timeline, and
collapsed raw assertion groups linked to an accepted asset.

A simulation can be marked as a **complete snapshot** for a stable coverage
key. Atlas compares only successful complete runs from the same data source,
customer/site, and coverage key. An asset omitted from the next comparable run
becomes a **No longer observed** reconciliation item; it is not deleted or
silently retired. A reviewer can mark it missing or inactive, retire it, keep
it active, or create an exception. If the external identity appears again,
Atlas resolves the missing episode and records a re-observation; a retired
asset is never silently reactivated.

The **Changes** page is a product knowledge timeline: discoveries, accepted
facts, relationship changes, missing/reobserved entities, source links, and
assertion lifecycle decisions. It is intentionally separate from **Audit**,
which records security and administrative activity. The architecture and test
flows are documented in
[knowledge changes and reconciliation](docs/architecture/knowledge-changes-and-reconciliation.md),
[Knowledge Foundation v1 testing](docs/testing/knowledge-foundation-v1.md), and
[Knowledge Foundation v2 testing](docs/testing/knowledge-foundation-v2.md).

## Manual authentication test

1. Start from a fresh database and bring the stack up with `--build`.
2. Confirm the API logs report that the bootstrap admin was created. Restart
   once and confirm another account is not created.
3. Open `/login` and sign in with `ATLAS_BOOTSTRAP_ADMIN_EMAIL` and
   `ATLAS_BOOTSTRAP_ADMIN_PASSWORD`.
4. Confirm login routes to the required password-change profile. Change the
   password, then confirm `/dashboard` is accessible and the header displays the
   configured email and display name.
5. Refresh `/dashboard`; the authenticated session should remain active.
6. Select **Log out** and confirm the browser returns to `/login`.
7. Open `/dashboard` directly while logged out and confirm it redirects to
   `/login`.
8. Verify cookie authentication from a terminal:

   ```bash
   ATLAS_API_URL=http://localhost:8000/api
   curl -c /tmp/atlas-cookies -X POST "$ATLAS_API_URL/auth/login" \
     -H 'Content-Type: application/json' \
     -d '{"email":"admin@example.com","password":"your-admin-password"}'

   curl -b /tmp/atlas-cookies "$ATLAS_API_URL/auth/me"
   ```

   Delete the temporary cookie jar after testing.

## Manual infrastructure test

After signing in, verify the persistent manual-data workflow:

1. Open **Customers**, create a customer, then refresh and confirm it remains.
2. Open **Sites**, select that customer, create a site, and confirm the customer name is shown.
3. Open **Assets**, select the customer and site, enter an asset name, type, and hostname, then create it. Add IP addresses from the asset detail interface section.
4. Create a second asset, open the first asset by selecting its name, and add a relationship to the second asset.
5. Refresh the asset detail page and confirm the asset fields and relationship remain.
6. Open **Knowledge Graph** (`/topology`) and confirm the customer → site → assets tree and relationship label appear.
7. Return to **Dashboard** and confirm the live customer, site, asset, and relationship counts.

The API container runs `alembic upgrade head` at startup. Existing deployments
must back up PostgreSQL before rebuilding and review the migration behavior
below; do not drop/recreate the database.

### Manual homelab modelling example

1. Create customer **Home Lab** and site **Home**.
2. Create asset **pve1** with type `proxmox_host`.
3. Create asset **docker01** with type `virtual_machine` or `docker_host`.
4. Create asset **nginx-proxy-manager** with type `docker_container` or `application`.
5. Open an asset detail page and create `docker01` → `runs_on` → `pve1`.
6. Create `nginx-proxy-manager` → `runs_on` → `docker01`.
7. Open **Knowledge Graph**, switch between **Platform** and **All relationships**, and verify node details and edge labels.
8. Filter the topology by Home Lab, Home, and an asset type; clear each filter and confirm the graph remains stable.
9. Refresh the browser and confirm all assets and relationships remain present without repeated idle API requests.

### Model a homelab network

Networks and VLANs represent subnets and broadcast/routing domains. Assets can
have one or more interfaces, and interface records are the source of truth for
IP and network membership. The legacy asset-level IP field remains API-compatible
but is not used by the web workflow.

1. Create customer **Home Lab** and site **Home**.
2. Open **Networks** and create **Apps VLAN** as a `vlan`, VLAN ID `5`, CIDR `192.168.5.0/24`, and gateway `192.168.5.1`.
3. Create **IoT VLAN** as a `vlan`, VLAN ID `3`, and CIDR `192.168.3.0/24`.
4. Create asset **docker01**, then open its asset detail page.
5. Add interface **eth0** with IP `192.168.5.8`, select **Apps VLAN**, and mark it primary.
6. Refresh the asset detail page and confirm the interface and network remain present.
7. Open **Knowledge Graph**, select **Network / VLAN**, and confirm docker01 appears under `VLAN 5 — Apps VLAN — 192.168.5.0/24`.
8. Confirm an asset without an interface appears under **Unassigned network** rather than being assigned from its primary IP silently.
9. Edit Apps VLAN, refresh the page, then delete a disposable network and confirm the list updates only after those user actions.

### Topology lenses

Atlas separates overlapping infrastructure questions into focused topology lenses:

- **Physical** shows firewalls, routers, switches, access points, storage, and physical hosts connected by `connects_to`, `uplinks_to`, or `connected_via`. Hosted workloads are summarized as counts instead of being drawn.
- **Platform** shows clusters, hypervisor hosts, VMs, LXCs, Docker hosts, containers, and applications using hosting and containment relationships.
- **Network / VLAN** groups every asset interface under its explicit Network/VLAN. Assets without interface membership remain unassigned.
- **Dependency** shows operational links such as `depends_on`, `proxies`, `authenticates`, `exposes`, `backs_up_to`, and `uses_storage`.
- **All relationships** is the advanced/debug lens. Use customer, site, asset type, relationship type, or focus-asset filters when it becomes busy.

To exercise the lenses with a representative homelab:

1. Create **UDM Pro**, **USW-16-POE**, **NAS**, **PBS**, **pve1**, and **pve2** assets.
2. Record `UDM Pro` → `uplinks_to` → `USW-16-POE`, then connect NAS, PBS, pve1, and pve2 to the switch with `connects_to`.
3. Create a **Proxmox Cluster** and record pve1 and pve2 as `member_of` the cluster.
4. Add VMs and LXCs with `runs_on` relationships to their Proxmox hosts.
5. Add a Docker host and containers/applications, then record their `runs_on` relationships.
6. Add an application → `depends_on` → database relationship.
7. Confirm **Physical** hides the VMs and containers but shows workload counts on the hosts.
8. Confirm **Platform** shows cluster → hosts → VMs/LXCs → containers/applications.
9. Confirm **Network / VLAN** uses interface membership and **Dependency** shows the application/database edge.
10. Select pve1 as the focus asset and confirm only pve1 and its directly connected neighbors remain. Clear focus and verify the full filtered lens returns without another API fetch.

### Model a homelab Service

1. Create Business Function **Identity and Access**.
2. Create Service **Authentik** as an **Application Service** with **High**
   criticality, purpose, owner/contact labels, RTO **4 hours**, RPO **24 hours**,
   and recovery notes.
3. Link Authentik to **Identity and Access**.
4. Add `Authentik runs on authentik-lxc` and suitable dependencies on AdGuard,
   Nginx Proxy Manager, and PBS Assets.
5. Create Infrastructure Service **DNS**, link its AdGuard LXC, then add
   `Authentik depends on DNS`.
6. Refresh both Service pages and confirm the records and typed links persist.
7. Evaluate Authentik completeness, fill one required gap, and confirm it
   resolves. Remove a disposable dependency and confirm the applicable gap can
   reopen while dependency history remains available.
8. Confirm the Service assertion list and Changes timeline contain the manual
   declarations and dependency events.
9. Open the Authentik Service graph and Identity and Access Business Function
   graph. Confirm Service, Asset, and Business Function nodes link to their
   detail pages and the Function shows connected Assets through its Services.
10. Sign in as Viewer and confirm these records remain readable but create,
    edit, dependency, archive, and evaluate controls are unavailable and the API
    rejects direct mutation attempts.

Stop the stack with `Ctrl+C`. To remove containers while retaining Atlas data,
run:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml down
```

> **Warning:** adding `-v` deletes the named PostgreSQL and Redis volumes. It
> destroys Atlas data and should be used only for an intentional disposable
> reset after a verified backup.

## Upgrade an existing installation

Before upgrading, record the deployed revision and make a verified PostgreSQL
backup. Replace obsolete `ATLAS_ADMIN_EMAIL`, `ATLAS_ADMIN_PASSWORD`, and
`ATLAS_ADMIN_DISPLAY_NAME` settings with the new names only if the users table is
genuinely empty. Existing database users and password hashes remain. The seed
recognizes the legacy group solely as a deprecated first-user fallback on an
empty table; it is never permanent authentication and cannot reset an existing
password. Remove either bootstrap group after first use.

The foundation migration:

- Creates a `Default Site` for each customer that needs one, assigns legacy
  site-less or mismatched-site assets and integrations, and derives relationship
  context without deleting inventory. Every integration has a valid site after
  the upgrade. A network whose legacy site belongs to another customer is
  preserved as a customer-wide network.
- Migrates string asset/relationship types to managed stable keys. Blank legacy
  asset and relationship type values normalize to `unknown` and `related_to`,
  respectively.
- Assigns each legacy user a global Master Administrator role to avoid an
  upgrade lockout. Review and narrow those assignments after validation.
- Normalizes login emails case-insensitively and aborts on a legacy collision;
  run the preflight query in the deployment guide before upgrading.
- Retains legacy cross-context relationships; new ones are rejected and a
  retained edge is visible only when both endpoints are authorized.
- Seeds roles, permissions, and system definitions idempotently.

Normal API startup runs the migration. To run only the migration step in the
Compose environment:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml run --rm api \
  alembic upgrade head
```

Rebuild/start the matched services, allow the API to run `alembic upgrade head`,
then verify health, login/password-change state, customer/site selectors,
scope-limited users, inventory counts, and topology. Remove bootstrap values
after first use.

Rollback should restore the pre-upgrade database backup and matching prior
application revision. Do not run old code against the upgraded schema or assume
an Alembic downgrade preserves ownership/type backfills. See
[deployment and upgrade guidance](docs/architecture/deployment-and-upgrades.md)
for backup commands, migration detail, rollback steps, and production security
limitations.

## Run services directly

### API

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m scripts.seed_admin
uvicorn app.main:app --reload
```

Export the API variables from the root `.env` before running those commands. If
PostgreSQL is in Compose but the API is on the host, use `localhost` rather than
the Compose-only `postgres` hostname in `DATABASE_URL`. The seed command is a
safe no-op when bootstrap values are absent or a user already exists. The API
container performs migration and bootstrap automatically.

To create a migration after changing the SQLAlchemy models, run:

```bash
cd apps/api
alembic revision --autogenerate -m "describe the schema change"
```

Run the API test suite with:

```bash
cd apps/api
pip install -r requirements-dev.txt
pytest
```

### Web

```bash
cd apps/web
npm install
npm run dev
```

Validate the production bundle with `npm run build`.

### Worker

```bash
cd apps/worker
python3 -m worker.main
```

## Plugin SDK

The package in `plugins/sdk` defines the boundary between Atlas and discovery
plugins. A plugin implements `DiscoveryPlugin` with:

- `validate_connection(config)` for a non-mutating connectivity check.
- `discover(config)` for raw vendor data collection.
- `normalize(discovery)` for vendor-neutral assets, facts, and relationships.

Atlas core implements `SyncBackend.sync(context, normalized)` to idempotently
persist normalized results. Keeping sync outside vendor plugins prevents them
from depending on Atlas database internals. Raw discovery payloads remain in
`DiscoveryResult` and are not embedded in normalized assets.

Run the SDK contract tests with:

```bash
cd plugins/sdk
python3 -m pytest
```

### Proxmox connection validation

The Proxmox package implements a read-only connection test using API token
authentication. Pass credentials to the SDK `ConnectionConfig` using
`token_id` (`user@realm!token-name`) and `token_secret` keys. Validation sends
an authenticated `GET /api2/json/nodes` request, confirming both authentication
and permission to enumerate nodes.

Proxmox URLs must use HTTPS. TLS verification is enabled by default and should
only be disabled for explicitly trusted development environments. Credentials,
authorization headers, and response bodies are never returned in validation
results.

Proxmox discovery collects nodes, QEMU VMs, LXC containers, storage pools, and
network bridges. Complete endpoint responses are retained on the discovery run
as raw JSON. Normalized assets use stable external identities and are upserted
by integration; repeat runs update `last_seen_at` instead of creating duplicate
assets. Assets absent from a later run are marked stale and are not deleted.

Each synchronized asset also receives a generated Markdown document containing
its normalized overview, description, metadata, facts, and incoming/outgoing
relationships. Generated documents are updated on repeat discovery runs and
reference the run that produced their current content. Raw vendor payloads are
not copied into documentation pages.

Run the Proxmox plugin tests with:

```bash
PYTHONPATH=plugins/sdk:plugins/proxmox python3 -m pytest plugins/proxmox/tests
```

The worker is currently a long-running placeholder. Queue consumption and job
orchestration will be added in a later increment; discovery, normalization,
and persistence services are implemented but are not yet dispatched by Redis.

## Knowledge completeness

Atlas can define a database-driven Knowledge Profile for each Asset Type and
evaluate assets after fields, custom fields, interfaces, relationships, or
accepted discovery data change. Missing or stale knowledge creates a separate
Knowledge Gap without blocking or deleting the operational asset. Asset detail,
the Operations **Knowledge Gaps** page, the Assets list, and Dashboard show
scoped completeness state. Authorized users can provide information, defer a
gap, record a reasoned exception, reopen it, or reevaluate the asset.

The Operations workflows remain deliberately separate: **Reconciliation**
handles proposed evidence decisions, while **Knowledge Gaps** handles absent or
insufficient knowledge. **Changes** remains under Overview as the meaningful
knowledge timeline.

Start in **Administration → Asset types → Knowledge profile**. Select existing
Asset Types, Relationship Types, and Custom Field Definitions in the structured
editor; no fixed homelab type names or pasted UUIDs are required. See the
[architecture](docs/architecture/knowledge-completeness.md),
[administrator guide](docs/admin/knowledge-profiles.md), and
[manual test plan](docs/testing/knowledge-completeness-v1.md).
