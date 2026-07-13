# Atlas

Atlas is an infrastructure knowledge and documentation platform for MSPs and
internal IT teams. This repository currently contains the local runtime
scaffold for the web application, API, background worker, and discovery
plugins.

## Repository layout

```text
apps/
  api/                 FastAPI application
  web/                 Next.js application
  worker/              Python background worker placeholder
plugins/
  sdk/                 Vendor-neutral discovery plugin contracts
  proxmox/             Proxmox discovery plugin placeholder
infra/
  docker/              Docker Compose configuration
docs/                   Product and architecture documentation
```

## Prerequisites

- Docker with Docker Compose v2

Node.js and Python are only required if you want to run an individual service
outside Docker.

## Start the local stack

1. Create your local environment file:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` before starting. At minimum, replace `AUTH_SECRET_KEY` and
   `ATLAS_ADMIN_PASSWORD`. For a remote Docker host, set:

   ```dotenv
   NEXT_PUBLIC_API_URL=http://<docker-host-ip>:8000
   CORS_ORIGINS=http://<docker-host-ip>:3000
   ```

   These values are browser-facing; `localhost` only works when the browser is
   running on the Docker host itself.

2. Build and start all services:

   ```bash
   docker compose --env-file .env -f infra/docker/docker-compose.yml up --build
   ```

   API startup applies migrations and idempotently seeds the administrator from
   `ATLAS_ADMIN_EMAIL`, `ATLAS_ADMIN_PASSWORD`, and
   `ATLAS_ADMIN_DISPLAY_NAME`.

3. Open the services:

   - Web: <http://localhost:3000>
   - Login: <http://localhost:3000/login>
   - API health check: <http://localhost:8000/health>

The API health endpoint returns `{"status":"ok"}`. The worker logs
`Atlas worker is ready` once it starts.

## Seed the administrator

Atlas does not expose public registration. The API container runs the admin seed
command automatically after migrations. The command creates the configured user
only when that email is missing, so container restarts do not create duplicates.

To run the same idempotent seed manually:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml exec api \
  python -m scripts.seed_admin
```

All three `ATLAS_ADMIN_*` variables are required. Passwords must contain at
least 12 characters, are stored as Argon2 hashes, and are never logged.

## Authentication API

- `POST /auth/login` accepts JSON containing `email` and `password` and returns
  an `access_token`, `token_type`, and safe user object.
- `GET /auth/me` accepts `Authorization: Bearer <token>` and returns the
  authenticated user.
- `POST /auth/logout` retains compatibility with the earlier cookie flow. The
  MVP web logout clears its bearer token locally.
- `GET /protected` demonstrates how future routes require authentication.

The web UI stores the bearer token in `localStorage` for the MVP. `/dashboard`
validates it through `/auth/me`; missing or rejected tokens redirect to
`/login`.

Authenticated CRUD endpoints are available for:

- `/customers`
- `/sites`
- `/manual-assets`

Collection routes support `GET` and `POST`; resource routes support `GET`,
`PATCH`, and `DELETE`. The corresponding web screens are available at
`/customers`, `/sites`, and `/assets`.

The current v0 data model does not yet relate users to workspaces. Customer
creation therefore requires an existing `workspace_id`, and all authenticated
users currently have access to the same records. Workspace-scoped authorization
must be added with the tenancy model.

For local HTTP development, `.env.example` sets `AUTH_COOKIE_SECURE=false`.
Production deployments must use HTTPS and set it to `true`.

## Manual authentication test

1. Start from a fresh database and bring the stack up with `--build`.
2. Confirm the API logs report that the configured admin was created (or
   already exists after a restart).
3. Open `/login` and sign in with `ATLAS_ADMIN_EMAIL` and
   `ATLAS_ADMIN_PASSWORD`.
4. Confirm login redirects to `/dashboard` and displays the configured email
   and display name.
5. Refresh `/dashboard`; the authenticated session should remain active.
6. Select **Log out** and confirm the browser returns to `/login`.
7. Open `/dashboard` directly while logged out and confirm it redirects to
   `/login`.
8. Verify bearer authentication from a terminal:

   ```bash
   curl -X POST "$NEXT_PUBLIC_API_URL/auth/login" \
     -H 'Content-Type: application/json' \
     -d '{"email":"admin@example.com","password":"your-admin-password"}'

   curl "$NEXT_PUBLIC_API_URL/auth/me" \
     -H 'Authorization: Bearer <access_token-from-login>'
   ```

Stop the stack with `Ctrl+C`, or remove its containers and volumes with:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml down -v
```

## Run services directly

### API

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Apply database migrations before starting the API directly:

```bash
cd apps/api
alembic upgrade head
```

The API container applies pending migrations automatically when it starts. To
create a migration after changing the SQLAlchemy models, run:

```bash
cd apps/api
alembic revision --autogenerate -m "describe the schema change"
```

Run the API model tests with:

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
