# I4C-A — exact Proxmox qualification checkpoint preparation

Prepared **13 October 2026**. This work prepares local branches for operator
review, commit and push, followed by interactive qualification on the test LXC.
**No live Proxmox qualification, production activation, commit, push, merge, tag
or publication was performed.** I4 remains incomplete. Native Debian/systemd
LIVE acceptance remains outstanding.

## Repository audit and identities

All three repositories began clean. The two task branches point to the merged
I4B baselines, also present in local Atlas `dev` and atlas-connectors `main`.

| Repository | Starting and current branch | Starting and current HEAD |
| --- | --- | --- |
| Atlas | `feature/integrations-i4c-proxmox-qualification` | `7cc20b76662edbf94e929a5f17dda8f6cc56b494` |
| atlas-connectors | `feature/i4c-proxmox-qualification` | `4f001b28df7a1618c7a87a5f8c911bafd4418fd8` |
| atlas-connector-sdk | `main` — read only, unchanged | `8b0518c462289cca4758c3b9bf362f1130928a1c` |

Reviewed repository AGENTS.md, accepted integration v1.3/ADRs, I4A runtime and
completion baseline, I4B completion, Connector source/manifest/SBOM/tests and
discovery/capability/permission/qualification docs, catalogue/store/lifecycle,
runtime verification, deployment packaging and applicable tests/migrations.
I4B source identity locks and bounded capability diagnostics are present. Atlas
core gains no Proxmox API/client/import/normalization/completeness policy.
Legacy plugin code and all Connector source/transport/completeness code are intact.

## Exact candidate and reproducibility

Candidate: **Proxmox Connector 0.2.0-i4b.1**, still **unqualified**, with no qualified
source versions. Proxmox **9.2.11 remains UNQUALIFIED**.

Bundle SHA-256:

```text
d283441dfa70d8e589fd3da868075bdb795a8cda938a78931437432b572166c8
```

Canonical `tools/build_bundle.py --candidate` builds twice matched byte-for-byte;
detached manifests also matched. The archive equals the pre-change I4B candidate.
The reviewed 18-file list contains fixed discovery/readiness/probe playbooks/modules,
normalization/discovery/secured transport helpers, exact candidate manifest and SPDX
SBOM, reviewed documentation and licences. Fixtures, injected source transport,
test tools, credentials, caches, preparation documents and unrelated files are
excluded. An independent verifier checks digest, exact source bytes, file set,
metadata modes/owners/timestamps, manifest/SBOM and contracts. Its committed-source
mode must be run again after the operator's actual commit; current detached HEAD
context does not claim that uncommitted I4C-A work is already in GitHub.

SDK **1.1.0** (minimum, exclusive maximum 2.0.0), AIP **1.0**, runtime baseline
**>=1.2.0,<2.0.0**, community.proxmox **2.0.0** exact archive SHA-256
`77e02e0d1e341c6b064900fe58484ad8880cee4832f5fd65d09834ed068216f6`.
Runtime baseline stays `atlas-ansible-i4a-v1` / **1.2.0**, runtime **0.3.1**,
ansible-core **2.19.7**, ansible-runner **2.4.3**, proxmoxer **2.3.0**.

## Selected staging mechanism and production controls

The existing normal catalogue/store installation rejects the actual candidate.
The `i4b-fixture` harness changes identity/qualification and is unsuitable for live
qualification. The new **generic local installation-authority CLI** is therefore
necessary. Its authority is documented in additive [ADR 0010](../../decisions/0010-local-connector-qualification.md);
existing accepted ADRs are preserved.

Use `python -m scripts.qualify_connector` (`stage`, `plan`, `activate`, `revoke`)
with explicit isolated-test acknowledgement. Docker/LXC is the selected deployment
path, using the committed opt-in override and **separate protected test store**.
No production installer uses that override. Root or the existing Docker installer
UID/GID is required. All execution processes opt in and bind their Atlas build SHA.
A read-only, installation-authority-owned 48-hour grant binds exact prerelease
ID/version/bundle/entire detached manifest, Atlas/Connector commits and store path.
API and runtime independently reject missing, changed, writable, expired, revoked,
symlinked, mismatched or forged grants/receipts. The normal store path is prohibited.

