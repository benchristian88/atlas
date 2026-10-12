# Routine development CI

`.github/workflows/ci.yml` runs on pull requests targeting `dev` or `main`,
pushes to either branch, and manual `workflow_dispatch`. Superseded runs for
the same PR/branch are cancelled. Every job runs on `ubuntu-24.04`.

These stable job names are intended as merge gates when branch protection is
configured separately; this change does not configure branch protection:

| Check | Required validation |
| --- | --- |
| **Backend / PostgreSQL** | Python 3.12; full API/SDK/Proxmox regression including installation, MFA, backup and release checks, real PostgreSQL/migration/nginx tests and Redis-backed restore checks; zero skipped tests; exactly one Alembic head; Python compilation. |
| **Frontend** | Node 22, `npm ci`, `npm test`, `npm run build`; Next telemetry disabled. |
| **Release & Deployment Integrity** | Canonical metadata, shared release-critical regression, actionlint 1.7.7, whitespace, committed dry-run packages, independent verifier and SHA256SUMS, extracted installer/upgrade help, protected configuration, actual production/development/packaged Compose configuration and packaged API/web/worker/runtime image builds. |

The backend uses `postgres:17-alpine` and matching PGDG PostgreSQL 17 clients.
It starts PostgreSQL after generating a protected configuration, so passwords
are random per job rather than checked-in credentials or repository secrets.
The bootstrap account creates fifteen separate databases owned by a generated
non-superuser/non-createdb role. Domain, setup, MFA and both backup test databases are
migrated; ten migration-test databases remain empty. All existing
`ATLAS_TEST_*` database variables are supplied, and JUnit skips fail the job.
Redis uses the `redis:7.4.6-alpine` Actions service with a `redis-cli ping`
healthcheck. The backend also installs the exact isolated Ansible runtime baseline and passes
`ATLAS_TEST_RUNTIME_PYTHON` for real test-only discovery/callback/cancellation.
The API test harness installs psutil for runtime-module tests; API production
requirements remain independent of runtime dependencies. Both servers publish only on runner loopback. PostgreSQL also has
a `pg_isready` healthcheck and a bounded authenticated readiness check.

Ubuntu 24.04's nginx 1.24 cannot validate the gateway's upstream `resolve`
directive. CI builds nginx 1.28.3 from an official HTTPS archive checked against
a fixed SHA-256, under runner temporary storage. The ingress suite runs that
binary against temporary copies of both production templates and disposable
loopback upstreams. The fixture checks the original Docker `listen 80` contract,
then changes only its temporary listener before **both** `nginx -t` and runtime
startup. It obtains a free port with `bind(('127.0.0.1', 0))`, requires a port
above 1024, and uses that loopback listener for both validation copies. Routing,
headers and the 2 GiB restore upload bound remain unchanged; no root nginx execution
is needed. A regression checks both generated listeners for all four fixture
variants.
The PGDG signing-key fingerprint is checked before installing signed client
packages; no server/systemd package or Atlas host installation is performed.

Checkout v7.0.1, setup-node v7.0.0 and setup-python v7.0.0 use official Node 24
Action runtimes and immutable full commit pins aligned with `release.yml`.
Atlas's frontend application/test runtime remains **Node 22**. The only
token permission is `contents: read`; checkout does not retain credentials.
There is no PR secret input, release/tag creation, registry push, publication
helper or artifact upload. Only pip's download cache and npm's lockfile-keyed
cache are retained. Credentials, database state, backup archives and generated
configuration are never cached or uploaded. Temporary protected configuration
and the PostgreSQL container/volume are removed by `always()` cleanup steps;
GitHub discards the runner and Redis service after the job.

`release.yml` remains the separate tag/manual release workflow and owns tag
validation, distribution artifacts and controlled publication. Both workflows
call `infra/ci/release-critical.sh` from `apps/api` with source SDK/Proxmox
`PYTHONPATH`, including native helper and runtime/package security regressions. I0 contract tests
run separately to avoid the existing legacy SDK pytest module-name collision.
Routine CI never requires a tag.

## Equivalent local checks

Use Python 3.12, Node 22, PostgreSQL **17** server/client tools, Redis 7 and nginx
1.28 or newer. Install regression dependencies without editable plugin installs
(tracked egg-info must remain clean for committed package construction):

```bash
python -m pip install --no-index --no-deps --require-hashes --find-links vendor/sdk -r vendor/sdk/requirements.txt
python -m pip install -r apps/api/requirements.txt pytest==8.4.1 httpx==0.28.1
export PYTHONPATH="$PWD/plugins/sdk:$PWD/plugins/proxmox"
export NEXT_TELEMETRY_DISABLED=1
```

I3 discovery acceptance uses a separate fresh runtime venv with only the vendored
canonical SDK and `apps/runtime/ansible/requirements.lock`. Runtime setup and
`pip check` use Python's `-I` mode so the backend's legacy plugin `PYTHONPATH` and
checked-in `.egg-info` metadata do not enter runtime dependency checks. The real
Ansible acceptance children use that venv's Python through `ATLAS_TEST_RUNTIME_PYTHON`.
Legacy plugin dependencies remain part of backend regression, separate from runtime.

For Docker-assisted local backend validation, use fresh disposable containers
and a protected directory. Never point these destructive PostgreSQL test suites
at an Atlas installation. If ports 5432/6379 or these container names are in
use, choose different ports/names and pass the PostgreSQL port to the helper:

```bash
ATLAS_CI_WORK=$(mktemp -d)
ATLAS_BIND_ADDRESS=127.0.0.1 python infra/install/configuration.py \
  --method docker_compose --output "$ATLAS_CI_WORK/postgres.env"
docker run --detach --name atlas-ci-postgres \
  --env-file "$ATLAS_CI_WORK/postgres.env" \
  --env POSTGRES_USER=atlas_ci_bootstrap --env POSTGRES_DB=postgres \
  --publish 127.0.0.1:5432:5432 postgres:17-alpine
docker run --detach --name atlas-ci-redis \
  --publish 127.0.0.1:6379:6379 redis:7.4.6-alpine
python infra/ci/prepare-postgres.py --config "$ATLAS_CI_WORK/postgres.env" \
  --env-file "$ATLAS_CI_WORK/backend.env"
set -a
source "$ATLAS_CI_WORK/backend.env"
set +a
export ATLAS_TEST_H3_REDIS_URL=redis://127.0.0.1:6379/0
# Set ATLAS_TEST_NGINX if the compatible test binary is outside PATH.
```

On Ubuntu 24.04, `infra/ci/install-linux-dependencies.sh` provides matching
clients/test nginx. It requires `RUNNER_TEMP`, `GITHUB_ENV` and `GITHUB_PATH`
pointing to disposable files/directories; add its emitted PostgreSQL path and
nginx environment value to the local shell. It changes only apt sources/client
packages on the host and builds test nginx in temporary storage.

From `apps/api`, run the canonical full suite and the shared release selector:

```bash
python -m alembic heads
python - <<'PY'
from alembic.config import Config
from alembic.script import ScriptDirectory
assert len(ScriptDirectory.from_config(Config('alembic.ini')).get_heads()) == 1
PY
python -m pytest tests ../../plugins/sdk/tests ../../plugins/proxmox/tests \
  -q -rs --tb=short
bash ../../infra/ci/release-critical.sh
```

All optional PostgreSQL/nginx suites should execute with **zero skips**. From
`apps/web`, run `npm ci`, `npm test` and `npm run build`. From the repository:

```bash
python -m compileall -q apps/api/app apps/api/scripts apps/api/migrations \
  apps/api/tests apps/worker/worker apps/runtime infra/install infra/release infra/ci plugins
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 \
  .github/workflows/ci.yml .github/workflows/release.yml
python infra/release/release.py metadata
python infra/release/release.py build --dry-run --output dist/release
python infra/release/release.py verify --require-committed --output dist/release
git diff-tree --check --root -m HEAD
git diff --check
```

Package construction above requires a clean committed checkout. To validate
uncommitted work locally, add `--worktree` to the dry-run build, use an output
directory outside the repository, and omit `--require-committed` from verification.
Those artifacts cannot be published. In the artifact directory, run
`sha256sum -c SHA256SUMS` (`shasum -a 256 -c SHA256SUMS` on macOS).
The [workflow](../../.github/workflows/ci.yml) contains the exact extraction,
help/configuration and Compose build commands. Always use `config --quiet`
with protected configuration so rendered credentials do not enter logs.

After backend checks, remove only the disposable containers and their temporary
files, and close the shell containing the test environment:

```bash
docker rm --force --volumes atlas-ci-postgres atlas-ci-redis
rm -rf "$ATLAS_CI_WORK"
```

## Validation scope

The browser scripts under `apps/web/scripts` require an operator-provided real
stack and Playwright module; they are separate from `npm test`. CI does not start
that stack or certify a native host's install/upgrade/reboot lifecycle.

Run `npm audit --json` separately when reassessing dependency security. Passing
regressions do not establish that dependency findings are resolved. Current CI
and supplied real-world acceptance results are recorded in historical validation,
separately from these repeatable procedures.

Repository-wide local Markdown targets and public-language boundaries are
validated in `tests/test_repository_docs.py`. Packaged-link checks run with the
release-critical regressions. Documentation changes need truthful feature claims,
valid links and balanced code fences.

For pending documentation, run `python -m pytest tests/test_repository_docs.py -q`
from `apps/api`. Its whitespace check reads root, `docs` and `.github` Markdown
directly from disk, including untracked files, and excludes dependency/generated
directories. It rejects trailing spaces/tabs, missing terminal newlines and extra
EOF blank lines. Three exact-byte snapshots preserve older hard breaks and an
older EOF blank line; editing those documents requires cleaning their whitespace.
No new document receives an exemption. Plain `git diff --check` omits untracked
files and cannot replace this check. Hosted CI also runs
`git diff-tree --check --root -m HEAD` against the committed change.

## I2 cross-repository contract and probe checks

API and runtime install the same SDK 1.1.0 wheel from `vendor/sdk` with a mandatory
SHA-256. Runtime installs it without validation extras; its config validation is
runtime-neutral and no Atlas/Ansible domain code enters the SDK. Docker build
context is repository root; native install/update and both release methods carry
the artifact and lock. Documentation tests load canonical package resources.

Run SDK tests and deterministic wheel builds in `atlas-connector-sdk`, and
Connector tests/two deterministic bundle builds in `atlas-connectors`. Their CI
is independent of Atlas's AGPL legacy plugin tests. Connector tag preparation
uses pinned Artifact Attestation and a protected environment; no remote successful
release/provenance is implied by local tests. Atlas's I2 regressions include real
PostgreSQL tenancy/ownership/crypto, I1-to-I2 migrations, portable credential
backup/restore, exact runtime verification and cleanup. Browser acceptance uses
`apps/web/scripts/check-i2-integrations-browser.mjs` against the production build;
its intercepted APIs prove UI behavior, separately from backend/source acceptance.
