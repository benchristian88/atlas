# I1 runtime and catalogue completion record

Date: **11 October 2026**. Result: **PASS WITH DOCUMENTED FOLLOW-UPS**.

The requested runtime/catalogue shell is implemented and validated. This result
does **not** certify a live Docker/systemd deployment, complete external SDK
extraction, enable remote package installation, or qualify vendor discovery.
The explicitly permitted SDK and fail-closed provenance fallbacks are described
below. All changes remain uncommitted and unpushed.

## Repository baseline and audit

- Branch: `feature/integrations-i1-runtime-catalogue`.
- HEAD: `77eeff71e9a803f0f665ffa150b24537e29b83a6`.
- Starting `git status --short`: empty; clean working tree.
- The branch spelling differs from the requested
  `feature/integration-rel-1-runtime-catalogue`. The existing branch was preserved.
- HEAD is the merge of I0 PR #37; the accepted specification, alignment matrix,
  completion report, contracts and ADRs 0003–0009 were present before edits.
- Initial Alembic head: `20261004_0026`; final single head:
  `20261011_0027`.

Read the repository instructions, integration design/contracts/decisions,
models/migrations, authorization and protected seeding, existing Integration and
DataSource ownership, System Settings/update infrastructure, encrypted-data and
bootstrap handling, deployment/release tooling, worker boundary, UI architecture,
four required mockups and adjacent UI/test conventions before implementation.

Rechecked `AtlasDiscoverySync._sync`: it directly changes accepted Asset fields,
registers taxonomy and marks omissions stale without the new coverage policy.
It is unchanged and is not imported or extended by this work. Existing plugin,
discovery, evidence, reconciliation and graph semantics remain intact.

The short plan communicated before edits was: implement authenticated isolated
runtime health; add packaged catalogue/verified store and one global active
identity; expose additive RBAC-protected APIs and the existing Integrations tabs;
extend both installers/release packaging; then validate and document explicit
SDK/provenance/deployment boundaries. No parallel architecture specification or
new ADR was created.

## Implementation and compatibility

Atlas now has a separately deployed runtime source under
`apps/runtime/ansible`, a bounded authenticated HTTP client, a hash-verified
offline catalogue, strict Manifest consumer adapter, protected immutable package
store, generic compatibility/lifecycle services, global installed-state
persistence, protected permissions and real Configured/Catalogue/Runtime UI.

The additive APIs are:

| API | Authorization and behavior |
| --- | --- |
| `GET /api/integrations` | Scoped `integrations.view`; safe existing legacy records, authorized customer/site names, no endpoint/user/secret references. |
| `GET /api/integration-catalogue`, `/{connector_id}` | `integrations.view`; real packaged metadata and separate installed/compatibility state. |
| `GET /api/integration-runtime` | Global `integration_runtime.view`; safe health/baseline/capabilities and package count. |
| `GET /api/installed-connectors`, `/{connector_id}` | Global `integration_runtime.view`; safe exact active identities. |
| `POST /api/integration-catalogue/{connector_id}/install`, `/activate` | Global `integration_runtime.manage`; only an exact approved catalogue version/digest, no caller URL/path/upload. Update and rollback use the same verified selection. |
| `DELETE /api/installed-connectors/{connector_id}` | Global `integration_runtime.manage`; live-usage guard, transactional quarantine, retained knowledge/audit. |

Existing contracts and routes are preserved. Public package selections use a
bare 64-character SHA-256 digest; Manifest/distribution descriptors retain the
unchanged `sha256:` wire format. Translation is explicit. Invalid payloads,
catalogue tampering, transport errors and lifecycle failures return sanitized
responses; paths, credentials and stack traces are not serialized.

## Runtime architecture and actual health evidence

The private runtime implements only:

- `GET /v1/health`;
- `GET /v1/capabilities`;
- `POST /v1/connectors/verify` with exact ID/version/digest.

All operations require the control credential. Missing/wrong credentials return
401. Unknown execution operations are unavailable; no arbitrary playbook, shell,
path, Git, Galaxy, source configuration or job endpoint exists. Future client
test/start/get/cancel methods explicitly raise unsupported errors instead of
faking execution.

