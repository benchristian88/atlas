# Deployment, upgrade, and rollback

Atlas's reference deployment is Docker Compose with separate web, API, worker,
PostgreSQL, and Redis services. PostgreSQL is the system of record. Redis data
is operational and may be recreated; the PostgreSQL volume must be backed up.

## Configuration boundary

Copy `.env.example` to `.env` and keep `.env` outside version control. The API
receives database, Redis, cookie/session, CORS, and optional bootstrap settings.
The web container receives only browser-public `NEXT_PUBLIC_API_URL` and the
development-origin allow-list. Compose deliberately does not inject the whole
`.env` into the Next.js container.

Required operational settings are:

- `AUTH_SECRET_KEY`: at least 32 unpredictable characters. Rotation logs out
  every user.
- `AUTH_SESSION_MINUTES`: signed-session lifetime from 1 to 10,080 minutes; the
  development default is 480.
- `AUTH_COOKIE_SECURE`: `false` only for local HTTP; `true` behind production
  HTTPS.
- `CORS_ORIGINS`: optional exact comma-separated web origins for intentional
  split-origin development. Leave blank for normal same-origin operation and
  never use a wildcard with authenticated requests.
- `NEXT_PUBLIC_API_URL`: optional browser API-base override. It defaults to
  `/api`; use an absolute URL ending in `/api` only for split-origin development.
- Database credentials and `DATABASE_URL`: replace the development values for
  any non-local deployment.

`ATLAS_BOOTSTRAP_ADMIN_EMAIL`, `ATLAS_BOOTSTRAP_ADMIN_PASSWORD`, and
`ATLAS_BOOTSTRAP_ADMIN_NAME` are optional and one-time. Set all three only while
creating the first user, change that temporary password, remove the values, and
restart the API. They do not reset or update an existing account.

The old `ATLAS_ADMIN_EMAIL`, `ATLAS_ADMIN_PASSWORD`, and
`ATLAS_ADMIN_DISPLAY_NAME` group is a deprecated migration fallback. It is read
only when the users table is empty and the preferred group is absent, emits a
warning, and performs the same one-time bootstrap. Do not add it to new
deployments; remove it immediately after a legacy bootstrap.
The reference Compose file intentionally forwards only the preferred new group;
rename legacy keys in `.env`. The fallback is for direct execution or an older
external orchestrator that still supplies the legacy environment.

## Fresh Compose installation

```bash
cp .env.example .env
# Edit .env: replace secrets and set all bootstrap values.
docker compose --env-file .env -f infra/docker/docker-compose.yml up -d --build
docker compose --env-file .env -f infra/docker/docker-compose.yml logs -f api
```

API startup runs `alembic upgrade head`, idempotent system-definition seeding,
and `python -m scripts.seed_admin` before starting Uvicorn. A fresh installation
with valid bootstrap values therefore has one forced-password-change Master
Administrator and, when the database had no customer, a starter
`Home / Homelab` context. Once login and password change succeed, remove the
bootstrap values and recreate the API container:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml up -d --force-recreate api
```

To stop containers while retaining data:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml down
```

> **Data-loss warning:** `docker compose down -v` deletes the named PostgreSQL
> and Redis volumes. It destroys Atlas data and is appropriate only for an
> intentional disposable reset after a verified backup.

## Upgrade checklist

1. Record the currently deployed commit/image and inspect the release diff and
   migration notes.
2. Make a PostgreSQL backup and verify that it is non-empty and restorable.
3. Copy `.env` to a separately protected backup. Do not place secrets in the
   repository or a ticket.
4. Replace obsolete `ATLAS_ADMIN_EMAIL`, `ATLAS_ADMIN_PASSWORD`, and
   `ATLAS_ADMIN_DISPLAY_NAME` entries. Existing database users remain. On an
   empty users table only, the seed accepts that full legacy group with a
   deprecation warning; it is not a permanent credential or reset mechanism.
5. Check for legacy login identifiers that differ only by case or surrounding
   whitespace. Resolve any rows returned by the query below deliberately before
   upgrading; the migration refuses to merge accounts automatically:

   ```sql
   SELECT lower(btrim(email)) AS normalized_email, count(*)
   FROM users
   GROUP BY lower(btrim(email))
   HAVING count(*) > 1;
   ```

6. Set the new `ATLAS_BOOTSTRAP_ADMIN_*` values only if the deployment truly has
   no database user. Setting them cannot repair or reset an existing account.
7. Pull/build the matching web, API, and worker version, then start the stack.
   The API applies migrations before accepting traffic.
8. Check API migration/startup logs, `/api/health`, login, forced-password-change
   state, context selection, a scope-limited account, and topology/inventory
   counts.
9. Remove any bootstrap values after first use and recreate the API container.

