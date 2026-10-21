# B1.2 implementation and acceptance report

Date: 21 October 2026 (Pacific/Auckland)

## A. Executive assessment

Implemented genuine offline provenance verification for supplied official
catalogue and executable package artifacts. Both original sequence-1 catalogue
bytes and the published Proxmox 0.2.0 package pass the production implementation.
Separate signer profiles, certificate numeric identities, exact-byte binding,
fail-closed errors, bounded subprocess handling and pinned distribution are in place.

The internal component is ready for manual review. No B1.3 retrieval, durable
trust promotion, package downloading/installation, UI or database change was
introduced. Existing bootstrap packages remain operational. Full native/systemd
host acceptance remains outstanding; existing mutable connector releases block
claims of production-ready remote publication authority for B1.3/B3.

## B. Repository state

Atlas branch: feature/integrations-official-catalogue-b1-2.
Initial and final HEAD: 2a69993118ee45f8d391eefc86ed1e49a1168c75.
The starting working tree was clean. All changes below remain local/uncommitted.
No Git branch/index/history/commit/push/fetch/PR/tag/release mutations occurred.

atlas-connectors remains clean on main at
83339e1747dc651ccdbdf4ab9ca8d4bc91d8c831; atlas-connector-sdk remains clean on
main at 8b0518c462289cca4758c3b9bf362f1130928a1c. Neither was modified.

## C. Changed files

Every material changed/new file is listed below. No migrations were required.

