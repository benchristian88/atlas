# H4 release distribution and update awareness — implementation and validation

Recorded 2026-10-04 on `feature/h4-release-distribution`, clean starting HEAD
`b7e0dae7122adf1b61846d63a0034e57d45d9b10`, the accepted merged H3 state.
The requested feature branch already existed. H1/H1.1, H2 and H3 are ACCEPTED.
H4 is **implemented and locally validated**, with hosted execution, publication
and real native lifecycle explicitly separate. No commit, push, merge, rebase,
tag, live GitHub Release or registry publication was performed.

## Native remediation after real Debian 13 testing

This subsequent remediation starts from the existing uncommitted H4 working
tree on the same branch/HEAD. Earlier H4 evidence below is historical; its native
claims are superseded by this section and the current installation/upgrade docs.
The user supplied actual Debian 13 native/systemd findings after the original
H4 completion report. **The remediated native lifecycle has not passed real
Debian acceptance yet. A fresh real Debian/systemd retest is required.**

### Findings inspected in the current H4 tree

| Supplied finding | Current H4 inspection before remediation |
| --- | --- |
| A — `--help` performs work | Already fixed by H4's early argument parsing. Regression strengthened to prove no preflight/install calls or new directories in an extracted helper tree, including bytecode directories. |
| B — prerequisite/service errors | Partly fixed: executable and Node version checks already preceded Atlas writes. Checks still stopped at the first error, and missing PostgreSQL/Redis units could raise raw `CalledProcessError`. |
| C — missing venv leaves partial install | Still applicable: venv creation followed account/config/code creation, without a capability probe. |
| D/E — completion lacks URL/ingress | Still applicable: setup code printed without an access URL; no bundled ingress existed, while web/API were private on loopback 3000/8000. |
| F — manually supplied nginx works | Supplied operator evidence supporting the existing same-origin architecture; no extra observations inferred. |
| G — HTTP first-run Secure-cookie failure | Still applicable: generated native cookie policy was `true`. Existing H1.1 `auto` policy and tests already supported effective HTTP/trusted-HTTPS behavior. |
| H — multi-MiB restore rejected with HTTP 413 | Supplied real evidence: manual nginx used its 1 MiB default, rejecting 2,888,096 bytes. Native had no managed ingress policy. H3's application/archive bound already was 2 GiB; Docker already configured that bound. |
| I — reserved restore slot after rejected upload | Correct H3 behavior, preserved. nginx rejected the request before FastAPI could claim it, so the ten-minute authorization remained until expiry. |

The supplied native run also established that a Docker-created `.atlasbackup`
reached the systemd target compatibly. It does not establish completion of the
remediated restore, installation, upgrade, restart or reboot lifecycle.

### Implementation, operator contract and upgrade behavior

nginx owns `ATLAS_BIND_ADDRESS:ATLAS_PORT` (default external port 3000), with
the existing H1.1 primary/default-route IPv4 selection and safe loopback fallback.
Native refuses wildcard/unusable addresses, invalid ports and ports 3001/8000.
Next.js is private on `127.0.0.1:3001`; FastAPI is private on `127.0.0.1:8000`.
`/api` and `/api/*` proxy to API without a trailing URI that strips `/api`;
everything else reaches web. Docker ports/gateway remain unchanged.

The required native template is `infra/nginx/native.conf`; the standard-library
helper is `infra/install/native_ingress.py`. Only root-owned
`/etc/nginx/conf.d/atlas.conf` and
`/etc/systemd/system/nginx.service.d/atlas.conf` are managed. Existing files must
carry the Atlas marker; symbolic/hard links, nonregular files and writable or
non-root-owned managed paths are refused. Atomic 0644 writes use private temporary
files in protected directories. `nginx -t` validates existing and candidate
configuration before activation; failure restores previous files, validates
them and reloads the previous configuration if activation was attempted. Other
nginx sites are retained. nginx is enabled at boot, ordered after API/web, and
health is checked through the external ingress before the setup-code handoff.

Restore upload locations stream with `client_max_body_size 2g`, 60-second idle
body/read timeouts and request buffering off, matching H3's 2 GiB policy.
Ordinary requests keep 20 MiB. No archive format, application size bound,
restore locking or ten-minute authorization semantics changed.

Fresh cookie configuration is the existing `AUTH_COOKIE_SECURE=auto`. Direct
HTTP issues usable non-Secure setup/session cookies. HTTPS forwarded by an
explicitly allowlisted external proxy issues Secure cookies. nginx ignores
forwarded scheme/client chains from untrusted peers and accepts only exact
`http`/`https` from trusted peers; no default proxy trust, wildcard network trust,
vendor behavior or native authentication mode is introduced. Native API's service
command forces loopback binding and `FORWARDED_ALLOW_IPS=127.0.0.1`, including
against conflicting EnvironmentFile values. HttpOnly, SameSite, cookie paths,
CSRF/Origin checks, session validation, setup closure/reset restrictions and MFA
remain unchanged. Existing explicit cookie policies are preserved on upgrade;
operators must deliberately choose `auto` for a legacy HTTP installation or
retain `true` with HTTPS. The protected environment is never silently rewritten.

