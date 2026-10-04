# Atlas package installation and upgrades

Obtain the matching artifact, manifest and `SHA256SUMS` from the
[official release page](https://github.com/benchristian88/atlas/releases).
[Verify checksums](releases.md#assets-and-validation) before extraction.
Packages have one versioned root. Fresh installation invokes the
installer inside that root: `python3 infra/install/compose.py` for Docker, or
`sudo python3 infra/install/native.py` on a prepared Debian/Ubuntu systemd host.
Keep the [installation prerequisites](installation.md) and proxy/one-ingress contract.
Git is no longer a production installation prerequisite.

## Before every upgrade

1. Create and download an [encrypted backup](backup-restore.md) and retain
   its passphrase separately. Retain the matching old release for recovery.
2. Verify the new release package and read release/migration notes.
3. Preserve protected configuration; never run a fresh installer against an
   existing deployment and never regenerate secrets to perform an upgrade.
4. Schedule a maintenance window, execute the supported helper below and confirm
   health, login/MFA, representative data and version/build identity afterward.

Upgrades do not perform automatic rollback. If an upgrade fails, keep traffic closed,
inspect service logs and recover using the matching release and encrypted restore procedure.
A failed upgrade does not require discarding the backup or creating new keys.

## Docker Compose upgrade

Extract the verified new Docker package into a **new directory**. From its root,
point at the absolute path of the existing protected `.env`:

```bash
python3 infra/install/upgrade.py --method docker_compose \
  --env-file /srv/atlas-current/.env --validate-only
python3 infra/install/upgrade.py --method docker_compose \
  --env-file /srv/atlas-current/.env --backup-confirmed
```

Substitute the actual existing configuration path. The file stays in place,
unchanged, including `POSTGRES_PASSWORD`, `AUTH_SECRET_KEY`,
`ATLAS_DATA_ENCRYPTION_KEY`, `ATLAS_BIND_ADDRESS`, `ATLAS_PORT`, proxy/cookie
settings and Compose project name overrides. Retain the old package directory
because it contains the protected configuration. Record the new active root and
use its Compose file together with that **same env-file** for subsequent commands.

The helper validates Compose, builds API/web/worker before stopping writers,
stops gateway/web/API/worker, then starts the new matching stack and waits for
health. It never removes volumes. The existing project name `atlas` (or an
existing `COMPOSE_PROJECT_NAME` override) preserves PostgreSQL, Redis and protected
`atlas_state` named volumes across directories. API startup applies migrations
and managed definitions before serving. Gateway configuration is loaded from the
new package. No `down -v`, setup-code reset, secret rotation or restore is part
of a normal upgrade. Do not override project identity between old/new commands.
Do not run two application stacks against the same database during migration.

Check `/api/health`, normal/MFA login and System Settings About/Updates. The
artifact-carried SHA takes precedence over the old `ATLAS_BUILD_ID` retained in
`.env`. The [single-origin](single-origin.md) gateway/NPM contract is unchanged.

## Native/systemd upgrade

Extract the verified native package **outside `/opt/atlas`**. On the prepared
supported Debian/Ubuntu host, from the new package root:

```bash
sudo python3 infra/install/upgrade.py --method systemd --validate-only
```

Create and download an [encrypted backup](backup-restore.md), then from the
same **new verified package** run:

```bash
sudo python3 infra/install/upgrade.py --method systemd --backup-confirmed
systemctl status nginx atlas-api atlas-web atlas-worker
```

The helper always reads the existing `/etc/atlas/atlas.env` and preserves it,
the database, signing/data keys, `/var/lib/atlas` protected application state and
existing service account. It stops writers, replaces only managed `apps`/`infra`
trees under `/opt/atlas`, installs matching dependencies using the existing venv,
builds standalone Next.js and repairs its cache ownership using the existing
unprivileged atlas identity. Shared installer functions install units,
reload systemd and wait for health. New API startup migrates and seeds before
serving. The helper preflights before stopping writers, installs distribution
nginx if missing, and updates only the Atlas-owned site and nginx ordering
drop-in after `nginx -t`. Invalid candidates restore previous managed files.
nginx is shared host infrastructure; unrelated nginx sites are neither deleted
nor stopped. Native web moves from loopback 3000 to 3001, API remains loopback
8000, and nginx owns the external Atlas address/port (default 3000). Other
services must leave loopback 3001 free. An old separate web upstream must be
changed to the single nginx endpoint. Health checks run through this ingress.
Host PostgreSQL/Redis are not recreated or provisioned again. Failure
leaves services stopped until operator diagnosis/recovery; there is no automatic
code/schema rollback. Keep the backup and old package before starting.

`--validate-only` checks package identity, protected configuration and complete
native preflight; it creates only a disposable venv probe, and installs no OS
packages or Atlas files. Read-only validation does not run an upgrade or exercise service lifecycle.
Native packaged upgrades and Docker-to-native restore have also been confirmed
in real Debian 13 testing; validate your own host and backup before proceeding.

The environment file is preserved byte-for-byte. For legacy files without
ingress settings, address detection and default port 3000 are used. Deliberately
add the actual `ATLAS_BIND_ADDRESS`, `ATLAS_PORT`, and any narrowly scoped
`ATLAS_TRUSTED_PROXIES` to the protected file to pin them. Legacy
`AUTH_COOKIE_SECURE=true` continues to require HTTPS; set it to `auto` deliberately
if using direct HTTP LAN access. `auto` retains Secure cookies for HTTPS forwarded
by an explicitly trusted proxy. The helper never silently downgrades an existing
policy. Keep `CORS_ORIGINS=` for same-origin access. Refresh the native site after
editing ingress settings with:

```bash
sudo python3 /opt/atlas/infra/install/native_ingress.py
```

Restart `atlas-api` after editing its cookie policy. Check the printed/access
endpoint's `/api/health`, HTTP setup/login, trusted HTTPS cookies, a multi-MiB
restore, login/MFA and installed SHA. Do not route to Next.js or expose FastAPI.

## Update awareness and offline operation

Global System Settings administrators see installed version, channel, build and
installation method in the Updates card. Normal access reads the process cache;
Check for updates deliberately requests a refresh, with a sixty-second minimum
between outbound requests. Success lasts four hours; failures last five minutes.
Requests use the fixed official public GitHub API, five-second total timeout,
three-page/300-record and combined 1 MiB bounds. No tokens or Atlas user/customer/
inventory data are sent, and no background telemetry or startup check exists.

Stable considers stable releases only; beta considers supported beta and stable
releases by SemVer, with stable winning at equal version. Drafts and invalid
versions/URLs are ignored. A locally newer build displays ahead-of-release.
Network/DNS/TLS/rate-limit/malformed-response failures show “Update information
is currently unavailable.” Atlas remains operational offline. About stays
focused on installed identity. `GET /api/system-settings/updates` and
`POST /api/system-settings/updates/check` require the existing global
`system_settings.manage` boundary and return normalized fields only.

Docker and native installations receive the matching operator upgrade guide
link on the official repository. Development installations use the development
Git workflow. Update checking provides no automatic package installation, shell execution,
Docker socket access, systemctl action, unattended restart or host control through
the application. Routine checks do not create audit noise.
