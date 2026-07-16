# Split-origin to single-origin migration

This is a coordinated frontend/backend routing release. The new frontend calls
`/api/*`, and the new backend no longer exposes unprefixed application routes.
Running one new component with one old component is unsupported.

## Prepare

1. Back up PostgreSQL and verify the backup is non-empty and restorable.
2. Back up `.env`, reverse-proxy configuration, and the deployed Git revision or
   image tags.
3. Keep the previous containers/images or revision available for rollback.
4. Add `/api/` routing to the existing frontend hostname. Forward it unchanged
   to the Compose `api` service on port 8000; keep all other paths routed to
   `web` on port 3000.
5. Set `NEXT_PUBLIC_API_URL=/api` or remove the value to use the built-in
   fallback. Leave `CORS_ORIGINS` blank for the target same-origin deployment.
6. Set `AUTH_COOKIE_SECURE=true` when the public entry point uses HTTPS.

## Coordinated deployment

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml up -d --build
```

The API applies the existing Alembic migrations and bootstrap checks as before;
this routing change adds no database migration. Verify:

1. `https://<ATLAS_HOST>/api/health` returns `{"status":"ok"}`.
2. Login, `/api/auth/me`, password change, refresh persistence, and logout work.
3. Customer/site context and dashboard counts load.
4. Customers, sites, assets, relationships, networks, interfaces, topology,
   profile, and permitted administration screens work.
5. Browser developer tools show only same-origin `/api/*` API requests and no
   requests to the former API hostname.
6. Test another browser and, where available, a mobile or managed corporate
   browser before removing the old API hostname.

The old public API hostname should remain available only for rollback during
validation, not as an Atlas application requirement.

## Rollback

1. Stop the updated web and API together.
2. Restore the previous reverse-proxy configuration and `.env` backup.
3. Redeploy the recorded previous matching web/API revision or image tags.
4. This release has no routing-related database migration, so a database restore
   is not normally needed. If rollback is combined with other schema changes,
   follow the database rollback procedure in
   [deployment and upgrades](../architecture/deployment-and-upgrades.md).
5. Verify the previous health, authentication, and core inventory paths before
   reopening access.

Do not claim or assume zero downtime: use a maintenance window unless your own
orchestration has tested atomic traffic switching for both services.