CLI parsing precedes host checks. Preflight aggregates useful failures before
account creation, configuration generation, application copying, database
provisioning or unit installation. It checks root, Debian/Ubuntu booted with
systemd, invoking Python >=3.12 and actual disposable venv/ensurepip creation,
Node >=22 at `/usr/bin/node`, npm, `/usr/bin/env`, `runuser`/`useradd`,
`psql`/`pg_dump`/`pg_restore`, available/running PostgreSQL and Redis units,
peer PostgreSQL administration and supported/matching server/client major 16/17,
fresh Atlas database/role conflicts, protected filesystem locations, existing
installation/configuration/state/units, service account/group, listener bind
availability where practical, required package inputs and nginx readiness or
apt installability. Upgrade checks preserve existing Atlas listeners while
checking the new private web listener on initial ingress adoption. The venv probe
is temporary and removed, including on failure; subprocess diagnostics are
captured and replaced with concise operator messages.

Python/venv, Node/npm, PostgreSQL and Redis remain prepared/running host
prerequisites. nginx alone is installed automatically, after successful preflight
and before Atlas mutation, with `apt-get install --yes --no-install-recommends
nginx`; preflight uses apt simulation. No repositories or remote scripts are
added. Package failure retains no newly created Atlas account/config/database;
apt may retain its own package changes and requires host diagnosis. Failures
later in installation retain protected keys/configuration/data for diagnosis;
there is no destructive automatic cleanup or claim of a transactional host install.

The native upgrade helper retains the H4 `--backup-confirmed` requirement,
preflights before stopping writers, prepares nginx before the maintenance window,
replaces only managed application trees, reuses the existing venv/account,
installs matched units/ingress and checks the public endpoint. It preserves
`/etc/atlas/atlas.env` byte-for-byte, signing/data/database credentials, database,
`/var/lib/atlas` and service identity. `--validate-only` performs read-only checks
plus the temporary venv probe; it installs no packages or services. Legacy absent
ingress settings use address detection/default port; the upgrade guide explains
how to pin settings deliberately and move any old TLS upstream to the bundled
single endpoint. The local ingress refresh CLI reads protected configuration
without shell evaluation and updates only the two managed files.

Example successful local handoff (illustrative address, setup credential replaced
with a placeholder):

```text
Atlas installed successfully.

Atlas is ready.

Open Atlas in your browser:

    http://192.168.3.195:3000/

Enter this one-time setup code:

    <ONE-TIME-SETUP-CODE>

The code is required only until Atlas has been initialised.
```

The actual address/port is resolved, never hardcoded. Loopback includes the
shared local-only explanation. The reset subprocess output is emitted only after
successful commit, to the intended local terminal; no raw code is persisted or
added to logs/reports. The database retains only its existing verifier.

### Remediation files, validation and security review

Material remediation files:

- `infra/install/native.py`, `configuration.py`, `native_ingress.py`, `upgrade.py`:
  preflight, protected fresh auto/ingress configuration, managed nginx lifecycle,
  public health/terminal handoff and preserving upgrades.
- `infra/nginx/native.conf`, `infra/systemd/atlas-api.service`,
  `infra/systemd/atlas-web.service`: scoped ingress, explicit private API trust
  and native web port 3001. Worker semantics remain unchanged.
- `infra/release/package-manifest.json`, `.github/workflows/release.yml`: required
  native helper/template inclusion and native contracts in release-critical CI.
- `apps/api/tests/test_native_install.py`, `test_release_distribution.py`,
  `test_release_foundation.py`, `test_nginx_gateway.py`, `test_setup_postgres.py`:
  preflight/ordering/help/error, configuration safety/rollback, upgrade
  preservation, negative package inputs and real local routing/upload plus native
  HTTP/HTTPS setup/session regression.
- `README.md`; deployment H1/H3/H4, single-origin/reverse-proxy/migration guides;
  deployment/release/auth architecture; roadmap/feature ledger; H1/H1.1/H3/H4
  testing records: current native contract, supplied evidence and fresh real
  acceptance requirement. Earlier H4 UI/update/release work was retained.

