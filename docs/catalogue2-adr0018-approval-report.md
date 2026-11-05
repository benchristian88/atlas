# Catalogue 2 — ADR 0018 acceptance and Publisher preparation

Date: **5 November 2026 (Pacific/Auckland)**.

## A. Executive assessment and decision scope

The owner explicitly accepted [ADR 0018](decisions/0018-catalogue-durable-publication-evidence.md)'s
architectural decisions, subject to native/systemd forward compatibility. This
change records that acceptance and prepares the next engineering increment. It
does not approve executable pins, adopt workflows, sign, publish, install or deploy.

The merged implementation preserves deployment-independent catalogue, Manifest,
package, verification and activation contracts. Compose remote writing has an
implementation; its release-owned installation approval is still unset. Native
remote writing is explicitly unsupported. Existing root-operated native staging,
unprivileged services and offline installed-package verification remain intact.
No Docker dependency requiring a new Connector release or catalogue schema was
found in the inspected contracts. The native gap is privileged staging and its
authorization/lifecycle integration, not publication format.

Architecture acceptance resolves the seven-asset contract, 900/300-second
historical bounds, supported witnesses, implementation-enforced selection
correlation, disabled cross-job recovery and separate installation authority.
It does not supply genuine successor signing evidence or continuous-protection
assurance. [ADR 0012](decisions/0012-official-catalogue-publication-authorization.md)
remains Proposed overall. Accepted ADRs 0006/0011/0013/0015/0016 are preserved.

## B. Verified repository state and security baselines

Both working trees were clean before changes. The existing Atlas feature branch
was reused only after the owner's explicit follow-up instruction. `origin` was
fetched in both repositories. Local base branches already equalled their fetched
remote branches, so no branch update, checkout or merge was needed.

| Repository | Working branch | HEAD / fetched base |
| --- | --- | --- |
| Atlas Impact | `feature/catalogue-v2-adr0018-approval` | `95cea88707981af544581b5665a5e5a77250fd1a`; local `dev` = `origin/dev` |
| Atlas Connectors | `main` | `078f4099c3fcf850557bf9148db207f696c0ecad`; local `main` = `origin/main` |