Atlas API/worker import no Ansible code. Runtime has no database/session/tenancy
authority and receives no Atlas authentication/database environment. Health is a
live read with a three-second total transport deadline, bounded 64 KiB responses,
no redirects/proxies/cookies/decompression and exact approved-baseline checks.
Disabled/unavailable/incompatible are normal states. A separate runtime database
record was unnecessary for one configured local runtime: health is live, while
durable installed/audit records preserve deployment identities.

A real temporary process with all fourteen pinned distributions reported healthy.
The actual Atlas HTTP client and public route orchestration produced:

| Local proof | Runtime result | Atlas health | Offline entries | Manual Asset |
| --- | --- | --- | --- | --- |
| Started runtime | Healthy | `ok` | 3 | Visible and unchanged |
| Stopped runtime | Unavailable | `ok` | 3 | Visible and unchanged |
| Restarted with the same secret file | Healthy | `ok` | 3 | Visible and unchanged |

Direct missing/wrong credential requests both returned 401. Listener inspection
showed only `TCP 127.0.0.1:8091 (LISTEN)`. No credential value was printed.

These local proofs used real HTTP and PostgreSQL with rollback-only manual
knowledge fixtures and a deterministic global test Principal dependency. They
do not claim deployed user-session/ingress or systemd-account qualification.
Local execution used Python 3.14/macOS and a temporary pinned distribution target;
production isolation is defined by the separate container/native venv and account.

## Docker networking and deployment proof

`infra/docker/docker-compose.yml` defines separate `runtime` and networkless
`runtime-init` services. Runtime has **no ports mapping**, connects only to
`runtime_private` with `internal: true`, mounts control/store volumes read-only,
uses a read-only filesystem, drops capabilities and enables no-new-privileges.
It has a credential-authenticated healthcheck and `unless-stopped` restart policy.
No Docker socket, PostgreSQL data/socket, host root or writable source mount exists.

API reaches `http://runtime:8091` on that private network. The existing gateway
remains the only public ingress. API/web readiness does not depend on runtime or
its provisioner. The installer starts core services first and treats optional
runtime readiness failure as an explicit warning; upgrades preserve this isolation.

This networking/packaging evidence is source/static regression proof. Docker is
not installed on this macOS host, so image builds, actual Compose configuration,
fresh startup, public ingress and stop/restart recovery in a disposable Docker
deployment remain operator acceptance items. Both CI workflows now build the
runtime/provisioner alongside API/web/worker; Actions were not executed here.

## Native/systemd packaging and credential lifecycle

Native source uses a dedicated `atlas-runtime` account and
`/opt/atlas/runtime-venv`, with exact `pip --no-deps` lock installation and
`pip check`. It requires no Docker/Podman. The dedicated hardened systemd unit
fixes loopback binding in code, does not load `atlas.env`, and gives only read
access to runtime control/store material. Runtime dependency/start failures
produce safe warnings and do not prevent core startup. Legacy upgrades tolerate
the previously absent runtime unit.

The native provisioner creates independent 384-bit random control material at
`/etc/atlas-runtime/control.secret`: root-owned, group
`atlas-runtime-control`, mode `0640`, inside a `0750` directory. API/runtime
receive that supplementary reader group; runtime cannot read Atlas's auth/DB
configuration. Existing valid material is preserved; invalid existing material
fails closed. Docker generates the same independent randomness once into
`runtime_control`, with directory `0700` and file `0400`, mounted read-only by
API/runtime. The secret is independent of AUTH/session, data-encryption, source
and future run-ingestion credentials.

Both installers support `--manual-only` and persist the opt-out. Upgrades append
missing runtime settings idempotently, preserving existing secrets, package state
and explicit opt-out. Original staging schema/manifests are copied at their
original documentation path for native fresh/upgrade deployments.

Native ownership/unit/idempotency/failure behavior is covered by static/helper
tests. Actual privileged Debian/systemd install, permissions under real service
identities, reboot, upgrade and failure isolation remain unexecuted because this
host has no Linux/systemd acceptance environment.

## SDK canonical-source/extraction result

**SDK extraction is not complete.** No sibling/local `atlas-connector-sdk`
project exists under `/Users/Ben/Code`; a separate owned/licensed project could
not safely be established within this repository workspace.

The request explicitly permitted retaining staging behind an isolated adapter in
this case. The unchanged schema files remain solely at:

- `docs/architecture/integrations/contracts/aip-v1.schema.json`;
- `docs/architecture/integrations/contracts/connector-manifest-v1.schema.json`.

`connector_contracts.py` is a narrowly isolated Atlas consumer, not a second SDK.
It pins Manifest identity `urn:atlas-connector-sdk:manifest:1.0` and SHA-256
`e1305db294527ea6645c9bc17d0325c3cf05adf1aa23d3084f6899f0bed896c0`, enables
Draft 2020-12 format validation and checks semantic references/bounds. Missing or
changed contracts fail closed. Deployment includes the original artifacts; no
competing source schema or existing AGPL-to-Apache relicensing was introduced.

Operator action: establish the separately owned SDK/licence provenance, extract
both schemas verbatim preserving identity/version, release the canonical package,
pin Atlas/runtime consumption and remove the staging adapter dependency. Accepted
ADR 0005 and the intended Apache SDK boundary remain unchanged; the documented
fallback is not a claim that the release extraction gate is complete.

## Approved baseline and initial supply-chain inventory

| Identity | Approved value |
| --- | --- |
| Runtime | `0.1.0` |
| Control protocol | `integration-runtime-v1` |
| AIP version | `1.0` |
| Baseline | `atlas-ansible-i1-v1`, version `1.0.0` |
| ansible-core / runner | `2.19.7` / `2.4.3` |
| Baseline SHA-256 | `11bad86b6a5b400980b0fd4733be4ea8d6bd07f8c4f76bea5d1d01685ad09825` |
| Lock SHA-256 | `437f84305958af89ed0864ca5d72c6fbfe740a3f422d1bdd5b0d610a6ab70a59` |

The lock additionally pins cffi 2.1.1, cryptography 50.0.2, jinja2 3.1.6,
lockfile 0.12.2, markupsafe 3.0.4, packaging 26.3, pexpect 4.9.0,
ptyprocess 0.7.0, pycparser 3.11, python-daemon 3.1.2, pyyaml 6.0.3 and
resolvelib 1.2.1. Vendor Collections are empty and not prequalified.
Docker pins the immutable Python 3.12 base-image manifest digest. Production
performs no dynamic Galaxy or unpinned dependency mutation.

`sbom.cdx.json` records exact versions, reference wheel hashes/licensing and
original notices under `notices/`. Reference artifacts are CPython 3.12 Linux
x86_64; this initial inventory is not final image/OS or all native-platform
qualification. Runtime GPL dependencies remain inside the runtime boundary.
Atlas remains AGPL-3.0-only.

## Catalogue, compatibility and protected store

The release-packaged `integration_bootstrap/catalogue.json` is immutable
catalogue truth, independently SHA-256 pinned:
`cb325e28b96e0632fe9df1dd3c2163b21fbb545b46f1806197aa4bb5541bc51a`.
Original example manifests have per-file pins. Catalogue reads need no network.
There is no fabricated remote refresh source.

Proxmox VE, Docker + Compose and UniFi Network are official **metadata-only**
entries. Versions/digests are null, package availability is false, source versions
are not qualified, licences read “Not published,” and no install/configure actions
appear. Example manifests cannot activate. Internal phase identifiers were removed
from product copy after real-payload browser inspection.

Generic compatibility covers Atlas/SDK/AIP/control/baseline version bounds,
implementation kind and exact required dependency identity/digest. Missing
approved dependencies require a runtime update; they never trigger installation.
Available/installable/installed/update/runtime-update/incompatible/verification
states are represented. Nonempty requirements without authenticated dependency
digest evidence fail closed.

The protected store layout is:

```text
/var/lib/atlas-connectors/
  <connector-id>/<semver>/<raw-sha256>/
    bundle.tar.gz
    manifest.json
    verification.json
    contents/
```

Paths derive only from validated internal package identity. Installation reads
only a fixed approved packaged source. Archives require exact digest/provenance,
embedded domain Manifest equality and notice/SBOM files. Bounds include 20 MiB
compressed archive, 10 MiB per file, 64 MiB content expansion, 256 members and
255-character paths, plus bounded tar header padding. Raw gzip expansion and
plain USTAR header preflight happen before tarfile can process hidden metadata.
PAX/GNU/sparse/special/link records, traversal, duplicates, unsafe permissions,
symlink ancestors and FIFO/nonregular reads are rejected.

