# H2 — Local Two-Factor Authentication: implementation and acceptance

Recorded 2026-10-04 on `feature/h2-two-factor-authentication`, based on accepted
H1 HEAD `51ae821eb17b79bdafcabbec3b03d4764d8f41af`. No commit, push, merge or
rebase was performed.

**H1/H1.1 — ACCEPTED. H2 — ACCEPTED. H3 — implemented and locally validated;
real Docker acceptance pending.** See [H3 evidence](h3-encrypted-backup-restore.md).

H1's real Debian Docker/LXC acceptance is user-reported evidence: fresh clone,
production installer, generated secrets, LAN URL, gateway and healthy services,
setup/reset, first administrator, login/dashboard, actual LXC reboot, direct LAN
and Nginx Proxy Manager using one upstream without an `/api` custom location.
It does not establish real native/systemd lifecycle acceptance; that remains H6.

H2 is accepted following the automated evidence below and subsequent real user
acceptance on Debian Docker/LXC. The user upgraded a throwaway installation using
`python3 infra/install/configuration.py --add-data-encryption-key --output .env`,
validated `docker compose --env-file .env -f infra/docker/docker-compose.yml config
--quiet`, and completed `up -d --build --wait`. The helper preserved existing
secrets. A second installation containing actual homelab Atlas data was
snapshotted and upgraded with the same supported procedure; its existing data
survived and the user tested and confirmed the installed H2 application working.

These are the supplied real Docker acceptance facts. They do not establish more
granular manual authenticator actions, Docker break-glass execution or a real
native/systemd lifecycle. The implementation-time local checks below remain
historical evidence. Native lifecycle remains an H6 release gate; the five
existing npm audit findings remain unresolved hardening work. See
[architecture](../architecture/local-two-factor-authentication.md) and
[deployment/recovery commands](../deployment/h2-mfa.md).

## Validation actually performed

| Check | Actual result and environment |
| --- | --- |
| Full API, SDK and Proxmox plugin tests | **627 passed, zero skipped**, PostgreSQL 17, Python 3.14. Separate freshly migrated databases for general domain, first-run and MFA suites, plus empty databases for all optional migration suites. Actual nginx binary supplied to ingress tests. |
| Web regression | **272 passed, zero skipped** with `npm test`. |
| Production frontend | **Passed**, `npm run build`. |
| Alembic graph | **One head**, `20261004_0026`. Upgrade/downgrade/re-upgrade, existing identities/password/RBAC preservation and reserved MFA flag retirement tested on PostgreSQL. |
| Python compilation | **Passed**, application, scripts, tests, installer and plugin Python trees. |
| First-run browser | **Passed**, generated production configuration, actual API startup/migrations/seeding, production Next server, PostgreSQL and the repository nginx ingress adapted only to local ports/upstreams. Setup closure, administrator creation, session setting, login and dashboard verified. |
| H2 browser | **Passed**, enrollment/password reauthentication, local canvas QR pixels/manual key, confirmation, twelve codes, password-only isolation, TOTP login, recovery login/reuse rejection, regeneration/old-code rejection, replacement, disable, re-enrollment and local module break-glass reset. Real clock and PyOTP-generated codes; no physical app. |
| Responsive/presentation browser | No page overflow at 1440, 1024, 800 and 390 pixels; light/blue and dark/purple verified. Sanitized screenshots contain enabled status only, with QR, manual seed and recovery codes removed. No browser JS errors or external requests in the H2 run. |
| Installer/native configuration | Automated generation, independence of secrets, protected file behavior, missing-key append/idempotence/refusal of invalid keys or symlinks, API-only Compose key wiring and unchanged restart/systemd security declarations passed. Real systemd services were not run. |
| H2 diff review | Completed for credential storage/disclosure, crypto, challenges, sessions, races, authorization and CSRF. See review findings below. |
| Markdown documentation | Four documentation regression tests passed after the final report; 144 local link targets in changed Markdown documents checked and passed. |
| Whitespace | `git diff --check` passed. |
| npm dependency audit | Five findings in unchanged dependencies: one critical (`next`), three high (`nanoid`, `postcss`, `sharp`), one moderate (`baseline-browser-mapping`). No reported finding in the added QR dependency. This is not a clean dependency audit; remediation remains release hardening work. |

Commands actually executed included:

