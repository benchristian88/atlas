# H1 public beta installation and first-run setup

Production installation methods are **Docker Compose** and **native/systemd**.
Direct execution is for developers; manual production installation is unsupported.
Use a same-origin HTTPS reverse proxy as described in [single-origin deployment](single-origin.md).
The installer works in an SSH/LXC terminal and does not open a browser.

## Docker Compose

Prerequisites: Python 3, Docker Engine enabled at boot, and Compose v2 supporting
`up --wait`. From a fresh checkout, with no existing `.env`:

```bash
python3 infra/install/compose.py
```

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

PostgreSQL/Redis are internal services; web/API ports bind host loopback.
A proxy container may reach `web:3000` and `api:8000` on the Compose network;
a host proxy uses loopback. Preserve `/api`. Configure host Docker automatic
startup; inside an LXC this remains the operator's container/host responsibility.
All five services use `unless-stopped`, including PostgreSQL and Redis.
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
| Deployment/browser policy | `AUTH_COOKIE_SECURE` (production true), optional exact `CORS_ORIGINS` |
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

For developer host access to Compose PostgreSQL/Redis add
`-f infra/docker/docker-compose.dev.yml` after the base file. Developers may
run ordinary tests with deterministic database fixtures without any installer.
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