No database migration or API route/domain/tenancy/MFA/backup-format change was
required. The single migration head remains `20261004_0026`. The native private
web listener changes; external proxy operators must use the new single endpoint.
Security review covered argv-only package/command execution, validated numeric
nginx interpolation, address/port conflicts, explicit forwarded-header trust,
cookie downgrade, root/service ownership and modes, symlink/hardlink/nonregular
paths, failed nginx rollback, package-manager failure and partial-install
preservation, privilege boundaries, bounded/streamed restore uploads and secret
output. No shell evaluation, blanket proxy trust, key regeneration, unrelated
site deletion or weaker H3 locking was introduced. Existing upstream npm findings
remain outside this remediation; earlier audit evidence is not a new clean audit.

Actual Debian apt installation, systemd ordering,
install/upgrade/restart/reboot, host permissions and browser/restore acceptance
must be retested on a fresh supported host. Local macOS nginx tests prove HTTP
transport behavior, and mocked lifecycle tests prove helper contracts only.

| Remediation validation actually run | Result |
| --- | --- |
| Final full API/SDK/Proxmox plugin suite, all optional PostgreSQL/nginx suites enabled | **848 passed, 0 failed/errors/skipped**, 155.50 seconds. Includes real PostgreSQL migrations/H1/H2/H3, new native loopback cookie cases, 64 actual nginx transport cases and native helper/release regressions. JUnit confirms 848/0/0/0. |
| Final focused native/H1/package/nginx suite | **136 passed**, 52.43 seconds. Includes extracted-tree help without created directories, actual 3 MiB uploads on both restore paths, 2 GiB oversized-header rejection and trusted/untrusted forwarding for both ingresses. |
| Workflow-equivalent release-critical command including native tests | **258 passed**, 14.24 seconds, with source SDK/Proxmox PYTHONPATH. Workflow YAML/permissions/pins/order regression passed; no GitHub-hosted execution. |
| Frontend | **279 passed, 0 skipped**, `npm test`. No UI/shared authentication implementation changes in this remediation. |
| Production frontend build | **Passed**, `npm run build`. |
| Python compilation | **Passed**, API/app/scripts/tests, worker, installers, release tooling and plugins. |
| Migration graph | **Passed**, `python -m alembic heads`: `20261004_0026 (head)` only; no migrations. |
| Release dry run and independent verification | **Passed** for Docker/native, metadata/tag, required inputs, manifest, identity and SHA-256. Missing native template/helper construction and missing-native-template archive verification regressions passed. |
| Standard checksum command | **Passed**, `shasum -a 256 -c SHA256SUMS`: both archives and manifest OK. |
| Verified-package extraction/help | **Passed**, 317 Docker and 316 native regular files. Docker fresh/upgrade and native fresh/upgrade/ingress help passed; Docker validate-only preserved generated protected configuration. |
| Documentation and whitespace | **Passed**, final local Markdown target/fence checker and `git diff --check`; final counts recorded with repository state below. |
| Actual Docker daemon/build and Debian apt/systemd lifecycle | **Not run here**: macOS has no Docker CLI/daemon or Linux systemd runtime. No actual remediated native acceptance claim. |

Full regression orchestration used a newly initialized disposable PostgreSQL
17.11 cluster and Redis 7.4.6 on loopback, separate databases for domain/setup/MFA
and migrations, non-superuser-owned H3 source/target databases, nginx 1.28.0 and
Python 3.14. All test processes/databases were stopped/removed afterward. Existing
deprecation/Pydantic warnings remain (1,117 in the full run). Initial focused
invocations encountered a fixture parent-directory error and sandbox-denied
listeners; these were corrected/rerun, and failed attempts are not counted as
passes. One auxiliary auth run skipped its opt-in PostgreSQL test; the final full
regression enabled it and skipped nothing. No automatic-review rejection remains.

Commands actually run included:

```bash
# disposable orchestration, then apps/api with ATLAS_TEST_* URLs and nginx
python -m pytest tests ../../plugins/sdk/tests ../../plugins/proxmox/tests \
  -q -rs --tb=short --junitxml=/private/tmp/atlas-native-regression-results.xml
python -m pytest tests/test_native_install.py tests/test_release_foundation.py \
  tests/test_release_distribution.py tests/test_nginx_gateway.py -q --tb=short
python -m pytest tests/test_release_foundation.py tests/test_docker_ingress.py \
  tests/test_native_install.py tests/test_backups.py tests/test_mfa.py \
  tests/test_release_distribution.py tests/test_updates.py \
  ../../plugins/sdk/tests ../../plugins/proxmox/tests -q --tb=short
python -m alembic heads

# apps/web
npm test
npm run build

# repository
python -m compileall -q apps/api/app apps/api/scripts apps/api/tests \
  apps/worker/worker infra/install infra/release plugins
python3 infra/release/release.py metadata --tag v0.1.0
python3 infra/release/release.py build --dry-run --worktree --tag v0.1.0 \
  --output /private/tmp/atlas-native-release-acceptance
python3 infra/release/release.py verify --tag v0.1.0 \
  --output /private/tmp/atlas-native-release-acceptance
python /private/tmp/atlas-h3-check-docs.py
git diff --check
git status --short

# artifact directory
shasum -a 256 -c SHA256SUMS
```

