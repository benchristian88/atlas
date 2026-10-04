# Deployment, upgrade, and rollback

Atlas's reference deployment is Docker Compose with a lightweight nginx ingress
gateway and separate web, API, worker, PostgreSQL, and Redis services. PostgreSQL is the system of record. Redis data
is operational and may be recreated; the PostgreSQL volume must be backed up.

## Configuration and installation boundary

Public beta production installation is supported through **Docker Compose** or
**native/systemd** only. Direct execution remains a developer workflow. Manual
production installation is unsupported. See [H1 installation](../deployment/h1-installation.md)
for generated secrets, configuration classification, first-run setup, reset
commands and native prerequisites.

Production configuration is generated with exclusive creation and restrictive
permissions; installers never overwrite an existing file. Database credentials,
Redis connectivity, `AUTH_SECRET_KEY`, `ATLAS_DATA_ENCRYPTION_KEY`, cookie/CORS policy and installation/build
identity are deployment configuration. Session lifetime is managed in Atlas
System Settings. `.env.example` is development-only. Neither bootstrap admin
credential group is read anymore.

The canonical application version/channel lives in `apps/api/app/release.json`.
Builds carry `ATLAS_BUILD_ID` when available and need no runtime Git. The
protected `/api/system-settings/build-info` endpoint and About display version,
channel, build ID and installation method (`docker_compose`, `systemd`, or
`development`). Frontend package versions are tooling metadata, not a separate
application identity. H4 adds [release packages and update awareness](release-distribution.md).
Packaged commit/method identity wins over preserved environment build IDs.

## Fresh Compose installation

Download and verify the Docker release package as shown in the installation
guide, then from its versioned root:

```bash
python3 infra/install/compose.py
```

The helper generates protected `.env`, builds/starts the healthy stack, and
prints the actual single-origin HTTP access URL and a one-time setup code to
the SSH terminal. Open `/setup` through that URL (or an optional trusted HTTPS
proxy), enter the code, choose a new Atlas and create the
first Master Administrator. Then sign in. Startup uses bounded database
readiness retries, `alembic upgrade head`, and protected definition seeding;
it never generates/logs a raw setup code or creates environment users.
All six services use `unless-stopped`. Only gateway port 80 is published at
`ATLAS_BIND_ADDRESS:ATLAS_PORT` (installer-detected default-route IPv4, port
3000; safe loopback fallback). API/web/database/cache remain internal. The
gateway preserves `/api`, Host including port, and sanitized forwarding headers.
Its empty-by-default `ATLAS_TRUSTED_PROXIES` allowlist accepts original HTTPS
only from explicitly trusted proxy peers. Docker API Uvicorn trusts internal
Compose peers (`FORWARDED_ALLOW_IPS=*`); this requires the API to remain
unpublished on the private Compose network. The development override restores
split ports and narrows API proxy trust to loopback. Application cookie auto
mode reads the ASGI request scheme, never raw forwarded headers. External TLS
proxies use one gateway upstream; single-origin operation leaves CORS blank.

Native/systemd bundles distribution nginx, with the same LAN IPv4/port detection
and loopback fallback. nginx owns the external default port 3000; native web
uses `127.0.0.1:3001` and API `127.0.0.1:8000`. Its dedicated Atlas site preserves
`/api`, accepts 2 GiB streamed restore uploads and sanitizes forwarding using
the same explicit external-proxy allowlist as Docker. Uvicorn trusts only
loopback and fresh cookie policy is `auto`. Complete read-only prerequisite
checks (including a disposable venv and database-conflict inspection) precede
Atlas mutation. Only nginx is automatically installed, using host apt packages.
Managed nginx updates validate before activation and restore previous files on
failure; unrelated host sites remain untouched. A systemd drop-in enables nginx
startup after Atlas API/web. Existing secrets/configuration/state survive upgrades;
legacy explicit cookie settings need deliberate operator review. PostgreSQL
authority, domain semantics, RBAC and discovery stay intact. Fresh real Debian
native lifecycle retesting is required after this H4 remediation.

