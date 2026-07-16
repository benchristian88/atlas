# Atlas Codex context

Atlas is an infrastructure knowledge, documentation, and topology platform for
homelabs, internal IT teams, and MSPs. Preserve the existing FastAPI,
SQLAlchemy/Alembic, Next.js, PostgreSQL, Redis, worker, and plugin-SDK
architecture when extending it.

## Repository and workflow

```text
apps/api       FastAPI API, SQLAlchemy models, Alembic migrations, pytest
apps/web       Next.js App Router UI
apps/worker    Background worker boundary
plugins/sdk    Vendor-neutral discovery contracts
plugins/proxmox
infra/docker   Compose development/reference deployment
docs           Product, architecture, testing, and operator guidance
```

The normal development/deployment workflow is local editing, commit/push,
pulling on the Docker host, then rebuilding with Compose. Do not replace working
project conventions to introduce a preferred framework.

## Implemented MVP foundation

The current foundation includes:

- Database-backed local users, recommended password hashes, active/lock/forced-
  change state, profile editing, and password change/reset boundaries.
- Expiring signed sessions in an `HttpOnly`, `SameSite=Lax` cookie. The browser
  uses `credentials: "include"`; it does not store a live bearer token in
  `localStorage`.
- Logout/password-change invalidation through `users.session_version`.
- Explicit permissions, protected built-in roles (Master Administrator,
  Administrator, Customer Administrator, Viewer), and role assignments at
  global/customer/site scope.
- Central FastAPI policy helpers and backend scope filters for inventory,
  topology, selectors, counts, and administration.
- An active customer/site selection shown in the protected header. Stored
  context is only a preference and is revalidated by the API.
- Managed asset/relationship types with stable keys, active/system flags, and
  guarded delete/deactivate behavior.
- Structured typed custom fields and dropdown choices, with global/asset-type
  applicability and a total limit of 10 active applicable fields per asset
  type.
- HTTPS icon URLs with remote SVG rejection and resolution order: asset
  override, asset-type default, generic fallback. The server does not fetch icon
  URLs.
- Durable, permission-gated, read-only audit history for authentication and
  administrative/security actions.

## Security and ownership invariants

Atlas ownership is always:

```text
Instance / workspace -> Customer -> Site -> Assets and relationships
```

Every interactive route must authenticate. Apart from the documented
authentication/profile operations and the slim read-only `/context` selector
needed to initialize the forced-password-change shell, application routes must
enforce forced-password-change state, require an explicit permission, and
constrain their query or mutation to an authorized global/customer/site
assignment. `/context` may expose only authorized customer/site IDs, names, and
statuses. Never rely on navigation hiding, active-context headers,
URL/query/body IDs, or browser storage as proof of access. Search, topology,
dashboards, summaries, and counts must not reveal inaccessible records.

New assets require a concrete authorized customer/site. New and edited
relationships require both endpoints to be accessible and in the same customer
and site. A migrated legacy cross-context edge is retained for data preservation
but is readable only when both endpoint contexts are accessible and cannot be
recreated.

Never return/log passwords, hashes, bootstrap credentials, session values,
cookies, authorization headers, or full secret-bearing request bodies. Audit
summaries must be explicitly safe. Avoid mass assignment of roles, access scope,
identity state, ownership, stable keys, or system flags.

Do not add server-side remote icon fetching without a designed SSRF boundary.
Do not accept remote SVG or inline executable image markup.

## Bootstrap behavior

The only environment-backed account operation is first-user bootstrap:

- `ATLAS_BOOTSTRAP_ADMIN_EMAIL`
- `ATLAS_BOOTSTRAP_ADMIN_PASSWORD`
- `ATLAS_BOOTSTRAP_ADMIN_NAME`

All three are optional as a set. When the users table is empty and all are valid,
create one forced-password-change global Master Administrator. If any user
exists, do nothing; never overwrite/reset/create by matching email. With all
three absent, startup continues without creating a user. Partial/invalid values
are a safe configuration error. If no customer exists, first-user bootstrap
also creates `Home / Homelab`; it does not add that context to an existing
installation. Operators remove bootstrap values after initialization.

For migration only, a complete legacy `ATLAS_ADMIN_EMAIL` /
`ATLAS_ADMIN_PASSWORD` / `ATLAS_ADMIN_DISPLAY_NAME` group is accepted with a
deprecation warning when the users table is empty and the preferred group is
absent. It follows the same one-time flow. Never show the old names in new setup
examples or treat them as live credentials; existing users make them a no-op.

`AUTH_SECRET_KEY`, `AUTH_SESSION_MINUTES`, and `AUTH_COOKIE_SECURE` remain API
session configuration. Production requires HTTPS, secure cookies, a narrow
credentialed CORS allow-list, and non-development database secrets. Compose must
never pass the complete `.env` into the web service.

## Data and migration conventions

Use SQLAlchemy models and Alembic; do not drop/recreate databases for schema
changes. Seed permissions, roles, and protected managed types idempotently
without overwriting administrator customizations.

The foundation upgrade creates a per-customer `Default Site` where legacy
assets or integrations need one, repairs missing or mismatched site ownership,
and makes integration sites required. It migrates legacy type strings to stable
managed keys, normalizing blank asset and relationship types to `unknown` and
`related_to`, respectively, and grants legacy users a global Master
Administrator assignment to preserve access. Operators review/narrow those
assignments after upgrade. Preserve legacy cross-context relationships and
enforce the both-endpoints access rule.

Used/system types, definitions, and options are deactivated rather than
destructively cascaded. Custom values use typed rows, not an arbitrary
unvalidated JSON object.

## Running and testing

```bash
cp .env.example .env
# Set AUTH_SECRET_KEY and, only for an empty users table, all bootstrap values.
docker compose --env-file .env -f infra/docker/docker-compose.yml up -d --build
```

API startup runs `alembic upgrade head` and the optional `scripts.seed_admin`
check. `docker compose ... down` preserves named volumes. Never suggest
`docker compose ... down -v` without an explicit warning that it destroys the
PostgreSQL data volume.

API tests:

```bash
cd apps/api
pip install -r requirements-dev.txt
pytest
```

Web validation:

```bash
cd apps/web
npm install
npm run build
```

The web package currently has no dedicated lint/type-check/unit-test scripts, so
do not claim those checks ran. Run plugin tests when changing plugin contracts or
discovery behavior. Do not claim Docker, migration, build, or test success unless
the corresponding command actually completed.

## Current limitations and next work

The MVP does not yet provide SSO/OIDC/SAML, MFA flows, self-service email
recovery, tamper-evident external audit retention, uploaded icon storage,
customer-specific managed types/fields, or new cross-site relationships. The
worker/Redis runtime is still an orchestration boundary rather than a complete
production job system.

The recommended next increment is deeper topology context and visualization,
then plugin discovery/ingestion permissions and worker orchestration. New plugin
permissions must join the explicit permission/assignment model rather than
bypassing it.