Final remediation artifacts are outside Git at
`/private/tmp/atlas-native-release-acceptance`:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `atlas-docker-compose-0.1.0.tar.gz` | 567280 | `0d5d0fc05b5551d217219bad353ff062e5af6631f8ae530e4a26812c10cb4244` |
| `atlas-systemd-0.1.0.tar.gz` | 571573 | `013031cf9250be85d557b0c7a9989f2e427379f56545b70cc898c11853a0fece` |
| `atlas-release-0.1.0.json` | 986 | Covered by verified SHA256SUMS. |
| `SHA256SUMS` | 284 | Covers both packages and manifest. |

They explicitly record `source_state: working_tree` and base commit
`b7e0dae7122adf1b61846d63a0034e57d45d9b10`; they are non-publishable acceptance
artifacts. No commit, push, merge, rebase, tag or publication occurred.

## Original H4 completion evidence (before native acceptance and remediation)

## H3 acceptance reconciliation

The user confirms successful completion of all documented H3 real-world
acceptance tests, including real Docker acceptance, and accepts H3. This supplied
fact is recorded in the H3 report, active roadmap, feature ledger and deployment
references. It adds to the previously recorded 681 backend/PostgreSQL/migration
and 276 frontend passing tests and real local production browser evidence.
No individual Docker observations are inferred. The historical H3 execution
table remains historical. Real native/systemd lifecycle remains H6, and the five
existing npm findings remain unresolved.

## Delivered scope and compatibility

The [release architecture](../architecture/release-distribution.md),
[operator guide](../deployment/h4-releases.md) and
[upgrade guide](../deployment/h4-upgrades.md) define the full policy.

`apps/api/app/release.json` remains the canonical version/channel authority,
currently `0.1.0` / `beta`. Source metadata is unchanged. The shared parser
rejects malformed/duplicate metadata, validates SemVer and supported channels,
and requires exactly `v<version>` when a release tag is supplied. Beta permits
numeric versions or `-beta.N`, mapping to GitHub prerelease; stable forbids
prerelease identifiers. Build metadata does not affect ordering. Stable ignores
beta; beta considers supported beta/stable, with stable winning equal SemVer.
A beta numeric tag cannot be reused to promote the same number to stable.

Docker packages retain local Compose builds; no registry architecture or image
publishing was introduced. Native packages retain the H1 install paths and
systemd units. A reviewed path manifest includes runtime trees, build inputs,
method-specific helpers/gateway/units and selected operator docs. Other source
document links point to the exact official commit, avoiding development files
in the bundle. `PACKAGE.json`, injected canonical metadata, manifest and
SHA256SUMS provide consistent commit/method identity and integrity. Packaged
identity takes precedence over old preserved environment build IDs, without
runtime Git. About and build-info retain their existing fields/authorization.
Malformed metadata also fails Docker builds and protected fresh configuration.

No database migration was required; one head remains `20261004_0026`. Existing
routes remain; GET `/api/system-settings/updates` and POST
`/api/system-settings/updates/check` are additive. They enforce the existing
permission **and global** `system_settings.manage` boundary; unauthenticated,
unprivileged and customer-scoped access are denied before fetching. No customer/
site domain, graph/topology/relationship/knowledge/discovery/reconciliation,
MFA security or backup format was changed.

The Updates card uses the sibling `ops-card system-settings-section` container,
existing headings/tokens and shared Buttons, with semantic live status and a
responsive metadata definition list. It owns availability/guidance; About keeps
installed identity. Docker/native receive fixed-repository, method-specific
operator guides; development receives Git-workflow guidance.

The server uses only the fixed official public GitHub release-list API: no token,
ambient proxy, cookie jar, redirects, user/tenant/inventory data or remote HTML.
Five-second total timeout, three locally constructed 100-item pages and combined
1 MiB limit bound the response. Drafts, malformed versions/dates/records and
unsafe/nonmatching URLs are excluded. HTTP/DNS/TLS/timeout/JSON/size/deep-nesting
failures safely return unavailable; no startup request or audit/log flood exists.
Process-local successful cache lasts four hours, failure cache five minutes,
manual refresh at least sixty seconds apart, and concurrent requests share a
fetch. The contract returns current version/channel/build/method, status, safe
latest version/channel/date/link, method-specific guide URL, checked time,
cache flag and remaining refresh interval; never the raw GitHub payload.