The existing bounded PackageStore validator/atomic installer and per-file verifier
are retained. Verification evidence explicitly says `operator-qualification`, with
no remote attestation assertion. Ordinary catalogue/install/activate endpoints
remain unchanged and cannot supply this source or local permission. Normal
activation still rejects the unqualified candidate, even when its test store exists.
The remote provenance verifier remains fail closed. Grant revocation stops new
verification/execution; already-authorized jobs must be cancelled/settled normally.

Local activation reuses PostgreSQL one-active-version state, mappings/dependent
configuration validation, runtime compatibility/recheck, active-run locks and audit.
A read-only `plan` previews unresolved requirements; explicit scope/mapping choices
are needed where the normal catalogue cannot represent an unlisted version.
Existing active managed taxonomy is reused; incompatible/unresolved choices fail.
All dependent live connections must be generic/manual. Saved credentials and
DataSource identities survive. Normal scoped Test Connection/Run Now, secret leases,
actual Runner/AIP ingestion, reconciliation and absence policy remain authoritative.
There are no migrations, public API/UI/route changes or new permission keys.

## Automated validation

Validation uses existing API and pinned native-style runtime Python environments,
reviewed local collection bytes, and disposable loopback PostgreSQL/Redis services.
No real Proxmox endpoint or source credential was used. Initial sandbox service
binding/shared-memory restrictions were resolved with approved local test execution.
An initial historical minimal-receipt inspection regression was corrected while
retaining ordinary and operator package gates. Final results are recorded below.

| Check | Executed command / environment | Result |
| --- | --- | --- |
| Connector full suite | Exact reviewed `ATLAS_TEST_COLLECTIONS_PATH`, `ATLAS_TEST_RUN_ANSIBLE=1`, runtime Python plus separate pytest support; `python -m pytest -q --tb=short` | 100 passed; four actual Runner cases, transport, normalization, capabilities/completeness, manifests, deterministic/default builds and docs included. |
| Candidate builds/independent inspection | Two `tools/build_bundle.py --candidate --output ...` calls, `cmp` archive/manifest/pre-change archive; `tools/verify_candidate.py --expected-digest ...`; default build | Passed; candidate digest above, all 18 files inspected; default version stays 0.1.0. |
| Runtime focused acceptance | API `.venv/bin/python -m pytest tests/test_connector_qualification.py tests/test_connector_qualification_postgres.py tests/test_i4b_runtime.py tests/test_source_identity.py tests/test_capability_diagnostics.py tests/test_i4a_runtime.py tests/test_i3_live_runtime.py -q --tb=short`, disposable DB and `ATLAS_TEST_RUNTIME_PYTHON` | 76 passed at that checkpoint; later additional cases are covered by final selectors below. |
| Merged qualification Compose configuration | `docker compose ... -f infra/docker/docker-compose.qualification.yml config --format json`, captured privately with ephemeral test environment; assertions on parsed configuration | Passed: exact opt-in/build identity, separate volume, worker/runtime read-only candidate mounts, no public listeners, existing networks and bootstrap unchanged. |
| Workflow lint | Existing actionlint executable against CI/release workflows in both writable repositories | Passed, no diagnostics; workflows unchanged. |