```bash
# apps/api, with all ATLAS_TEST_* PostgreSQL URLs and ATLAS_TEST_NGINX configured
/private/tmp/atlas-h1-venv/bin/python -m pytest \
  tests ../../plugins/sdk/tests ../../plugins/proxmox/tests -q -rs --tb=short

# apps/web
npm test
npm run build
npm audit --json

# apps/api
/private/tmp/atlas-h1-venv/bin/python -m alembic heads
/private/tmp/atlas-h1-venv/bin/python -m pytest tests/test_markdown_docs.py -q

# repository root
/private/tmp/atlas-h1-venv/bin/python -m compileall -q apps/api/app \
  apps/api/scripts apps/api/tests infra/install plugins
git diff --check
git status --short
```

A disposable local harness ran the two checked-in browser scripts,
`apps/web/scripts/check-first-run-browser.mjs` and
`apps/web/scripts/check-mfa-browser.mjs`, against actual services. Credentials
arrived over stdin; seeds and generated codes remained ephemeral. The second
script's report recorded `result: passed`, `physicalAuthenticator: false`,
`localCommand: true`, `dockerCommand: false`, and empty JS-error/external-request
lists. It executed the actual `python -m scripts.mfa reset --user <email>`
subprocess against the disposable account and checked the audit event, unchanged
password and return to password-only login. It did not run a Docker exec or the
native `/etc/atlas` adapter.

The full backend run deliberately used production MFA session settings
(`autoflush=False`, `expire_on_commit=False`). Existing optional migration tests
now resolve the current single head instead of a historical hardcoded head.
No committed migration was edited.

## H2 security review findings resolved

Live acceptance exposed a recovery-code disable transaction bug: with production
autoflush disabled, deleting the factor cascaded its dirty consumed-code row
before that row was written. Reset now explicitly flushes before cascading
deletion, within the same transaction. The fixtures match production settings,
and the final full suite and live disable/local-reset journeys passed afterward.

The session review also found that a user already loaded into the identity map
could retain a stale session version after waiting for a row lock. Locked login,
logout, password change and administrator updates/reset now reload the locked
row; account-owned MFA mutations recheck the requesting version after locking.
This prevents an older request from overwriting a newer revocation generation.

All MFA mutations lock the existing User first. Real concurrent PostgreSQL tests
cover enrollment confirmation, TOTP verification, recovery consumption and
competing login attempts. Only one request can consume the same factor/challenge.
Wrong-key/account-bound/tampered ciphertext fails closed. No plaintext seed or
code is persisted; no secret-bearing audit metadata or validation echo is
returned. The HttpOnly challenge cannot authenticate normal endpoints or bearer
requests. Origin defenses, effective HTTP/HTTPS cookie policy and protected
global Master reset authorization have regression coverage.

The added dependencies are pinned: `pyotp==2.9.0` (MIT),
`cryptography==46.0.5` (Apache-2.0/BSD) and frontend `qrcode==1.5.4` (MIT).
The npm lockfile preserves existing package versions. Whole-product security
review and resolution of the existing audit findings belong to H6.

## Historical implementation-time manual checklist

H2 is now accepted on the supplied Docker evidence above. This historical
checklist records the originally proposed granular checks; it does not claim
they were subsequently performed. Use a disposable/secondary account and save
its recovery codes before testing.
Do not capture QR/manual keys, recovery codes or submitted OTPs in artifacts.

- Run a real H2 Docker production installation/upgrade with the generated data
  key. Verify LAN URL, setup code/reset/closure, gateway `/api/health`, first
  administrator, login, dashboard, restart declarations and NPM one upstream.
  A new actual reboot is not required solely for this key addition, and none is
  claimed here.
- With a physical standards-compatible authenticator, scan the local QR (also
  inspect manual entry), confirm, save exactly twelve codes, log out and sign in
  with password plus real TOTP. Then use a recovery code, reject its reuse,
  regenerate with password/TOTP and reject old unused codes.
- Exercise replacement and disable with real factors; verify abandoning a
  replacement leaves the old authenticator usable.
- On that disposable MFA account, execute the documented interactive Docker
  reset command. Check unchanged password, password-only login, rejection of
  old recovery credentials/challenges and `auth.mfa_local_reset` audit.