Upgrade helpers are operator-run only. Docker builds before stopping writers,
uses the existing protected env-file/project/volumes, starts matching new code/
gateway and waits for migration/definition seeding/health. Native stops services,
replaces only managed apps/infra trees and reuses H1 dependency-build/unit/health
primitives, preserving configuration/database/keys/state/service identity.
Backup confirmation is required; no secret regeneration, volume deletion,
automatic rollback, self-update, web download/execution or host control exists.

## Validation actually performed

| Check | Actual result |
| --- | --- |
| Full API/SDK/plugin/PostgreSQL/migration regression | **776 passed, zero skipped**, including all existing H1/H2/H3 and optional PostgreSQL/nginx suites. Final focused metadata/installer/transport rechecks also passed after final hardening. |
| Focused H4/H1 tests | **115 passed**; semantic/channel/tag policy, HTTP bounds/failure/cache/concurrency, authorization, packages/checksums/imports/modes/links, archive attacks, reproducibility and simulated upgrade preservation. |
| Release-critical workflow command | **228 passed**, executed locally with workflow-equivalent SDK/Proxmox PYTHONPATH. No editable installation is used in CI because this repository tracks egg-info files and release construction requires a clean checkout. |
| Frontend | **279 passed, zero skipped**, final `npm test`. |
| Production frontend build | **Passed**, final `npm run build`. |
| Browser/visual | **Passed** against actual production Next/API/PostgreSQL/Redis/nginx and Chrome. Twenty-four light/dark × default/blue/purple × 1440/1024/800/390 states; no page overflow or JS errors. |
| Workflow | PyYAML syntax/permission/trigger/pin/publication-order regression and **actionlint 1.7.7 passed**. No GitHub-hosted execution. |
| Alembic | **Passed**, single `20261004_0026 (head)`. No migration changes. |
| Compilation | **Passed**, API/application/scripts/tests, worker, installers, release tooling and plugins. |
| Release dry run | Both packages, manifest and SHA256SUMS built; independent verification and extraction/help/config-validation performed. Artifact table below. |
| Reproducibility | Repeated construction produced byte-identical archives, manifest and checksum file with the same source/commit/toolchain. Dependency/image builds are not claimed byte-reproducible. |
| Checksums | Internal verifier and actual `shasum -a 256 -c SHA256SUMS` passed for both packages and manifest. SHA-256 is not a signature. |
| Compose | Static service/context/ingress/state/key/restart/COPY validation passed. **Actual Docker Compose CLI/config/image build was not run locally**, because no Docker CLI/daemon is installed. Workflow includes packaged Compose validation/build for hosted execution. |
| Native | Extracted installer help, unit/prerequisite/StateDirectory/privilege contracts and simulated helper preservation/order tests passed. **No real Linux systemd lifecycle, systemd-analyze or native dependency installation/upgrade** was run on this macOS host. |
| Audit | Live `npm audit --json`: **five unresolved findings**, one critical Next, three high nanoid/postcss/sharp, one moderate baseline-browser-mapping. Not clean. No runtime dependency/lockfile changes or new product license/audit impact. |
| Documentation / whitespace | Actual final local Markdown targets/code-fence and `git diff --check` results recorded below. |

The full regression used isolated disposable PostgreSQL 17.11 databases,
non-superuser H3 source/target ownership, real Redis 7.4.6 and nginx; Python 3.14
is the available local interpreter. CI/Docker target Python 3.12. Test databases
were removed after execution. Existing deprecation/Pydantic warnings remain;
passing is not warning-free. Sandbox restrictions initially prevented local
listeners/npm DNS; the authorized local test and registry-read commands then ran
with reviewed sandbox escalation. No automatic review rejection remained.

Commands actually executed included:

```bash
# apps/api with disposable ATLAS_TEST_* URLs, nginx and Redis
python -m pytest tests ../../plugins/sdk/tests ../../plugins/proxmox/tests \
  -q -rs --tb=short --junitxml=/private/tmp/atlas-h4-regression-results.xml
python -m pytest tests/test_release_distribution.py tests/test_updates.py \
  tests/test_release_foundation.py -q --tb=short
python -m alembic heads

# apps/web
npm test
npm run build
npm audit --json

# repository
python -m compileall -q apps/api/app apps/api/scripts apps/api/tests \
  apps/worker/worker infra/install infra/release plugins
python3 infra/release/release.py metadata --tag v0.1.0
python3 infra/release/release.py build --dry-run --worktree --tag v0.1.0 \
  --output /private/tmp/atlas-h4-release-acceptance
python3 infra/release/release.py verify --tag v0.1.0 \
  --output /private/tmp/atlas-h4-release-acceptance

# artifact directory
shasum -a 256 -c SHA256SUMS

# pinned local tooling, caches outside repository
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 .github/workflows/release.yml

git diff --check
git status --short
```

## Browser acceptance