| Release-critical | From `apps/api`: `bash ../../infra/ci/release-critical.sh`, API venv PATH, legacy plugin PYTHONPATH, disposable PostgreSQL/Redis and pinned runtime Python | **543 passed**, no skips. I4B/I4A, source identity, diagnostics, store/bootstrap, release and new qualification unit/PostgreSQL cases included. |
| I3 / configuration / lifecycle regression | API `python -m pytest tests/test_i3_discovery.py tests/test_i3_live_runtime.py tests/test_discovery_sync.py tests/test_i2_integrations.py tests/test_connector_lifecycle_api.py tests/test_connector_lifecycle_postgres.py tests/test_integration_catalogue_api.py -q --tb=short`, disposable DB, pinned runtime and `REDIS_URL=redis://127.0.0.1:16379/0` | **97 passed**, no skips. An initial Redis selector defaulted to port 6379; the final command explicitly used the disposable service. |
| Contracts and documentation | From Atlas root: `PYTHONPATH=plugins/sdk:plugins/proxmox apps/api/.venv/bin/python -m pytest docs/architecture/integrations/contracts/tests apps/api/tests/test_repository_docs.py apps/api/tests/test_markdown_docs.py -q --tb=short` | **95 passed**. |
| Migration graph | From API: `.venv/bin/python -m alembic heads` | Existing single head **20261012_0029**; no migrations required. |
| Release dry-run and independent verification | `apps/api/.venv/bin/python infra/release/release.py build --output /private/tmp/atlas-i4c-a/release --dry-run --worktree`; `... release.py verify --output ...` | Passed for Docker Compose/systemd packages; working-tree artefacts explicitly non-publishable. No image/installer execution claimed. |
| Compilation | API venv `python -m compileall -q` on changed API modules/CLI/tests and runtime; Connector build venv on tools/source/tests | Passed. Generated caches are ignored/excluded. |
| Diff / production / SDK preservation | `git diff --check` in all three repositories; `git diff --exit-code` for Atlas bootstrap/SDK/baseline/locks and Connector candidate/source; direct bootstrap digest/capability assertions | Passed. SDK clean/unchanged; no production or candidate source bytes changed. |
| Pinned Python 3.12 Docker Connector suite | `docker run --rm --network none --read-only`, tmpfs `/tmp`, read-only Connector/pytest mounts, reviewed `/app/collections`, `ATLAS_TEST_RUN_ANSIBLE=1`, explicit test-only exported-source commit; `python -m pytest -q --tb=short` in `atlas-runtime:i4a-validation` | **100 passed**, no skips; all four actual Runner cases executed. |
| Packaged Docker builds | Extracted independently verified working-tree dry-run; isolated project `atlas-i4c-a-validation`; `docker compose ... config --quiet` and `build api web worker runtime runtime-init connector-bootstrap` | **All six images built successfully**, including production web build. Local validation tags only; no deployment/release/publication. |
| Actual packaged Docker authority / store / runtime checks | Private temporary script `/private/tmp/atlas-i4c-a/docker-qualification-validation.py`: ephemeral volumes, no network, read-only roots, exact real candidate CLI stage, runtime health/verify, disabled/revoked rechecks, mutation denial and retained normal bootstrap | Passed. Existing installer **UID/GID 10001:10001** explicitly selected; exact candidate verified, runtime write denied, disabled/revoked candidate unavailable, original 0.1.0 still verified/probe-only. No source call, database activation or live credential. Volumes removed after checks. |

Existing dependency deprecation warnings remain. Frontend tests/build are not
applicable because no frontend changed.
Docker Desktop was initially unavailable; after the operator started it, all
previously unavailable Docker checks above were executed successfully. The first
container authority check correctly rejected the API account's different primary
group; the procedure now explicitly selects the existing installer UID/GID rather
than relaxing the guard. No LXC deployment, live source qualification or native
Debian/systemd LIVE acceptance is claimed.

## Material files and purpose

Atlas material files:

- `apps/api/app/services/connector_qualification.py`: exact protected local authority and verifier.
- `apps/api/app/services/connector_verification.py`: additive explicit qualification receipt identity.
- `apps/api/app/services/connector_store.py`: exact operator path through existing validation/store checks.
- `apps/api/app/services/connector_lifecycle.py`: local activation option retaining lifecycle guards.
- `apps/api/app/services/integration_connections.py`: use authoritative store qualification validation.
- `apps/api/scripts/qualify_connector.py`: local stage/preview/activate/revoke, explicit scopes/mappings and audit.
- `apps/api/tests/test_connector_qualification.py`: grant/archive/identity/default rejection/security regression.
- `apps/api/tests/test_connector_qualification_postgres.py`: transactional activation, retained source/credentials, normal I3, mapping/scope/run/preview checks.
- `apps/runtime/ansible/atlas_runtime/qualification.py`: independent runtime grant and ordinary qualification policy.
- `apps/runtime/ansible/atlas_runtime/server.py`: invoke that independent verification before execution.
- `infra/docker/docker-compose.qualification.yml`: opt-in separate test volume with read-only execution mounts.
- `infra/ci/release-critical.sh`: include new qualification regressions.
- `docs/decisions/0010-local-connector-qualification.md`: explicit additive test authority decision.
- `docs/deployment/connector-qualification.md`: exact staging, preview, activation and cleanup commands.
- `docs/deployment/integration-runtime.md`: link the contained test procedure.
- `docs/architecture/integrations/integration-roadmap.md`: truthful preparation/live gate status.
- `docs/product/feature-ledger.md`: implemented preparation component; production discovery stays partial.
- `docs/architecture/integrations/i4c-a-preparation.md`: this review/validation/state record.

