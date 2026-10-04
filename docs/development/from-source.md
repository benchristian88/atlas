# Development from source

This workflow is for local development. Production operators use
[verified release packages](../deployment/installation.md).

## Repository layout

- `apps/api`: FastAPI, PostgreSQL models/migrations, domain services and tests.
- `apps/web`: Next.js UI, shared components, Node tests and browser checks.
- `apps/worker`: limited worker placeholder.
- `plugins/sdk` and `plugins/proxmox`: vendor-neutral contracts and tested adapter.
- `infra`: deployment, release and CI tooling.
- `docs`: operator guides, architecture and product reference; dated records in history.

## Local Compose stack

Prerequisites: Python 3, Docker Engine and Compose v2. From a development checkout:

```bash
cp .env.example .env
chmod 600 .env
python3 infra/install/configuration.py --add-data-encryption-key --output .env
```

Replace the development `POSTGRES_PASSWORD` and `AUTH_SECRET_KEY` in the protected
file with independent random values before starting. The signing key must be at
least 32 random characters; do not put secrets in tracked files or shared logs.
The data-key helper generates its independent key without displaying it.

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml up -d --build --wait
docker compose --env-file .env -f infra/docker/docker-compose.yml exec api \
  python -m scripts.setup_code reset
```

Open `http://127.0.0.1:3000/setup` and use the terminal code to create the first
administrator. API health is `http://127.0.0.1:3000/api/health`. Startup applies
migrations and seeds definitions, not user credentials. The default stack uses
one gateway and relative `/api` browser requests.

For intentional split-port development, add
`-f infra/docker/docker-compose.dev.yml` after the base Compose file and set:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000/api
CORS_ORIGINS=http://localhost:3001
```

That override publishes direct web on loopback 3001, API on 8000 and local
database/cache ports. Keep it out of production. See
[single-origin routing](../deployment/single-origin.md) for cookie/proxy behaviour.

## Direct processes and checks

Direct development needs Python 3.12+, Node 22+, PostgreSQL and Redis. API
requirements are in `apps/api/requirements.txt`; use a virtual environment.
Source plugin imports use `PYTHONPATH` pointing at `plugins/sdk` and
`plugins/proxmox`. Configure protected environment values for your disposable
local database, apply `alembic upgrade head`, run `python -m scripts.seed_system`,
then `python -m uvicorn app.main:app --reload` from `apps/api`.

From `apps/web`, run `npm ci` and `npm run dev`. Host-run Next uses port 3000;
configure an absolute `http://localhost:8000/api` base and exact
`http://localhost:3000` CORS origin for that split development arrangement.

See [development CI](../testing/continuous-integration.md) for canonical backend,
frontend, migration, package and workflow validation. PostgreSQL test suites
must use disposable databases. Follow [CONTRIBUTING.md](../../CONTRIBUTING.md)
and the [UI architecture](../architecture/ui-architecture.md) for changes.
