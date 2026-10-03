# H1 public beta installation and first-run setup

Production installation methods are **Docker Compose** and **native/systemd**.
Direct execution is for developers; manual production installation is unsupported.
Docker provides direct single-origin LAN access and supports an optional HTTPS
reverse proxy as described in [single-origin deployment](single-origin.md).
Native/systemd still requires an operator-configured host reverse proxy.
The installer works in an SSH/LXC terminal and does not open a browser.

## Docker Compose

Prerequisites: Git, Python 3, Linux `iproute2`, Docker Engine enabled at boot,
and Compose v2 supporting `up --wait`. Until formal release packaging exists,
acquire the source and select the supported release tag or commit (substitute
repository and version values):

```bash
git clone <repository-url> atlas
cd atlas
git switch --detach <supported-release-tag-or-commit>
python3 infra/install/compose.py
```

For a supported release branch, use `git switch <supported-release-branch>`
instead. Use the version supplied with the release, not a development feature
branch. Future release packaging will replace source checkout where appropriate.
The fresh installer requires no existing `.env`; it refuses existing files.

The helper creates root-of-checkout `.env` with mode `0600`, independently
generates a 256-bit PostgreSQL password and 384-bit session-signing key, builds
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
Redis and worker have no host ports. The installer inspects Linux IPv4 default
routes, chooses the unique interface with the lowest route metric, obtains the
kernel-selected source address without sending packets or using DNS, and checks
that it is a suitable global-scope IPv4 address assigned to that interface.
IPv6 routes do not affect this choice. Ambiguous routes, loopback/link-local or
unusable sources, missing `ip`, and inspection failure fall back to `127.0.0.1`
with a local-only message. Detection never falls back to `0.0.0.0`.

Generated `ATLAS_BIND_ADDRESS` is the detected LAN IPv4 address and `ATLAS_PORT`
is `3000`. Explicit IPv4 and port overrides are validated and persisted:

```bash
ATLAS_BIND_ADDRESS=192.168.3.195 ATLAS_PORT=4300 python3 infra/install/compose.py
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
operator's container/host responsibility. All six services use `unless-stopped`,
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

The supported helper targets Debian/Ubuntu Linux with systemd and these installed
prerequisites: Python >=3.12 with venv support, Node.js >=22 at `/usr/bin/node`, npm,
PostgreSQL (`postgresql.service`, local peer administration / password host
authentication), Redis (`redis-server.service`) and `runuser`/`useradd`.
Dependency package installation and TLS/proxy configuration remain host
preparation; use the helper for Atlas installation rather than a manual
production procedure.

From a fresh checkout on the prepared host:

```bash
sudo python3 infra/install/native.py
```

The helper refuses existing `/opt/atlas` or `/etc/atlas/atlas.env`. It creates or
uses an unprivileged `atlas` service account, installs code and dependencies at
`/opt/atlas`, builds standalone Next.js output, and creates
`/etc/atlas/atlas.env` owned by root and group atlas, mode `0640`, inside a `0750`
directory. Group read is required for local management by the service identity.
Secrets use the same independent randomness as Compose and never enter process
arguments. PostgreSQL provisioning passes its credential on stdin and refuses
an existing Atlas role/database; it never changes existing database credentials.

The helper installs `atlas-api`, `atlas-web`, and `atlas-worker` units, reloads
systemd and enables/starts them and the required local PostgreSQL/Redis services.
Units use `WantedBy=multi-user.target`, `Restart=on-failure`, a 15-second retry
delay, start-rate limits and an unprivileged account. API readiness retries
accommodate delayed PostgreSQL. Web/API bind loopback; proxy them through HTTPS.
The worker remains the existing limited worker boundary, not new orchestration.
Only the web cache is writable by its hardened service.

Local lost-code reset:

```bash
sudo -u atlas /opt/atlas/venv/bin/python \
  /opt/atlas/infra/install/manage.py setup-code reset