To stop containers while retaining data:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml down
```

> **Data-loss warning:** `docker compose down -v` deletes the named PostgreSQL
> and Redis volumes. It destroys Atlas data and is appropriate only for an
> intentional disposable reset after a verified backup.

## Package upgrades

Use the [H4 configuration-preserving upgrade helper and checklist](../deployment/h4-upgrades.md)
for H1–H3 installations. Create/download an H3 encrypted backup first. Existing
`.env`, `/etc/atlas/atlas.env`, database and protected state are retained.
The following historical migration checklist remains relevant to pre-H1 source
deployments; it does not replace the package upgrade procedure.

## Legacy foundation upgrade checklist

1. Record the currently deployed commit/image and inspect the release diff and
   migration notes.
2. Make a PostgreSQL backup and verify that it is non-empty and restorable.
   Encrypted MFA additionally depends on `ATLAS_DATA_ENCRYPTION_KEY`; retain its
   protected configuration. PostgreSQL alone cannot restore MFA to a new key.
3. Copy `.env` to a separately protected backup. Do not place secrets in the
   repository or a ticket.
4. Remove retired `ATLAS_ADMIN_*`, `ATLAS_BOOTSTRAP_ADMIN_*` and
   `AUTH_SESSION_MINUTES` entries. Existing users/passwords remain. The new
   session setting starts at 480; set any desired previous custom value through
   System Settings after upgrading. Retain existing database/signing secrets:
   the fresh-install generator intentionally refuses an existing environment.
5. Check for legacy login identifiers that differ only by case or surrounding
   whitespace. Resolve any rows returned by the query below deliberately before
   upgrading; the migration refuses to merge accounts automatically:

   ```sql
   SELECT lower(btrim(email)) AS normalized_email, count(*)
   FROM users
   GROUP BY lower(btrim(email))
   HAVING count(*) > 1;
   ```

6. Build/start matching services. Startup migrates before serving traffic.
7. Check migration logs, `/api/health`, normal login, a scoped account, context
   selection, topology/inventory counts, and System Settings.
8. Confirm `/setup` cannot initialize an installation with existing users.

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

## H2 local MFA upgrade

Revision `20261004_0026` adds one-to-one encrypted TOTP state, recovery verifiers
and bounded login challenges. Existing accounts remain unenrolled; password
hashes and assignments do not change. Fresh installers generate independent
256-bit data-encryption material. Existing configurations need the missing key
added with the protected helper before production startup; it never replaces
existing secrets. See [H2 deployment](../deployment/h2-mfa.md). H3 now includes
this material in its passphrase-encrypted payload and rewraps to target data
material. See [H3 operator recovery](../deployment/h3-backup-restore.md); H2 alone
did not supply backup/restore or key rotation.

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

## H3 encrypted backup and restore

Use [H3 backup/restore](../deployment/h3-backup-restore.md) for UI download,
initialized overwrite, first-run restore and exact shared-service Docker/native
local recovery commands. Target deployment configuration stays local, including
signing/data keys; MFA is rewrapped and sessions are invalidated. H3 adds protected
`atlas_state` staging/recovery and native `StateDirectory=atlas`, not another
authoritative operational data store. Match PostgreSQL client/server versions.

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

- For HTTPS, terminate TLS at a maintained reverse proxy and configure the
  gateway's narrow trusted-proxy list; Docker cookie auto mode then marks cookies
  Secure. Direct LAN HTTP uses non-Secure cookies. Explicit `true` forces HTTPS.
- PostgreSQL/Redis ports are internal to production Compose. Use the separate
  development override only when local access is needed.
- Put secrets in the deployment platform's secret store where possible rather
  than long-lived plaintext environment files.
- Leave CORS blank for normal same-origin operation; use a narrow exact origin
  list only for deliberate split origins. Set security headers/content-security
  policy at the edge. Cached Asset icons use Atlas itself; allow remote hosts only for
  the existing Asset Type default images. See [Asset icon caching](asset-icon-cache.md)
  for the additive migration and PostgreSQL persistence.
- Send logs and audit events to protected external retention if tamper evidence
  or regulatory retention is required.
- Add reverse-proxy rate limits and monitoring for repeated authentication
  failure until distributed application throttling is available.
- Atlas local authentication provides optional TOTP, one-time recovery codes and
  [local MFA break-glass reset](../deployment/h2-mfa.md). SSO and email-based account
  recovery remain deferred. Maintain a tested database backup
  and at least two usable global Master Administrators.