For a short maintenance-window upgrade:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml down
docker compose --env-file .env -f infra/docker/docker-compose.yml build
docker compose --env-file .env -f infra/docker/docker-compose.yml up -d
docker compose --env-file .env -f infra/docker/docker-compose.yml logs --tail=200 api
```

Running `alembic upgrade head` directly is equivalent to the migration part of
container startup:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml run --rm api \
  alembic upgrade head
```

Do not run two migration jobs concurrently.

## Foundation migration behavior

The authentication/access foundation migration is additive and preserves
legacy inventory:

- It creates permissions, protected built-in roles, role-permission mappings,
  scoped role assignments, session/profile state, managed type/custom-field
  tables, icon columns, and the expanded audit structure.
- It creates a `Default Site` for each customer that needs one, assigns
  site-less or invalidly paired legacy assets and integrations to that
  customer's site, and derives relationship context from the source asset.
  Integration sites are required after the migration. A network with a missing
  or cross-customer site reference is preserved as a customer-wide network.
- It migrates legacy string asset/relationship types to stable managed type
  keys. Blank asset and relationship type values normalize to `unknown` and
  `related_to`, respectively, so every existing record resolves a managed type.
- It assigns each legacy user the Master Administrator role at global scope so
  an upgrade does not unexpectedly remove access. Operators should review and
  narrow these assignments immediately after validating the upgrade.
- It normalizes login email case and surrounding whitespace. A pre-existing
  case-insensitive collision aborts the migration with a clear error rather than
  choosing which account to keep.
- It retains a legacy relationship whose endpoints are in different contexts to
  avoid destroying topology history, marks it `legacy_cross_context`, and uses
  the source asset as its stored context. New cross-customer and cross-site
  relationships are prohibited, and the retained edge is readable only when a
  user can access both endpoints.
- Seeds and backfills are conflict-safe/idempotent; restarting at the same
  revision does not duplicate roles, permissions, types, customers, sites, or
  users.

The migration does not drop and recreate the database. Check migration logs and
compare per-customer assets/relationships before and after upgrading.

## User accent preference migration

Revision `20260717_0005` adds the nullable `users.accent_colour` column. It does
not rewrite or delete existing user records: a null value deliberately retains
the Atlas default accent. Normal API startup applies the revision through
`alembic upgrade head`; no preference backfill or operator input is required.
The downgrade removes only this preference column, so export any chosen accent
values first if they need to be retained across a rollback.

## User theme mode migration

Revision `20260909_0015` adds nullable `users.theme_mode`, constrained to
`light`, `dark`, or `system`. Null is returned as `system`, preserving OS-based
mode selection for existing accounts. The accent preference remains separate.
Apply `alembic upgrade head` before serving the updated API (normal API startup
already does this). No backfill is needed. Downgrading removes the theme mode
preference only; accent preferences and all other user data are retained.

## Backup example

The following creates a PostgreSQL custom-format backup on the Docker host. The
redirection occurs on the host; protect the resulting file as sensitive data.

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml exec -T postgres \
  sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > atlas-before-upgrade.dump
test -s atlas-before-upgrade.dump
```

Also test restoration in an isolated PostgreSQL instance on a routine basis. A
backup that has never been restored is not a verified recovery plan.

## Rollback

Application code and database schema must remain a matched version. The safest
rollback after a schema migration is:

1. Stop Atlas writers.
2. Preserve a diagnostic backup of the failed upgraded database.
3. Recreate an empty PostgreSQL database/volume.
4. Restore the verified pre-upgrade backup.
5. Deploy the exact pre-upgrade commit/images and its environment file.
6. Validate health, login, counts, and a representative asset before reopening
   access.

Do not merely deploy old application code against a newer schema, and do not
assume `alembic downgrade` is a data-preserving rollback. Backfilled ownership,
type conversion, and new administrative writes can make a schema-only downgrade
lossy. Use revision downgrades only if that specific migration documents and
tests a safe path.

## Production limitations and checklist

- Terminate TLS at a maintained reverse proxy and set secure cookies.
- Restrict database/Redis ports to trusted networks; the Compose port mappings
  are development conveniences.
- Put secrets in the deployment platform's secret store where possible rather
  than long-lived plaintext environment files.
- Set a narrow CORS origin list and security headers/content-security policy at
  the edge. Cached Asset icons use Atlas itself; allow remote hosts only for
  the existing Asset Type default images. See [Asset icon caching](asset-icon-cache.md)
  for the additive migration and PostgreSQL persistence.
- Send logs and audit events to protected external retention if tamper evidence
  or regulatory retention is required.
- Add reverse-proxy rate limits and monitoring for repeated authentication
  failure until distributed application throttling is available.
- Atlas local authentication does not yet provide SSO, MFA, email-based account
  recovery, or a break-glass recovery command. Maintain a tested database backup
  and at least two usable global Master Administrators.