- Real native/systemd installation/start/reboot and native adapter acceptance
  remain H6/release acceptance. The implementation/static tests do not stand in
  for a real Linux lifecycle.

No Docker binary/daemon or systemd exists in this execution environment, and a
physical authenticator device is unavailable. `docker compose config --quiet`,
Docker installer execution, real LAN/NPM H2 deployment, actual Docker reset and
real systemd lifecycle were therefore not run. H1 acceptance remains valid as
supplied by the user; it is not reclassified as new H2 execution evidence.

## Completion report A–AI

| Item | Delivered behavior/evidence |
| --- | --- |
| A. H1 acceptance | Ledger, roadmap, H1 acceptance/ingress and installation references record H1/H1.1 accepted on Debian Docker/LXC. Native lifecycle explicitly remains H6. |
| B. Files | Every material changed file and its purpose is listed below. |
| C. Migration | New additive `20261004_0026`, parent `20261004_0025`; one head; three MFA tables and cascade constraints. |
| D. Library/standard | PyOTP 2.9.0, RFC 6238, SHA-1, six digits, thirty seconds, issuer Atlas and account email label. |
| E. Seed entropy | Cryptographically random 32-character base32 seed, 160 bits. |
| F. Encryption | cryptography AES-256-GCM; fresh random 96-bit nonce, 128-bit authentication tag, account-bound associated data, metadata version 1. Both pending and active seeds encrypted. |
| G. Data key | Independent random 32-byte/64-hex bootstrap secret from both installers; protected existing environment files; safe append helper for upgrades; production startup fails closed; no auth-key derivation, database copy or frontend exposure. |
| H. Database | One-to-one `user_mfa`, child `mfa_recovery_codes`, one current `mfa_challenges` row/account, existing `users.mfa_enabled` status. PostgreSQL is authoritative. |
| I. Enrollment | Authenticated current password; encrypted ten-minute pending enrollment; replacement invalidates prior pending; bounded invalid confirmations; atomic possession confirmation and recovery generation. |
| J. QR | qrcode 1.5.4 renders standard otpauth payload locally into canvas; no remote request or URI navigation. |
| K. Manual key | Displayed only during authenticated pending enrollment; memory cleared on completion/expiry/navigation; no later active-seed API. |
| L. Recovery format | Exactly twelve random 120-bit codes; 24 characters from a 32-character unambiguous alphabet, six groups of four. |
| M. Recovery storage | Account-bound domain-prefixed SHA-256 verifiers only; constant-time compare over all twelve including consumed entries; one atomic consumption; no plaintext retrieval. |
| N. Login challenge | Password verified first; five-minute HttpOnly/SameSite=Lax scoped cookie, separate audience, account/version/attempt binding, database revocation, H1 Secure-cookie policy; no normal session until factor succeeds. |
| O. Replay | Persisted strictly increasing accepted TOTP counter; current ± one step only; enrollment establishes used step; collision handling rejects replay; user-row locking. |
| P. Attempts | Five failures exhaust login challenge; persistent factor lockout for fifteen minutes, bounded enrollment attempts and existing password lockout conventions; account-local, no global lockout. |
| Q. Self-disable | Password plus TOTP/recovery; delete factor/pending/recovery/replay, revoke challenges and old sessions, refresh requesting normal session, audit. |
| R. Replacement | Password plus existing TOTP/recovery; one pending replacement, old factor active until new confirmed; atomic promotion/new recovery codes; revoke old sessions/challenges. |
| S. Regeneration | Password plus fresh TOTP only; all old codes invalidated atomically; exactly twelve replacements displayed once. |
| T. Administrator | Global users.edit plus protected global Master boundary and target manageability; self-admin reset blocked; actor/target audit; password retained, all MFA/session material invalidated. |
| U. Docker reset | `docker compose --env-file .env -f infra/docker/docker-compose.yml exec api python -m scripts.mfa reset --user <email>`; interactive exact RESET confirmation. Documented/static wiring; actual Docker execution pending. |
| V. Native reset | `sudo -u atlas /opt/atlas/venv/bin/python /opt/atlas/infra/install/manage.py mfa reset --user <email>`; protected local configuration adapter. Real systemd/adapter execution pending. |
| W. Audit | Enabled, replaced, recovery regenerated/used, disabled, admin reset, local reset, challenge start and sanitized failures; actor/target recorded; no seeds/OTP/URI/plaintext codes/data key. |
| X. H3 boundary | Explicit dependency on ATLAS_DATA_ENCRYPTION_KEY; future passphrase-encrypted backup package must include it; database-only restore/new key cannot decrypt seeds; no H3 engine added. |
| Y. Existing accounts | MFA disabled on upgrade, including reserved pre-H2 flag; no auto-enrollment, password hash or RBAC change. Tested preservation. |
| Z. Automated | 627 API/plugin/PostgreSQL tests and 272 frontend tests passed, no skips; crypto, session, authorization, Origin, storage, race, CLI, migration and installer behavior covered. |
| AA. Build | Production frontend build passed. |
| AB. Browser/authenticator | Real production API/frontend/PostgreSQL/nginx browser flows passed, with local real-time PyOTP. Physical authenticator not tested. |
| AC. Break-glass | Actual local module CLI passed against disposable production-configured account; unchanged password/no-MFA login/audit checked. Actual Docker and native wrapper not executed. |
| AD. Docker/H1 | Generator/static Compose/restart tests, real nginx ingress tests and production first-run browser passed; no H2 Docker daemon/installer/LAN/NPM/reboot run. H1 accepted evidence retained. |
| AE. Systemd | Key generation/protected-file and existing unit/restart/security declarations validated automatically; no real Linux systemd lifecycle. |
| AF. Diff security | Targeted review complete, transaction ordering and stale session-generation races fixed, full regression/browser rerun passed. No full-product audit claim. |
| AG. Not tested | Physical app, Docker Compose CLI/config execution, H2 real Docker installation/reset/LAN/NPM, native adapter/systemd lifecycle, H3 backup portability. Existing npm audit findings unresolved. |
| AH. Diff check | `git diff --check` clean. |
| AI. Repository | Feature branch, original HEAD unchanged, no commit/push; exact short status follows file inventory. |