`apps/web/scripts/check-updates-browser.mjs` ran through a disposable production
stack using the opt-in `tests.h4_browser_app` ASGI harness. Only that test module
redirects the server-side GitHub transport to a loopback HTTP source and exposes
its loopback control server; it is excluded from both packages. Normal Atlas has
no repository/source/control configuration endpoint. Real migrations/seeding,
setup, global Master login, settings authorization and UI ran unchanged. No
browser API interception was used, and no public Atlas GitHub release API read,
release page navigation, download, host command or publication was performed.
Official GitHub documentation/Action commit pages were read separately to verify
workflow/API/pin/attestation design.

The browser verified current/up-to-date, newer supported beta, unavailable source,
safe release link, cached response and production refresh cooldown; all three
installation guidance paths and identity fields; a real manual POST refresh
with a test-only shortened interval; and continued Dashboard/API health when
GitHub was unavailable. The backend suite separately enforces the real sixty-
second rate policy. The final matrix used actual profile theme/accent preferences.
Computed padding, radius, border, background and H2 typography were compared with
General at every size/theme/accent; desktop/mobile light/dark screenshots were
visually inspected alongside sibling cards. No JS errors or external browser
requests occurred. Backend credentials and setup codes arrived on stdin and
were excluded from reports/screenshots.

Final browser evidence:
`/private/tmp/atlas-h4-browser-56a9eab0/artifacts/report.json` and
`updates-{light,dark}-{1440,1024,800,390}.png`.

## Release dry-run artifacts

The output is deliberately outside Git at
`/private/tmp/atlas-h4-release-acceptance`. Its manifest explicitly records
`source_state: working_tree`, selected-source digest and base commit SHA; it does
not claim that the uncommitted H4 changes are in the recorded base commit.
Publication verification refuses these assets. Clean committed release
construction uses the exact Git snapshot and the same core implementation.
No live image, Release, tag or publication occurred.

| File | Bytes |
| --- | ---: |
| `atlas-docker-compose-0.1.0.tar.gz` | 564519 |
| `atlas-systemd-0.1.0.tar.gz` | 563829 |
| `atlas-release-0.1.0.json` | 986 |
| `SHA256SUMS` | 284 |

All three entries in SHA256SUMS verified. The manifest's package hashes/sizes
matched the actual files, identity and archive contents. Tests read and extracted
both validated roots with the data extraction filter, invoked both fresh
installer help paths and the upgrade help path, and validated a random ephemeral
protected Docker configuration without mutating it. Negative archives with
traversal, absolute paths, symbolic/hard links, duplicates, .env, database/Git
files, unsafe modes, missing installer/import, literal credential-like contents
and mismatched build identity were rejected even after recomputing checksums.
No secrets, Git metadata, tests, screenshots, caches, node_modules, virtualenv,
local database, backup or user data were included.

## Security review of the H4 diff

Reviewed H4-specific permissions, injection, source/asset/archive, credential,
network, UI and authorization boundaries. Final publication alone receives
contents-write; no id-token/packages/attestation permissions were added.
Tag/metadata/dev ancestry validation precedes dependency scripts. Manual dispatch
cannot publish; no PR or ordinary branch push triggers publication. Checkout
credentials are not persisted, Actions use official immutable SHAs, and the
publication token is scoped to the final native gh adapter step. All dynamic tag
values cross environment/argv boundaries; no expression enters shell run text,
no eval/shell=True or remote release-body execution exists. Uploaded assets are
limited to verified packages/manifest/checksums.

Review hardened duplicate canonical metadata, working-tree parent symlink
handling, archive-member counts and compatibility/source declarations, malformed
nested JSON, no-cookie transport, artifact identity precedence and protected
configuration's canonical policy validation. Tracked SDK egg-info regeneration
was avoided in CI by using source-module PYTHONPATH. Package paths are a reviewed
allowlist with runtime-dependency checks, source links/nonregular files are
rejected and no host/user/branch/uncontrolled timestamp enters package identity.
Server links must exactly match fixed official repository paths; remote content
never reaches HTML rendering or shell execution. New endpoints deny unauthorized/
scoped callers before network work; routine checks create no audit events. No
host-control capability or arbitrary repository URL setting exists.

This is an H4 diff review, not the H6 whole-product security review. Signing/
attestation are deferred after inspecting official GitHub capabilities, until the
repository release/verification policy is exercised. Existing upstream mutable
base-image tags and unpinned transitive Python dependency resolution remain
external build inputs; package bytes alone are the proven reproducibility scope.

## Completion report A–AS

