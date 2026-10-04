# Routine development CI

`.github/workflows/ci.yml` runs on pull requests targeting `dev` or `main`,
pushes to either branch, and manual `workflow_dispatch`. Superseded runs for
the same PR/branch are cancelled. Every job runs on `ubuntu-24.04`.

These stable job names are intended as merge gates when branch protection is
configured separately; this change does not configure branch protection:

| Check | Required validation |
| --- | --- |
| **Backend / PostgreSQL** | Python 3.12; full API/SDK/Proxmox regression including H1–H4, real PostgreSQL/migration/nginx tests and H3 Redis restore checks; zero skipped tests; exactly one Alembic head; Python compilation. |
| **Frontend** | Node 22, `npm ci`, `npm test`, `npm run build`; Next telemetry disabled. |
| **Release & Deployment Integrity** | Canonical metadata, shared H4 release-critical regression, actionlint 1.7.7, whitespace, committed dry-run packages, independent verifier and SHA256SUMS, extracted installer/upgrade help, protected configuration, actual production/development/packaged Compose configuration and packaged API/web/worker image builds. |

The backend uses `postgres:17-alpine` and matching PGDG PostgreSQL 17 clients.
It starts PostgreSQL after generating a protected configuration, so passwords
are random per job rather than checked-in credentials or repository secrets.
The bootstrap account creates twelve separate databases owned by a generated
non-superuser/non-createdb role. Domain, setup, MFA and both H3 databases are
migrated; seven migration-test databases remain empty. All existing
`ATLAS_TEST_*` database variables are supplied, and JUnit skips fail the job.
Redis uses the `redis:7.4.6-alpine` Actions service with a `redis-cli ping`
healthcheck. Both servers publish only on runner loopback. PostgreSQL also has
a `pg_isready` healthcheck and a bounded authenticated readiness check.

Ubuntu 24.04's nginx 1.24 cannot validate the gateway's upstream `resolve`
directive. CI builds nginx 1.28.3 from an official HTTPS archive checked against
a fixed SHA-256, under runner temporary storage. The ingress suite runs that
binary against both production templates and disposable loopback upstreams.
The PGDG signing-key fingerprint is checked before installing signed client
packages; no server/systemd package or Atlas host installation is performed.

All Actions use the same immutable official pins as `release.yml`. The only
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
`PYTHONPATH`. Its selector is unchanged from H4, including native regression;
H4's historical **228-test** result is historical evidence, not a fixed current
test count. Routine CI never requires a tag.

## Equivalent local checks

Use Python 3.12, Node 22, PostgreSQL **17** server/client tools, Redis 7 and nginx
1.28 or newer. Install regression dependencies without editable plugin installs
(tracked egg-info must remain clean for committed package construction):

```bash
python -m pip install -r apps/api/requirements.txt pytest==8.4.1 httpx==0.28.1
export PYTHONPATH="$PWD/plugins/sdk:$PWD/plugins/proxmox"
export NEXT_TELEMETRY_DISABLED=1
```

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
  apps/api/tests apps/worker/worker infra/install infra/release infra/ci plugins
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 \
  .github/workflows/ci.yml .github/workflows/release.yml
python infra/release/release.py metadata
python infra/release/release.py build --dry-run --output dist/release
python infra/release/release.py verify --require-committed --output dist/release
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

## Limitations and evidence

`npm audit` is omitted from merge gates. H4 recorded five unresolved findings
(one critical, three high, one moderate); this task changes no dependencies and
does not claim they are fixed. Run `npm audit --json` separately to reassess
them. [H4's original validation](h4-release-distribution.md) remains historical.

There is no canonical repository-wide Markdown/link linter. Existing document
generation and packaged-link regressions run in pytest; changed documentation
links are also checked locally. CI does not introduce a formatter.

The browser scripts under `apps/web/scripts` require an operator-provided real
stack and Playwright module; they are not part of `npm test`. CI does not start
that stack or claim browser, native install/upgrade/reboot, or real Debian/systemd
lifecycle acceptance. Those remain separate acceptance evidence.

Local implementation validation on 2026-10-04 used Python **3.14.7**, Node
**24.19.0**, PostgreSQL/client **17.11**, Redis **7.4.6** and a temporary nginx
**1.28.3** build on macOS:

| Executed check | Result |
| --- | --- |
| Full canonical API/SDK/Proxmox suite using the new database helper | **853 passed, zero skipped**, 151.13 seconds; JUnit has no failures/errors. Generated environment permissions and refusal to reuse an existing cluster also passed; disposable databases/processes were removed. |
| Shared H4 selector | **258 passed**, 14.96 seconds; existing deprecation warnings remain. |
| `npm ci --no-audit`, `npm test`, `NEXT_TELEMETRY_DISABLED=1 npm run build` | Locked installation, **279 passed, zero skipped**, production build passed. Audit was not rerun. |
| Both workflow YAML files, actionlint **1.7.7**, `bash -n` on CI shell helpers | Passed. Five CI contract tests also passed in the full suite and the final focused recheck. |
| `compileall`, Alembic head assertion, whitespace checks | Passed; single existing `20261004_0026` head, no migrations. |
| Metadata, `build --dry-run --worktree`, independent verifier, actual `sha256sum -c SHA256SUMS` | Both package archives and manifest passed. Local uncommitted artifacts use the explicitly non-publishable worktree mode. |
| Extracted Compose/native installer and upgrade/configuration `--help`; generated configuration validation | Passed; configuration mode **0600**. |
| Changed Markdown links and code fences | **127** local link targets passed; no unclosed code fences. |
| Upstream prerequisites | Official nginx archive SHA-256 and PGDG key fingerprint verified; both official container tags exist for Linux/amd64. |

Hosted execution of this new workflow has not occurred during implementation.
The first GitHub run must establish Python 3.12/Node 22 runner execution, signed
Linux prerequisite installation, Docker health/Compose/image builds and actual
cancellation/cache behaviour. Docker CLI/daemon and Linux systemd are unavailable
locally; no Docker config/build or native lifecycle result is claimed here.