Verified metadata/content is written into an immutable staging directory, fsynced
and atomically published. Runtime independently verifies the exact tuple, archive,
embedded Manifest, receipt and every extracted hash. Its store mount/access is
read-only. Native root ownership stays authoritative; no root HTTP writer was
added. Because I1 ships no executable bundles, the future native executable
release workflow must attach to the existing privileged operator/package boundary
before offering production installs.

## Database, activation, rollback and uninstall

One additive migration, `20261011_0027_installed_connector_packages.py`, follows
`20261004_0026`. It creates only global operational installed state and seeds
protected runtime permissions. It changes no scoped Integration/credential fields,
accepted knowledge or historical migration. Fresh upgrade and previous-head
upgrade preserve existing customer data and scoped grants.

`InstalledConnectorPackage.connector_id` is the primary key: one active identity
per Connector, not side-by-side active versions. Database checks admit only active,
verified rows. Version/digest/protocol/publisher/evidence/baseline/timestamps are
safe operational metadata; catalogue content remains packaged.

A transaction advisory lock serializes absent-row installs, updates, rollback and
uninstall. Activation checks compatibility, exact verified store identity and
independent runtime inspection before switching the active row and writing the
existing audit event. Failed activation retains the prior active identity.
Historical audit events retain exact version/digest.

Rollback explicitly selects another compatible verified catalogue tuple. The
usage-counter abstraction queries current Integration ownership conservatively:
all legacy rows, including disabled ones, are live. I2 can extend it for reviewed
retirement rather than replacing a hard-coded zero.

Uninstall atomically quarantines **all versions** under the Connector, removes
database active authority/audits in one transaction, restores every address if the
transaction fails, and deletes only the opaque quarantined subtree after commit.
Concurrent newly installed code is not deleted by old cleanup. Cleanup failure
returns a safe pending flag. Assets, DataSources, runs, evidence, assertions,
Changes and discovery/knowledge history are never purged.

## RBAC, tenancy and security observations

Protected `integration_runtime.view/manage` keys are seeded idempotently for
built-in administrator roles. Runtime/package routes require global grants;
customer/site grants carrying those keys still fail. `integrations.manage`
alone never authorizes global code installation. Scoped configured queries use
the existing authorization/context predicates and do not expose hidden IDs/counts,
endpoints or credential references.

Security regressions cover missing/wrong control auth, no public runtime port,
loopback-only native binding, secret/non-disclosure, unsupported execution input,
archive/path/link/FIFO/bomb bounds, digest and embedded Manifest tampering,
fail-closed provenance, exact identity/verification/one-active invariants,
scoped/non-admin access, outage isolation and offline catalogue behavior.

No real credential appears in source, documentation examples, test fixtures,
API/UI output or release artifacts. Tests generate ephemeral material at runtime.
The unchanged canonical schemas, legacy SDK/plugin code, worker and discovery
services were checked for scope drift. No source credentials, Test Connection,
Integration configuration/create workflow, scheduling, Run Now, AIP callback,
job secret/token, vendor call, asset/service/function creation or onboarding
implementation was added.

## Provenance research and exact remaining gap

SHA-256 is verified independently of provenance. A generic verifier interface is
separate from bootstrap and GitHub/Sigstore policy. Bootstrap accepts only exact
ID/version/digest tuples allowlisted by the trusted release-packaged catalogue,
not self-asserted bundle trust. I1 has no executable bootstrap entries; inert
deterministic bundles exercise this boundary.