| Item | Result / evidence |
| --- | --- |
| A | H3 user-confirmed real-world/Docker acceptance recorded without invented observations; native H6 and npm findings preserved. |
| B | Exact material file inventory below. |
| C–F | Sole release.json authority, shared strict SemVer policy, exact v-version tags and beta/stable GitHub mapping. |
| G–I | Reviewed Docker/native source packages extend H1 installers; Docker local builds retained, registry publishing absent. |
| J–L | Version/schema/commit/source/method/artifact manifest and standard SHA256SUMS; signing/attestation deferred explicitly. |
| M–O | Exact-commit release workflow, explicit least privilege, tag-only real publication, manual dispatch dry-run only. |
| P–R | Same local/CI packaging implementation, content/identity/checksum validation and proven same-toolchain byte reproducibility. |
| S–W | Fixed server-side public release list, five-second/1-MiB/three-page bounds, four-hour/five-minute/sixty-second cache policy, SemVer/channel selection and offline-safe status. |
| X–Y | Globally protected normalized update contract and consistent System Settings card with accessible live state/shared controls. |
| Z–AB | Matching Docker/native operator procedures and helpers preserve secrets/state/data; H3 backup-before-upgrade required/recommended; no web auto-update. |
| AC | Existing About/build-info preserved; injected commit/method identity wins over stale env without runtime Git. |
| AD–AF | Complete local nonpublishing dry run, exact filenames/bytes above and independent checksum verification. |
| AG–AI | 279 frontend and 776 full API/SDK/plugin/PostgreSQL/migration tests passed with zero skips; production build passed. |
| AJ | Real production browser/control-HTTP acceptance, all methods/states and 24 theme/accent/width checks; no browser interception/JS errors. |
| AK–AM | Local Compose CLI, real systemd lifecycle and hosted workflow execution not performed; static validation/actionlint passed. |
| AN–AO | H4 security review completed; five existing npm findings remain, no product dependency changes. |
| AP | Live publication, signing/attestation, Docker daemon/config/image build and real native lifecycle remain unexecuted here. Python 3.12 runtime not executed locally. |
| AQ–AS | Final documentation-link/whitespace results and exact repository state below. |

## Material files changed

| Files | Purpose |
| --- | --- |
| `.github/workflows/release.yml` | Deliberate exact-commit/tag release and dispatch dry-run pipeline with isolated publication permission. |
| `.gitignore` | Exclude generated distribution output. |
| `apps/api/app/release.py`, `apps/api/Dockerfile` | Shared canonical parsing/SemVer/channel/tag/order and packaged identity; malformed build metadata fails early. |
| `apps/api/app/services/updates.py`, `apps/api/app/routes/system_settings.py` | Bounded fixed GitHub transport, cache/normalized status and globally protected additive endpoints. |
| `infra/release/package-manifest.json`, `infra/release/release.py`, `infra/release/publish.py` | Reviewed package policy, deterministic build/verify CLI and thin native gh publication adapter. |
| `infra/install/configuration.py`, `infra/install/native.py`, `infra/install/upgrade.py` | Strict artifact-aware configuration identity, reused native primitives/help and configuration-preserving operator upgrades. |
| `apps/web/app/admin/system-settings/page.js`, `apps/web/components/updates.js`, `apps/web/components/updates.module.css`, `apps/web/lib/updates.mjs` | Sibling-card update experience, normalized copy and installation-specific guidance. |
| `apps/api/tests/test_release_distribution.py`, `apps/api/tests/test_updates.py`, `apps/api/tests/h4_browser_app.py` | Package/workflow/upgrade/parser/security/transport/permission tests and excluded opt-in backend browser harness. |
| `apps/web/tests/updates.test.mjs`, `apps/web/scripts/check-updates-browser.mjs` | UI regression and repeatable real backend browser/visual acceptance. |
| `README.md`, `docs/README.md` | Package installation/upgrade/dry-run references and current release position. |
| `docs/architecture/release-distribution.md`, `docs/architecture/deployment-and-upgrades.md` | H4 release/update architecture and compatibility with accepted deployment mechanisms. |
| `docs/deployment/h1-installation.md`, `docs/deployment/h3-backup-restore.md`, `docs/deployment/h4-releases.md`, `docs/deployment/h4-upgrades.md` | Package acquisition, checksum verification, deliberate publication, backup-first preserving upgrades and offline behavior. |
| `docs/product/development-roadmap.md`, `docs/product/feature-ledger.md`, `docs/testing/h3-encrypted-backup-restore.md` | H1/H2/H3 acceptance reconciliation and truthful H4 implementation/remaining gates. |
| `docs/testing/h4-release-distribution.md` | This validation/security/completion report and exact repository state. |

No migration, dependency/lockfile, existing Compose/gateway/systemd-unit,
backup/MFA/domain model or unrelated file changes were made.

## Final checks and repository state