Read-only GitHub API checks independently confirmed both branch refs and the
merged PR identities: [Atlas #57](https://github.com/benchristian88/atlas/pull/57)
merged at the Atlas HEAD above, from `b55bd5f376b0d78178a9f8d8abca6175a051ed1c`;
[Connectors #48](https://github.com/benchristian88/atlas-connectors/pull/48) merged
at the producer HEAD above, from `d709681126662d432622bd92f27b862e37586476`.
No newer base-branch commit was observed. Fetch imported the already existing
producer tags `proxmox-v0.2.1` and `proxmox-v0.2.2`; no tag or release was created.
`feature/catalogue-v2-publisher-successor` was absent in both repositories and was
not created or modified.

Review covered the actual consumer authorization/history/downloader/routes,
PackageStore/lifecycle, native installer and units, Compose configuration,
producer driver/archive/publisher/generator, active workflows, policy/trust,
historical security fixtures and tests. The original
[Atlas implementation report](catalogue2-engineering-report.md),
[Atlas remediation report](catalogue2-security-remediation-report.md), and producer
completion/remediation reports at the verified producer baseline were inspected;
their historical evidence and status narratives were not rewritten.

All **27** producer frozen-control SHA-256 values in
`tests/fixtures/publication_evidence/preserved.json` match current bytes. These
include all seven active workflows, policy/trust, historical publication tools,
registry/sequence and immutable fixtures. All six Catalogue 2 approval constants
and fingerprints remain `None`: producer `APPROVED_SUCCESSOR` and
`APPROVED_SUCCESSOR_SHA256`; Atlas `APPROVED_FUTURE_POLICY` and
`APPROVED_FUTURE_POLICY_SHA256`; `APPROVED_REMOTE_INSTALLATION` and
`APPROVED_REMOTE_INSTALLATION_SHA256`.

This is not a claim that every historical publication authority is inactive.
The existing producer `policy.json` has `enabled: true`, S4 verifier trust has
`live_signer_accepted: true`, connector trust is already accepted, and Atlas's
exact ADR 0013 bootstrap is approved. Those existing authorities were preserved,
not disabled or extended to Catalogue 2. Hosted enable variables, effective App
permissions, secrets and environment policy were not inspected or changed; their
current live values cannot be certified from Git. The new driver is fail-closed
on its unset approval before credentials/provider operations, and is not used by
the unchanged active Publisher workflow.

## C. Exact ADR 0018 acceptance amendments

The proposal date remains 4 November; the explicit acceptance date is **5 November
2026**. The decision scope distinguishes owner architectural approval from later
security acceptance of concrete executable identities and live actions.

The accepted ordinary inventory is exactly `catalogue-NNNNNN.json`,
`catalogue.sigstore.json`, `current.json`, `current.sigstore.json`, `preflight.json`,
`preflight.sigstore.json`, and `policy.json`. Sequence one's exact historical
four-asset exception remains confined to ADR 0013. Original bytes, independent
Atlas authority, source C, signer S, first-attempt run, immutable identities and
authenticated contiguous history remain mandatory.

The [historical-authorization decision](decisions/0018-catalogue-durable-publication-evidence.md#historical-authorization)
accepts at most 900 seconds from original observation start through expiry,
selection within 900 seconds of original issuance and publication within 300
seconds of the latest authenticated selection witness. Preserve the 30-second
pre-finalization reserve, all post-publication checks, original-run/attempt time
validation and fail-closed missing/inconsistent evidence. Accept one to eight
verified Tlog witnesses under existing roots and allowlisted logs, without a
two-log quorum claim. GitHub transport timestamps remain unsigned; authenticated
log evidence does not prove continuous GitHub protection.

The [selection-binding decision](decisions/0018-catalogue-durable-publication-evidence.md#selection-binding)
accepts identical original C/run/attempt, separately authenticated preflight and
selection, exact build-source agreement, identical retained selection bytes/bundle,
immutable seven-asset co-location, reviewed one-selection-per-source code and
consumer rejection of source reuse. This is implementation-enforced correlation.
The preflight does not directly sign later pointer or numeric asset identities.

The [recovery decision](decisions/0018-catalogue-durable-publication-evidence.md#recovery)
keeps cross-job recovery disabled with the exact existing disposition
`disabled-pending-permanent-archive-decision`. Stranded immutable releases grant no
retry, expired-evidence reuse or pointer advance. Future recovery requires its own
permanent evidence contract and approval.

Separate release-owned installation authorization, global administrator exact
review/confirmation, compatibility, mappings, dependent configuration, protected
staging, PostgreSQL activation/audit and offline ordinary operation remain
required. Native compatibility is a binding architectural condition, with no
claim of current native remote support. The ADR index, operator runbooks and
feature ledger now reflect this scope. The feature remains Partially implemented.

## D. Platform-neutral versus Docker-specific architecture

| Concern | Shared contract / deployment-specific implementation |
| --- | --- |
| Catalogue and chain | Same signed documents, seven-asset archive, independent trust, immutable history and original sequence-one root in either deployment. |
| Connector distribution | Same Manifest, tar.gz bytes, hash, immutable official release/asset, source and Sigstore package profile. No Docker selector is required. |
| Administrator and domain | Same global permission and exact confirmation, compatibility/dependency checks, mappings, scoped Integrations/DataSources and credential handling. |
| Store and activation | Same `connector_id/version/digest` tuple, manifest/verification metadata, PackageStore safety/atomicity, independent runtime verification and PostgreSQL active identity/audit. |
| Offline operation | Installed ordinary packages are locally verified; runtime execution has no catalogue freshness dependency. Local-release lease/revocation rules remain distinct and unchanged. |
| Compose staging | API's existing writable `connector_store` mount; bootstrap UID/GID 10001; runtime mount read-only. |
| Native staging | Root-operated installer stages approved packages; root-owned store, unprivileged API and dedicated runtime. Remote privileged handoff is absent. |

The current local-only restrictions are explicit in
[`RemoteInstallationPolicy`](../apps/api/app/services/remote_connector_packages.py):
`packaging_mode` defaults to and is checked against `docker_compose`.
[`_install`](../apps/api/app/routes/integrations.py) checks healthy runtime and
compatibility, then rejects non-Compose remote selection with HTTP 409
`remote_install_requires_docker` before entering `downloaded_package()` or
PackageStore. These are application capability/approval checks, not fields in a
published Connector Manifest or catalogue. They need future additive adaptation.

Compose's writable API mount is deployment configuration. It is not authority
for the runtime to install packages. No API route, schema, package, SDK or runtime
implementation changed in this task.

## E. Native/systemd forward-compatibility assessment

Reusable current capabilities:

- [`native.py`](../infra/install/native.py) installs the vendored SDK with hashes,
  prepares the pinned offline verifier in the application installation boundary,
  builds a separate runtime environment and root-stages fixed approved bundles
  through `scripts.stage_integration_bootstrap`. Staging does not activate DB state.
- [`runtime.configure`](../infra/install/runtime.py) enforces dedicated unprivileged
  runtime identity and root-owned protected store/control directories, rejecting
  symlinks or group/world-writable paths. Store mode is 0750, root-owned with the
  control group; this gives service read/traverse access without store write.
- [`atlas-api.service`](../infra/systemd/atlas-api.service) runs as `atlas`, with
  `NoNewPrivileges`, `PrivateTmp` and `ProtectSystem=strict`.
  [`atlas-runtime.service`](../infra/systemd/atlas-runtime.service) runs as
  `atlas-runtime`, with read-only store/control paths, no capabilities and no
  Atlas database/auth environment. The worker's environment is filtered.
- [`PackageStore.install`](../apps/api/app/services/connector_store.py) verifies
  digest, provenance, manifest and archive safety, then publishes immutable
  contents by locked atomic rename/fsync. An already staged exact tuple takes the
  integrity-verification path without acquiring a write lock. Runtime verification
  and existing activation/mapping/dependent checks can reuse that tuple offline.

Precise gaps are a reviewed narrow staging IPC/request contract, a privileged
installer identity/unit and sandbox, secure verified-byte transfer across
`PrivateTmp`, independent enforcement of committed exact installation authority,
anti-replay/concurrency/restart behavior, and coordination with final locked
currentness/lifecycle checks. The existing bootstrap command deliberately accepts
no arbitrary paths, URLs or package selectors; it is not a remote installer helper.
Changing store ownership or invoking that command with an untrusted selector is
not a parity implementation.

A minimal future boundary should leave retrieval, catalogue authentication,
administrator review and Connector business logic in shared unprivileged domain
code. It should pass bounded already verified package bytes and exact identities
to a root-owned, fixed-purpose staging service or constrained one-shot operation.
Use authenticated local IPC, fixed store roots and descriptor-based or protected
handoff rather than caller-chosen filesystem paths; API and helper private `/tmp`
namespaces are not interchangeable. The helper must independently check peer,
exact durable authorization/request generation, replay/expiry and immutable
package identity, rehash the actual transferred bytes, and reuse existing pinned
verification/PackageStore logic before atomic publication. An API boolean or
caller-created verification receipt alone is insufficient authorization.

The authorization channel itself needs separate design/security approval, for
example narrowly scoped read-only access to a committed exact installation
request, without database administration or activation-writing privileges. That
is a future option, not an existing request model. The helper must have no network
download function, arbitrary command execution, publication/GitHub credentials,
Atlas signing keys or runtime installation delegation. API and runtime stay
unprivileged. PostgreSQL remains authoritative for activation; a staged tuple
alone never makes a package active. Recheck current accepted selection and
dependent state under existing locks before normal runtime verification,
activation and audit; a crash may leave a verified inactive tuple, never implicit
execution authority.

No published catalogue, Manifest, immutable package bytes or PackageStore disk
layout change is needed for parity. A small internal staging adapter is needed
at the current direct `PackageStore.install()` call, plus a separately approved
native installation policy and capability check. Existing public selection fields
can remain; any job/status extension would be additive if the chosen staging
protocol requires it. A durable native request model might need an additive
migration, but no such schema or migration is selected here. Removal/quarantine
and update/revocation/handoff behavior also need explicit native lifecycle review;
installation support must not silently promise those privileged operations.

The same immutable Proxmox 0.2.2 release can supply both deployment modes. Its
existing package digest, Manifest dependencies and Sigstore proof are verified
before each deployment's protected staging and normal activation. No repackaging,
new Connector version, catalogue schema field or producer pipeline change is
required merely to add native staging.

Future acceptance must exercise actual supported Linux/systemd ownership and
service isolation, rejected non-admin/forged/replayed/stale requests, byte/path/
symlink/TOCTOU/archive attacks, verifier and identity failures, runtime inability
to write/install, active-run/dependent/mapping restrictions, concurrent install
and withdrawal/refresh races, interrupted staging/commit/restart, complete audit,
local-release revocation/handoff, offline execution and restore currentness.
Compare exact stored identities with Compose using the same immutable release.
No live native acceptance is claimed by this review or the host contract tests.

**Defect classification:** a Docker field or runtime dependency that forced a
different Connector release or catalogue schema would violate ADR 0018 and require
remediation before acceptance. None was identified in this inspection. The
documented Compose-only policy/route and absent native helper are supported scope
limits, with additive consumer work required for parity.

## F. Producer successor S preparation and freeze sequence

This is a plan for later authorized work on
`feature/catalogue-v2-publisher-successor`, not an instruction executed here.

1. Have the operator record the accepted ADR in an immutable Atlas commit. The
   current decision references are its `#historical-authorization`,
   `#selection-binding` and `#recovery` sections. That commit SHA is unresolved
   because this task does not commit. Do not fabricate an immutable approval URL.
2. From newly verified clean producer `main`, populate only the release-owned
   `SuccessorApproval` and its fingerprint in `tools/catalogue_evidence_driver.py`,
   with corresponding approval/negative regression tests and a decision record.
   The six fields must be: the independently checked original policy-byte digest
   below; `selection_seconds=900`; `publication_seconds=300`; immutable references
   to the accepted historical and selection decisions; and
   `recovery_decision='disabled-pending-permanent-archive-decision'`. The recovery
   disposition is anchored in ADR 0018, not a permission to implement recovery.
   Do not embed S or final publication source C in this record.
3. Generate `APPROVED_SUCCESSOR_SHA256` using the exact production expression
   `digest(canonical_json(asdict(record)))`, then test the no-argument approval
   accessor and hostile changes. The serializer is sorted UTF-8 JSON, indent 2,
   `ensure_ascii=False`, `allow_nan=False`, with one final newline. It is not
   compact JSON. Neither a hash of a Python repr nor reserialized policy bytes is
   equivalent. Final decision-reference bytes and therefore the approval
   fingerprint are unresolved here; no operational record is populated.
   In `tests/test_catalogue_evidence_driver.py`, deliberately adapt the test that
   currently asserts production constants are `None`: retain missing-approval
   denial by explicitly injecting an unset record in an isolated test process,
   and separately test the real approved record/fingerprint. Add wrong-digest,
   missing/altered decision, gate-off, recovery and pre-credential rejection cases.
   Do not delete the fail-before-provider assertion merely because a record exists.
4. Independently review/freeze the immutable producer revision containing that
   approval, driver, archive verifier, isolated reusable signer and generator as
   **S**. Freeze first, then use its actual 40-hex SHA in callers and trust. A
   branch name, current merged baseline or synthetic test SHA is not an approved S.
5. Generate both inactive Publisher and catalogue-build outputs with
   `tools/prepare_evidence_workflow.py --revision S --kind publisher` and
   `--kind catalogue-build`, each using an exclusive temporary output. The
   generator reads byte-pinned historical S4 templates, not the active caller
   being replaced. The build generator switches to `build_catalogue_candidate.py`
   and `catalogue/candidate-v2`; it does not invent a build signer S pin. Build
   provenance remains at the eventual source C under its existing profile.
6. In a separately reviewed adoption change, update `catalogue-publish.yml` and
   `catalogue.yml`. Publisher reusable signer `@S`, executable checkout `ref: S`
   and `ATLAS_IMPLEMENTATION_REVISION=S` must agree. Source checkout remains
   `${{ github.sha }}` in `publication-source`, consumed as data by S. Source
   `verifier-trust.json` and the independently administered environment
   `VERIFICATION_POLICY` must select the same S and exact numeric/root policy.
   Keep successor live signer acceptance false until its genuine acceptance is
   approved; `acceptance_only=true` supports that signing qualification.
7. Preserve historical S4 template hashes, its frozen trust fixture and all old
   bootstrap/token/isolation regressions. The adoption review must deliberately
   update only the active-control preservation fingerprints for intentionally
   changed files; never rebaseline the historical evidence or remove assertions.
   Adapt `test_frozen_safeguards_and_all_historical_implementation_files_unchanged`
   explicitly: it currently compares live workflow/trust paths with old hashes.
   Keep the original snapshot as historical evidence, retain checks against the
   pinned S4 templates/trust, and add separately reviewed successor active-path
   expectations. Its old-driver-path assertion alone is not successor acceptance.
   Run both historical and successor workflow profiles and hostile mutations.
   Keep bootstrap/recovery absent from the successor dispatch/commands, original
   admission before token minting, no Workflows Write and exact baseline scopes.
8. After separate permission to adopt/pin and dispatch, run hosted Python 3.12 CI
   and genuine **acceptance-only** signing while `CATALOGUE_EVIDENCE_ENABLED` is
   unset/false. Preserve original preflight, bundle, source policy and actual
   invocation. Verify the certificate signer S, source/buildConfig C, original
   run/attempt, subject/digest/predicate and authenticated witnesses independently.
   Verify Publisher is skipped, no Publisher token/write occurs, no inherited
   secrets, and the Verifier key/token cannot enter Publisher jobs or artifacts.
   Validate real baseline Publisher registration and installed effective access,
   Verifier restrictions, ruleset bypass lists and environment isolation. Local
   mutation tests are necessary but cannot establish those platform facts.
9. Only after genuine independent acceptance, separately approve the successor
   live trust values and Atlas policy pins. Final producer main source **C** is
   established after adoption/trust-data changes and successful required CI.
   Build the candidate twice at that exact C, compare original catalogue bytes
   and verify its genuine build attestation. Its final digest/run/asset IDs are
   unresolved until then. A subsequent source change invalidates the build choice.
10. A later owner action may enable only `CATALOGUE_EVIDENCE_ENABLED` and authorize
    one fresh ordinary publish dispatch. The generated job and driver both enforce
    that gate. Keep `CONNECTOR_PUBLICATION_ENABLED` disabled; 0.2.2 already exists.
    Require original preflight before credentials, seven-asset immutable readback,
    accepted temporal limits/reserve and final current CAS. Then obtain independent
    anonymous seven-asset/chain verification and interrupted-provider acceptance.
    An acceptance-only signature is never ordinary-publication authority. A failed
    post-publication check leaves current unchanged and recovery disabled.

This ordering avoids self-reference: policy bytes contain neither S nor C; the
approval fingerprint contains policy digest and decision references but no S;
freezing produces S; later workflow/trust adoption refers to S and produces C.
Atlas separately pins S/policy after review and its own policy fingerprint is
bound by the installation approval, not fed back into S. If executable code or
the approval record changes, freeze a new S and repeat its pin/signing review.
Reusing the frozen template generator also avoids a workflow-generation cycle.

## G. Consumer policy and exact pin requirements

These values are independently reproducible from the checked-in files at the
verified baselines. They are review inputs, not approval of a new successor.

| Identity / bytes | Exact value and source |
| --- | --- |
| Original producer policy SHA-256 | `c9a88eeb6c7e6d0a7f1a08eaa07eeed5ea251449db7104f7757626842cf1bbe9`; SHA-256 of `catalogue/publication/policy.json`, also in the frozen preservation fixture. |
| Current historical S4 | `2dd1ffcd2f5677dc35bdbc8f68ea28275c91c285`; active Publisher caller/checkout/environment, verifier trust and generator `OLD_PIN`. It is not the future S. |
| Existing connector signer implementation | `dc79af8e3115e263c267989dfa9ba72599c25463`; `connector-trust.json`, preserved for already published packages. |
| Producer repository / owner / human | `1414494920` / `93822871` / `93822871`; Atlas release-owned bootstrap review and producer constants/policy. |
| Publication / package / verification environments | `24999137498` / `24617213627` / `25016263801`; independent Atlas review, producer policy/trust. |
| Publisher App / installation / bot | `5422372` / `174027755` / `346232650`; producer policy and authorization constants, Atlas review for App/bot. |
| Verifier App / installation | `5424851` / `174088125`; producer `publication_authorization.py`; not new credentials or bypass authority. |
| Publication workflow / required CI App | `392548804` / `15368`; Atlas bootstrap/public-observation review. Synthetic fixture workflow IDs are not production pins. |
| Main / history / bootstrap / current / publication-tag rulesets | `25618213` / `25618809` / `25628137` / `25618684` / `25618901`; both independently reviewed sources. |
| Frozen root | `sigstore-public-good-2026-10-21`, SHA-256 `3c2cc7f357dc064ec527fdcd78da6e9245c21a381e1abaa0f2b62b186bcac1a1`; Atlas and producer distribution locks/root bytes. |
| Verifier | GitHub CLI `2.102.1`; exact archive and executable pins for Linux/macOS amd64/arm64 remain in `app/attestation/distribution.json` and `tools/publication_trust/distribution.json`. No binary/PATH/root override. |
| Historical template SHA-256 | Publisher `52fbc2775d3e718fdc4e1b8ebf1e97fe44767c3214c649d3a11578b01d189bee`; build `111387fd0c74d3b9e123c8555e9e514312031504749338080f3a2b316f884aa1`; generator and byte-identical retained S4 templates. |

The existing verifier distribution pins are identical in the independent Atlas
and producer locks; retain all of them:

| Platform | Archive SHA-256 | Extracted executable SHA-256 |
| --- | --- | --- |
| Linux amd64 | `77b9e297e94c50336823d0f84de7ef1be60cba704601fa0d98f129f47a94987b` | `d7e919c19ad89502313325c2690bf8a8556234ec734b7a4593e39244ab3e4a87` |
| Linux arm64 | `5019b3cc6e8a03bb4d88600f8dbda2add8e6407705c159b0c63151036e77a1af` | `2a94934af93acc2161e165841559b532cce266c805a600b71392761941bed264` |
| macOS amd64 | `91c5fbd493274b545b03ef32a89c2a21238393c0c0b1108210967199b3230d9d` | `d9825cb94889c72939419ac3b890e853d3daf0cd7681009d8d51fd4b96224398` |
| macOS arm64 | `08bfef98b50c553df122bb34ee8dcf415cae7d3b108891488964a0df07aa2aeb` | `b547134b94ff3139051f4cf96cf7081b368ce323450829c6e65d1f7c02833a92` |

**Original-policy-byte warning:** the committed policy's human-readable key order
is not the sorted canonical serializer's order. Its original hash above is the
required archived policy hash. Reformatting it would change that identity and
require a new independently reviewed policy/approval fingerprint; do not normalize
it while preparing S. Canonicalization applies to the new approval dataclass,
not to substituted archived policy bytes.

`FuturePublicationPolicy` must independently set the exact reviewed S in both
`signer_revision` and `expectations.consumer_review.reviewed_producer_revision`;
it must set the original policy digest, complete `PublicObservationReviewExpectations`
including workflow/rulesets/numeric authorities, verification environment,
900/300-second limits and accepted historical/selection references. Recovery must
retain the literal disposition above. Generate its fingerprint with
`sha256(official_catalogue_ingestion.canonical(asdict(policy)))`, including the
same explicit indented-JSON/newline convention. Archive policy or producer trust
cannot fill this Atlas record or choose independent verification authority.

Original preflight uses `.github/workflows/catalogue-verifier.yml`, predicate
`https://atlas-impact.dev/attestations/publication-preflight/v2`, subject
`preflight.json`, pinned signer S and GitHub OIDC issuer
`https://token.actions.githubusercontent.com`. Selection and catalogue use their
distinct existing SLSA profiles at source C, with exact buildConfig/workflow,
GitHub-hosted runner, public repository/owner numeric IDs and first-attempt
invocation checks. Accept only authenticated Tlog witnesses from
`https://rekor.sigstore.dev` and `https://log2025-1.rekor.sigstore.dev` under the
approved frozen roots. Preserve original-run rereads and release publication-time
checks independently of signature timestamps.

`RemoteInstallationPolicy` needs a separately approved `approval_reference`,
the exact resulting Atlas publication-policy fingerprint, and `docker_compose`
mode; hash it using the same consumer canonical serializer. Architectural ADR
acceptance is not that executable approval. Future native mode needs its own
reviewed policy/adapter, without changing remote publication authority.

Known immutable package evidence was corroborated by read-only GitHub release
API: [Proxmox 0.2.2](https://github.com/benchristian88/atlas-connectors/releases/tag/proxmox-v0.2.2)
is immutable, release **429608780**, package asset **693849044**, source
`e58788a667c0c0006477ac149e8ad28aedda0745`, digest
`2d66fc69b9cf9c70d7df117fe41bff3e3e056299f1908cde965e9e3f75e59abf`.
Its five assets remain index, Manifest, package, package bundle and SHA256SUMS.
The local genuine unchanged package/bundle were cryptographically tested; no new
package signing or publication was performed. The candidate retains 0.2.0 identity
as withdrawn and references this exact 0.2.2. Future catalogue S, final C, build/
publication run IDs, catalogue digest/release/assets, immutable ADR commit,
approval fingerprints and Atlas deployment build remain **unresolved**. No
successful successor signing evidence or operational approval reference is invented.

## H. Tests, executed evidence, failures and skips

No tests or assertions were altered. Test stores/files are temporary. No LXC,
application database or live installation was accessed; no disposable database
was provisioned. Existing PostgreSQL test URL was explicitly unset for the host
run. All results below were executed in this task unless labelled historical.

Atlas, from `apps/api`:

```bash
env -u ATLAS_TEST_DATABASE_URL -u DATABASE_URL PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -B -m pytest -q -rs -p no:cacheprovider \
  tests/test_repository_docs.py tests/test_native_install.py \
  tests/test_runtime_packaging.py tests/test_connector_packages.py \
  tests/test_connector_bootstrap.py tests/test_official_provenance.py \
  tests/test_attestation_distribution.py tests/test_catalogue_future.py \
  tests/test_remote_connector_packages.py tests/test_integration_catalogue_api.py \
  tests/test_catalogue_request_budget.py --tb=short \
  --junitxml=/private/tmp/atlas-adr0018-consumer.xml
```

Result: **340 passed, 26 skipped, zero failures/errors**, 27.21 seconds on host
Python 3.14. The 724 warnings are existing dependency deprecations/field metadata.
Breakdown: documentation 14; native installer 27; runtime packaging 16; packages
80; offline bootstrap 7; provenance 81; distribution 19; future catalogue 45
passed/2 skipped; remote packages 2 passed/22 skipped; catalogue API 33;
request-budget 16 passed/2 skipped. The 26 skips all require disposable migrated
PostgreSQL: two chain transactions, twenty-two remote download/confirmation/
activation/tamper/native-denial/race cases and two request-budget/transaction cases.
The documentation cases are rerun after final edits, as recorded below.

An additional isolated `unittest.mock` control-flow probe called the real
`_install` with a synthetic authorized selection and synthetic healthy systemd
runtime, while download/store/DB access were fail-on-call sentinels. It passed:
HTTP 409 `remote_install_requires_docker`, rollback only, no download/store/DB
access. This verifies route ordering; it does not replace the skipped PostgreSQL
authorization/activation test or establish native deployment acceptance.

Producer, from its unchanged repository:

```bash
env -u ATLAS_TEST_DATABASE_URL -u ATLAS_TEST_SOURCE_COMMIT \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -rs \
  -p no:cacheprovider tests/test_documentation.py \
  tests/test_publication_evidence.py tests/test_catalogue_evidence_driver.py \
  tests/test_evidence_workflows.py tests/test_verifier_workflow.py \
  tests/test_publication_packaging.py tests/test_publication_bootstrap.py \
  tests/test_publication_authorization.py tests/test_publication_contract.py \
  tests/test_publication_crypto.py --tb=short \
  --junitxml=/private/tmp/atlas-adr0018-producer.xml
```

Result: **629 passed, zero skips/failures/errors**, 21.98 seconds. Module counts in
that order: 1, 133, 12, 19, 21, 13, 115, 131, 180, 4. These include original-byte
archive/deadline/provider-delay rejection, unchanged historical S4, successor
workflow mutations, checkpoint failure, unset authority and forced recovery denial.
Future successor signature outputs/provider writes in these tests are synthetic;
the genuine historical crypto fixtures are not new successor acceptance.

Additional checks: `python -B -m alembic heads` reports the single unchanged head
`20261101_0032`, without connecting to a database. AST/byte checks confirm all six
approval constants remain unset, 27/27 producer frozen controls match, original
policy digest is unchanged, and the future branch is absent. Final documentation,
whitespace and protected-file checks are recorded in the completion validation
below.

Not executed: database-backed activation/request-budget tests (26 skips), full API
or producer runtime suites, disposable Docker/Python 3.12 security runner, hosted
CI, genuine successor signing/permission-isolation, live published seven-asset or
interrupted-provider acceptance, frontend/browser builds, live native/systemd or
LXC/source operations. `actionlint` was not found on PATH; workflow files are
unchanged and existing workflow security contracts passed. The runtime packaging
suite did execute `docker compose config` (configuration validation only, no
daemon/project operations). No native installer was run against the host.

The unchanged pre-merge Atlas remediation report records **205 Docker security
passes with zero skips**, including the remote-installation path, and the producer
report records **2,897** complete-suite passes. Those are inspected historical
results, not fresh executions in this task. Current host tests alone cannot claim
that the skipped Docker/PG activation regressions are freshly green.

## I. Risks, outstanding genuine acceptance and security gates

- S and its independent approval/fingerprints are not yet established. No producer
  or consumer runtime input may activate them. Hosted settings and effective
  credential isolation still require separately authorized independent acceptance.
- The accepted correlation has the stated direct-signature limitation. Authenticated
  observations/witnesses do not prove uninterrupted protections, present hidden
  bypass state or immunity to trusted-provider/sole-maintainer/credential compromise.
- The thirty-second margin is admission headroom, not an atomic provider transaction.
  A delayed or ambiguous finalization can strand an immutable successor; leave
  current unchanged, retain evidence and obtain a separately reviewed disposition.
- Cross-job recovery remains disabled. Do not reuse an expired preflight or modify
  immutable assets to recover. No sequence-two exception is introduced.
- Current bounded history is 32 revisions/32 MiB total/8 MiB evidence per revision,
  with 240-second retrieval budget and 300-second refresh lease. Larger chains
  require reviewed incremental history work. Full-database rollback remains outside
  what a checkpoint in the same restored database can detect.
- New remote installation needs independent release-owned approval, global package
  administrator permission and exact confirmation. Backend permission/global scope,
  customer/site-scoped configurations, mappings, DataSources, secrets, local-release
  restrictions, PostgreSQL activation and audit were not changed or delegated to
  downloaded metadata. Runtime remains a read/execute consumer.
- The 26 database-backed skips are a current validation limitation, not a waived
  gate. Native parity needs separate implementation/security acceptance; no live
  systemd support, source qualification or deployment success follows from this ADR.

## J. Changed-file inventory, branch status and next operator action

| Atlas file | Purpose |
| --- | --- |
| `docs/decisions/0018-catalogue-durable-publication-evidence.md` | Record actual owner acceptance, assurance limits, native compatibility and remaining activation gates. |
| `docs/decisions/README.md` | Accepted 0018 index entry; keep 0012 Proposed overall. |
| `docs/deployment/catalogue2.md` | Update merged/accepted state, original-byte hashing, freeze/pin order and native capability boundary. |
| `docs/deployment/official-catalogue.md` | Preserve current sequence-one behavior while referencing accepted future architecture and independent pending pins. |
| `docs/product/feature-ledger.md` | Keep Partially implemented; distinguish accepted architecture from inactive executable approvals. |
| `docs/catalogue2-adr0018-approval-report.md` | This A–J engineering assessment and exact validation/gate inventory. |

No producer or SDK files changed. No database migration was required; models,
migrations, Manifest/package/catalogue schemas, public APIs/UI routes, runtime,
active workflows, pins, policy, approval constants and immutable release documents
are unchanged. This task changes documentation only. Historical ADRs and security
evidence reports are preserved.

**Recommended next engineering increment:** establish and independently review the
inactive release-owned successor contract approval, then freeze S on the separate
future producer branch. Its acceptance criteria are exact original policy digest,
immutable ADR decision references, canonical approval fingerprint, 900/300 limits,
disabled recovery, all historical/successor security regressions, and generated
workflow outputs ready for a separate adoption/pin review. This removes the next
code-level blocker to genuine acceptance-only signing without enabling publication.

The operator's immediate action is to review this documentation diff and record
it through their own commit/PR process, creating the immutable ADR reference for
that next increment. No commit, push, PR, merge, release or operation is performed
by this report. S adoption, hosted signing, live gate activation, publication,
Atlas executable approval and deployment remain separately controlled actions.

### Completion validation and repository state

After the documentation edits, the complete existing repository-documentation
suite passed again: **14 passed, zero skipped/failures/errors**, 0.35 seconds,
using the same host test environment and
`pytest -q -rs -p no:cacheprovider tests/test_repository_docs.py --tb=short
--junitxml=/private/tmp/atlas-adr0018-docs.xml`. This rerun overlaps the original
340 host passes and is not fourteen new distinct cases. The checks include all
local Markdown link targets, untracked-document whitespace, public-guide language
and code fences. Final scope/anchor/hash checks and both `git diff --check`
commands passed. No non-documentation change or staged change exists.

Atlas remains `feature/catalogue-v2-adr0018-approval` at
`95cea88707981af544581b5665a5e5a77250fd1a`. Its `git status --short` is:

```text
 M docs/decisions/0018-catalogue-durable-publication-evidence.md
 M docs/decisions/README.md
 M docs/deployment/catalogue2.md
 M docs/deployment/official-catalogue.md
 M docs/product/feature-ledger.md
?? docs/catalogue2-adr0018-approval-report.md
```

Connectors remains `main` at `078f4099c3fcf850557bf9148db207f696c0ecad`;
`git status --short` returns no output. No producer file, approval record, workflow
or pin was modified. All changes are local, unstaged documentation. No commits,
pushes, PRs, merges, releases, signing, publication, installation, deployment,
GitHub setting changes, database operations or live operations occurred. Neither
`192.168.3.220` nor `atlas-test-docker` was accessed.
