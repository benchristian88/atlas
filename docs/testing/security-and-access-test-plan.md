# Authentication and access foundation test plan

This matrix defines the required automated and migration-level verification for
the Atlas authentication/RBAC/context/administration foundation. It is a test
plan, not a claim that every case already has a passing automated test. It
supplements, rather than replaces, route-specific CRUD and plugin tests.

## Supported commands

Run from a clean checkout with a disposable test database:

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Under Node.js 22+, the web project currently exposes a production build check
but no dedicated unit-test/lint/type-check scripts:

```bash
cd apps/web
npm install
npm run build
```

Also retain plugin contract coverage:

```bash
python3 -m pytest plugins/sdk
PYTHONPATH=plugins/sdk:plugins/proxmox python3 -m pytest plugins/proxmox/tests
```

Do not report any command as passing unless it ran to completion in the target
environment. Compose startup/migration verification requires Docker and
PostgreSQL; an in-memory/model-only test is not a substitute.

## Authentication

| Case | Required assertion |
| --- | --- |
| Empty-table bootstrap | Creates one active forced-change user, secure password hash, global Master Administrator assignment, and no plaintext secret. |
| Existing user | Bootstrap returns a no-op regardless of supplied email/password and never creates/resets another account. |
| Missing/partial values | All absent is a safe no-op; partial values are a safe configuration error. |
| Deprecated variable fallback | A complete legacy group works with a warning only on an empty users table when the preferred group is absent; any existing user makes it a no-op. |
| Password validation | Email is normalized; passwords shorter than 12 or longer than the supported maximum are rejected. |
| Valid login | Updates last login/failure state, audits success, and sets the expected HttpOnly/SameSite cookie. |
| Invalid login | Generic `401`, no cookie, failure count/lock behavior, safe audit event, and unknown-email timing hash path. |
| Disabled/locked account | Cannot log in or continue using an old signed session. |
| Forced change | Normal protected APIs return `403` while profile/password/logout and the slim, scope-filtered `/context` bootstrap response remain reachable. |
| Profile update | Only display name changes; role/scope/mass-assignment fields are ignored or rejected. |
| Password change | Requires current password and matching strong replacement, hashes it, clears forced state, increments session version, and audits safely. |
| Logout | Clears cookie, increments session version, and rejects the captured old cookie. |
| Secret hygiene | Login/profile/admin/audit serializers omit hashes, cookie/token values, and temporary passwords. |
| Request origin | State-changing requests with an unapproved `Origin` return `403`; approved/no-origin API clients follow the normal policy. |

## Permissions and assignments

Use parametrized cases over the built-in roles and all permission keys.

| Case | Required assertion |
| --- | --- |
| Master/global | Every permission succeeds across Customer A and B. |
| Administrator | Granted operations succeed only in assignment scope; Master-reserved permissions remain absent unless explicitly mapped. |
| Customer Administrator | Customer A operations succeed according to role mapping; equivalent Customer B IDs return `403`/hidden `404`. |
| Viewer | Read routes work in scope; every create/edit/delete/admin mutation returns `403`. |
| Mixed assignments | Different roles at Customer A/Site A1 and Customer B/Site B1 do not broaden one another. |
| Invalid site pair | A site ID submitted with another customer is rejected by schema/policy. |
| Inactive role | Its assignment grants no effective permission. |
| Protected definitions | Built-in permission/role deletion and unsafe edits fail. |
| Last master | Disabling/demoting/self-demoting/removing the last active global Master Administrator fails transactionally. |

Test the central policy helpers directly and at representative API boundaries.
A helper-only test cannot prove a route actually declares and applies the
dependency.

## Scope and IDOR isolation

- Customer A principals cannot list, get, update, delete, or infer Customer B
  customers, sites, assets, interfaces, networks, relationships, integrations,
  custom values, or audit events.
- Site A1 assignments do not include Site A2, including when the caller changes
  path IDs, query parameters, `X-Atlas-*` headers, or JSON ownership fields.
- Search, dashboard summaries/counts, selector options, and every topology lens
  are computed from scoped SQL and contain no inaccessible IDs, labels, totals,
  or dangling relationship endpoints.