```

The wrapper reads the protected file without shell evaluation. The same
initialized refusal applies. Inspect lifecycle failures with
`systemctl status atlas-api atlas-web atlas-worker` and `journalctl -u atlas-api`.
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
invalidates every setup authorization, then opens normal sign in. Restore
Backup is visible but disabled until its later implementation; H1 supplies no
fake restore endpoint.

## Configuration classification

| Category | Configuration |
| --- | --- |
| Required generated production secrets | `POSTGRES_PASSWORD`, `AUTH_SECRET_KEY` |
| Deployment/browser policy | Docker `AUTH_COOKIE_SECURE=auto` (HTTP non-Secure, trusted HTTPS Secure); explicit `true`/`false` overrides; native default `true`; optional exact `CORS_ORIGINS` for deliberate split origins only |
| Docker ingress | `ATLAS_BIND_ADDRESS` (IPv4), `ATLAS_PORT` (1–65535, default 3000), `ATLAS_TRUSTED_PROXIES` (empty by default; explicit external proxy IP/CIDR list) |
| Artifact/install identity | `ATLAS_INSTALL_METHOD`, `ATLAS_BUILD_ID`; canonical version/channel in `apps/api/app/release.json` |
| Standard internal defaults | DB/user `atlas`; Compose DB host `postgres`, Redis `redis://redis:6379/0`, browser API `/api` |
| Advanced bootstrap overrides | `DATABASE_URL`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `REDIS_URL`, `NEXT_PUBLIC_API_URL` as appropriate; custom URLs remain external |
| Atlas System Settings | `auth.session_minutes`, labelled Session lifetime, integer 1–10080, default 480 |
| Development only | `NEXT_ALLOWED_DEV_ORIGINS`, `.env.example` credentials and HTTP cookie setting |
| Retired | `AUTH_SESSION_MINUTES`, `ATLAS_BOOTSTRAP_ADMIN_EMAIL/PASSWORD/NAME`, deprecated `ATLAS_ADMIN_*` |

Compose derives the database connection safely using SQLAlchemy URL encoding;
operators need not construct a URL. The supported native Redis service is local;
its worker is currently a placeholder and does not require runtime Redis access.
The web service receives browser-public configuration only. Signing secrets stay
outside PostgreSQL and are not a future TOTP/data-encryption key.

For developer split ports and host access to Compose PostgreSQL/Redis add
`-f infra/docker/docker-compose.dev.yml` after the base file. Developers may
reach direct API on loopback port 8000 and direct web on loopback port 3001
(the gateway keeps 3000), or run ordinary tests without any installer. For split
ports, set the absolute API base and exact web CORS origin as documented.
Never copy the development environment into a production deployment.

## Upgrade compatibility

Revision `20261004_0025` adds singleton installation state and the session setting.
Existing users/password hashes and application data remain unchanged. Any
existing user marks the installation initialized; deleting/ disabling accounts
does not reopen setup. Fresh empty databases start uninitialized. Keep existing
database and signing secrets when upgrading; remove retired credentials. The
session setting begins at 480: set a previous customized environment duration in
System Settings after upgrade if required. Existing signed tokens retain their
expiry; newly issued login/password-change cookies read the database value.

No graph, inventory, tenancy or domain semantics change. `/api/setup/*` and
the globally authorized `/api/system-settings/build-info` are additive APIs.
About exposes version/channel/build/install identity without deployment secrets.
No Git is required at runtime; Compose embeds the build ID in its image and
native configuration carries it from installation. Update checking, TOTP,
backup/restore engines and the final security review remain later passes.

## H1.1 update of an existing Docker installation

Retain the existing `.env`, signing/database secrets and named volumes. The
fresh installer deliberately refuses an existing environment; do not regenerate
credentials to update an initialized installation. Add the actual LAN IPv4
`ATLAS_BIND_ADDRESS`, `ATLAS_PORT=3000`, `AUTH_COOKIE_SECURE=auto`, and optionally
`ATLAS_TRUSTED_PROXIES=<external-proxy-source-IP>` to the protected file. Keep
`CORS_ORIGINS` blank for same-origin use. Then run the documented Compose
`up -d --build --wait` command. Existing explicit `true`/`false` policies remain
supported; `true` requires HTTPS for browser setup/login. Update an external
proxy to use only the gateway upstream and remove its old separate API location.
No H1.1 database migration is required. Existing users and initialized setup
closure remain intact. Native/systemd receives no Docker gateway or ingress
redesign. Repeat the [H1.1 Linux acceptance](../testing/h1-docker-ingress.md).
