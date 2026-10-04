> **Historical validation record.** Preserved for traceability; dates, milestone names and execution results describe the original work. This is not current installation guidance or the active product roadmap.

# H1.1 Docker single-ingress correction and acceptance

**H1 / H1.1 — ACCEPTED.** User-reported real Debian Docker/LXC acceptance
proved fresh clone, production installer, generated secrets, detected LAN URL,
healthy gateway/API/web/database/cache, setup-code generation/reset, first
administrator, login/dashboard and actual LXC reboot/recovery. Direct LAN HTTP
and external Nginx Proxy Manager HTTPS worked using **one upstream only**, with
no `/api` custom location. This includes the H1.1 cookie Secure policy.
This is historical Docker ingress evidence. Subsequent real native findings and
the required fresh remediated Debian retest are recorded in the
[H4 report](h4-release-distribution.md#native-remediation-after-real-debian-13-testing).
At H1.1 validation time native/systemd had automated/static validation only; real Linux installation and
reboot remain H6/release acceptance. The implementation and original local
validation below are retained as historical evidence.

## Implementation report (A–K)

| Item | Result |
| --- | --- |
| A — Gateway | `nginx:stable-alpine`, repository-owned config and numeric IP/CIDR trust-list entrypoint. `/api` and `/api/*` retain the entire URI/query string to API 8000; all other paths reach web 3000. Docker DNS refresh handles replaced upstream containers. |
| B — Host/internal ports | Before: loopback 3000→web and 8000→API. After: only configured IPv4:port→gateway 80; API, web, PostgreSQL, Redis, worker remain unpublished. Development override deliberately retains DB 5432/cache 6379/API 8000 and direct web 3001 on loopback; gateway uses 3000. |
| C — IP detection | JSON `ip -4` inspection: unique lowest-metric default-route interface, kernel route-selected IPv4 source, and assigned global-scope address verification. No DNS or outbound packet. IPv6 ignored; missing/ambiguous/unusable routes or tool/parse failure safely use loopback with a clear message. |
| D — Bind override | Explicit `ATLAS_BIND_ADDRESS` IPv4 skips detection and is persisted. Explicit loopback or wildcard is allowed; automatic failure never chooses a wildcard. |
| E — Port | `ATLAS_PORT` defaults to 3000; validated decimal 1–65535 override is persisted and used in the access URL. |
| F — Installer output | Actual URL and one-time code after health readiness. Local-only loopback and explicit wildcard guidance. Independent database/auth secrets remain protected and absent from output/subprocess arguments. |
| G — Cookie auto mode | Docker configuration defaults to `auto`; the shared helper uses `Request.url.scheme`. Setup issue/delete, login, password change and logout all use it. `true`/`false` still force policy; native generation remains `true`. HttpOnly, SameSite=Lax, paths, token checks and Origin protections retained. |
| H — Trust boundary | Empty external allowlist by default. nginx accepts an exact forwarded http/https only from an explicitly allowlisted socket peer; otherwise it uses its own scheme. It replaces untrusted client/Host forwarding. API Uvicorn accepts sanitized headers on the unpublished trusted Compose network. Do not publish API or connect untrusted containers with this setting. Trusted edge proxies must replace browser forwarding headers. |
| I — Direct HTTP | Automated PostgreSQL setup→admin→login→authenticated context→password change→logout passes with non-Secure cookies and blank CORS. Actual nginx routes/URI/Host preservation and ignored spoofed headers pass. Real LAN browser acceptance subsequently passed on Debian. |
| J — External HTTPS | Automated trusted-Uvicorn scheme/cookie checks and PostgreSQL full lifecycle pass with Secure cookies. Real nginx accepts HTTPS indication only from an allowlisted peer and rejects malformed/chained indications. Actual TLS/NPM/browser acceptance subsequently passed on Debian. |
| K — CORS | No generated proxy domains or public URL setting. Normal single-origin CORS remains blank; existing exact split-origin compatibility remains. Custom host port is retained for existing Origin checks. |

Sanitized installer output (illustrative address/code, no real credential):

```text
Atlas is ready.

Open Atlas in your browser:

    http://192.168.3.195:3000

Enter this one-time setup code:

    XXXX-XXXX-XXXX-XXXX-XXXX

The code is required only until Atlas has been initialised.
```

No database migration, API route/response change, domain change or tenancy change
is required. The new local reset CLI `--access-url` argument is additive. Existing
RBAC, customer/site scope, SameSite, Origin and token validation remain in place.

## Validation (L–M, P)

Actual validation on macOS (Python 3.14, Node 24, disposable PostgreSQL 17).
An official nginx 1.28.0 source build under `/private/tmp` supplied the binary
because neither Docker nor nginx was installed. Tests validate the production
config with `nginx -t`, then substitute only loopback upstreams/listener/include
paths for execution; Docker DNS/container lifecycle is not simulated as passed.
The first nginx run found 64 KiB upstream zones too small for this host's larger
memory pages. Increasing them to 256 KiB fixed the config and all final checks
passed.

Commands actually executed (`apps/api` unless noted; test URL/nginx environment
variables supplied for disposable resources):

```bash
python -m pytest tests/test_setup_postgres.py tests/test_auth.py \
  tests/test_docker_ingress.py tests/test_release_foundation.py -q
python -m pytest tests/test_nginx_gateway.py -q -x --tb=short
python -m pytest tests ../../plugins/sdk/tests ../../plugins/proxmox/tests -q -rs --tb=short
python -m alembic heads
# apps/web
npm test
npm run build
# repository root
python -m compileall -q apps/api/app apps/api/scripts infra/install
git diff --check
```

- Focused PostgreSQL/setup/auth/installer suite: **114 passed**.
- Actual nginx configuration/routing/header-trust suite: **26 passed**.
- Full backend/plugin suite, including nginx and PostgreSQL: **587 passed,
  6 skipped**. Skips are existing optional empty-database migration tests for
  Asset Category, Presentation, H1 release migration, Topology Layers, Topology
  Positions and Topology Roles. No schema changes were made in H1.1.
- Frontend: **269 passed**, production build **passed** (including `/setup`).
- Migration graph: exactly **20261004_0025 (head)**; no new migration required.
- Python compilation and **71** local Markdown link targets: **passed**.
- YAML parsing and production/development service, sole published port, restart,
  health and secrets/output contracts: **passed** in automated tests.
- `git diff --check`: **clean**.

Not executed here: `docker compose config`, container/image build/start,
Docker DNS/recreation and host/LXC reboot, remote LAN browser or real NPM/TLS
acceptance. This macOS host has no Docker. Exact Linux commands follow below.
Local nginx plus real PostgreSQL lifecycle tests verify complementary layers;
they do not claim the complete remote Docker/TLS browser journey passed.

## Documentation and material files (N)

- `infra/docker/docker-compose.yml`, `infra/docker/gateway/default.conf`,
  `infra/docker/gateway/15-atlas-trusted-proxies.sh`: ingress, health, header
  sanitization, proxy trust and sole host port.
- `infra/docker/docker-compose.dev.yml`: deliberate development ports and narrowed
  loopback API forwarding trust.
- `infra/install/configuration.py`, `infra/install/compose.py`: route inspection,
  validated/persisted ingress settings and actual installer URL.
- `apps/api/app/auth.py`, `apps/api/app/routes/auth.py`,
  `apps/api/app/routes/setup.py`: request-scheme cookie policy at every issue/delete.
- `apps/api/scripts/setup_code.py`: actual access URL with one-time code output.
- `apps/api/tests/test_docker_ingress.py`, `apps/api/tests/test_nginx_gateway.py`,
  `apps/api/tests/test_auth.py`, `apps/api/tests/test_setup_postgres.py`,
  `apps/api/tests/test_release_foundation.py`: detection/configuration/output,
  Compose contracts, actual nginx and setup/auth security regression.
- `README.md`, `docs/deployment/h1-installation.md`,
  `docs/deployment/single-origin.md`, `docs/deployment/reverse-proxy-examples.md`,
  `docs/deployment/split-origin-migration.md`: source acquisition, single upstream,
  direct access, cookie policy and proxy trust; native differences explicit.
- `docs/architecture/deployment-and-upgrades.md`,
  `docs/architecture/authentication-and-access-control.md`: actual deployment and
  authentication boundary.
- `docs/product/feature-ledger.md`: implemented correction with Linux revalidation
  accepted; recorded user-reported H1/H1.1 Linux evidence and separate native limitation.
- `docs/testing/h1-release-foundation.md`: historical H1 baseline clearly linked
  to this correction; original evidence retained.
- `docs/testing/h1-docker-ingress.md`: completion evidence and exact Linux steps.

## Real Debian Docker/LXC acceptance (O)

Use the existing LXC for an update, preserving its configuration/data. The fresh
installer is intentionally exclusive: on an existing installation,
`python3 infra/install/compose.py` must refuse to overwrite `.env`. Do not delete
that file or regenerate credentials to bypass the refusal. Update to the H1.1
checkout, retain signing/database secrets and volumes, and edit only ingress/
policy keys in the protected file:

```dotenv
ATLAS_BIND_ADDRESS=<actual-default-route-LAN-IPv4>
ATLAS_PORT=3000
AUTH_COOKIE_SECURE=auto
ATLAS_TRUSTED_PROXIES=
CORS_ORIGINS=
```

Confirm the address with `ip -j -4 route show default` and
`ip -j -4 route get 1.1.1.1`. A supported release version belongs in permanent
installation guidance; this feature branch is only a development test artifact.

For **fresh installer/setup acceptance**, use a separate disposable Linux
installation with no existing Atlas `.env` or volumes. Acquire source and select
the version as in [installation](../../deployment/installation.md), then run:

```bash
python3 infra/install/compose.py
```

Verify the printed URL contains that LXC's actual LAN address/port, and the
terminal prints only its one-time setup code, with no database/auth secret.
Test a second disposable installation with explicit bind/port overrides if
needed; do not overwrite the existing initialized installation.

For either fresh install or the existing-install update, run from the checkout:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml config --quiet
docker compose --env-file .env -f infra/docker/docker-compose.yml up -d --build --wait
docker compose --env-file .env -f infra/docker/docker-compose.yml ps
docker compose --env-file .env -f infra/docker/docker-compose.yml port gateway 80
docker compose --env-file .env -f infra/docker/docker-compose.yml exec -T gateway nginx -t
```

`config --quiet` avoids printing resolved deployment secrets. Expect six services
running, gateway/API/web/PostgreSQL/Redis healthy, and the existing worker
running (it has no separate healthcheck). The sole host mapping is actual LAN
IP:3000→gateway:80. API/web/database/cache have no host port. `EXPOSE` metadata or
an unbound container port shown by `ps` is not a published host socket.

From **another LAN device** (replace IP/port):

```bash
curl -fsS http://<actual-ip>:3000/api/health
```

Expect `{"status":"ok"}`. Open `http://<actual-ip>:3000` in the browser. On a
fresh instance, verify `/setup`, code verification, first administrator creation,
sign in, dashboard, context selection and authenticated navigation. Cookies must
be HttpOnly/SameSite=Lax and **not Secure** on HTTP. On the existing initialized
instance, verify login/dashboard and that setup/reset remain closed. Browser
Network must show same-origin `/api/*`, with no requests to port 8000 and no CORS
configuration required. A request with an unapproved Origin must still fail.

For HTTPS/NPM acceptance, edit only:

```dotenv
ATLAS_TRUSTED_PROXIES=<actual-NPM-source-IP-seen-by-gateway>
```

Recreate the gateway using `up -d gateway`. Configure NPM **one Proxy Host**:
chosen domain → `http://<actual-ip>:3000`, TLS configured normally, Custom
Locations empty. No `/api` location. Leave Atlas CORS blank. The source allowlist
must identify the actual socket peer, including any NAT translation; do not
allowlist an entire LAN for convenience. The external proxy must set verified
Host/protocol/client headers rather than accept browser-supplied indications.

From another LAN device:

```bash
curl -fsS https://<domain>/api/health
```

Expect `{"status":"ok"}`. Open `https://<domain>/`, verify normal login,
dashboard and authenticated navigation. Inspect `atlas_session` in browser
cookie tools: **Secure**, HttpOnly and SameSite=Lax. On a separately fresh HTTPS
instance, verify setup authorization is also Secure and the full setup succeeds.
A direct HTTP request sending `X-Forwarded-Proto: https` from a non-allowlisted
peer must still issue a non-Secure cookie in auto mode; malformed forwarded
protocol from the trusted peer must not select HTTPS.

Finally reboot the Docker host/LXC normally. After it returns, repeat `ps`,
HTTP/HTTPS health, login and dashboard checks. Verify gateway also returned
without a manual start and all six services retain `unless-stopped`. Do not
intentionally stop containers before this reboot test: that policy preserves an
operator's explicit stop. Never use `down -v` as part of this acceptance.

## Repository state (Q)

No commit, push, merge or rebase performed. Command actually executed:
`git status --short`.

```text
 M README.md
 M apps/api/app/auth.py
 M apps/api/app/routes/auth.py
 M apps/api/app/routes/setup.py
 M apps/api/scripts/setup_code.py
 M apps/api/tests/test_auth.py
 M apps/api/tests/test_release_foundation.py
 M apps/api/tests/test_setup_postgres.py
 M docs/architecture/authentication-and-access-control.md
 M docs/architecture/deployment-and-upgrades.md
 M docs/deployment/h1-installation.md
 M docs/deployment/reverse-proxy-examples.md
 M docs/deployment/single-origin.md
 M docs/deployment/split-origin-migration.md
 M docs/product/feature-ledger.md
 M docs/testing/h1-release-foundation.md
 M infra/docker/docker-compose.dev.yml
 M infra/docker/docker-compose.yml
 M infra/install/compose.py
 M infra/install/configuration.py
?? apps/api/tests/test_docker_ingress.py
?? apps/api/tests/test_nginx_gateway.py
?? docs/testing/h1-docker-ingress.md
?? infra/docker/gateway/
```