- Asset creation validates customer/site ownership. A global list context cannot
  be used as a creation context.
- New/updated relationships require distinct accessible endpoints in the same
  customer/site and an active applicable relationship type.
- A grandfathered cross-context legacy relationship appears only when both
  endpoint contexts are authorized; it is absent from single-endpoint scope and
  cannot be duplicated or edited into another cross-context edge.

## Managed types and lifecycle

Cover both asset and relationship types:

- Stable keys and unique names reject duplicates and unsafe key changes.
- Only active types appear in new-record choices.
- Existing records continue to serialize an inactive type and its display
  metadata.
- Referenced type deletion conflicts with a clear error; deactivation succeeds.
- System-defined type deletion fails even when unused.
- An unused user-created type can be deleted without cascading inventory.
- Relationship direction/inverse labels and source/target applicability are
  preserved and enforced.

## Custom fields

- Global fields count for every asset type. Activating/applying a definition
  that makes any type exceed 10 fails atomically; exactly 10 succeeds.
- Text, multiline, number, date, boolean, URL, and dropdown values accept valid
  canonical values and reject mismatched types.
- Required applicable fields are enforced on create/edit without requiring
  irrelevant fields.
- Dropdown values must select an active option belonging to that definition.
- Definition keys remain stable after values exist; incompatible type changes
  and destructive option/definition deletion fail.
- Deactivation excludes a field from new editing while preserving and
  serializing existing values.
- A Viewer can read but cannot write values.
- Moving an asset to another type revalidates required/applicable values and the
  effective field set.

## Icons

- Schema validation accepts absolute HTTPS raster-image URLs and rejects HTTP,
  relative URLs, credentials-in-URL, `data:`, `javascript:`, and remote `.svg`
  paths case-insensitively.
- Asset override wins over type default; type default wins over the generic
  fallback; missing values select the fallback.
- API processing does not make a network request to the configured URL.
- A browser image-load error replaces the remote image with the generic icon
  without executing content.

## Audit

- Login success/failure/logout, password change/reset, user status/assignment,
  customer/site, managed types, custom definitions/options, and sensitive
  settings create the expected event in the same safe transaction semantics.
- Events snapshot available actor identity and customer/site context, outcome,
  target, and request metadata without secrets.
- Search event JSON and serialized responses for plaintext test passwords,
  hashes, `Authorization`, `Cookie`, session JWTs, bootstrap variables, and
  secret keys; all must be absent.
- `audit.view` is required, customer/site filters respect scope, and no ordinary
  create/update/delete audit endpoint exists.

## Migration and deployment

Run upgrade tests against both an empty pre-foundation schema and a fixture with
multiple customers, null-site and mismatched-site assets and integrations,
blank legacy type values, legacy users, and a cross-context relationship:

1. Take/verify a backup.
2. Run `alembic upgrade head` once and validate row counts/foreign keys.
3. Confirm each customer needing a site has one `Default Site`, null/invalid
   asset and integration site ownership is backfilled, integration sites are
   non-null and customer-matched, invalid network site ownership normalizes to
   customer-wide, blank asset/relationship types resolve as `unknown`/
   `related_to`, stable type records exist, and each legacy user has one global
   Master assignment.
4. Confirm the cross-context edge remains marked/recognizable and subject to the
   both-endpoints read rule.
5. Run `alembic upgrade head` and system/bootstrap seeds again; counts and
   customizations remain unchanged.
6. Start Compose with no bootstrap values against the upgraded database and
   confirm startup succeeds.
7. Render `docker compose config` and verify bootstrap/database/auth secrets are
   not present in the web service environment.
8. Exercise the backup-restore rollback procedure in an isolated environment.

Test lifecycle cleanup with `docker compose down`, which must preserve the
PostgreSQL volume. Use `down -v` only for the deliberately disposable fixture;
it destroys the database volume.

## Security review gate

Before release, inspect every API router for authentication, required permission,
and scope/object checks. Specifically review IDOR substitutions, mass
assignment, frontend-only assumptions, cross-customer totals, custom-field
validation, icon SSRF/script paths, cascade behavior, last-master invariants,
and secret-bearing audit/log data. Record any deferred route or control as a
known limitation rather than treating UI hiding as coverage.
