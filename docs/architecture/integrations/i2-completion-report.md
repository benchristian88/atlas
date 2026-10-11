# I2 — Generic Integrations, SecretProvider and Test Connection

12 October 2026. **PASS WITH DOCUMENTED FOLLOW-UPS** for I2, including completed
operator-reported live Docker upgrade and Proxmox connection acceptance. Native/
systemd, remote GitHub provenance and I4 source/discovery qualification remain
separate follow-ups. The live evidence below comes from the operator's deployment,
not from intercepted browser fixtures or local package tests.

The original implementation audit/results and Git inventory below are historical
snapshots of that development run. The operator subsequently committed/deployed
the feature branch. This acceptance follow-up began on clean Atlas HEAD
`2af196fd73aad1c8a1c18d253594c6bfb1e1292d`, branch
`feature/integrations-i2-generic-secrets-test-connection`; its edits are uncommitted
and unpushed. No live credential, private key or certificate fingerprint value is
recorded here.

## Audit, authority and starting state

All three repositories were readable/writable and clean at the original start.
The original implementation run used these branches and HEADs:

| Repository | Branch | HEAD | Starting status |
| --- | --- | --- | --- |
| atlas | `feature/integrations-i2-generic-secrets-test-connection` | `7e2a8c9ec1e04b27e1f32153347380f05d4d9a59` | Clean |
| atlas-connector-sdk | `feature/i2-canonical-sdk` | `2f121840e5b61dba9b39d0bfc25d176edffb8eef` | Clean |
| atlas-connectors | `feature/i2-proxmox-test-connection` | `6733d7e8269bfa154538fee233b1c5dae236b0cf` | Clean |

Atlas `dev` contained merged accepted I1 at the starting HEAD. Before changes,
AGENTS.md, models/migrations, reachable APIs/UI, tests, accepted ADRs 0003–0009,
v1.3, alignment/roadmap, I0/I1 reports, SecretProvider/runtime contracts, existing
crypto/backup, release/native/Compose packaging and UI architecture/mockups were
inspected. Starting Alembic head was `20261011_0027`. The recorded implementation
plan covered canonical extraction/package boundaries, additive persistence/crypto,
verified runtime probing, manifest UI, then regression/deployment/documentation.
`AtlasDiscoverySync._sync`, legacy plugin normalization and reconciliation code
remain unchanged and are not used by the new path.

One actual contract conflict was referred to the operator: v1 required discovery
and qualified sources even for a truthful probe. The operator approved an additive
versioned Manifest 1.x extension while retaining v1 and prohibiting example
activation. No historical ADR was rewritten and no architecture v1.4/v2 was created.

## Canonical SDK and licensing

`atlas-connector-sdk` is the sole canonical schema/validator owner, Apache-2.0.
Version **1.1.0**, artifact `atlas_connector_sdk-1.1.0-py3-none-any.whl`, is consumed
byte-for-byte by Atlas and Connectors through `vendor/sdk/requirements.txt`:

```text
SHA256 a01cf35d47ab2f791375586114527fca3ed6335a7611cff14a6e8475c8380e0e
```

Two pinned-backend builds produced identical wheels. The artifact contains three
schema resources plus Apache LICENSE/NOTICE. Original schema bytes were compared
directly to Atlas's starting Git tree:

| Unchanged canonical schema | SHA-256 |
| --- | --- |
| AIP 1.0 | `db34dc0d484a83998da9aeec4517648d60ca4ee6ddd4ed7657c4c0031133189d` |
| Manifest 1.0 | `e1305db294527ea6645c9bc17d0325c3cf05adf1aa23d3084f6899f0bed896c0` |

Atlas's former staged JSON files are non-authoritative `$ref` pointers. Production
uses installed SDK resources; I0 contract tests use SDK validation. There is no
second production schema implementation. New SDK helpers cover strict JSON,
SemVer/bounds, declarative config, source compatibility and deterministic AIP
fixtures without importing Atlas DB, tenancy, trust, runtime or vendor code.
Validation extras are optional so the isolated runtime has no unpinned jsonschema
dependency. API installs its existing pinned validator dependencies.

Manifest **1.1** adds `discover: false`, fixed Test Connection-only entry semantics
and `unqualified`/`untested` qualification. Probe packages omit discovery scopes,
classes, facts and entry points; discovery packages retain original declarations.
Manifest v1 is still accepted. Example/fixture manifests still fail production
activation. AIP is unchanged.

Atlas application/runtime stay AGPL-3.0-only. SDK and official Connector source are
Apache-2.0; new helper implementations contain no copied AGPL application/legacy
plugin implementation. The user-authorized schema extraction preserved bytes.
Upstream licences/notices remain separate; this is an engineering ownership result,
not a new legal conclusion. Atlas carries build artifacts, not vendor implementation
source. Root third-party notices and runtime/Connector SBOM metadata are updated.

## Persistence, migration and ownership

Additive migration `20261012_0028_generic_integrations.py` follows I1. The sole
head is **20261012_0028**. It adds nullable generic identity/version/digest/schema,
DataSource/creation-key/opaque credential reference, safe config/scopes/enabled/
retirement/last-test/version compatibility state, protected secret records, global
versioned taxonomy mappings and `integrations.run` with normal admin grants.
Legacy endpoint/identity/secret-reference columns and records are preserved.
No discovery records are backfilled and no history is destroyed.

Creation commits one scoped Integration, exactly one DataSource and encrypted
credential revision together. Scope-composite FK and existing DataSource-to-Site FK
bind the Customer/Site; DataSource uniqueness prevents sharing, and scoped
creation-key uniqueness/advisory serialization prevents retry duplication. DB and
API tests exercise rollback, mismatched scope, duplicate ownership and retries.
DataSource identity survives credentials, probes, disabling and retirement.
Retirement disables the connection/destroys live credentials but keeps Integration,
DataSource and attributable knowledge history.