| File | Reason |
| --- | --- |
| [.dockerignore](../../../.dockerignore) | Exclude locally prepared platform binaries from image contexts. |
| [.github/workflows/ci.yml](../../../.github/workflows/ci.yml) | Provision the locked verifier before backend and release-integrity tests. |
| [.github/workflows/release.yml](../../../.github/workflows/release.yml) | Provision the locked verifier in the build-only validation job; publication unchanged. |
| [.gitignore](../../../.gitignore) | Exclude prepared executables and optional offline archive caches. |
| [THIRD-PARTY-NOTICES.md](../../../THIRD-PARTY-NOTICES.md) | Record upstream CLI MIT licence and public trust-material distribution. |
| [apps/api/Dockerfile](../../../apps/api/Dockerfile) | Install the platform verifier at image build time before the unprivileged service starts. |
| [apps/api/app/services/connector_verification.py](../../../apps/api/app/services/connector_verification.py) | Expose genuine provenance methods through the existing class; retain remote install rejection. |
| [apps/api/tests/fixtures/official_catalogue/README.md](../../../apps/api/tests/fixtures/official_catalogue/README.md) | Document origins, hashes, public-data review and provenance limits. |
| [apps/api/tests/test_connector_lifecycle_api.py](../../../apps/api/tests/test_connector_lifecycle_api.py) | Prove genuine provenance cannot bypass catalogue registration or installation authority. |
| [apps/api/tests/test_connector_packages.py](../../../apps/api/tests/test_connector_packages.py) | Update fail-closed missing-attestation expectation. |
| [apps/api/tests/test_official_catalogue.py](../../../apps/api/tests/test_official_catalogue.py) | Update only the legacy install error expectation; structural coverage unchanged. |
| [docs/architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md](../../../docs/architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md) | Add current evidence and clarify mutable publication versus target architecture. |
| [docs/architecture/integrations/official-catalogue-v1.md](../../../docs/architecture/integrations/official-catalogue-v1.md) | Keep B1.1 separate and describe the new B1.2 boundary accurately. |
| [docs/decisions/README.md](../../../docs/decisions/README.md) | Link ADR 0011. |
| [docs/deployment/installation.md](../../../docs/deployment/installation.md) | Link the added build/install dependency and offline procedure. |
| [docs/product/feature-ledger.md](../../../docs/product/feature-ledger.md) | Mark the internal verifier implemented, preserve incomplete remote journeys and native limits. |
| [docs/testing/continuous-integration.md](../../../docs/testing/continuous-integration.md) | Document mandatory real-verifier CI provisioning and offline tests. |
| [infra/ci/release-critical.sh](../../../infra/ci/release-critical.sh) | Include security/distribution suites in the shared release-critical selector. |
| [infra/install/native.py](../../../infra/install/native.py) | Prepare the verifier as root in shared fresh-install/upgrade build logic. |
| [infra/release/package-manifest.json](../../../infra/release/package-manifest.json) | Require verifier source, lock, roots, licence and upstream evidence in both release packages. |
| [apps/api/app/attestation/LICENSE.gh](../../../apps/api/app/attestation/LICENSE.gh) | Preserve upstream GitHub CLI MIT licence. |
| [apps/api/app/attestation/distribution.json](../../../apps/api/app/attestation/distribution.json) | Pin four upstream archives, extracted binaries and the reviewed root snapshot. |
| [apps/api/app/attestation/trusted-root.jsonl](../../../apps/api/app/attestation/trusted-root.jsonl) | Frozen Public Good Fulcio/Rekor/CT trust material. |
| [apps/api/app/attestation_distribution.py](../../../apps/api/app/attestation_distribution.py) | Shared fixed-path platform/version/root/binary integrity contract. |
| [apps/api/app/services/official_provenance.py](../../../apps/api/app/services/official_provenance.py) | Typed bounded offline subprocess verification and distinct authenticated policy enforcement. |
| [apps/api/scripts/prepare_attestation_verifier.py](../../../apps/api/scripts/prepare_attestation_verifier.py) | Integrity-checked build/install preparation, including offline archives. |
| [apps/api/tests/fixtures/official_catalogue/catalogue.sigstore.json](../../../apps/api/tests/fixtures/official_catalogue/catalogue.sigstore.json) | Freeze the genuine published sequence-1 bundle. |
| [apps/api/tests/fixtures/official_catalogue/package.sigstore.json](../../../apps/api/tests/fixtures/official_catalogue/package.sigstore.json) | Freeze genuine package evidence without executable package bytes. |
| [apps/api/tests/test_attestation_distribution.py](../../../apps/api/tests/test_attestation_distribution.py) | 19 distribution integrity, malformed-config, platform and packaging tests. |
| [apps/api/tests/test_official_provenance.py](../../../apps/api/tests/test_official_provenance.py) | 81 real-crypto, rejection, identity and subprocess tests. |
| [docs/architecture/integrations/b1-2-completion-report.md](../../../docs/architecture/integrations/b1-2-completion-report.md) | This implementation, validation and handoff record. |
| [docs/decisions/0011-offline-official-provenance.md](../../../docs/decisions/0011-offline-official-provenance.md) | Record the approved pinned offline verifier decision without rewriting accepted history. |
| [docs/deployment/attestation-verification.md](../../../docs/deployment/attestation-verification.md) | Full interface, bootstrap, policy, deployment, rotation and publication prerequisites. |
| [infra/ci/verify-official-fixtures.py](../../../infra/ci/verify-official-fixtures.py) | Opt-in real package/catalogue acceptance and profile-swap checks without download/install/execution. |
| [vendor/attestation/README.md](../../../vendor/attestation/README.md) | Document independent upstream authentication and frozen TUF evidence. |
| [vendor/attestation/gh-2.102.1-checksums.txt](../../../vendor/attestation/gh-2.102.1-checksums.txt) | Retain upstream checksum asset. |
| [vendor/attestation/gh-2.102.1.sigstore.json](../../../vendor/attestation/gh-2.102.1.sigstore.json) | Retain independently verified upstream build attestation covering all supported archives. |
| [vendor/attestation/tuf-bootstrap/root.json](../../../vendor/attestation/tuf-bootstrap/root.json) | Retain the original authenticated TUF capture: root.json. Historical evidence, not an update service. |
| [vendor/attestation/tuf-bootstrap/snapshot.json](../../../vendor/attestation/tuf-bootstrap/snapshot.json) | Retain the original authenticated TUF capture: snapshot.json. Historical evidence, not an update service. |
| [vendor/attestation/tuf-bootstrap/targets.json](../../../vendor/attestation/tuf-bootstrap/targets.json) | Retain the original authenticated TUF capture: targets.json. Historical evidence, not an update service. |
| [vendor/attestation/tuf-bootstrap/timestamp.json](../../../vendor/attestation/tuf-bootstrap/timestamp.json) | Retain the original authenticated TUF capture: timestamp.json. Historical evidence, not an update service. |
| [vendor/attestation/tuf-bootstrap/trusted_root.json](../../../vendor/attestation/tuf-bootstrap/trusted_root.json) | Retain the original authenticated TUF capture: trusted_root.json. Historical evidence, not an update service. |
| [docs/deployment/releases.md](../../../docs/deployment/releases.md) | Replace the obsolete verifier-placeholder statement with the B1.2/remote-install boundary. |
| [docs/deployment/discovery-runs.md](../../../docs/deployment/discovery-runs.md) | Clarify that B1.2 provenance does not change the historical I3 discovery checkpoint. |
| [docs/architecture/integrations/integration-roadmap.md](../../../docs/architecture/integrations/integration-roadmap.md) | Close the verifier research item while retaining remote acceptance and native follow-ups. |