Final local documentation validation passed: **12 changed Markdown documents,
171 relative link targets, balanced code fences**. `git diff --check` passed.
Final pinned actionlint execution returned exit 0 without diagnostics. The
workflow-equivalent release-critical command passed **228 tests**. Compilation,
independent checksum verification and both extracted installer/upgrade help
paths passed. Docker/native archives contained respectively **317 / 314**
reviewed regular files. Repeating the current acceptance dry run produced
byte-identical artifacts again. A checksum invocation from the repository root
initially could not resolve artifact-relative filenames; it was rerun in the
artifact directory and all three entries passed. No failing invocation is
counted as a pass.

The final full regression was 776 passed / zero skipped, followed by 115 focused
release/update/foundation tests after the last parser/configuration/manifest
hardening and 228 workflow-critical tests after the CI clean-checkout adjustment.
No product code changed after those relevant checks. Frontend/browser evidence
above is from the final UI build.

Only genuine remaining gates: real Docker CLI/daemon validation in this
implementation environment, actual native/systemd lifecycle (H6), GitHub-hosted
workflow execution and deliberate real publication, deferred signing/attestation,
and the five existing dependency findings for H5/H6. No runtime dependency was
added. No migration was created. No user work was discarded.

Branch remains `feature/h4-release-distribution` and HEAD remains
`b7e0dae7122adf1b61846d63a0034e57d45d9b10`. All changes are uncommitted.
No commit, push, merge, rebase, tag, Release or live registry publish occurred.
Generated assets and local acceptance evidence are outside Git.

`git status --short` at completion:

```text
 M .gitignore
 M README.md
 M apps/api/Dockerfile
 M apps/api/app/release.py
 M apps/api/app/routes/system_settings.py
 M apps/web/app/admin/system-settings/page.js
 M docs/README.md
 M docs/architecture/deployment-and-upgrades.md
 M docs/deployment/h1-installation.md
 M docs/deployment/h3-backup-restore.md
 M docs/product/development-roadmap.md
 M docs/product/feature-ledger.md
 M docs/testing/h3-encrypted-backup-restore.md
 M infra/install/configuration.py
 M infra/install/native.py
?? .github/
?? apps/api/app/services/updates.py
?? apps/api/tests/h4_browser_app.py
?? apps/api/tests/test_release_distribution.py
?? apps/api/tests/test_updates.py
?? apps/web/components/updates.js
?? apps/web/components/updates.module.css
?? apps/web/lib/updates.mjs
?? apps/web/scripts/check-updates-browser.mjs
?? apps/web/tests/updates.test.mjs
?? docs/architecture/release-distribution.md
?? docs/deployment/h4-releases.md
?? docs/deployment/h4-upgrades.md
?? docs/testing/h4-release-distribution.md
?? infra/install/upgrade.py
?? infra/release/
```

## Final native-remediation repository state

Final documentation validation passed: **18 changed Markdown documents, 188 local link targets, balanced code fences**. `git diff --check` passed. The state below includes pre-existing H4 work and this remediation; HEAD/branch are unchanged and no commit/push/publication occurred.

```text
 M .gitignore
 M README.md
 M apps/api/Dockerfile
 M apps/api/app/release.py
 M apps/api/app/routes/system_settings.py
 M apps/api/tests/test_nginx_gateway.py
 M apps/api/tests/test_release_foundation.py
 M apps/api/tests/test_setup_postgres.py
 M apps/web/app/admin/system-settings/page.js
 M docs/README.md
 M docs/architecture/authentication-and-access-control.md
 M docs/architecture/deployment-and-upgrades.md
 M docs/deployment/h1-installation.md
 M docs/deployment/h3-backup-restore.md
 M docs/deployment/reverse-proxy-examples.md
 M docs/deployment/single-origin.md
 M docs/deployment/split-origin-migration.md
 M docs/product/development-roadmap.md
 M docs/product/feature-ledger.md
 M docs/testing/h1-docker-ingress.md
 M docs/testing/h1-release-foundation.md
 M docs/testing/h3-encrypted-backup-restore.md
 M infra/install/configuration.py
 M infra/install/native.py
 M infra/systemd/atlas-api.service
 M infra/systemd/atlas-web.service
?? .github/
?? apps/api/app/services/updates.py
?? apps/api/tests/h4_browser_app.py
?? apps/api/tests/test_native_install.py
?? apps/api/tests/test_release_distribution.py
?? apps/api/tests/test_updates.py
?? apps/web/components/updates.js
?? apps/web/components/updates.module.css
?? apps/web/lib/updates.mjs
?? apps/web/scripts/check-updates-browser.mjs
?? apps/web/tests/updates.test.mjs
?? docs/architecture/release-distribution.md
?? docs/deployment/h4-releases.md
?? docs/deployment/h4-upgrades.md
?? docs/testing/h4-release-distribution.md
?? infra/install/native_ingress.py
?? infra/install/upgrade.py
?? infra/nginx/
?? infra/release/
```