## SecretProvider and data-key lifecycle

`AtlasEncryptedSecretProvider` uses the existing `data_encryption_key()` and
`ATLAS_DATA_ENCRYPTION_KEY`; there is no second master/operator key. Maintained
AES-GCM uses a fresh 12-byte nonce per field/revision. AAD is:

```text
atlas-integration-secret:v1:<customer>:<site>:<integration>:<field>:<revision>
```

Only ciphertext/nonce, version, ownership, field names and timestamps are stored
in `integration_secrets`; Integration holds an opaque UUID. Responses omit the
reference, ciphertext, nonce, AAD and every secret value. Config JSON accepts
only declared non-secret fields. Pydantic/write validation errors are sanitized;
request representations, audits and fixed diagnostics disclose no credential value.
Secret state returns field names/Configured only; no reveal/plaintext GET exists.

Create/replace validate the required visible fields, encrypt first, swap reference
and destroy the old revision in one transaction. Failure preserves the old state.
Clear is explicit/confirmed and leaves an unconfigured connection. Enable/disable
preserve credentials, DataSource and previous safe test metadata; config/credential
changes invalidate stale test state. Audit events record safe actor/scope/action/
field-name/result metadata.

The existing encrypted-data registry now includes the Integration adapter with
keyset batching, fresh nonce and no internal commits. All adapters authenticate
and rewrap in the existing restore transaction. Real PostgreSQL backup/restore
proved ciphertext preservation, no plaintext in archive/dump, destination-key
readability, stable IDs and old/wrong key/AAD rejection. A bad field aborts rewrap;
existing restore rollback/maintenance behavior is retained. Deployment-local control
credentials remain outside backups. Historical downloaded archives retain their
ciphertext under normal operator retention.

## Global mappings and package lifecycle

Mappings are keyed by Connector ID/version/kind/source-class, independent of
Customer/Site. Active existing Asset/Relationship stable keys have FK deletion
protection. Only exact recommended keys auto-map; display-name/fuzzy matches do
not. Relationship direction and allowed endpoint types are checked. Required
unresolved mappings block activation/use; optional declarations may be explicitly
ignored. Global runtime/package permissions authorize read/write administration;
scoped Integration management never authorizes global code or taxonomy changes.
Manual mapping changes and package activation are audited. Normal reference-data
administration is linked, with no Connector-created types.

Real live/disabled generic owners and legacy owners block uninstall. Retired
connections retain provenance but release executable ownership. New package
activation verifies its exact tuple, validates mappings and all dependent safe
config/scopes/configured-field presence without decrypting credentials, and updates
identities transactionally only after validation. Missing new required credentials
preserve the current tuple and return a safe configuration-required error; global
administrators see `Update requires configuration`. Scoped viewers receive no
cross-tenant dependent IDs/counts/config. Guided staging/migration of future newly
required fields remains later release UX; I2 does not force an incompatible update.

## Official Connector baseline and Proxmox package

The Apache monorepo has independently versioned `connectors/proxmox/`, manifest,
fixed playbook/module, README/NOTICE/SPDX inventory, tests, deterministic builder
and CI/tag-attestation preparation. Sorted plain USTAR, fixed owners/modes/mtime
and gzip timestamp make rebuilds identical. The domain Manifest is inside the
archive; digest/distribution/source identity descriptors and index are detached.

Proxmox **0.1.0**, Manifest **1.1**, exact archive:

```text
sha256:81addfe3509d3b7858523542382e4b2124b18eec7a1da2af52d7981d651a61f1
Atlas bootstrap index SHA256:
641361fd2a41ab5f36ff542b9fef7f8b5080cffc3c71b9016bcad8a4acee71ed
```

The package advertises Test Connection true, discover/scheduling/snapshot false,
no discovery entry/AIP/classes/facts/scopes and unqualified source versions. Both
token ID and secret are declared secret fields. Endpoint/TLS/fingerprint fields
are bounded Manifest declarations; Atlas UI/core contains no Proxmox field map.
Passwords/root login fallback is unsupported.