## D. Trust implementation

GitHub CLI 2.102.1 verifies original bytes against local Sigstore v0.3 bundles
and the fixed Public Good root snapshot. The wrapper requires a successful
bounded subprocess result before using certificate or statement evidence.
Repository benchristian88/atlas-connectors, numeric repository 1414494920 and
owner 93822871 were independently established through the public repository API
and confirmed in the authenticated certificates. Identity is not obtained from
untrusted manifests.

Catalogue: .github/workflows/catalogue.yml at refs/heads/main.
Package: .github/workflows/release.yml at refs/tags/{id}-v{version}, with expected
source commit/digest context. Both require GitHub Actions issuer, hosted runner,
SLSA v1, exact SAN/build signer/build configuration and consistent source commits.
No connector allowlist or vendor exception exists.

The root identity is sigstore-public-good-2026-10-21, SHA-256
3c2cc7f357dc064ec527fdcd78da6e9245c21a381e1abaa0f2b62b186bcac1a1.
All four CLI archives were matched to upstream checksums and independently
verified by Python Sigstore 4.5.0 with its separate clean-home TUF bootstrap.
The retained upstream bundle authenticates deployment.yml, source commit
89d7dcec017194af1d6f8853176b2dae9c1da762, on the actual upstream patch branch.
No new Python cryptographic runtime dependency was introduced.

Runtime bounds: 4 MiB catalogue, 20 MiB package, 1 MiB bundle, 128 KiB roots,
64 MiB binary, 1 MiB combined stdout/stderr, 20-second subprocess deadline.
No shell, PATH fallback, ambient secrets/config, stdin, user-selected executable
or roots. Private files use 0600 in a 0700 workspace, with process-group cleanup.
Typed errors never expose raw stderr. Generic gh failures map conservatively to
unverifiable_provenance rather than guessed signature/identity diagnoses.

See [complete trust/deployment contract](../../deployment/attestation-verification.md)
for exact archive pins, source audit, bootstrap, limits and rotation procedure.

## E. Real publication verification

| Property | Genuine catalogue | Genuine package |
| --- | --- | --- |
| Artifact | catalogue.json / catalogue-000001.json | proxmox-0.2.0.tar.gz |
| SHA-256 | 55533ca67e7e9a14f82961e0a8c34ad78e2596049b3db02fde787494e3975afd | a14fec5ab485c980688ff5907e8835ddd3e9cecd1a6989ef252cbcb1b1dc4ef8 |
| Source commit | 91dfd86f18d0b59ff977bb1e8a5fef42c5329943 | 456a5bfdd1398c19da9ffef29216029027e24278 |
| Authenticated workflow | .github/workflows/catalogue.yml | .github/workflows/release.yml |
| Authenticated source ref | refs/heads/main | refs/tags/proxmox-v0.2.0 |
| Rekor witness, UTC | 2026-10-18T16:07:56Z | 2026-10-18T06:51:38Z |
| Result | Accepted through production verifier | Accepted through production verifier |