The authoritative
[GitHub CLI verification documentation](https://cli.github.com/manual/gh_attestation_verify)
describes repository/signer-workflow or certificate-identity constraints,
source digest/predicate checking and offline bundle/custom trusted-root inputs.
The [Sigstore bundle documentation](https://docs.sigstore.dev/about/bundle/)
requires artifact digest and timestamp/signing-validity verification; its
[threat model](https://docs.sigstore.dev/about/threat-model/) distinguishes valid
identity from approved trust and covers trust-root freshness. Reviewed on
11 October 2026.

No official released Connector repository/workflow artifact, reviewed pinned
verifier dependency or packaged trust-root bundle exists here. Therefore the
production GitHub/Sigstore adapter **always fails closed** with
`official_provenance_verifier_unavailable` after independent digest checking.
It does not accept a manifest claim as a signature, assume an external gh/cosign
CLI, download mutable branches or offer a skip-verification path.

Hand-off: qualify the official immutable release/workflow identity, pinned
verification implementation and offline trust-root/revocation policy, then prove
exact digest/repository/workflow/source binding before enabling remote installs.
This is the explicitly allowed secure boundary fallback, not completed remote
attestation verification.

## UI implementation and visual acceptance

The existing Integrations route now provides Configured, Catalogue and authorized
Runtime tabs. Configured displays safe real records or a true empty state.
Catalogue uses backend data and backend-approved immutable actions only. Runtime
shows health/version/protocol/baseline/packaging/Ansible versions and subdued
technical digests/capabilities. No control credential or fake Configure/Test/Run
flow is present.

Read all four required mockups and the canonical UI architecture guide. Reused
PageHeader, Button, EntityIdentity, Surface/Section, CatalogueFilters, DataTable,
central statuses, auth/workspace context and sibling admin tabs. Browser
inspection compared catalogue/runtime structures to the mockups and computed
Surface styling to System Settings. Keyboard focus, semantic controls,
light/dark, user accents and responsive widths were checked.

- Frontend unit suite: **285 passed**.
- Production Next build: **passed**, 39 routes.
- Production-build fixture matrix: **264 passed** across 11 scenarios,
  light/dark, default/blue/purple accents and widths 1440/1024/800/390.
- Final real-API-payload browser smoke: **12 passed** (8 catalogue/healthy and
  4 unavailable), desktop/mobile and light/dark. Captured real route/HTTP/runtime
  responses rendered correct 2.19.7/2.4.3 versions and final operator-facing copy.
- Screenshots were viewed directly; visual acceptance is not inferred from unit
  snapshots. No overflow/browser errors or unsafe management controls surfaced.

The 264-state matrix uses deterministic API fixtures for unreleased installable/
installed/failure states. The 12-check smoke uses real captured API/runtime
payloads with intercepted browser authentication/context/transport. Neither
claims a deployed Docker/native end-to-end browser stack.

## Tests and commands actually executed

Commands below ran from `apps/api` unless stated otherwise. Temporary protected
environment files supplied thirteen isolated PostgreSQL databases; nginx 1.28.3
and Redis 7.4.6 were built solely under `/private/tmp`, with verified official
archives and loopback listeners. No host package installation occurred.

```bash
source /private/tmp/atlas-i1-validation-15_hurfs/closure.env
export ATLAS_TEST_NGINX=/private/tmp/atlas-i1-test-services/nginx/sbin/nginx
PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/private/tmp/atlas-i0-test-deps:.:../../plugins/sdk:../../plugins/proxmox \
  .venv/bin/python -m pytest tests ../../plugins/sdk/tests ../../plugins/proxmox/tests \
  -q -rs --tb=short -W ignore \
  --junitxml=/private/tmp/atlas-i1-validation-15_hurfs/backend-closure.xml
```

**Final full matrix: 1,040 passed, zero skips, zero failures (152.58 seconds).**
This includes existing API/plugin, PostgreSQL migrations, backup/MFA/auth,
deployment/release, docs, ingress and new runtime/package/security suites.

```bash
PYTHONPATH=/private/tmp/atlas-i0-test-deps:. .venv/bin/python -m pytest \
  ../../docs/architecture/integrations/contracts/tests -q -W ignore
.venv/bin/alembic heads
```

**I0 contracts: 77 passed. Alembic: one head, 20261011_0027.**
I0 runs separately because the legacy SDK has another `test_contracts.py`
module name; combining them in one default pytest process caused a collection
collision. No schema/test was deleted to hide it.

After final whole-Connector uninstall hardening:

```bash
source /private/tmp/atlas-i1-validation-15_hurfs/test.env
PYTHONPATH=/private/tmp/atlas-i0-test-deps:.:../../plugins/sdk:../../plugins/proxmox \
  .venv/bin/python -m pytest tests/test_connector_packages.py \
  tests/test_connector_lifecycle_api.py tests/test_connector_lifecycle_postgres.py \
  tests/test_integration_catalogue_api.py -q --tb=short -W ignore
```

**118 passed**, including both-version removal/restoration, real PostgreSQL/audit
transaction failures and independent store inspection.

Other successful executed validation:

| Command/check | Result |
| --- | --- |
| Final focused runtime/native/release/CI suite | 127 passed before final CI wiring. |
| Updated `bash ../../infra/ci/release-critical.sh` | 410 passed before two final whole-store removal tests. |
| Workflow assertions | 5 passed. |
| Pinned actionlint 1.7.7 on both workflows | Passed. |
| Catalogue/package final focused suite | 79 passed. |
| Catalogue/API/docs focused regression | 118 passed after copy correction, before final report expansion. |
| `npm test` from `apps/web` | 285 passed. |
| `npm run build` from `apps/web` | Passed. |
| `node apps/web/scripts/check-integrations-browser.mjs` with temporary Playwright/Chrome environment | 264 passed. |
| Temporary `node /private/tmp/atlas-i1-ui-live-smoke.mjs`, healthy/unavailable modes | 12 passed. |
| Real client/route proof script, healthy/unavailable/recovered | All passed; knowledge unchanged. |
| Direct missing/wrong runtime credential and listener inspection | 401/401; loopback only. |
| Worktree release dry-run build and independent verifier | Both package methods passed; final snapshot verification recorded below. |
| `git diff --check` | Clean. |

An earlier full run reported 952 passed, 68 nginx skips and one stale backup
migration-head assertion. That assertion was updated for the new additive head;
temporary nginx/Redis enabled the final zero-skip run. Initial missing local
development dependencies were resolved using existing/pinned dependency tooling.
No failing regression was removed.

## Documentation and exact material files

Updated the active specification/contract README only to document the explicitly
authorized SDK fallback, without rewriting I0 history or ADR decisions.
Roadmap, product status/feature ledger, installation/upgrades, runtime operator
guide, CI guide and third-party notices now distinguish implemented shell work
from SDK/provenance/live deployment and I2+ work.

| Files/group | Purpose |
| --- | --- |
| `apps/api/app/main.py`, `models.py`, `permissions.py`, `requirements.txt` | Additive routing, global active state/RBAC and existing I0 JSON Schema pin. |
| `apps/api/app/routes/integrations.py` | Safe scoped records and global runtime/catalogue/package APIs. |
| `services/integration_runtime.py`, `connector_contracts.py`, `connector_catalogue.py`, `connector_verification.py`, `connector_store.py`, `connector_lifecycle.py` | Bounded transport, strict adapter, packaged truth, verifier policy, protected filesystem and atomic lifecycle. |
| `apps/api/app/integration_bootstrap/catalogue.json` | Truthful offline three-entry metadata snapshot. |
| `apps/api/migrations/versions/20261011_0027_installed_connector_packages.py` | Sole additive migration; global table and protected permissions. |
| New API runtime/catalogue/package/lifecycle/migration test files | Security, tenancy, identity, SQL/FS atomicity, offline and packaging regressions. |
| Existing model/backup/native/release/CI test files | Extend exact table/head/service/package/matrix expectations. |
| `apps/runtime/ansible/Dockerfile`, `README.md`, `atlas_runtime/*`, `baseline.json`, `requirements.lock`, `sbom.cdx.json`, `notices/*` | Isolated process/image, provisioning/control/inspection, pinned inventory and preserved upstream licences. |
| Eight `apps/web` files listed in repository state | Reachable tabs/cards/runtime, shared states/helpers, regressions and production browser acceptance script. |
| `apps/api/Dockerfile`, `infra/docker/docker-compose.yml` | Canonical schema/baseline packaging and private default runtime. |
| `infra/install/{compose,configuration,native,runtime,upgrade}.py` | Automatic/preserved credential, native account/store/venv, opt-out and failure isolation. |
| `infra/systemd/atlas-api.service`, `atlas-runtime.service` | Separate hardened runtime and API secret-reader group. |
| `infra/release/{package-manifest.json,release.py}` | Both package methods include required runtime/contracts/notices and current schema. |
| `infra/ci/{prepare-postgres.py,release-critical.sh}`, both workflow files | Thirteen DBs, new security suites, separate I0 and runtime image builds. |
| Active integration/product/deployment/testing docs and `THIRD-PARTY-NOTICES.md` | Truthful status, operator behavior, validation and licensing boundaries. |

The exact complete path inventory, including every upstream notice, is the
`git status --short --untracked-files=all` block below.

## Remaining acceptance and I2 hand-off

1. Establish/extract/license-review and pin the external canonical SDK; replace
   the isolated staging adapter. No remote repository was created.
2. Qualify the official immutable Connector release pipeline and pinned
   GitHub/Sigstore/offline trust-root verifier before remote installation.
3. Perform real disposable Docker image/configuration/start/ingress/outage/restart
   and upgrade acceptance; Docker tooling is absent here.
4. Perform privileged Debian/systemd fresh install, actual account/file permissions,
   reboot persistence, idempotent upgrade and runtime failure acceptance; this
   macOS host cannot run that environment.
5. Qualify image/OS/native-platform dependency/license inventory and the future
   native privileged executable-package install workflow with real bundles.
6. I2 attaches generic scoped configuration/SecretProvider and reviewed retirement/
   mapping/update guards to existing ownership; I3 adds dispatch/jobs/AIP/token
   lifecycle. Vendor implementations, final qualified offline bundles, onboarding
   and final release hardening remain I4–I8.

No source/vendor/discovery work is claimed by shell acceptance. No commit, merge,
push, tag, release, rebase, reset or Git-history mutation occurred.

## Final packaging and hygiene

Final release packages were built and independently verified:

```bash
python3 infra/release/release.py build --dry-run --worktree \
  --output /private/tmp/atlas-i1-release-final-review
python3 infra/release/release.py verify \
  --output /private/tmp/atlas-i1-release-final-review
# From /private/tmp/atlas-i1-release-final-review:
shasum -a 256 -c SHA256SUMS
```

All three checksums passed. Both package methods extracted successfully, and
six packaged installer/upgrade `--help` checks passed. Original I0 schemas/examples,
runtime baseline/lock/SBOM/notices and the single migration head were included.

| Artifact | SHA-256 |
| --- | --- |
| `atlas-docker-compose-0.1.0.tar.gz` | `647c416b67d6a7ca160e2eda308aeb756b99a42bdbed8e04057de3788a906b07` |
| `atlas-systemd-0.1.0.tar.gz` | `2eddfacc3a2be5f1ef0cc74fb6e72ce30697577114be1da177808c3c4bf6e852` |
| `atlas-release-0.1.0.json` | `0a5e4e393df218382df6fc9521e7bd1c1c686bb0fa72a2330cfafae195e18f06` |

These are explicitly nonpublishable working-tree artifacts. Their manifest
records source HEAD `77eeff71e9a803f0f665ffa150b24537e29b83a6`, working-tree
source SHA-256 `91643174d418751ff31dfa1f6119297168c3b72d633c989701df0436e82de400`,
current schema `20261011_0027` and minimum upgrade schema `20261004_0025`.
No Docker image build or release publication was performed.

Final documentation checks passed (18 tests), Python compilation passed,
`git diff --check` was clean, and the exact material-path inventory below was
rechecked. The new runtime bytecode cache was removed. No secrets, generated
caches/build outputs or unexpected lockfile changes enter that inventory.
Temporary runtime, PostgreSQL, Redis and web validation processes were stopped;
evidence and artifacts remain outside the repository.

Final documentation command, from `apps/api`:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/atlas-i0-test-deps:. \
  .venv/bin/python -m pytest tests/test_markdown_docs.py \
  tests/test_repository_docs.py -q -W ignore
```

## Repository state

Command: `git status --short --untracked-files=all`.

```text
 M .github/workflows/ci.yml
 M .github/workflows/release.yml
 M THIRD-PARTY-NOTICES.md
 M apps/api/Dockerfile
 M apps/api/app/main.py
 M apps/api/app/models.py
 M apps/api/app/permissions.py
 M apps/api/requirements.txt
 M apps/api/tests/test_backup_postgres.py
 M apps/api/tests/test_ci_workflow.py
 M apps/api/tests/test_models.py
 M apps/api/tests/test_native_install.py
 M apps/api/tests/test_release_distribution.py
 M apps/api/tests/test_release_foundation.py
 M apps/web/app/integrations/page.js
 M apps/web/lib/status.mjs
 M apps/web/tests/helpers/components.mjs
 M docs/architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md
 M docs/architecture/integrations/contracts/README.md
 M docs/architecture/integrations/integration-roadmap.md
 M docs/deployment/installation.md
 M docs/deployment/upgrades.md
 M docs/product/feature-ledger.md
 M docs/product/status.md
 M docs/testing/continuous-integration.md
 M infra/ci/prepare-postgres.py
 M infra/ci/release-critical.sh
 M infra/docker/docker-compose.yml
 M infra/install/compose.py
 M infra/install/configuration.py
 M infra/install/native.py
 M infra/install/upgrade.py
 M infra/release/package-manifest.json
 M infra/release/release.py
 M infra/systemd/atlas-api.service
?? apps/api/app/integration_bootstrap/catalogue.json
?? apps/api/app/routes/integrations.py
?? apps/api/app/services/connector_catalogue.py
?? apps/api/app/services/connector_contracts.py
?? apps/api/app/services/connector_lifecycle.py
?? apps/api/app/services/connector_store.py
?? apps/api/app/services/connector_verification.py
?? apps/api/app/services/integration_runtime.py
?? apps/api/migrations/versions/20261011_0027_installed_connector_packages.py
?? apps/api/tests/test_connector_lifecycle_api.py
?? apps/api/tests/test_connector_lifecycle_postgres.py
?? apps/api/tests/test_connector_packages.py
?? apps/api/tests/test_i1_migration_postgres.py
?? apps/api/tests/test_integration_catalogue_api.py
?? apps/api/tests/test_integration_runtime.py
?? apps/api/tests/test_runtime_packaging.py
?? apps/runtime/ansible/Dockerfile
?? apps/runtime/ansible/README.md
?? apps/runtime/ansible/atlas_runtime/__init__.py
?? apps/runtime/ansible/atlas_runtime/bootstrap.py
?? apps/runtime/ansible/atlas_runtime/healthcheck.py
?? apps/runtime/ansible/atlas_runtime/server.py
?? apps/runtime/ansible/baseline.json
?? apps/runtime/ansible/notices/ansible-core/Apache-License.txt
?? apps/runtime/ansible/notices/ansible-core/COPYING
?? apps/runtime/ansible/notices/ansible-core/MIT-license.txt
?? apps/runtime/ansible/notices/ansible-core/PSF-license.txt
?? apps/runtime/ansible/notices/ansible-runner/LICENSE.md
?? apps/runtime/ansible/notices/cffi/LICENSE
?? apps/runtime/ansible/notices/cryptography/LICENSE
?? apps/runtime/ansible/notices/cryptography/LICENSE.APACHE
?? apps/runtime/ansible/notices/cryptography/LICENSE.BSD
?? apps/runtime/ansible/notices/jinja2/LICENSE.txt
?? apps/runtime/ansible/notices/markupsafe/LICENSE.txt
?? apps/runtime/ansible/notices/packaging/LICENSE
?? apps/runtime/ansible/notices/packaging/LICENSE.APACHE
?? apps/runtime/ansible/notices/packaging/LICENSE.BSD
?? apps/runtime/ansible/notices/pexpect/LICENSE
?? apps/runtime/ansible/notices/ptyprocess/LICENSE
?? apps/runtime/ansible/notices/pycparser/LICENSE
?? apps/runtime/ansible/notices/python-daemon/LICENSE.ASF-2
?? apps/runtime/ansible/notices/python-daemon/LICENSE.GPL-3
?? apps/runtime/ansible/notices/pyyaml/LICENSE
?? apps/runtime/ansible/notices/resolvelib/LICENSE
?? apps/runtime/ansible/requirements.lock
?? apps/runtime/ansible/sbom.cdx.json
?? apps/web/app/integrations/integrations.module.css
?? apps/web/components/integration-panels.js
?? apps/web/lib/integrations.mjs
?? apps/web/scripts/check-integrations-browser.mjs
?? apps/web/tests/integrations.test.mjs
?? docs/architecture/integrations/i1-completion-report.md
?? docs/deployment/integration-runtime.md
?? infra/install/runtime.py
?? infra/systemd/atlas-runtime.service
```
