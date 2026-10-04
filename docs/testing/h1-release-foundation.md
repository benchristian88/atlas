# H1 release foundation: validation and completion report

> **H1 — ACCEPTED**, including H1.1, on real Debian Docker/LXC (user-reported acceptance). Fresh clone and production installer, independent generated secrets, LAN URL, healthy gateway/application/database/cache, setup generation/reset, first administrator, login/dashboard, actual LXC reboot/recovery, direct LAN access and external Nginx Proxy Manager with **one upstream and no `/api` custom location** passed.
>
> The original execution evidence below is retained. Subsequent real Debian 13 native testing exposed preflight/partial-install, ingress/URL, HTTP-cookie and restore-upload failures; [H4 remediation](h4-release-distribution.md#native-remediation-after-real-debian-13-testing) records the supplied findings and corrections. Fresh remediated Linux lifecycle acceptance remains required. [H1.1 evidence](h1-docker-ingress.md) records the accepted Docker ingress correction.

Validation date: 2026-10-04. Branch: `feature/release-foundation`.
Starting commit: `52365fb69a741381a58ee216f867a2bf546f9381`.
No commit, push, merge, rebase or history rewrite was performed.

## Delivered behavior and configuration (B–R)

- **B — Database:** additive revision `20261004_0025`, parent `20261004_0024`.
  Adds constrained singleton `installation_state` and seeds the existing
  `system_settings` table with `auth.session_minutes=480`. No inventory,
  knowledge, topology, credential or historical record is remapped/deleted.
- **C — Canonical version:** `apps/api/app/release.json`, version `0.1.0`,
  release channel `beta`. Frontend package metadata no longer drives About.
- **D — Exposed metadata:** global-settings-authorized
  `GET /api/system-settings/build-info` and About expose `version`,
  `release_channel`, `build_id`, and `install_method`. Build identity is captured
  from Git when available by installation tooling, carried in the API image or
  native configuration, and needs no runtime Git. Missing identity is explicit.
- **E — Installation method:** constrained to `docker_compose`, `systemd`, or
  `development`. Production generators emit the supported production method;
  the development example identifies itself separately.
- **F — Environment changes:** retains external database/Redis connectivity,
  public API base, signing key, cookie/CORS policy and install metadata.
  Standard Compose supplies DB/user `atlas`, DB host `postgres`, Redis
  `redis://redis:6379/0`, and API base `/api` internally. `DATABASE_URL` remains
  an advanced override and is safely derived otherwise. `NEXT_ALLOWED_DEV_ORIGINS`
  is development-only. Both environment admin credential groups are retired.
  `AUTH_SESSION_MINUTES` is ignored and removed from supported templates.
- **G — Compose secrets:** independent cryptographic `token_hex(32)` database
  password (256 bits) and `token_hex(48)` signing key (384 bits), generated into
  `.env` by exclusive creation, mode `0600`; existing/empty files and symlinks
  refuse overwrite. Neither secret is displayed. No development password is
  a production fallback. No secret enters the web build/environment.
- **H — Native secrets:** same generator, `/etc/atlas/atlas.env`, root:atlas
  `0640`, directory `0750`. PostgreSQL provisioning consumes stdin and suppresses
  credential-bearing SQL statement/error logging. No secret is a process
  argument. Atlas services use an unprivileged account. Fresh installation
  refuses existing install/configuration or Atlas PostgreSQL role/database.
- **I/J — Setup code/verifier:** 20 independent characters from a 32-character
  alphabet, five groups of four, 100 bits, avoiding I/O/0/1. Hyphens/case are
  presentation only. PostgreSQL persists an Argon2 verifier, never the raw code.
  The code appears once in local installer/reset terminal output.
- **K — Setup authorization:** ten-minute, HttpOnly/SameSite=Lax `atlas_setup`
  cookie scoped to `/api/setup`, with deployment Secure policy, a separate
  `atlas-setup` JWT audience, random token ID and setup-generation claim. It
  cannot authenticate normal Atlas operations. Reset and initialization revoke
  all previous setup authorizations. Five failures impose a shared fifteen-minute
  PostgreSQL lockout. Setup responses are not cached; validation errors omit
  submitted credentials.
- **L — Atomicity:** `SELECT ... FOR UPDATE` on the singleton serializes
  verification/reset/creation. User, normal global Master Administrator
  assignment, optional Home/Homelab starter context, audit event, initialized
  marker and verifier invalidation share one transaction. Rollback retains a
  usable uninitialized state; competing transactions yield exactly one admin.
- **M/N — Reset:** commands below work only while uninitialized, revoke the
  previous code/cookies, and print a fresh code once. Initialized instances
  refuse clearly; no force flag, remote reset API or admin-password-reset path.
- **O — Existing databases:** any existing user causes migration initialization,
  preserving users/hashes. A defensive user-existence check also blocks legacy
  takeover before backfill. Removing/ disabling accounts does not reopen an
  initialized marker.
- **P — Session lifetime:** normal System Setting and UI, integer 1–10080,
  default/fallback 480, global `system_settings.manage`. Login and password change
  read it for token expiry and cookie max-age. Changes affect newly issued
  sessions. Previous customized environment values must be re-entered in
  Settings after upgrade; they are not silently imported as runtime authority.
- **Q — Docker resilience:** all five services have `unless-stopped`; health
  dependencies plus bounded API database readiness retries precede migrations
  and definitions. Host/LXC must start Docker at boot. Intentionally stopped
  containers stay stopped. DB/cache ports are internal and web/API ports bind
  loopback; a separate override supplies developer DB/cache ports.
- **R — Native resilience:** installer installs/enables three Atlas units and
  required local dependencies. `WantedBy=multi-user.target`, dependency ordering,
  `Restart=on-failure`, 15-second delay and start-rate limits. API retries DB
  readiness; installer checks both API/web readiness and unit active state.

Docker local reset:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml exec api \
  python -m scripts.setup_code reset
```

Native local reset:

```bash
sudo -u atlas /opt/atlas/venv/bin/python \
  /opt/atlas/infra/install/manage.py setup-code reset
```

## API/UI compatibility and security boundaries

Setup and build-info endpoints are additive. Normal login/logout/profile,
password-change, RBAC, customer/site and graph APIs retain their contracts.
First-run `/setup` is public but reveals only initialization/authorization state;
all mutations require the server-controlled uninitialized state and a valid
setup credential. Normal application APIs still require existing authentication
and scope policy. A fresh protected-page visit opens setup; existing instances
retain sign in. Restore is visibly disabled and has no fake endpoint.

The current Origin middleware and SameSite protection apply to setup. Backend
settings permission checks remain authoritative. H1 changes no topology,
dependency, accepted-knowledge, integration or tenancy semantics.

## Tests and actual validation (S–Z)

The host is macOS, Python 3.14, Node 24, PostgreSQL 17, Chrome and Playwright.
Python dependencies and a loopback-only disposable PostgreSQL cluster were
created under `/private/tmp`. Regression and first-run tests use separate
databases: inventory fixtures legitimately create users and must not share the
fresh setup fixture. This is ordinary test seeding, without a production installer.

New/updated automated coverage includes fresh/legacy initialization, verifier
redaction, valid/invalid/throttled code, request-validation redaction, scoped and
expired setup authorization, secure cookies, missing authorization, password
policy, Master permissions, successful real login/logout, rollback, simultaneous
transactions, permanent endpoint/code/cookie invalidation, local reset output
and refusal, settings bounds/authorization/issuance/environment independence,
metadata restrictions, configuration secrets/permissions/no overwrite/symlinks,
and Compose/systemd restart contracts. Frontend coverage checks first-run route
protection and truthful About/restore presentation.

Commands actually run (test environments use generated test secrets and
disposable URLs, omitted here to keep this report credential-free):

```bash
# apps/api, migrated disposable regression + separate first-run databases
pytest tests ../../plugins/sdk/tests ../../plugins/proxmox/tests -q -rs

# empty disposable legacy upgrade database
pytest tests/test_release_migration_postgres.py -q

# focused setup/auth/settings review
pytest tests/test_setup_postgres.py tests/test_auth.py \
  tests/test_administration.py tests/test_release_foundation.py -q

# apps/web
npm test
npm run build

# apps/api
alembic upgrade head
alembic heads

# repository root
python3 -m compileall -q apps/api/app apps/api/scripts infra/install
git diff --check
```

- **T — Full backend/plugin regression:** **512 passed, 6 skipped**. The six
  skips require independently supplied empty migration databases: Asset Category,
  Presentation, Topology Layers, Topology Positions, Topology Roles, and H1
  legacy migration. The H1 legacy migration was run separately and **passed**.
  Existing graph/topology, authorization, inventory, discovery/plugin, user and
  session regression tests ran. The final focused setup/auth/settings suite was
  **91 passed, 1 skipped** (an existing optional PostgreSQL profile test lacked its
  separate URL in that focused command; it ran in the full suite). Warnings are
  existing Python 3.14/Starlette/FastAPI deprecations.
- **U — Frontend:** **269 tests passed**, production `npm run build` passed,
  including the new `/setup` route. This build was used for live acceptance.
- **V — Docker:** actual Compose YAML parsed successfully; tests verified all
  restart policies, internal DB/cache exposure, required secret variables and
  public-only web configuration. Production environment generation, independent
  secrets, `0600`, overwrite/symlink refusal and method metadata were executed.
  **Not run:** `docker compose config`, image/container builds, stack startup,
  container restart recovery or host/LXC reboot; Docker is absent on this host.
- **W — systemd:** Python installer compilation and static unit section,
  service-account, restart and install-target checks passed. Native method and
  generated secret configuration were tested; resulting path/ownership/chmod,
  dependency and enable logic were inspected in source. **Not run:**
  `systemd-analyze verify`, real installation, service enable/start/restart,
  installed ownership/permissions or reboot; the host is macOS without systemd.
- **API startup:** actual `python -m scripts.start` succeeded against the
  disposable initialized database, ran migrations/system definitions, served
  health and preserved initialized setup closure. The temporary API was stopped.
- **Migration graph:** `alembic heads` returned exactly `20261004_0025 (head)`.
  Empty-database upgrades and the populated legacy upgrade passed on PostgreSQL.
- **Z — Hygiene/documentation:** `git diff --check`, Python compilation and local
  Markdown-link target checks passed. No unrelated tracked changes were present.

One final regression attempt encountered transient host disk exhaustion,
causing PostgreSQL to enter recovery. It was not reported as passing. After
removing only task-created disposable completed/failed databases and allowing
recovery, the complete final rerun passed (512/6). No user data was removed.

**X — Browser acceptance:** real production Next.js build, real FastAPI/PostgreSQL,
same-origin local proxy, no auth mocks. Passed fresh protected-route→setup,
code verification, disabled restore, admin creation→sign in→login, initialized
setup closure, separate unauthenticated initialized-instance→login, and normal
login again. System Settings accepted 90 and browser-native bounds rejected
0/10081. Setup layout checked at 1440/800/390 without horizontal overflow.
The repeatable script is `apps/web/scripts/check-first-run-browser.mjs`; it reads
ephemeral generated credentials through stdin and never persists them.
Screenshots and sanitized report live at `/private/tmp/atlas-h1-browser/`:
`setup-code-1440.png`, `setup-code-800.png`, `setup-code-390.png`,
`setup-choices.png`, `setup-administrator.png`, `system-settings.png`, `report.json`.

**Y — Security diff review:** inspected secret creation/storage/output,
credential/token leakage, setup URLs/storage/caching, bypass and race behavior,
Origin/SameSite defenses, cookie generation/fixation/revocation, initialized
reset refusal, permissions, random generation, shell-free subprocess arguments,
development defaults and safe errors. Fixed FastAPI validation echoing submitted
setup credentials, hid SQL parameters, redacted setup-code audit keys, and
suppressed credential-bearing native provisioning SQL logs/errors. No raw setup
code, signing/database secret, generated deployment environment or browser
authorization token was added to tracked sources. This is the H1 diff review,
not the deferred final product security review.

## Documentation and deferred scope

Updated only first-run/auth/session/deployment guidance, relevant README
instructions, security test plans and feature-ledger reality. The separate
[installation guide](../deployment/h1-installation.md) supplies actual supported
commands and native prerequisites. No accepted ADR was superseded: PostgreSQL,
central RBAC, graph semantics and knowledge boundaries are preserved.

TOTP, backup archive/restore engines, releases/update checking, licensing,
integration expansion and broader onboarding remain deliberately deferred.
Production Linux installation/lifecycle acceptance must be completed on a host
with Docker/systemd; macOS cannot prove those behaviors.

## A — Material files changed

| File | Purpose |
| --- | --- |
| `.env.example` | Separate developer-only configuration and retire environment admin/session settings. |
| `README.md` | Correct first-run/development/upgrade instructions only. |
| `apps/api/Dockerfile` | Artifact build ID, unprivileged API runtime, resilient startup command. |
| `apps/api/app/audit.py` | Redact setup-code keys in audit metadata. |
| `apps/api/app/auth.py` | Use database-backed session duration and existing password/cookie primitives. |
| `apps/api/app/database.py` | Derive the connection URL and hide SQL parameters. |
| `apps/api/app/main.py` | Register setup routes and redact/disable caching of setup responses. |
| `apps/api/app/models.py` | Declare constrained singleton first-run state. |
| `apps/api/app/routes/auth.py` | Read session setting when issuing login/password-change cookies. |
| `apps/api/app/routes/system_settings.py` | Enforce session bounds and expose protected build identity. |
| `apps/api/migrations/env.py` | Use the same safely derived connection configuration for migration/startup. |
| `apps/api/scripts/create_user.py` | Prevent local user creation from bypassing first-admin setup. |
| `apps/api/scripts/seed_admin.py` | Retire environment credential creation; retain a safe compatibility command. |
| `apps/api/tests/test_auth.py` | H1 security/settings/migration/deployment coverage or regression fixture updates. |
| `apps/api/tests/test_models.py` | H1 security/settings/migration/deployment coverage or regression fixture updates. |
| `apps/api/tests/test_seed_admin.py` | H1 security/settings/migration/deployment coverage or regression fixture updates. |
| `apps/web/app/admin/system-settings/page.js` | Session lifetime editor and canonical application About metadata. |
| `apps/web/app/globals.css` | Reuse auth composition and provide restrained setup-choice spacing. |
| `apps/web/app/login/page.js` | Route uninitialized installations to setup and preserve normal login. |
| `apps/web/components/root-shell.js` | Gate fresh protected routes through server initialization status. |
| `apps/web/lib/session-state.mjs` | Represent the setup-required route state without granting a user session. |
| `apps/web/tests/system-lifecycle.test.mjs` | Regress first-run route protection, secret handling and truthful metadata UI. |
| `docs/architecture/authentication-and-access-control.md` | Keep relevant authentication/deployment/security documentation truthful. |
| `docs/architecture/deployment-and-upgrades.md` | Keep relevant authentication/deployment/security documentation truthful. |
| `docs/product/feature-ledger.md` | Record implemented H1 capabilities and explicit platform/restore limits. |
| `docs/testing/auth-shell-test-plan.md` | Keep relevant authentication/deployment/security documentation truthful. |
| `docs/testing/security-and-access-test-plan.md` | Keep relevant authentication/deployment/security documentation truthful. |
| `infra/docker/docker-compose.yml` | Production defaults/restart/internal service exposure, with separate developer override. |
| `apps/api/app/config.py` | Safe bootstrap database URL derivation with production credential requirements. |
| `apps/api/app/release.json` | Single canonical version/channel/artifact identity source. |
| `apps/api/app/release.py` | Load artifact identity and validate supported installation method. |
| `apps/api/app/routes/setup.py` | First-run API contracts, code verification and atomic administrator creation. |
| `apps/api/app/services/installation.py` | Shared row-locked first-run state, verifier, scoped authorization and admin transaction. |
| `apps/api/app/services/system_settings.py` | Canonical setting key, bounds and safe absent-row default. |
| `apps/api/migrations/versions/20261004_0025_release_foundation.py` | Add installation state and seed session lifetime safely. |
| `apps/api/scripts/seed_system.py` | Reuse protected RBAC/taxonomy/context definitions and seed session setting. |
| `apps/api/scripts/setup_code.py` | Local one-time-code reset/output/refusal. |
| `apps/api/scripts/start.py` | Validate startup configuration, retry DB readiness, migrate/seed and exec API. |
| `apps/api/tests/test_release_foundation.py` | H1 security/settings/migration/deployment coverage or regression fixture updates. |
| `apps/api/tests/test_release_migration_postgres.py` | H1 security/settings/migration/deployment coverage or regression fixture updates. |
| `apps/api/tests/test_setup_postgres.py` | H1 security/settings/migration/deployment coverage or regression fixture updates. |
| `apps/web/app/setup/page.js` | Atlas setup-code, choices, disabled restore and first-admin experience. |
| `apps/web/lib/setup.js` | Credentialed setup requests and explicit status contract. |
| `apps/web/scripts/check-first-run-browser.mjs` | Repeatable real UI/API acceptance using ephemeral stdin credentials. |
| `apps/web/tests/setup.test.mjs` | Regress first-run route protection, secret handling and truthful metadata UI. |
| `docs/deployment/h1-installation.md` | Keep relevant authentication/deployment/security documentation truthful. |
| `docs/testing/h1-release-foundation.md` | Detailed A–AA completion, actual evidence, unresolved platform checks and Git state. |
| `infra/docker/docker-compose.dev.yml` | Production defaults/restart/internal service exposure, with separate developer override. |
| `infra/install/compose.py` | Protected production generation/install or shell-free native local management. |
| `infra/install/configuration.py` | Protected production generation/install or shell-free native local management. |
| `infra/install/manage.py` | Protected production generation/install or shell-free native local management. |
| `infra/install/native.py` | Protected production generation/install or shell-free native local management. |
| `infra/systemd/atlas-api.service` | Unprivileged, enabled boot targets, dependency ordering and controlled restarts. |
| `infra/systemd/atlas-web.service` | Unprivileged, enabled boot targets, dependency ordering and controlled restarts. |
| `infra/systemd/atlas-worker.service` | Unprivileged, enabled boot targets, dependency ordering and controlled restarts. |

## AA — Repository state

Command actually executed: `git status --short`.

```text
 M .env.example
 M README.md
 M apps/api/Dockerfile
 M apps/api/app/audit.py
 M apps/api/app/auth.py
 M apps/api/app/database.py
 M apps/api/app/main.py
 M apps/api/app/models.py
 M apps/api/app/routes/auth.py
 M apps/api/app/routes/system_settings.py
 M apps/api/migrations/env.py
 M apps/api/scripts/create_user.py
 M apps/api/scripts/seed_admin.py
 M apps/api/tests/test_auth.py
 M apps/api/tests/test_models.py
 M apps/api/tests/test_seed_admin.py
 M apps/web/app/admin/system-settings/page.js
 M apps/web/app/globals.css
 M apps/web/app/login/page.js
 M apps/web/components/root-shell.js
 M apps/web/lib/session-state.mjs
 M apps/web/tests/system-lifecycle.test.mjs
 M docs/architecture/authentication-and-access-control.md
 M docs/architecture/deployment-and-upgrades.md
 M docs/product/feature-ledger.md
 M docs/testing/auth-shell-test-plan.md
 M docs/testing/security-and-access-test-plan.md
 M infra/docker/docker-compose.yml
?? apps/api/app/config.py
?? apps/api/app/release.json
?? apps/api/app/release.py
?? apps/api/app/routes/setup.py
?? apps/api/app/services/installation.py
?? apps/api/app/services/system_settings.py
?? apps/api/migrations/versions/20261004_0025_release_foundation.py
?? apps/api/scripts/seed_system.py
?? apps/api/scripts/setup_code.py
?? apps/api/scripts/start.py
?? apps/api/tests/test_release_foundation.py
?? apps/api/tests/test_release_migration_postgres.py
?? apps/api/tests/test_setup_postgres.py
?? apps/web/app/setup/
?? apps/web/lib/setup.js
?? apps/web/scripts/check-first-run-browser.mjs
?? apps/web/tests/setup.test.mjs
?? docs/deployment/h1-installation.md
?? docs/testing/h1-release-foundation.md
?? infra/docker/docker-compose.dev.yml
?? infra/install/
?? infra/systemd/
```

All changes belong to H1; no pre-existing user edits were present.