## Files changed

All paths below are relative to the repository root. Existing normal session and
non-MFA login behavior are preserved; login adds `mfa_required` and permits a
null `user` only during the new challenge branch. New account/admin endpoints
are additive. Frontend Profile, login and user administration expose the flows.
No topology, inventory, accepted knowledge, discovery, integration or tenant/site
models/semantics changed. Backend authorization remains authoritative; new admin
reset is global-only, and account operations act only on the authenticated user.

| Files | Purpose |
| --- | --- |
| `.env.example`, `README.md` | Explicit development key setup/upgrade and recovery documentation links. |
| `apps/api/app/config.py`, `apps/api/scripts/start.py`, `apps/api/app/main.py` | Validate independent encryption material in production startup; register MFA and redact/no-store auth responses. |
| `apps/api/app/models.py`, `apps/api/migrations/versions/20261004_0026_local_mfa.py` | MFA persistence and additive migration. |
| `apps/api/app/services/mfa.py`, `apps/api/app/routes/mfa.py` | Crypto, locking, factors, recovery, scoped challenges and account contracts. |
| `apps/api/app/auth.py`, `apps/api/app/routes/auth.py`, `apps/api/app/schemas.py` | Two-stage login, normal-session compatibility, session revocation/password-change handling. |
| `apps/api/app/routes/users.py`, `apps/api/app/audit.py` | Protected administrator reset and credential-safe audit behavior. |
| `apps/api/scripts/mfa.py`, `infra/install/manage.py` | Confirmed local break-glass reset and native management adapter. |
| `apps/api/requirements.txt` | Pinned PyOTP/cryptography dependencies. |
| `infra/install/configuration.py`, `infra/docker/docker-compose.yml` | Fresh installer key generation, protected existing-file append helper and API-only key wiring. |
| `apps/api/tests/test_mfa.py`, `apps/api/tests/test_mfa_postgres.py`, `apps/api/tests/test_mfa_migration_postgres.py` | Crypto/configuration, complete behavior/security/races, real PostgreSQL migration tests. |
| `apps/api/tests/test_models.py`, `apps/api/tests/test_release_foundation.py` | Schema registration and installer/secret/deployment regression. |
| `apps/api/tests/test_asset_category_migration_postgres.py`, `apps/api/tests/test_topology_layers_migration_postgres.py`, `apps/api/tests/test_topology_positions_migration_postgres.py`, `apps/api/tests/test_topology_roles_migration_postgres.py` | Existing optional tests resolve the current head; domain behavior unchanged. |
| `apps/web/components/mfa-security.js`, `apps/web/components/mfa-security.module.css`, `apps/web/app/profile/page.js` | Profile security flow, local QR/manual setup, recovery/management and responsive shared Atlas UI. |
| `apps/web/app/login/page.js`, `apps/web/lib/auth.js`, `apps/web/lib/login-result.mjs` | Public two-stage login with HttpOnly challenge and explicit recovery alternative. |
| `apps/web/app/admin/users/page.js` | Restrained status and confirmed privileged reset. |
| `apps/web/package.json`, `apps/web/package-lock.json` | Pinned local QR renderer and its dependency graph. |
| `apps/web/tests/mfa.test.mjs`, `apps/web/scripts/check-mfa-browser.mjs` | Frontend contract/security regression and repeatable live browser acceptance. |
| `docs/README.md`, `docs/architecture/authentication-and-access-control.md`, `docs/architecture/deployment-and-upgrades.md`, `docs/architecture/local-two-factor-authentication.md` | Current architecture, implementation/security/key and H3 boundary references. |
| `docs/deployment/h1-installation.md`, `docs/deployment/h2-mfa.md` | H1 acceptance, installer key requirement and exact recovery commands. |
| `docs/product/development-roadmap.md`, `docs/product/feature-ledger.md` | H1 accepted, H2 implemented with acceptance pending; truthful scope/status. |
| `docs/testing/h1-release-foundation.md`, `docs/testing/h1-docker-ingress.md` | Supplied Debian acceptance recorded without inventing native lifecycle evidence. |
| `docs/testing/auth-shell-test-plan.md`, `docs/testing/security-and-access-test-plan.md`, `docs/testing/h2-local-two-factor-authentication.md` | H2 acceptance linkage and this complete report. |