The catalogue remains 10,585 original bytes, schema 1.0, sequence 1,
generated_at 2026-10-18T16:04:26Z. The genuine bundle is attestation 57152061.
Original bytes and B1.1 structural implementation were not changed.

Repository/owner numeric identities, signer/source fields, issuer and runner are
certificate-authenticated. Subject name/digest, predicate and build dependencies
are signed workflow claims checked against those identities. Release asset IDs,
human approval, current-pointer freshness and release immutability are not
certificate guarantees. The captured release API records independently reported
immutable=false for both releases.

## F. Connector package readiness

B3 can call verify_package(bytes, bundle_bytes, PackageArtifactContext(...)) for
any valid connector ID/version. Its returned VerifiedProvenance is deliberately
not the legacy VerificationEvidence accepted by the package store. B3 must add
accepted catalogue/publication/eligibility checks and deliberate authorization
before creating installation evidence.

The real package passed on macOS arm64 and Linux amd64/arm64. Both genuine
artifacts failed under the opposite signer profile; changed bytes failed.
The package was neither extracted for installation nor executed/activated, and
its executable bytes were not added to the repository. A PostgreSQL API regression
proves even genuine catalogue provenance does not register or install the entry.

## G. Deployment support

| Mode | Tested result / limitation |
| --- | --- |
| Docker API Linux arm64 | Production Dockerfile built; genuine catalogue/package verification with network none, read-only filesystem, UID 10001, no capabilities; protected root/binary checks passed. |
| Docker API Linux amd64 | Same build/offline checks passed under emulation on arm64 Docker host. |
| Native preparation, both Linux architectures | In disposable containers, copied source to /opt/atlas/apps/api, removed existing binary, installed from locked local archive offline, then verified as UID 10001 with protected-file assertions. |
| Full native/systemd host | Fresh install, reboot and upgrade on an actual Debian/systemd host were not run. No such acceptance is claimed. |
| macOS arm64 development | Local archive preparation, production verification and deterministic security suites passed. |
| macOS amd64 | Upstream archive/binary integrity and genuine provenance verified; Intel Mac execution not run. |
| Worker/runtime | No verifier binary installed; existing execution/bootstrap regressions passed. |

The API image and native installation authority own the dependency. Native workers
share the installation filesystem but do not verify remote provenance. The
execution runtime keeps its independent installed-package integrity boundary.
Offline archive caching is supported; no application-start download is introduced.

## H. Security tests

Commands actually executed from apps/api unless otherwise specified:

~~~bash
.venv/bin/python -m pytest tests/test_official_provenance.py tests/test_attestation_distribution.py tests/test_official_catalogue.py tests/test_connector_packages.py tests/test_connector_bootstrap.py tests/test_integration_catalogue_api.py tests/test_connector_qualification.py tests/test_integration_runtime.py tests/test_runtime_packaging.py tests/test_native_install.py tests/test_release_distribution.py -q --tb=short
~~~

Final result: **487 passed, 0 failed, 0 skipped** (718 existing dependency warnings).
This includes **100 new provenance/distribution cases**. Real cryptography covers
sequence 1, exact-byte tampering, signatures, certificate changes, subject/predicate
changes, log proof/evidence removal, root failure and signer-profile mismatch.
Negative policy tests start from actual successful verifier output and mutate it
only to assert rejection. There is no mocked positive cryptographic verification.

