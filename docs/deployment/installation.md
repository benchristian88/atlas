# Installation and first-run setup

Production installation methods are **Docker Compose** and **native/systemd**.
Direct execution is for developers; manual production installation is unsupported.
Both installers provide direct single-origin LAN access and support an optional HTTPS
reverse proxy as described in [single-origin deployment](single-origin.md).
The installer works in an SSH/LXC terminal and does not open a browser.
Both methods include the authenticated isolated [local integration runtime](integration-runtime.md)
by default; `--manual-only` preserves explicit manual-only operation.

## Docker Compose

Prerequisites: Python 3, Linux `iproute2`, Docker Engine enabled at boot,
and Compose v2 supporting `up --wait`. Download the versioned Docker Compose
package, release manifest and `SHA256SUMS` from the [official releases](https://github.com/benchristian88/atlas/releases),
[verify before extraction](releases.md#assets-and-validation), then from its
versioned root run:

```bash
python3 infra/install/compose.py
```

Git is not required for a packaged installation. See [packaged upgrades](upgrades.md)
for existing deployments; run the fresh installer only for a new installation.
The fresh installer requires no existing `.env`; it refuses existing files.

The helper creates package-root `.env` with mode `0600`, independently
generates a 256-bit PostgreSQL password, 384-bit session-signing key and independent
256-bit MFA data-encryption key, builds
the stack, waits for health, and prints one setup code. Secrets are never
displayed. An existing file, including an empty file or symlink, is refused.
There is no automatic overwrite or credential rotation. If installation stops
after configuration creation, retain the file and resume:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml up -d --build --wait
docker compose --env-file .env -f infra/docker/docker-compose.yml exec api \
  python -m scripts.setup_code reset
```

Only the nginx gateway publishes a host port. It routes `/api` and `/api/*`
unchanged to `api:8000`, and all other paths to `web:3000`. API, web, PostgreSQL,
Redis, worker and runtime have no host ports. The runtime uses a separate internal
network and a durable independently generated control-secret volume. The installer inspects Linux IPv4 default
routes, chooses the unique interface with the lowest route metric, obtains the
kernel-selected source address without sending packets or using DNS, and checks
that it is a suitable global-scope IPv4 address assigned to that interface.
IPv6 routes do not affect this choice. Ambiguous routes, loopback/link-local or
unusable sources, missing `ip`, and inspection failure fall back to `127.0.0.1`
with a local-only message. Detection never falls back to `0.0.0.0`.

Generated `ATLAS_BIND_ADDRESS` is the detected LAN IPv4 address and `ATLAS_PORT`
is `3000`. Explicit IPv4 and port overrides are validated and persisted:

```bash
ATLAS_BIND_ADDRESS=192.0.2.10 ATLAS_PORT=4300 python3 infra/install/compose.py
```

The IP above is illustrative. After all services pass health checks, the helper
prints the actual `http://<bind-address>:<port>` followed by the one-time setup
code. Loopback URLs are identified as local-only. An explicit `0.0.0.0` is allowed
but requires using the host's actual LAN address in the browser. Database/auth
secrets are never displayed. Open the printed URL from another LAN device for
setup, login and normal authenticated navigation; the browser uses `/api` on
that same port, without CORS or port 8000.

For an external HTTPS proxy, configure **one upstream** pointing at this gateway
and set `ATLAS_TRUSTED_PROXIES` in `.env` to its actual source IP (or a narrow
CIDR), comma-separated without spaces if multiple. Recreate the gateway after
changing this list. No NPM custom `/api` location or external hostname setting is
needed. The gateway ignores forwarded protocol/client headers from other peers.
A trusted proxy must replace incoming `X-Forwarded-Proto` and client forwarding
headers with its own verified values. See [reverse-proxy examples](reverse-proxy-examples.md).

Configure host Docker automatic startup; inside an LXC this remains the
operator's container/host responsibility. All persistent services use `unless-stopped`,
including gateway, PostgreSQL and Redis.
Health dependencies govern initial startup; the API independently retries
database readiness with a bounded increasing delay and migrates before serving.
Restart policies handle subsequent failures and reboot. Intentionally stopped
containers remain stopped; explicitly start them when wanted.

To replace a lost setup code, run the same `exec api ... setup_code reset` command
above. It invalidates the previous code and all setup cookies, and prints the new
code once to the local terminal. It refuses initialized instances and has no
force flag. It is not a password-reset tool.

## Native/systemd

The supported helper targets Debian/Ubuntu Linux booted with systemd. Prepare
Python >=3.12 with working venv/ensurepip (`python3-venv` for that interpreter),
Node.js >=22 at `/usr/bin/node`, npm, matching PostgreSQL 16/17 server/client tools
(`psql`, `pg_dump`, `pg_restore`), and Redis. PostgreSQL (`postgresql.service`)
and Redis (`redis-server.service`) must already be running; local postgres peer
administration and Atlas password host authentication are required. `runuser`
and `useradd` must be available. These remain explicit host prerequisites; Atlas
does not add a third-party Node repository or install them automatically.

The installer **installs nginx itself when absent**, using `apt-get install
--yes --no-install-recommends nginx` from the host's configured distribution
packages. It adds no repository and executes no remote installer script.
Prepare current apt package indexes/network access; preflight simulates package
installation first. Existing nginx must have its distribution systemd service
and pass `nginx -t`. TLS remains optional operator configuration.

Download the native/systemd package, release manifest and `SHA256SUMS` from the
[official releases](https://github.com/benchristian88/atlas/releases) and
[verify before extraction](releases.md#assets-and-validation). From the verified
package root on the prepared host:

```bash
sudo python3 infra/install/native.py
```

`--help` exits successfully before host checks or installation work. Complete
preflight reports useful missing requirements together, without subprocess
tracebacks. It checks root/host, service/tool/version availability, a disposable
venv creation with the invoking Python, protected filesystem locations, account/
group, existing installation/state/units, PostgreSQL role/database conflicts,
bind/port availability, nginx package installability and source/template inputs.
The temporary venv is removed. All checks precede Atlas account, configuration,
code, database or unit creation. nginx package failure also precedes those steps;
apt itself may retain package-manager changes and needs operator diagnosis.

The helper refuses existing `/opt/atlas` or `/etc/atlas/atlas.env`. It creates or
uses an unprivileged `atlas` service account, installs code and dependencies at
`/opt/atlas`, builds standalone Next.js output, and creates
`/etc/atlas/atlas.env` owned by root and group atlas, mode `0640`, inside a `0750`
directory. Group read is required for local management by the service identity.
Secrets use the same independent randomness as Compose and never enter process
arguments. PostgreSQL provisioning passes its credential on stdin and refuses
an existing Atlas role/database; it never changes existing database credentials.

The helper installs `atlas-api`, `atlas-web`, `atlas-worker` and the separately
isolated `atlas-runtime` units, reloads
systemd and enables/starts them and the required local PostgreSQL/Redis services.
Units use `WantedBy=multi-user.target`, `Restart=on-failure`, a 15-second retry
delay, start-rate limits and an unprivileged account. API readiness retries
accommodate delayed PostgreSQL. FastAPI stays on `127.0.0.1:8000`, and native-only
Next.js uses `127.0.0.1:3001`. Bundled nginx owns the external endpoint at the
same detected default-route IPv4 address and default port 3000 as Docker, with
safe `127.0.0.1` fallback. Explicit `ATLAS_BIND_ADDRESS`/`ATLAS_PORT` overrides
are supported; native refuses wildcard/unusable addresses and private ports
3001/8000. `/api` and `/api/*` keep their prefix; everything else goes to web.
Only `/etc/nginx/conf.d/atlas.conf` and the nginx systemd ordering drop-in
`/etc/systemd/system/nginx.service.d/atlas.conf` are managed. Other sites and
operator configuration remain in place. Root-owned managed paths reject links
and non-Atlas files. `nginx -t` runs before activation; failed candidates restore
previous managed configuration. nginx is enabled at boot and ordered after API/web.

Restore upload routes stream up to the 2 GiB backup cap; ordinary requests allow 20 MiB.
The helper checks health through nginx, then prints successful installation,
the actual usable HTTP URL and the same local one-time setup-code handoff as
Docker. Loopback-only URLs are clearly labelled. No browser launch is attempted.
Fresh native configuration uses `AUTH_COOKIE_SECURE=auto`: direct HTTP works;
HTTPS through an allowlisted external proxy keeps Secure cookies. Native Uvicorn
trusts only loopback; nginx ignores external forwarding unless the peer appears
in the empty-by-default `ATLAS_TRUSTED_PROXIES` list. See
[reverse-proxy configuration](reverse-proxy-examples.md#nativesystemd).
The existing worker owns bounded generic discovery dispatch/recovery and fixed
schedules, with PostgreSQL authoritative and Redis as disposable hints. Its
filtered native environment excludes user/session authentication secrets.
Only the web cache is writable by its hardened service.

Local lost-code reset:

```bash
sudo -u atlas /opt/atlas/venv/bin/python \
  /opt/atlas/infra/install/manage.py setup-code reset
```

The wrapper reads the protected file without shell evaluation. The same
initialized refusal applies. Inspect lifecycle failures with
`systemctl status nginx atlas-api atlas-web atlas-worker` and `journalctl -u atlas-api`.
An interrupted fresh native install needs operator diagnosis of retained paths;
the helper will not overwrite or remove them automatically.

## First-run browser experience

Open `/setup`, enter the terminal code, choose **Set up a new Atlas**, and enter
name/email/password/confirmation. The code uses five four-character groups
with 100 bits of entropy; hyphens/case are presentation only. Only Argon2
verification material is stored. The raw code never enters browser storage,
URLs, audit details, startup logs or API response bodies. Protect the terminal
output as a temporary installation credential.

Verification issues a separate ten-minute HttpOnly/SameSite=Lax setup cookie
with the deployment's Secure policy. Five failures impose a database-backed
fifteen-minute lockout. Creation uses the existing password policy and global
Master Administrator role. Account, assignment, context, audit and initialization
commit together under a singleton row lock. Success clears the verifier and
invalidates every setup authorization, then opens normal sign in. Alternatively,
choose [encrypted fresh restore](backup-restore.md)
with the same one-time setup authorization. Restore uses existing accounts and
does not create a new administrator.

## Configuration classification

| Category | Configuration |
| --- | --- |
| Required generated production secrets | `POSTGRES_PASSWORD`, `AUTH_SECRET_KEY`, `ATLAS_DATA_ENCRYPTION_KEY` |
| Deployment/browser policy | Both installers generate `AUTH_COOKIE_SECURE=auto` (HTTP non-Secure, trusted HTTPS Secure); explicit `true`/`false` overrides preserved on upgrade; optional exact `CORS_ORIGINS` for deliberate split origins only |
| Bundled ingress | `ATLAS_BIND_ADDRESS` (IPv4), `ATLAS_PORT` (1–65535, default 3000; native reserves 3001/8000), `ATLAS_TRUSTED_PROXIES` (empty by default; explicit external proxy IP/CIDR list) |
| Artifact/install identity | `ATLAS_INSTALL_METHOD`, `ATLAS_BUILD_ID`; canonical version/channel in `apps/api/app/release.json` |
| Standard internal defaults | DB/user `atlas`; Compose DB host `postgres`, Redis `redis://redis:6379/0`, browser API `/api` |
| Advanced bootstrap overrides | `DATABASE_URL`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `REDIS_URL`, `NEXT_PUBLIC_API_URL` as appropriate; custom URLs remain external |
| Atlas System Settings | `auth.session_minutes`, labelled Session lifetime, integer 1–10080, default 480 |
| Development only | `NEXT_ALLOWED_DEV_ORIGINS`, `.env.example` credentials and HTTP cookie setting |
| Retired | `AUTH_SESSION_MINUTES`, `ATLAS_BOOTSTRAP_ADMIN_EMAIL/PASSWORD/NAME`, deprecated `ATLAS_ADMIN_*` |

Compose derives the database connection safely using SQLAlchemy URL encoding;
operators need not construct a URL. The supported native Redis service is local;
the worker uses Redis dispatch hints and scans durable PostgreSQL intent when
Redis is unavailable.
The web service receives browser-public configuration only. Signing secrets stay
outside PostgreSQL and are not a future TOTP/data-encryption key.

For developer split ports and host access to Compose PostgreSQL/Redis add
`-f infra/docker/docker-compose.dev.yml` after the base file. Developers may
reach direct API on loopback port 8000 and direct web on loopback port 3001
(the gateway keeps 3000), or run ordinary tests without any installer. For split
ports, set the absolute API base and exact web CORS origin as documented.
Never copy the development environment into a production deployment.

## Upgrades and compatibility

Use the [packaged upgrade guide](upgrades.md). Run `upgrade.py` from the **new
verified release package**, preserve deployment configuration and make an
encrypted backup before replacing application code. Do not use `git pull`,
manually overwrite `/opt/atlas`, or rerun the fresh installer over an installation.

Existing users and password hashes remain intact. An instance with existing
users is initialized and cannot reopen first-run setup by deleting accounts.
The singleton installation migration is `20261004_0025`; production startup
applies migrations and managed definitions before serving. Local MFA additionally
uses the independent data key described in [MFA configuration](mfa.md).

Native installation targets Debian/Ubuntu hosts meeting the prerequisites above;
the installer checks distribution identity and capabilities, not a blanket list
of supported version numbers. Real Debian 13 testing used Python 3.13, Node 22,
PostgreSQL 17 and Redis, including a Docker-created backup restored into native
Atlas and a packaged native upgrade. These supplied results do not certify every
distribution/version combination. Node 22+ may require a suitable upstream or
system package because the distribution default may be older; prepare it safely
before running Atlas. Do not use an unreviewed root `curl | bash` installer.

## Stop or remove an installation

For Docker, run from the active package root with the existing protected env-file:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml down
```

This stops/removes containers while retaining named volumes. After an upgrade,
use the recorded existing env-file path. Retain `postgres_data`, `atlas_state`
and protected configuration for recovery. `down -v` destroys those volumes;
use it only for deliberate data destruction after an independently verified backup.

Native has no automated uninstall helper. Stop and disable the Atlas units when
decommissioning, then deliberately review the Atlas-owned code, configuration,
state, database/role, units and nginx files. Do not remove shared PostgreSQL,
Redis or nginx or unrelated nginx sites as part of Atlas removal. Retain the
encrypted backup and deployment configuration until recovery is no longer needed.