The module calls only `/api2/json/access/permissions` (the token's own permission
map to prove authentication) and `/api2/json/version`; it enumerates no inventory.
Empty grants produce bounded permission-limited information without claiming
inventory capability. Numeric version is sanitized; no version is called supported
without actual qualification. The narrow permissions behavior was checked against
[official Proxmox source](https://github.com/proxmox/pve-access-control/blob/master/src/PVE/API2/AccessControl.pm)
on 12 October 2026. This is I2 probe evidence, not the mandatory I4 external/ACL/
edge-case qualification review. No third-party source was copied.

## Runtime, leases and network security

New private authenticated operation:

```text
POST /v1/connectors/test-connection
{reference:{connector_id,version,digest},request_id,config,credentials}
```

No caller path/playbook/module/command/shell/arguments/package URL/scope/callback
is accepted. Fixed runtime-owned `test_connection.yml` is resolved from independently
verified installed ID/version/digest and immutable content hashes. Runtime remains
read-only to the store and has no DB/user/session/canonical tenancy authority.
The API does not import Ansible or call Proxmox. Discovery/get/cancel methods remain
explicitly unsupported; legacy discovery behavior is intact.

The provider grants only required visible secret fields under a request-bound
30-second in-memory lease. Saved tests hold the Integration row lock through
invocation, serializing credential/package changes. Lease exit clears/revokes
values. Preview creates no persistent connection/DataSource. Runtime receives
values through a private pipe, not argv/environment, then private 0700 workspace/
0600 files. Only internal input/result paths enter Ansible variables. `no_log`,
suppressed output/event retention and fixed result filtering keep credentials out
of logs/artifacts. Results are limited to 4 KiB, request to 128 KiB, probes to four
and child lifetime to 22 seconds (API deadline 28 seconds). Success/failure/error/
timeout kill/reap the process group and remove workspace. Startup removes abandoned
owned probe directories while retaining links/unrelated entries. Capacity rejection
also clears received credentials. Managed-memory physical zeroisation is not claimed.

HTTPS/default certificate verification is mandatory unless an explicit advanced
insecure exception is chosen; there is no downgrade. SHA-256 fingerprint is checked
before headers/token transmission. Userinfo, query/fragment, malformed ports,
unsupported schemes, redirects, loopback/link-local/unspecified/multicast/reserved
and known metadata targets are refused. RFC1918/ULA source addresses remain usable.
All DNS results are vetted and connections pin a numeric peer with original SNI/
host verification; no ambient proxy/cookie/redirect authority exists. DNS is bounded
by the runtime process deadline; socket operations use six-second limits and source
response bodies are bounded to 128 KiB. Raw vendor responses/errors never return.

Results contain only allowed category/boolean/TLS/version fields. Atlas derives
supported/untested/known-incompatible from the exact Manifest. Unqualified I2
versions warn, known-incompatible results fail; no unsupported qualification claim
is made. Probes write only safe audit and last-test metadata, with no Asset,
EvidenceRecord, DiscoveryRun, Service, Business Function or AIP ingestion side effect.

## API, RBAC and UI compatibility

Additive routes cover form metadata/unsaved preview, Integration list/detail/create/
PATCH, credential PUT/confirmed DELETE, saved Test Connection, confirmed retirement
and global versioned mapping GET/PUT. Existing list fields/legacy statuses/routes
remain supported; only generic records link to generic detail. Backend principal
scope filtering returns 404 for inaccessible/guessed objects; manage/run are checked
independently. Site scope is derived from authorized Atlas records. Secret status
is safe, not permission to materialize. Package/mapping operations retain global
permission checks. Sensitive validation/API responses use no-store/sanitized errors.

Configured/Add/detail reuse PageHeader, Button, Surface/Section, field/grid/table,
status/tokens and Atlas auth/workspace architecture. The wizard is Scope → Connection
→ Test → Review; conditional TLS controls and secret markers come from the Manifest.
Credentials begin blank and are never rehydrated; replacement is full write-only
and Clear explicitly confirmed. Detail shows safe last test/version/compatibility,
config and lifecycle. Global mapping resolution links existing reference-data pages.
No Run Now/schedule/onboarding/discovery control appears.

A real production Chrome build was inspected at 1440 and 390 pixels in light/dark,
default and two user accents. Twelve complete workflows cover configured-empty/Add,
authorized scope, blank passwords, verified/fingerprint/insecure warning, visible
loading, connected/auth/TLS/runtime failure, review/save/detail/configured state,
no password hydration, Replace/Clear, unresolved mappings, viewer/global hiding,
overflow and keyboard focus. Screenshots were viewed for forms/detail/mappings,
and compared with supplied mockups/adjacent primitives. Inspection corrected crowded
step markers and unstyled mapping selectors. Browser APIs are deterministic
interceptions: this proves UI behavior, separately from actual backend/runtime tests.
No real/source credential values appear in screenshots or reports.

## Deployment and external acceptance

**Docker: live acceptance completed; operator report recorded 12 October 2026.** Root build context carries
the exact SDK wheel offline with hash verification in API/runtime. Runtime retains
no published port, private control/source-egress separation, read-only root/store,
capability drop and no-new-privileges; ephemeral `/tmp` is a bounded tmpfs. It has
no Docker socket, DB mount, signing/data key or user session. Both package methods
passed independent worktree archive/identity/checksum verification. The original
local host had no Docker engine; the operator has now separately confirmed real
image builds and successful upgrade of an existing Docker deployment. Both
one-shot services exited 0: `runtime-init` provisioned control/store permissions,
and `connector-bootstrap` ran `python -m scripts.stage_integration_bootstrap`
through the trusted catalogue verifier/store path. Proxmox 0.1.0 was staged at:

```text
/var/lib/atlas-connectors/proxmox/0.1.0/81addfe3509d3b7858523542382e4b2124b18eec7a1da2af52d7981d651a61f1
```

This is the exact release-approved archive digest recorded above, not a manually
extracted or unverified package. Alembic reached `20261012_0028`. Installation via
the real Atlas Catalogue UI succeeded, and the probe-only package correctly
showed zero discovery taxonomy mappings. Database activation remained an explicit
administrator action. These facts are operator-reported live evidence; this
follow-up does not invent deployment image IDs or a deployed commit hash.

**Native/systemd: statically validated, not privileged Linux-tested.** Fixed loopback
8091, dedicated runtime account/control credential, pinned separate venv and
root-owned read-only store are retained. The root installer stages only fixed
release-approved bootstrap bytes using the same verifier, without database
activation. API/runtime share existing control-reader access; services acquire no
store write authority. Existing exact tuples can be verified/activated without a
write lock, while tampered bytes fail. Native filesystem package removal/missing
new package staging remains operator-owned. macOS cannot qualify Linux systemd/
root installation. Actual local HTTP and Ansible execution evidence below does
not substitute for a privileged deployment acceptance run.

**Actual local execution:** a separate temporary pinned runtime venv ran real
Ansible Runner/module from the verified archive through authenticated loopback
HTTP/Atlas client. Health matched all approved dependencies; unauthenticated probe
returned 401. An intentionally blocked loopback source produced `unsafe_endpoint`,
credential access was revoked and workspace removed. This proves real transport/
execution/cleanup without any live source connection or inventory.

**Remote GitHub:** release preparation uses exact repository
`benchristian88/atlas-connectors`, workflow `.github/workflows/release.yml`, protected
`connector-release` environment, tag/version verification and pinned
[actions/attest v4.2.1](https://github.com/actions/attest/releases/tag/v4.2.1).
It prepares/attests artifacts; this work has not pushed/triggered/published them.
The descriptor's source HEAD is contextual for this dirty-tree build, not proof
that its uncommitted source exists at that commit. Atlas's remote verifier remains
fail-closed. Local bootstrap trust binds exact digest to the Atlas release. Operator
qualification requires the reviewed pushed workflow, immutable assets, authenticated
attestation issuer/predicate/repository/workflow/source commit, trust roots and
revocation/negative cases before enabling remote production installation.

**Live Proxmox: I2 connection acceptance completed; operator report recorded 12 October 2026.** The
operator confirmed the Add Integration wizard end-to-end, including successful
live authentication with a dedicated least-privilege API token. The self-signed
Proxmox certificate was validated using SHA-256 fingerprint pinning. The detected
source version was **9.2.11**; compatibility correctly remained **untested** and
Manifest source qualification remained **unqualified**. This successful connection
is not an I4 qualified-version, permission/ACL or discovery acceptance result.

Review and saved detail pages neither displayed credential values nor rehydrated
secret fields. A saved Test Connection succeeded using the stored encrypted
credentials. After a runtime restart, a further saved Test Connection succeeded
without re-entering credentials. No token identity/value, private key, endpoint
or certificate fingerprint value is recorded in this acceptance evidence. The
operator did not report live invalid-token/failure-injection tests; existing
deterministic negative/security tests remain distinct evidence.

**UI acceptance follow-up:** the operator found Catalogue → Configured tab
navigation failing although direct `/integrations` worked. The Configured link
now explicitly selects `?tab=configured`, matching the existing Catalogue/Runtime
query-routing pattern. The default `/integrations` route remains supported; the
page layout and Runtime permissions are unchanged. Production browser regressions
click Catalogue → Configured → Catalogue → Runtime → Configured, verify URL,
selected navigation/content, and retain Runtime hiding/fallback for a scoped
viewer. Local follow-up execution results are recorded below; they are separate
from the operator's live source/deployment results.

## Executed validation

Environment: local Python 3.14, Node 24/Chrome, PostgreSQL 17 with fourteen isolated
non-superuser databases, Redis 7.4.6 and nginx 1.28 test binary. CI defines Python
3.12/Node 22/Linux; that remote workflow was statically linted, not executed here.
Protected temporary DB/key/test value files were not committed or printed.

| Repository/check | Exact command or equivalent execution | Result |
| --- | --- | --- |
| Atlas full backend + legacy SDK/Proxmox | From `apps/api`: `python -m pytest tests ../../plugins/sdk/tests ../../plugins/proxmox/tests -q --tb=short --junitxml=/private/tmp/atlas-i2-validation/backend-accepted.xml`, all fourteen `ATLAS_TEST_*` DB variables, Redis/nginx enabled | 1,074 passed, zero failures/errors/skips (168.00 seconds) |
| Atlas final targeted regressions | `python -m pytest tests/test_i2_integrations.py tests/test_i2_runtime.py tests/test_connector_packages.py tests/test_runtime_packaging.py tests/test_native_install.py tests/test_integration_runtime.py tests/test_integration_catalogue_api.py tests/test_repository_docs.py -q --tb=short` | 213 passed |
| Shared release-critical checks | From `apps/api`: `bash ../../infra/ci/release-critical.sh`, real nginx enabled | 434 passed |
| Canonical I0 fixtures | `python -m pytest docs/architecture/integrations/contracts/tests -q` | 77 passed |
| SDK | `python -m pytest -q --tb=short` | 14 passed |
| SDK deterministic build | `PYTHONPATH=/private/tmp/atlas-i2-build-tools python tools/build.py --outdir /private/tmp/atlas-i2-sdk-final-a` and `...-b`, wheel `cmp` | Passed; identical hash above |
| SDK integrity | Python byte comparison to `git show HEAD:...schema.json`, ZIP resource/LICENSE/NOTICE checks, both consumer artifacts compared | Passed |
| Connectors | `python -m pytest -q --tb=short` | 24 passed |
| Connector deterministic bundle | `python tools/build_bundle.py --output /private/tmp/atlas-i2-proxmox-acceptance` and `...-repeat`, archive `cmp` | Passed; identical digest above |
| Frontend | `npm test`; `npm run build` | 289 passed; production build passed |
| Production browser | `ATLAS_PLAYWRIGHT_MODULE=... ATLAS_CHROME_PATH=... node scripts/check-i2-integrations-browser.mjs` against local production server | 12 complete workflows; zero page errors; screenshots inspected |
| Real private HTTP/Ansible probe | `/private/tmp/atlas-i2-runtime-venv/bin/python /private/tmp/atlas-i2-runtime-live.py`; isolated exact baseline; `python -m pip check` | Authenticated transport/401/real module/cleanup passed; no broken requirements |
| Distribution | `python infra/release/release.py build --dry-run --worktree --output /private/tmp/atlas-i2-release-final`; `python infra/release/release.py verify --output /private/tmp/atlas-i2-release-final` | Both methods verified; non-publishable worktree dry run |
| Final SDK release/native upgrade regressions | `python -m pytest tests/test_release_distribution.py tests/test_native_install.py tests/test_runtime_packaging.py tests/test_ci_workflow.py tests/test_repository_docs.py -q --tb=short` | 96 passed after final packaging fixes |
| Final documentation links | `python -m pytest tests/test_repository_docs.py -q` after report completion | 14 passed |
| Workflow lint | actionlint 1.7.7 on Atlas CI/release, SDK CI, Connector CI/release | Passed |
| Migration | `python -m alembic heads` and actual I1→I2/fresh PostgreSQL/restore migrations | Single `20261012_0028`; tested |
| Python/whitespace | `python -m compileall -q ...`; `git diff --check` in all three repositories | Passed in all three repositories |

Backend warnings include existing deprecation/FastAPI/Pydantic/ORM test warnings;
no hidden skip constitutes acceptance. Earlier development runs caught stale I1
expectations, absent disposable Redis, a DELETE test helper mismatch, an audit-test
field typo and the report link before it existed; these were corrected and are not
presented as passing evidence. The full 1,074-test run preceded the final release-workflow SDK install/native vendor-copy corrections;
the affected release/upgrade/CI/docs suite was then rerun successfully (96 tests).
Final commands/results above are authoritative.
Local logs, protected test setup and browser evidence are under `/private/tmp`.
They are validation artifacts, not source/product state. The disposable web,
PostgreSQL and Redis validation services were stopped after completion.

## Acceptance follow-up validation — 12 October 2026

The operator-reported live Docker/Proxmox outcomes are recorded in the deployment
section above. This coding-session validation used local production Chrome with
intercepted API state; it did not repeat the live source tests or receive credentials.

| Check | Command | Result |
| --- | --- | --- |
| Before-fix tab regression | Production browser script against the previous build | Failed at Catalogue → Configured: explicit configured-tab URL was not reached |
| Frontend regression | From `apps/web`: `npm test` | 289 passed, zero failures/skips |
| Production build | From `apps/web`: `npm run build` | Passed |
| Navigation/browser regression | From `apps/web`: `ATLAS_PLAYWRIGHT_MODULE=/private/tmp/atlas-i1-browser-tools/node_modules/playwright/index.mjs ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' ATLAS_BROWSER_OUTPUT=/private/tmp/atlas-i2-tab-navigation-after node scripts/check-i2-integrations-browser.mjs` against production port 3137 | 12 complete workflows passed; zero page errors; tab URL/selected content/Runtime permission assertions included |
| Repository documentation | From `apps/api`: `python -m pytest tests/test_repository_docs.py -q` | 14 passed |
| Whitespace | `git diff --check` | Passed |

Changed files: the Integrations page uses an explicit Configured query link;
the production browser script adds real navigation and Runtime permission
regressions; this report, the Integration roadmap, feature ledger and product
status record the completed live acceptance without extending I2 scope. There
are no migration, backend/API or authorization contract changes.

Follow-up `git status --short` (all changes uncommitted/unpushed):

```text
 M apps/web/app/integrations/page.js
 M apps/web/scripts/check-i2-integrations-browser.mjs
 M docs/architecture/integrations/i2-completion-report.md
 M docs/architecture/integrations/integration-roadmap.md
 M docs/product/feature-ledger.md
 M docs/product/status.md
```

## Deferred hand-off and security observations

I3 must add durable orchestration/Run Now/schedules, run-bound token/ingestion receipt/
callback/finalisation/cancellation/recovery and maintenance coordination. No such
endpoint, worker dispatch, queue or token was implemented in I2. I4 must perform
the dated external-reference/least-privilege ACL review, real qualified-version
matrix and Proxmox identity/coverage/cluster/storage/guest-agent/edge-case work,
then deliberately upgrade the Connector to discovery capability. Docker/UniFi
implementation, onboarding and whole-release hardening remain I5–I8.

Preserve I1 exact identity/trust/protected store and existing Atlas data-key/backup
lifecycle. Source reachability is an operator configuration boundary; private LAN
addresses are intentionally allowed but local/metadata destinations are denied.
No direct source calls occur in Atlas core. No plaintext source credentials,
Authorization header, exception/stacktrace, arbitrary executable path or cross-tenant
object identifier is included in normal API/UI/audit output. No live secret was supplied to this coding session or added to any repository.
The operator supplied the dedicated token only to the deployed write-only UI. Physical memory erasure is not guaranteed by
managed runtimes; access revocation and file cleanup are the tested guarantees.

Remaining follow-ups are I4 source/discovery qualification, privileged native/
systemd acceptance, remote release/attestation verification and guided future
package-config migration. Live Docker upgrade and I2 Proxmox connection acceptance
are completed; they are no longer outstanding follow-ups.
They are explicit external/later-phase boundaries, not claims of current support.

## Material files and final repository state

The following historical inventory lists original implementation files and the
exact Git status captured at that time. It is not the current follow-up checkout
state; original edits were subsequently committed by the operator.


### atlas

| File | Purpose |
| --- | --- |
| `.github/workflows/ci.yml` | Pinned CI/build/attestation and regression consumption |
| `.github/workflows/release.yml` | Pinned CI/build/attestation and regression consumption |
| `THIRD-PARTY-NOTICES.md` | Dependency and project ownership notices |
| `apps/api/Dockerfile` | Hash-pinned SDK consumption in API packaging |
| `apps/api/app/integration_bootstrap/catalogue.json` | Digest-bound offline probe artifact/metadata; remaining entries non-executable |
| `apps/api/app/main.py` | Route reachability and credential-safe validation responses |
| `apps/api/app/models.py` | Additive generic identity, secret ownership and global mapping persistence |
| `apps/api/app/permissions.py` | Scoped Test Connection grant |
| `apps/api/app/routes/integrations.py` | Scoped Integration/global mapping and package/reference lifecycle API |
| `apps/api/app/routes/reference_data.py` | Scoped Integration/global mapping and package/reference lifecycle API |
| `apps/api/app/services/connector_catalogue.py` | Canonical contract policy, ownership/mappings, encrypted secret/rewrap and runtime transport |
| `apps/api/app/services/connector_contracts.py` | Canonical contract policy, ownership/mappings, encrypted secret/rewrap and runtime transport |
| `apps/api/app/services/connector_lifecycle.py` | Canonical contract policy, ownership/mappings, encrypted secret/rewrap and runtime transport |
| `apps/api/app/services/connector_store.py` | Canonical contract policy, ownership/mappings, encrypted secret/rewrap and runtime transport |
| `apps/api/app/services/encrypted_data.py` | Canonical contract policy, ownership/mappings, encrypted secret/rewrap and runtime transport |
| `apps/api/app/services/integration_runtime.py` | Canonical contract policy, ownership/mappings, encrypted secret/rewrap and runtime transport |
| `apps/api/requirements.txt` | Hash-pinned SDK consumption in API packaging |
| `apps/api/tests/test_backup_postgres.py` | I2 regression evidence and additive I1 expectation compatibility |
| `apps/api/tests/test_ci_workflow.py` | I2 regression evidence and additive I1 expectation compatibility |
| `apps/api/tests/test_connector_packages.py` | I2 regression evidence and additive I1 expectation compatibility |
| `apps/api/tests/test_i1_migration_postgres.py` | I2 regression evidence and additive I1 expectation compatibility |
| `apps/api/tests/test_integration_catalogue_api.py` | I2 regression evidence and additive I1 expectation compatibility |
| `apps/api/tests/test_integration_runtime.py` | I2 regression evidence and additive I1 expectation compatibility |
| `apps/api/tests/test_models.py` | I2 regression evidence and additive I1 expectation compatibility |
| `apps/api/tests/test_release_distribution.py` | I2 regression evidence and additive I1 expectation compatibility |
| `apps/api/tests/test_runtime_packaging.py` | I2 regression evidence and additive I1 expectation compatibility |
| `apps/runtime/ansible/Dockerfile` | Bounded exact probe process, SDK baseline/package notices and isolated packaging |
| `apps/runtime/ansible/atlas_runtime/server.py` | Bounded exact probe process, SDK baseline/package notices and isolated packaging |
| `apps/runtime/ansible/baseline.json` | Bounded exact probe process, SDK baseline/package notices and isolated packaging |
| `apps/runtime/ansible/sbom.cdx.json` | Bounded exact probe process, SDK baseline/package notices and isolated packaging |
| `apps/web/app/globals.css` | Manifest configuration/detail/mapping UI and browser/unit acceptance |
| `apps/web/app/integrations/page.js` | Manifest configuration/detail/mapping UI and browser/unit acceptance |
| `apps/web/components/integration-panels.js` | Manifest configuration/detail/mapping UI and browser/unit acceptance |
| `apps/web/lib/api.js` | Manifest configuration/detail/mapping UI and browser/unit acceptance |
| `apps/web/lib/status.mjs` | Manifest configuration/detail/mapping UI and browser/unit acceptance |
| `apps/web/tests/helpers/components.mjs` | Manifest configuration/detail/mapping UI and browser/unit acceptance |
| `docs/architecture/encrypted-backup-restore.md` | Truthful active architecture/product/operator/validation evidence |
| `docs/architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md` | Truthful active architecture/product/operator/validation evidence |
| `docs/architecture/integrations/contracts/README.md` | Truthful active architecture/product/operator/validation evidence |
| `docs/architecture/integrations/contracts/aip-v1.schema.json` | Truthful active architecture/product/operator/validation evidence |
| `docs/architecture/integrations/contracts/connector-manifest-v1.schema.json` | Truthful active architecture/product/operator/validation evidence |
| `docs/architecture/integrations/contracts/integration-runtime.md` | Truthful active architecture/product/operator/validation evidence |
| `docs/architecture/integrations/contracts/secret-provider.md` | Truthful active architecture/product/operator/validation evidence |
| `docs/architecture/integrations/contracts/tests/test_contracts.py` | Truthful active architecture/product/operator/validation evidence |
| `docs/architecture/integrations/integration-roadmap.md` | Truthful active architecture/product/operator/validation evidence |
| `docs/deployment/backup-restore.md` | Truthful active architecture/product/operator/validation evidence |
| `docs/deployment/integration-runtime.md` | Truthful active architecture/product/operator/validation evidence |
| `docs/deployment/releases.md` | Truthful active architecture/product/operator/validation evidence |
| `docs/development/from-source.md` | Truthful active architecture/product/operator/validation evidence |
| `docs/product/feature-ledger.md` | Truthful active architecture/product/operator/validation evidence |
| `docs/product/status.md` | Truthful active architecture/product/operator/validation evidence |
| `docs/testing/continuous-integration.md` | Truthful active architecture/product/operator/validation evidence |
| `infra/ci/prepare-postgres.py` | Native/Compose/release/CI artifact and migration integration |
| `infra/ci/release-critical.sh` | Native/Compose/release/CI artifact and migration integration |
| `infra/docker/docker-compose.yml` | Native/Compose/release/CI artifact and migration integration |
| `infra/install/native.py` | Native/Compose/release/CI artifact and migration integration |
| `infra/install/runtime.py` | Native/Compose/release/CI artifact and migration integration |
| `infra/install/upgrade.py` | Native/Compose/release/CI artifact and migration integration |
| `infra/release/package-manifest.json` | Native/Compose/release/CI artifact and migration integration |
| `infra/release/release.py` | Native/Compose/release/CI artifact and migration integration |
| `apps/api/app/integration_bootstrap/bundles/proxmox-0.1.0.tar.gz` | Digest-bound offline probe artifact/metadata; remaining entries non-executable |
| `apps/api/app/integration_bootstrap/manifests/docker.json` | Digest-bound offline probe artifact/metadata; remaining entries non-executable |
| `apps/api/app/integration_bootstrap/manifests/proxmox.json` | Digest-bound offline probe artifact/metadata; remaining entries non-executable |
| `apps/api/app/integration_bootstrap/manifests/unifi-network.json` | Digest-bound offline probe artifact/metadata; remaining entries non-executable |
| `apps/api/app/routes/integration_connections.py` | Scoped Integration/global mapping and package/reference lifecycle API |
| `apps/api/app/services/connector_mappings.py` | Canonical contract policy, ownership/mappings, encrypted secret/rewrap and runtime transport |
| `apps/api/app/services/integration_connections.py` | Canonical contract policy, ownership/mappings, encrypted secret/rewrap and runtime transport |
| `apps/api/app/services/integration_secrets.py` | Canonical contract policy, ownership/mappings, encrypted secret/rewrap and runtime transport |
| `apps/api/migrations/versions/20261012_0028_generic_integrations.py` | Additive I1-to-I2 migration |
| `apps/api/scripts/stage_integration_bootstrap.py` | Root-only fixed bootstrap staging through existing verifier |
| `apps/api/tests/test_i2_backup_postgres.py` | I2 regression evidence and additive I1 expectation compatibility |
| `apps/api/tests/test_i2_integrations.py` | I2 regression evidence and additive I1 expectation compatibility |
| `apps/api/tests/test_i2_migration_postgres.py` | I2 regression evidence and additive I1 expectation compatibility |
| `apps/api/tests/test_i2_runtime.py` | I2 regression evidence and additive I1 expectation compatibility |
| `apps/runtime/ansible/atlas_runtime/probe.py` | Bounded exact probe process, SDK baseline/package notices and isolated packaging |
| `apps/runtime/ansible/atlas_runtime/probe_worker.py` | Bounded exact probe process, SDK baseline/package notices and isolated packaging |
| `apps/runtime/ansible/notices/atlas-connector-sdk/LICENSE` | Bounded exact probe process, SDK baseline/package notices and isolated packaging |
| `apps/runtime/ansible/notices/atlas-connector-sdk/NOTICE` | Bounded exact probe process, SDK baseline/package notices and isolated packaging |
| `apps/web/app/integrations/[id]/page.js` | Manifest configuration/detail/mapping UI and browser/unit acceptance |
| `apps/web/app/integrations/mappings/[connector]/page.js` | Manifest configuration/detail/mapping UI and browser/unit acceptance |
| `apps/web/app/integrations/new/page.js` | Manifest configuration/detail/mapping UI and browser/unit acceptance |
| `apps/web/components/integration-configuration.js` | Manifest configuration/detail/mapping UI and browser/unit acceptance |
| `apps/web/lib/integration-configuration.mjs` | Manifest configuration/detail/mapping UI and browser/unit acceptance |
| `apps/web/scripts/check-i2-integrations-browser.mjs` | Manifest configuration/detail/mapping UI and browser/unit acceptance |
| `apps/web/tests/integration-configuration.test.mjs` | Manifest configuration/detail/mapping UI and browser/unit acceptance |
| `docs/architecture/integrations/i2-completion-report.md` | Truthful active architecture/product/operator/validation evidence |
| `vendor/sdk/atlas_connector_sdk-1.1.0-py3-none-any.whl` | Identical exact SDK wheel and mandatory SHA-256 lock |
| `vendor/sdk/requirements.txt` | Identical exact SDK wheel and mandatory SHA-256 lock |

```text
 M .github/workflows/ci.yml
 M .github/workflows/release.yml
 M THIRD-PARTY-NOTICES.md
 M apps/api/Dockerfile
 M apps/api/app/integration_bootstrap/catalogue.json
 M apps/api/app/main.py
 M apps/api/app/models.py
 M apps/api/app/permissions.py
 M apps/api/app/routes/integrations.py
 M apps/api/app/routes/reference_data.py
 M apps/api/app/services/connector_catalogue.py
 M apps/api/app/services/connector_contracts.py
 M apps/api/app/services/connector_lifecycle.py
 M apps/api/app/services/connector_store.py
 M apps/api/app/services/encrypted_data.py
 M apps/api/app/services/integration_runtime.py
 M apps/api/requirements.txt
 M apps/api/tests/test_backup_postgres.py
 M apps/api/tests/test_ci_workflow.py
 M apps/api/tests/test_connector_packages.py
 M apps/api/tests/test_i1_migration_postgres.py
 M apps/api/tests/test_integration_catalogue_api.py
 M apps/api/tests/test_integration_runtime.py
 M apps/api/tests/test_models.py
 M apps/api/tests/test_release_distribution.py
 M apps/api/tests/test_runtime_packaging.py
 M apps/runtime/ansible/Dockerfile
 M apps/runtime/ansible/atlas_runtime/server.py
 M apps/runtime/ansible/baseline.json
 M apps/runtime/ansible/sbom.cdx.json
 M apps/web/app/globals.css
 M apps/web/app/integrations/page.js
 M apps/web/components/integration-panels.js
 M apps/web/lib/api.js
 M apps/web/lib/status.mjs
 M apps/web/tests/helpers/components.mjs
 M docs/architecture/encrypted-backup-restore.md
 M docs/architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md
 M docs/architecture/integrations/contracts/README.md
 M docs/architecture/integrations/contracts/aip-v1.schema.json
 M docs/architecture/integrations/contracts/connector-manifest-v1.schema.json
 M docs/architecture/integrations/contracts/integration-runtime.md
 M docs/architecture/integrations/contracts/secret-provider.md
 M docs/architecture/integrations/contracts/tests/test_contracts.py
 M docs/architecture/integrations/integration-roadmap.md
 M docs/deployment/backup-restore.md
 M docs/deployment/integration-runtime.md
 M docs/deployment/releases.md
 M docs/development/from-source.md
 M docs/product/feature-ledger.md
 M docs/product/status.md
 M docs/testing/continuous-integration.md
 M infra/ci/prepare-postgres.py
 M infra/ci/release-critical.sh
 M infra/docker/docker-compose.yml
 M infra/install/native.py
 M infra/install/runtime.py
 M infra/install/upgrade.py
 M infra/release/package-manifest.json
 M infra/release/release.py
?? apps/api/app/integration_bootstrap/bundles/proxmox-0.1.0.tar.gz
?? apps/api/app/integration_bootstrap/manifests/docker.json
?? apps/api/app/integration_bootstrap/manifests/proxmox.json
?? apps/api/app/integration_bootstrap/manifests/unifi-network.json
?? apps/api/app/routes/integration_connections.py
?? apps/api/app/services/connector_mappings.py
?? apps/api/app/services/integration_connections.py
?? apps/api/app/services/integration_secrets.py
?? apps/api/migrations/versions/20261012_0028_generic_integrations.py
?? apps/api/scripts/stage_integration_bootstrap.py
?? apps/api/tests/test_i2_backup_postgres.py
?? apps/api/tests/test_i2_integrations.py
?? apps/api/tests/test_i2_migration_postgres.py
?? apps/api/tests/test_i2_runtime.py
?? apps/runtime/ansible/atlas_runtime/probe.py
?? apps/runtime/ansible/atlas_runtime/probe_worker.py
?? apps/runtime/ansible/notices/atlas-connector-sdk/LICENSE
?? apps/runtime/ansible/notices/atlas-connector-sdk/NOTICE
?? apps/web/app/integrations/[id]/page.js
?? apps/web/app/integrations/mappings/[connector]/page.js
?? apps/web/app/integrations/new/page.js
?? apps/web/components/integration-configuration.js
?? apps/web/lib/integration-configuration.mjs
?? apps/web/scripts/check-i2-integrations-browser.mjs
?? apps/web/tests/integration-configuration.test.mjs
?? docs/architecture/integrations/i2-completion-report.md
?? vendor/sdk/atlas_connector_sdk-1.1.0-py3-none-any.whl
?? vendor/sdk/requirements.txt
```

### atlas-connector-sdk

| File | Purpose |
| --- | --- |
| `LICENSE` | Complete project Apache licensing |
| `README.md` | Canonical ownership/build/phase documentation |
| `.github/workflows/ci.yml` | Pinned CI/build/attestation and regression consumption |
| `.gitignore` | Exclude generated caches/builds/artifacts |
| `NOTICE` | Schema extraction/source licensing notice |
| `pyproject.toml` | Pinned build backend, resources/version and optional validation dependency |
| `src/atlas_connector_sdk/__init__.py` | Canonical runtime-neutral schema/validation/config/fixture package |
| `src/atlas_connector_sdk/aip.py` | Canonical runtime-neutral schema/validation/config/fixture package |
| `src/atlas_connector_sdk/configuration.py` | Canonical runtime-neutral schema/validation/config/fixture package |
| `src/atlas_connector_sdk/contracts.py` | Canonical runtime-neutral schema/validation/config/fixture package |
| `src/atlas_connector_sdk/schemas/aip-v1.schema.json` | Canonical runtime-neutral schema/validation/config/fixture package |
| `src/atlas_connector_sdk/schemas/connector-manifest-v1.1.schema.json` | Canonical runtime-neutral schema/validation/config/fixture package |
| `src/atlas_connector_sdk/schemas/connector-manifest-v1.schema.json` | Canonical runtime-neutral schema/validation/config/fixture package |
| `tests/test_contracts.py` | Canonical contract or Connector probe security tests |
| `tools/build.py` | Deterministic reproducible build/schema evolution |
| `tools/evolve_manifest.py` | Deterministic reproducible build/schema evolution |

```text
 M LICENSE
 M README.md
?? .github/workflows/ci.yml
?? .gitignore
?? NOTICE
?? pyproject.toml
?? src/atlas_connector_sdk/__init__.py
?? src/atlas_connector_sdk/aip.py
?? src/atlas_connector_sdk/configuration.py
?? src/atlas_connector_sdk/contracts.py
?? src/atlas_connector_sdk/schemas/aip-v1.schema.json
?? src/atlas_connector_sdk/schemas/connector-manifest-v1.1.schema.json
?? src/atlas_connector_sdk/schemas/connector-manifest-v1.schema.json
?? tests/test_contracts.py
?? tools/build.py
?? tools/evolve_manifest.py
```

### atlas-connectors

| File | Purpose |
| --- | --- |
| `LICENSE` | Complete project Apache licensing |
| `README.md` | Canonical ownership/build/phase documentation |
| `.github/workflows/ci.yml` | Pinned CI/build/attestation and regression consumption |
| `.github/workflows/release.yml` | Pinned CI/build/attestation and regression consumption |
| `.gitignore` | Exclude generated caches/builds/artifacts |
| `connectors/proxmox/NOTICE` | Apache Proxmox probe-only implementation/Manifest/SBOM/notices |
| `connectors/proxmox/README.md` | Apache Proxmox probe-only implementation/Manifest/SBOM/notices |
| `connectors/proxmox/library/atlas_probe.py` | Apache Proxmox probe-only implementation/Manifest/SBOM/notices |
| `connectors/proxmox/manifest.json` | Apache Proxmox probe-only implementation/Manifest/SBOM/notices |
| `connectors/proxmox/sbom.spdx.json` | Apache Proxmox probe-only implementation/Manifest/SBOM/notices |
| `connectors/proxmox/test_connection.yml` | Apache Proxmox probe-only implementation/Manifest/SBOM/notices |
| `requirements-dev.txt` | Pinned SDK/validator/test development dependency |
| `tests/test_proxmox.py` | Canonical contract or Connector probe security tests |
| `tools/build_bundle.py` | Deterministic reproducible build/schema evolution |
| `vendor/sdk/atlas_connector_sdk-1.1.0-py3-none-any.whl` | Identical exact SDK wheel and mandatory SHA-256 lock |
| `vendor/sdk/requirements.txt` | Identical exact SDK wheel and mandatory SHA-256 lock |

```text
 M LICENSE
 M README.md
?? .github/workflows/ci.yml
?? .github/workflows/release.yml
?? .gitignore
?? connectors/proxmox/NOTICE
?? connectors/proxmox/README.md
?? connectors/proxmox/library/atlas_probe.py
?? connectors/proxmox/manifest.json
?? connectors/proxmox/sbom.spdx.json
?? connectors/proxmox/test_connection.yml
?? requirements-dev.txt
?? tests/test_proxmox.py
?? tools/build_bundle.py
?? vendor/sdk/atlas_connector_sdk-1.1.0-py3-none-any.whl
?? vendor/sdk/requirements.txt
```