Subprocess/distribution cases cover missing/corrupt/writable/linked executables,
unsupported version, malformed distribution metadata, roots, environment and
argument isolation, unsafe temporary root, private file permissions, cleanup,
timeout, nonzero exit, malformed JSON and bounded stdout/stderr. Synthetic
executables are used exclusively for negative process-failure cases.

From repository root, opt-in real package acceptance:

~~~bash
PYTHONPATH=apps/api apps/api/.venv/bin/python infra/ci/verify-official-fixtures.py --package /private/tmp/atlas-proxmox-public-release/proxmox-0.2.0.tar.gz
~~~

Result: both genuine artifacts accepted and **5 tamper/profile rejections**.
The same script ran in both production API images with --network none,
--read-only, --cap-drop ALL, --security-opt no-new-privileges, a noexec /tmp,
readonly fixture/package mounts and --require-protected. Both passed.

Upstream archive acceptance used Python Sigstore 4.5.0 verify identity with the
retained bundle, exact deployment.yml patch-branch identity and Actions issuer;
all four archive verifications exited 0. See vendor evidence README for command.

## I. Regression tests and other validation

A new private-socket PostgreSQL 17 cluster was initialized in /private/tmp with
UTF-8, no TCP listener and a private 0700 socket directory. A non-superuser,
non-createdb role owned a new disposable database, migrated to head. Command:

~~~bash
.venv/bin/python -m pytest tests/test_connector_lifecycle_postgres.py tests/test_connector_lifecycle_api.py tests/test_connector_qualification_postgres.py tests/test_i2_integrations.py -q --tb=short
~~~

Result: **32 passed, 0 failed, 0 skipped** (718 existing warnings).
The cluster was stopped afterward; no production credentials or databases used.
This includes global/scoped ownership, bootstrap/lifecycle behavior, protected
store and genuine provenance's lack of install authority. Existing API/UI routes,
qualification, discovery/ingestion and automatic-update behavior are unchanged.
No database migration was required; the sole head remains 20261018_0030.

Additional commands/results:

~~~bash
.venv/bin/python -m pytest tests/test_repository_docs.py -q -k 'not untracked_markdown_whitespace_is_detected' --tb=short
.venv/bin/python -m alembic heads
GOPATH=/private/tmp/atlas-b12-actionlint-go GOCACHE=/private/tmp/atlas-b12-actionlint-cache go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 .github/workflows/ci.yml .github/workflows/release.yml
apps/api/.venv/bin/python infra/release/release.py build --dry-run --worktree --output /private/tmp/atlas-b12-evidence/release-final
apps/api/.venv/bin/python infra/release/release.py verify --output /private/tmp/atlas-b12-evidence/release-final
git diff --check
~~~

Documentation: **9 passed, 5 deliberately deselected**. Those five existing tests
create temporary Git repositories; they were excluded to respect the operator's
Git-management restriction. Migration head: exactly one. Workflow lint: passed.
Python compileall on changed implementation/tooling: passed. Both working-tree
Docker/native release packages built and verified; package tests also check byte
reproducibility. These are non-publishable dry-run packages. Whitespace: clean.

Docker builds actually executed:

~~~bash
docker build --platform linux/arm64 -f apps/api/Dockerfile -t atlas-b12-api:arm64 .
docker build --platform linux/amd64 -f apps/api/Dockerfile -t atlas-b12-api:amd64 .
~~~

Validation issues resolved during work: the first provenance run had one overly
broad test permission assertion including CLI-created cache directories; it now
checks the three sensitive input files. The next combined run exposed an old
B1.1 placeholder-error expectation, updated to missing_attestation. Sandbox
loopback restrictions caused 22 runtime setup errors; an authorized rerun passed
all 34 runtime tests. The first temporary database used SQL_ASCII, which was
incompatible with the local Python driver; it was stopped and replaced by a
fresh UTF-8 cluster. Offline actionlint cache lookup lacked the module; the pinned
lint then ran successfully with disposable downloaded dependencies. A repeat
dry-run correctly refused a nonempty output directory; the final build used a
new release-final directory.