atlas-connectors material files:

- `tools/build_bundle.py`: reviewed explicit file list preserves candidate/default package bytes.
- `tools/verify_candidate.py`: independent digest/source/file-set/contract/checkpoint inspector.
- `tests/test_i4c_checkpoint.py`: immutable contents and inspection regression coverage.
- `README.md`: link preparation and planned live runbook.
- `connectors/proxmox/docs/i4c-live-qualification.md`: interactive Mac/GitHub/LXC workflow and planned live checks.
- `connectors/proxmox/docs/i4c-a-preparation.md`: Connector-specific preparation/evidence record.

SDK: **no files changed**. Bootstrap/catalogue, candidate manifest/SBOM/source,
collection/dependency locks and existing I4B COMPLETE/security rules are unchanged.

## Next operator checkpoint and remaining gates

Review the exact diffs/statuses, commit the listed changes on each feature branch,
record full resulting SHAs, and push those feature branches. The exact commands
are in the Connector live runbook; **pause after those pushes**, then perform the
interactive LXC checkpoint. Pull those exact commits, build twice on the LXC,
independently verify the fixed digest and new committed-source identity, record
both SHAs/candidate/runtime/collection identities, and follow the Atlas procedure.
Do not use uncommitted Mac artefacts.

Live checks requiring the operator: 9.2.11 version/auth/readiness, actual token/user
ACL intersection and unfiltered ACL proof/NoAccess, real Runner/AIP discovery,
available classes/topology, COMPLETE/PARTIAL/no-absence proof, unchanged repeat runs,
safe negatives and optional explicitly chosen disposable mutations. Missing classes
or unsafe scenarios stay untested. No destructive infrastructure changes are required.

Production bootstrap/catalogue still expose **Proxmox 0.1.0**, with
`discover=false`, scheduling=false, complete_snapshot=false and no discovery entry
point/dependency. Candidate **0.2.0-i4b.1** stays unqualified; **9.2.11** stays
unqualified; no Connector GitHub release is published; **I4 stays incomplete**.
Native LIVE acceptance and remote official provenance remain genuine follow-ups.
Revocation/expiry blocks new execution and preserves history. This slice supplies
no automatic previous-version configuration conversion: candidate scopes may be
incompatible with the original probe-only package. Keep the qualification
connection disabled until a separately reviewed compatible restore; do not bypass
the normal dependent-configuration guard or delete knowledge to force rollback.

## Final repository state (`git status --short`)

Atlas (all changes are this task; HEAD/branch unchanged):

```text
 M apps/api/app/services/connector_lifecycle.py
 M apps/api/app/services/connector_store.py
 M apps/api/app/services/connector_verification.py
 M apps/api/app/services/integration_connections.py
 M apps/runtime/ansible/atlas_runtime/server.py
 M docs/architecture/integrations/integration-roadmap.md
 M docs/deployment/integration-runtime.md
 M docs/product/feature-ledger.md
 M infra/ci/release-critical.sh
?? apps/api/app/services/connector_qualification.py
?? apps/api/scripts/qualify_connector.py
?? apps/api/tests/test_connector_qualification.py
?? apps/api/tests/test_connector_qualification_postgres.py
?? apps/runtime/ansible/atlas_runtime/qualification.py
?? docs/architecture/integrations/i4c-a-preparation.md
?? docs/decisions/0010-local-connector-qualification.md
?? docs/deployment/connector-qualification.md
?? infra/docker/docker-compose.qualification.yml
```

atlas-connectors:

```text
 M README.md
 M tools/build_bundle.py
?? connectors/proxmox/docs/i4c-a-preparation.md
?? connectors/proxmox/docs/i4c-live-qualification.md
?? tests/test_i4c_checkpoint.py
?? tools/verify_candidate.py
```

atlas-connector-sdk: **empty output, clean**.

Stop at this reviewable uncommitted checkpoint. The next commit SHAs belong to
the operator's explicit review/commit/push step, not to this preparation report.