## Repository state

`git status --short` at completion:

```text
 M .env.example
 M README.md
 M apps/api/app/audit.py
 M apps/api/app/auth.py
 M apps/api/app/config.py
 M apps/api/app/main.py
 M apps/api/app/models.py
 M apps/api/app/routes/auth.py
 M apps/api/app/routes/users.py
 M apps/api/app/schemas.py
 M apps/api/requirements.txt
 M apps/api/scripts/start.py
 M apps/api/tests/test_asset_category_migration_postgres.py
 M apps/api/tests/test_models.py
 M apps/api/tests/test_release_foundation.py
 M apps/api/tests/test_topology_layers_migration_postgres.py
 M apps/api/tests/test_topology_positions_migration_postgres.py
 M apps/api/tests/test_topology_roles_migration_postgres.py
 M apps/web/app/admin/users/page.js
 M apps/web/app/login/page.js
 M apps/web/app/profile/page.js
 M apps/web/lib/auth.js
 M apps/web/package-lock.json
 M apps/web/package.json
 M docs/README.md
 M docs/architecture/authentication-and-access-control.md
 M docs/architecture/deployment-and-upgrades.md
 M docs/deployment/h1-installation.md
 M docs/product/development-roadmap.md
 M docs/product/feature-ledger.md
 M docs/testing/auth-shell-test-plan.md
 M docs/testing/h1-docker-ingress.md
 M docs/testing/h1-release-foundation.md
 M docs/testing/security-and-access-test-plan.md
 M infra/docker/docker-compose.yml
 M infra/install/configuration.py
 M infra/install/manage.py
?? apps/api/app/routes/mfa.py
?? apps/api/app/services/mfa.py
?? apps/api/migrations/versions/20261004_0026_local_mfa.py
?? apps/api/scripts/mfa.py
?? apps/api/tests/test_mfa.py
?? apps/api/tests/test_mfa_migration_postgres.py
?? apps/api/tests/test_mfa_postgres.py
?? apps/web/components/mfa-security.js
?? apps/web/components/mfa-security.module.css
?? apps/web/lib/login-result.mjs
?? apps/web/scripts/check-mfa-browser.mjs
?? apps/web/tests/mfa.test.mjs
?? docs/architecture/local-two-factor-authentication.md
?? docs/deployment/h2-mfa.md
?? docs/testing/h2-local-two-factor-authentication.md
```