The complete unrelated backend/frontend/Ansible live suites and production
frontend build were not run: no UI/runtime discovery implementation changed.
Full native/systemd host acceptance and Intel Mac execution remain untested.

## J. Remaining security risks

Both connector GitHub releases remain mutable. Build attestations do not prove
release approval, release asset identity or protected publication. B1.3/B3 need
operator-established immutable versioned releases/snapshots, a separate mutable
current pointer, reviewed source/tag/environment protection and explicit approval.
The recommendation is documented; no live publication behavior/settings changed.

Frozen roots cannot establish awareness of later revocations. Root/verifier
rotation requires reviewed Atlas release/image/native upgrades, including offline
operators. Atlas release acquisition retains its existing checksum-only trust
boundary. Workflow compromise can produce signed false predicate assertions;
provenance is not an independent proof of build correctness. OS process isolation
is inherited from existing service/container controls; a verifier is not a sandbox
for package execution. No package execution is introduced.

## K. PR readiness

Changes are ready for manual source/security review with the deployment limits
above explicitly retained. No commit, PR or remote write was made. Review the
pinned upstream evidence/root bootstrap and publication prerequisites before
release. The prepared local CLI binary and optional caches are Git-ignored;
large platform executables are not source artifacts. No unrelated user changes
were present or altered.

## L. B1.3 handoff

Call GithubSigstoreVerifier().verify_catalogue(original_bytes, local_bundle_bytes,
subject_name=expected_name), alongside the unchanged parse_official_catalogue.
Retain the same bytes and bind their SHA-256 to VerifiedProvenance. Revalidate any
mutable parsed data before durable promotion. There is no boolean structural-to-
trusted cast, trusted-catalogue provider registration or persistence implementation.

B1.3 must implement bounded retrieval, publication identity/protection checks,
transactional monotonic sequence acceptance, equal-sequence byte consistency,
rollback rejection, current-pointer handling and explicit refresh/withdrawal
semantics. B3 must separately verify executable bytes using verify_package and
apply installation qualification/compatibility/global-admin/store gates. Existing
customer/site authorization remains authoritative. Publication hardening and
full native host acceptance must not be inferred from this component's success.

## Final working-tree status

Command: git status --short (all work remains uncommitted).

~~~text
 M .dockerignore
 M .github/workflows/ci.yml
 M .github/workflows/release.yml
 M .gitignore
 M THIRD-PARTY-NOTICES.md
 M apps/api/Dockerfile
 M apps/api/app/services/connector_verification.py
 M apps/api/tests/fixtures/official_catalogue/README.md
 M apps/api/tests/test_connector_lifecycle_api.py
 M apps/api/tests/test_connector_packages.py
 M apps/api/tests/test_official_catalogue.py
 M docs/architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md
 M docs/architecture/integrations/integration-roadmap.md
 M docs/architecture/integrations/official-catalogue-v1.md
 M docs/decisions/README.md
 M docs/deployment/discovery-runs.md
 M docs/deployment/installation.md
 M docs/deployment/releases.md
 M docs/product/feature-ledger.md
 M docs/testing/continuous-integration.md
 M infra/ci/release-critical.sh
 M infra/install/native.py
 M infra/release/package-manifest.json
?? apps/api/app/attestation/
?? apps/api/app/attestation_distribution.py
?? apps/api/app/services/official_provenance.py
?? apps/api/scripts/prepare_attestation_verifier.py
?? apps/api/tests/fixtures/official_catalogue/catalogue.sigstore.json
?? apps/api/tests/fixtures/official_catalogue/package.sigstore.json
?? apps/api/tests/test_attestation_distribution.py
?? apps/api/tests/test_official_provenance.py
?? docs/architecture/integrations/b1-2-completion-report.md
?? docs/decisions/0011-offline-official-provenance.md
?? docs/deployment/attestation-verification.md
?? infra/ci/verify-official-fixtures.py
?? vendor/attestation/
~~~
