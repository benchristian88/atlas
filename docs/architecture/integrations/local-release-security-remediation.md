# Phase 4B.12A — security review remediation evidence

Repository: `/Users/Ben/Code/atlas`

Branch: `feature/secure-local-release-acceptance`

HEAD: `808ee0f76f77c11e17a6c403806ce0666e30074e` (unchanged; implementation uncommitted).

The original local-release implementation was already present as working-tree
changes. This task preserves it and remediates the review findings. No commit,
push, merge, catalogue publication, LXC deployment or live source call was made.
The [original engineering report](local-release-acceptance.md) is historical.
Current decisions and human operating instructions are in [ADR 0015](../../decisions/0015-local-release-execution-authority.md)
and the [operator procedure](../../deployment/local-release-acceptance.md).

The original remediation record below is retained as history. The subsequent
independent re-review's three recovery findings, their reproductions and final
closure evidence are recorded in [Final recovery remediation](#final-recovery-remediation).

## Findings and evidence

The supplied request identifies the first finding as HIGH and the revocation-audit
finding as LOW. It identifies the other five collectively as HIGH/MEDIUM without
individual ratings; this report does not invent individual grades. “H/M*” below
means that original individual rating was not supplied.

Before fixes, the new reproduction suite demonstrated nine failing cases: staged
probe launch, timestamp-sensitive activation, three automatic triggers, combined
artifact/lease expiry, application checkpoint modification, boolean-only isolation
acceptance and missing revocation audit. The initial checkpoint test had an
unpersisted audit actor; after persisting it, the route demonstrably accepted the
forbidden write and the corrected test failed with “DID NOT RAISE”. The other eight
failed directly for their intended security assertions. These are reproduction
results, not passing-test counts.

| Original severity / scenario | Exact remediation code | Original reproduction and remediation proof | Remaining limits |
| --- | --- | --- | --- |
| HIGH: staging grant admitted execution before approval | [artifact staging](../../../apps/api/app/services/connector_release_acceptance.py#L133), [committed publication](../../../apps/api/app/services/connector_release_acceptance.py#L376), [activation](../../../apps/api/app/services/connector_release_acceptance.py#L445), [offline checker](../../../apps/runtime/ansible/atlas_runtime/local_release.py#L85), [runtime admission](../../../apps/runtime/ansible/atlas_runtime/server.py#L159), [probe](../../../apps/runtime/ansible/atlas_runtime/probe.py#L76), [discovery](../../../apps/runtime/ansible/atlas_runtime/jobs.py#L155) | [staged-only direct probe](../../../apps/api/tests/test_local_release_remediation.py#L22) failed before fixes by reaching worker launch; now denied while integrity inspection succeeds. [Direct discovery](../../../apps/api/tests/test_local_release_remediation.py#L336), [replay](../../../apps/api/tests/test_local_release_remediation.py#L184), [commit failure](../../../apps/api/tests/test_local_release_remediation.py#L278), [post-commit failure/recovery](../../../apps/api/tests/test_local_release_remediation.py#L249), [reactivation](../../../apps/api/tests/test_local_release_remediation.py#L299) and [independent-session locks](../../../apps/api/tests/test_local_release_remediation.py#L434) exercise real admission and durable boundaries. | Root/filesystem/DB durability and trustworthy clock are assumed. Already admitted work may finish. Full privileged rollback is outside scope. |
| H/M*: full health dictionaries compared changing timestamps | [stable runtime identity](../../../apps/api/app/services/connector_release_acceptance.py#L313) and independent healthy checks during activation/maintenance | [production health adapter with advancing timestamps](../../../apps/api/tests/test_local_release_remediation.py#L43) failed before fixes and now activates. [Changed runtime/state](../../../apps/api/tests/test_local_release_authority_postgres.py#L172) still rejects stale plans. | No live baseline/image/source acceptance is claimed by synthetic dependency fixtures. |
| H/M*: local connections could onboard, schedule and dispatch automatically | [creation/detail/probe context](../../../apps/api/app/routes/integration_connections.py#L156), [schedules](../../../apps/api/app/routes/integration_discovery.py#L126), [manual guard](../../../apps/api/app/services/integration_connections.py#L42), [run intent](../../../apps/api/app/services/discovery_orchestration.py#L90), [worker dispatch](../../../apps/api/app/services/discovery_orchestration.py#L189), [runtime checker](../../../apps/runtime/ansible/atlas_runtime/local_release.py#L85) | [automatic triggers](../../../apps/api/tests/test_local_release_remediation.py#L70) all failed before fixes by being accepted. [Connection/schedule/Run Now routes](../../../apps/api/tests/test_local_release_remediation.py#L353), [preexisting worker intent](../../../apps/api/tests/test_local_release_remediation.py#L378), runtime automatic-context rejection and normal I2/I3 suites prove restriction and compatibility. | Runtime control credentials remain privileged. API scoped RBAC continues to authorize individual manual operations. |
| H/M*: staging-started 48-hour grant permanently disabled immutable tuple | [single-use approval](../../../apps/api/app/services/connector_release_acceptance.py#L334), [consumption](../../../apps/api/app/services/connector_release_acceptance.py#L370), [lease maintenance](../../../apps/api/app/services/connector_release_acceptance.py#L493), [execution/status](../../../apps/api/app/services/local_release_authority.py#L243), [CLI](../../../apps/api/scripts/accept_connector_release.py#L16) | [artifact persistence](../../../apps/api/tests/test_local_release_remediation.py#L78) failed before fixes at 49 hours. [Approval expiry/replay](../../../apps/api/tests/test_local_release_remediation.py#L196), [fresh-process offline expiry/renewal](../../../apps/api/tests/test_local_release_remediation.py#L218), recovery, revocation and [separate status](../../../apps/api/tests/test_local_release_remediation.py#L410) cover the new lifecycles. Receipt bytes are asserted unchanged by renewal. | Approval: ten minutes, consumed at commit boundary. Execution: maximum 48 hours, explicit reviewed renewal. Renewal/recovery require the bound DB and healthy runtime; execution within the lease needs neither GitHub nor DB access at runtime. |
| H/M*: ordinary SystemSetting PATCH could alter enrollment checkpoint | [reserved internal setting](../../../apps/api/app/routes/system_settings.py#L68) | [checkpoint reproduction](../../../apps/api/tests/test_local_release_remediation.py#L85) originally accepted the write; final regression uses the actual HTTP PATCH with a global `system_settings.manage` principal and proves 409 with the original checkpoint retained. | Direct privileged SQL/database restore is outside application-RBAC protection; mismatched checkpoints deny API execution. |
| H/M*: isolation evidence contained only operator booleans | [resource observation](../../../apps/api/app/services/local_release_authority.py#L83), [isolation comparison/enrollment](../../../apps/api/app/services/local_release_authority.py#L140), [inspection CLI](../../../apps/api/scripts/bind_local_release_instance.py#L10), [runtime binding](../../../apps/runtime/ansible/atlas_runtime/local_release.py#L34), [Compose identity mount](../../../infra/docker/docker-compose.local-release.yml#L1) | [boolean-only report](../../../apps/api/tests/test_local_release_remediation.py#L104) was accepted before fixes. [Five resource-substitution cases](../../../apps/api/tests/test_local_release_remediation.py#L325) now reject database/cluster, deployment and protected storage mismatch before writing enrollment files. Existing copied/writable/binding tests remain. | Database/Redis/runtime/worker/credentials/mount human inspection is mandatory. Matching identities/configuration do not prove physical isolation. New cluster-ID read privilege is required. |
| LOW: revocation lacked PostgreSQL audit | [filesystem-first revoke and reconciliation](../../../apps/api/app/services/connector_release_acceptance.py#L171) | [missing audit reproduction](../../../apps/api/tests/test_local_release_remediation.py#L111) failed before fixes; [outage/denial/idempotent reconciliation](../../../apps/api/tests/test_local_release_remediation.py#L311) proves durable denial before DB access and exactly one eventual audit event. | Outage returns `audit: reconciliation_required`; root must reconcile against the bound DB. |

## Transaction and authorization details

Artifact staging evidence and immutable receipts never carry execution permission.
Plans issue protected signed ten-minute approvals for one operation, exact state
digest and reviewed lease duration. They include complete dependency/configuration/
credential revisions via digests, mappings, taxonomy, previous active identity,
resource inspection and stable runtime compatibility identity. Capacity and
`last_checked_at` are excluded, while healthy status is checked independently.

Store locking serializes root operations. PostgreSQL connector, dependent row,
secret, mapping and taxonomy locks are acquired outside preview savepoints:
rolling back a PostgreSQL savepoint releases locks acquired inside it. This was
confirmed with independent sessions and a bounded lock-timeout regression.

Activation consumes approval and durably removes the old current lease before
updating active state. A new activation UUID, lease UUID, binding, approved-plan
identity and time window commit with the PostgreSQL activation audit. An independent
Session then checks visibility of that exact row, original consumed signed approval
and audit before a signed current lease is published by atomic rename. Historical
leases remain evidence and are never accepted as current authority. Both runtime
execution entry points call the independent checker; `verify_connector` stays an
integrity-only inspection operation and creates no circular activation requirement.

Failure before commit leaves the previous DB record and execution denied if
fencing already happened. Failure after commit leaves the new active record but
no current execution authority and reports an explicit recovery error. Publication
failure is audited where the DB is available. Reviewed recovery is itself audited,
revalidates committed evidence and cannot extend expiry. Reviewed renewal retains
artifact receipts and generation, changes the lease identity and invalidates old
requests. Revocation is a durable signed artifact tombstone, final for that artifact
authorization, immediately respected without PostgreSQL; audit reconciliation
checks the bound DB and serializes by artifact to prevent duplicates.

No migrations were required. The existing active row's JSON evidence carries local
activation metadata separately from the immutable artifact receipt, and the existing
SystemSetting holds protected enrollment. Alembic remains at single head
`20261021_0031`. Existing routes and catalogue behavior remain; installed local
packages gain additive `local_execution` status. No frontend implementation changes.
Global runtime-management and scoped customer/site connection/discovery RBAC remain
authoritative. Runtime gets neither DB credentials nor the operator private key.

## Earlier remediation validation record

Final combined Linux/root run: **1,395 passed, zero failures, zero skips**, 556
warnings from existing migration/dependency deprecations and expected constraint
fixtures. This is the unique passing-test count; earlier overlapping checkpoints
and the later strengthened expiry test are not added to it. Alembic upgrade and
heads checks passed with one head, `20261021_0031`.

Exact final combined invocation (the harness copies source into its disposable
filesystem, migrates a fresh database and calls `pytest.main` with these arguments):

```bash
docker run --rm --user 0:0 --name atlas-4b12a-runner \
  --network atlas-4b12a-tests \
  --mount type=bind,source=/Users/Ben/Code/atlas,target=/workspace,readonly \
  --mount type=bind,source=/private/tmp/atlas-4b12a-harness-w2kp2nsz,target=/harness,readonly \
  --entrypoint python atlas-b13-api:arm64 /harness/run-remediation.py \
  tests/test_local_release_remediation.py tests/test_local_release_authority_postgres.py \
  tests/test_connector_release_acceptance.py tests/test_connector_qualification_postgres.py \
  tests/test_connector_lifecycle_postgres.py tests/test_i3_discovery.py \
  tests/test_integration_catalogue_api.py tests/test_connector_lifecycle_api.py \
  tests/test_connector_qualification.py tests/test_connector_packages.py \
  tests/test_official_provenance.py tests/test_attestation_distribution.py \
  tests/test_runtime_packaging.py tests/test_catalogue_source.py tests/test_catalogue_trust.py \
  tests/test_catalogue_publication_evidence.py tests/test_catalogue_bootstrap_authorization.py \
  tests/test_official_catalogue.py tests/test_official_catalogue_selection.py \
  tests/test_official_catalogue_ingestion.py tests/test_trusted_catalogue.py \
  tests/test_connector_bootstrap.py tests/test_i2_integrations.py tests/test_i3_runtime.py \
  tests/test_integration_runtime.py tests/test_i3_concurrency_postgres.py \
  tests/test_discovery_diagnostics_concurrency_postgres.py tests/test_administration.py -q --tb=short
```

The Linux/root harness uses fresh PostgreSQL databases owned by non-superuser
`atlas_test`, independently committed per-test schemas and separate Sessions,
isolated Redis and no published ports or production mounts. PostgreSQL grants only
the additional non-secret cluster-ID function access needed for these tests.
The API image supplies its original integrity-checked pinned Linux verifier. The
test-only harness copies pinned psutil 7.2.2 from the cached runtime image because
the API image intentionally lacks runtime process dependencies. No product test
was removed or weakened for this environment issue. Original fixture archives,
attestations, frozen roots and verifier profiles are unchanged.

The pre-remediation combined-expiry negative case is superseded by the explicitly
requested separate lifecycle tests: artifact integrity continues after expiry,
while the actual runtime checker denies expiry, wrong generations, altered leases,
automatic triggers, revoked authority and staging-only requests. Fresh child
processes disable sockets and re-read protected files to test offline/restart
admission before expiry, at expiry and after reviewed renewal. The production
health adapter is exercised with advancing check timestamps. Worker/Ansible output
is synthetic in execution-materialization tests; no source call or LXC operational
qualification is implied.

The expiry/renewal case was subsequently strengthened with fresh API processes
and independent database Sessions, forbidding HTTP while preserving PostgreSQL
access. Its separate rerun **passed (1 test, 12 existing warnings)**. It is already
one of the 1,395 tests and is not counted again. The rerun used the same Docker
command with only
`tests/test_local_release_remediation.py::test_expiry_reviewed_renewal_and_offline_restart_do_not_change_artifact_evidence -q --tb=short`
as the pytest arguments.

An initial expanded run had 1,386 passes and seven runtime-cleanup failures due
to missing psutil in the API-only harness. This was a harness setup defect; the
pinned cached runtime dependency was supplied before the final combined run.
Those overlapping passes are not added to the final count.

Actual merged Compose validation used generated disposable credentials and
`--env-file /dev/null`, without starting any Atlas deployment. Assertions checked
selected stores, read-only public/store/deployment mounts, private-key isolation,
root-only operator capabilities and private runtime/no DB environment: **PASS**.
No production `.env` contents or credentials were printed.

Additional commands: Python `compileall -q` for changed API/runtime/operator
modules **PASS**; `git diff --check` and untracked text whitespace inspection
**clean**; relative documentation/code-line link check **64 links resolved**.
No frontend build or full new image build was run because no frontend code changed
and deployment/image acceptance is outside this task.

## Material working-tree inventory

The inventory includes original uncommitted local-release implementation files
present before remediation as well as files changed by this remediation.

| Files | Purpose |
| --- | --- |
| `apps/api/app/services/connector_release_acceptance.py` | Original release identity/signature adapter; split staging/approval/activation/lease lifecycle, independent commit checks, renewal/recovery and revocation audit. |
| `apps/api/app/services/local_release_authority.py` | Protected enrollment/resource identities, staging evidence, leases, fences and effective status. |
| `apps/api/app/services/connector_lifecycle.py` | Local operator gate, revoked-authority guard and additive installed status. |
| `apps/api/app/services/connector_store.py` | Original additive local staging/integrity adapter retained. |
| `apps/api/app/services/integration_connections.py` | Database/receipt/lease validation and manual policy. |
| `apps/api/app/services/discovery_orchestration.py` | Immutable generation/lease context, manual intent and worker dispatch guards. |
| `apps/api/app/services/integration_runtime.py` | Additive local execution context in private probe transport. |
| `apps/api/app/routes/integration_connections.py` | Manual connection creation, scheduling-capability response and probe context. |
| `apps/api/app/routes/integration_discovery.py` | Manual-only schedule changes. |
| `apps/api/app/routes/integrations.py` | Effective authorization response and pre-uninstall revocation guard. |
| `apps/api/app/routes/system_settings.py` | Enrollment-checkpoint modification prohibition. |
| `apps/api/scripts/accept_connector_release.py` | Plan/activate/renew/recover/revoke/reconcile operator interface. |
| `apps/api/scripts/bind_local_release_instance.py` | Independent resource observation and enrollment. |
| `apps/runtime/ansible/atlas_runtime/local_release.py` | Independent artifact verification and execution-authority checker. |
| `apps/runtime/ansible/atlas_runtime/server.py` | Shared runtime execution-admission method. |
| `apps/runtime/ansible/atlas_runtime/probe.py` | Test Connection admission. |
| `apps/runtime/ansible/atlas_runtime/jobs.py` | Discovery admission. |
| `apps/runtime/ansible/atlas_runtime/qualification.py` | Original additive dispatch to local integrity adapter; prerelease behavior retained. |
| `apps/api/tests/test_local_release_remediation.py` | Review reproductions, real HTTP/runtime/fresh-process and independent-session regressions. |
| `apps/api/tests/test_local_release_authority_postgres.py` | Original root/PostgreSQL suite adapted to genuine committed sessions and separate lifecycles. |
| `apps/api/tests/test_connector_release_acceptance.py` | Original genuine release/provenance policy tests retained. |
| `apps/api/tests/test_runtime_packaging.py` | Public deployment identity mount and operator/consumer isolation. |
| `apps/api/tests/fixtures/local_release/README.md`, `manifest.json`, `package.sigstore.json`, `proxmox-0.2.2.tar.gz`, `release.json`, `tag-ref.json` | Original captured immutable release/signature bytes retained unchanged. |
| `infra/docker/docker-compose.local-release.yml` | Protected public deployment identity shared read-only alongside existing separate authority volumes. |
| `docs/decisions/0014-local-release-acceptance.md` | Original accepted ADR retained with explicit partial-supersession notice. |
| `docs/decisions/0015-local-release-execution-authority.md` | Security lifecycle/resource-binding decision. |
| `docs/decisions/README.md` | ADR index. |
| `docs/deployment/local-release-acceptance.md` | Precise isolation, expiry, renewal, revocation and crash-recovery procedure. |
| `docs/deployment/attestation-verification.md`, `docs/deployment/integration-runtime.md` | Original additive local-acceptance cross-references retained. |
| `docs/product/feature-ledger.md` | Current implemented behavior and outstanding live acceptance. |
| `docs/architecture/integrations/local-release-acceptance.md` | Historical pre-review report retained and clearly marked. |
| `docs/architecture/integrations/local-release-security-remediation.md` | This current findings/remediation/validation/inventory report. |

## Operational limits and re-review boundary

No live Proxmox/LXC/Ansible qualification, full image build, native deployment,
reboot or cross-architecture acceptance was performed. Root/deployment key/provider
compromise, dishonest human inspection, complete privileged rollback/cloning and
clock rollback are outside the boundary. Frozen Sigstore roots retain their existing
revocation-awareness limits. Physical directory identities deliberately reject
unreviewed storage substitution; planned volume migration, key/build rotation and
cross-instance restore need separate reviewed procedures. Pre-review authority
files fail closed and are never silently rewritten or upgraded. There was no live
enrolled LXC in this implementation task.

Expiry/revocation stops new admission, not jobs already admitted. Manual requests
still traverse the existing worker; automatic intent is rejected rather than
creating a new execution system. Historical package and discovery knowledge are
retained. PostgreSQL remains the authoritative active-package/audit store. No SDK,
Connector repository, original signed archive, trust root, catalogue release or
production deployment was changed.

**REMEDIATION COMPLETE — READY FOR INDEPENDENT RE-REVIEW**

## Final recovery remediation

This follow-up addresses the independent re-review's **CONDITIONAL PASS**. The
accepted execution, isolation, provenance and catalogue mechanisms were retained.
Branch and HEAD remain as recorded above; all work remains uncommitted.

### Three-finding closure matrix and before/after reproductions

| Finding | Before fixes (executed reproductions) | Fix and after evidence | Status |
| --- | --- | --- | --- |
| MEDIUM: expired lease prevents credential repair | Clearing credentials, advancing beyond lease expiry and calling the real credential replacement route returned HTTP 409; renewal also required valid credentials. | [Installed metadata policy](../../../apps/api/app/services/integration_connections.py#L15) and [maintenance routes](../../../apps/api/app/routes/integration_connections.py#L223) retain package/receipt/database/schema checks while omitting execution-lease validation only for maintenance. [Exact regression](../../../apps/api/tests/test_local_release_recovery.py#L30) clears credentials, expires the lease, proves Test Connection and fresh runtime admission denied, repairs credentials/configuration, reviews renewal and authorizes manual discovery. [Negative maintenance cases](../../../apps/api/tests/test_local_release_recovery.py#L246) cover tenant scope, schema and altered installed bytes. Repair does not change or publish authority. | Closed |
| MEDIUM: cannot restore ordinary bundled management | After local activation/revocation, activating the real bundled `proxmox 0.1.0` in a separate store failed `local_release_not_authorized`: the old guard checked the original binding against the replacement store. | [Root-reviewed handoff](../../../apps/api/app/services/local_release_restoration.py#L130), [normal-lifecycle consumption](../../../apps/api/app/services/connector_lifecycle.py#L49) and [transactional consumer](../../../apps/api/app/services/local_release_restoration.py#L162). [Real HTTP activation and independent DB reads](../../../apps/api/tests/test_local_release_recovery.py#L86), [rollback/retry](../../../apps/api/tests/test_local_release_recovery.py#L198) and [separate CLI/API processes with UID 10001](../../../apps/api/tests/test_local_release_recovery.py#L444) prove the handoff. Original configuration values, ciphertext, tenant/source identity, historical evidence/assertions and audits survive. Probe-only scope adaptation is explicit, reviewed and retains prior selections in signed evidence. | Closed |
| LOW: interrupted revocation blocks audit reconciliation | Injecting failure at file fsync exposed the final tombstone pathname before publication completed and before read-only protection was applied. The corrected reproduction failed its assertion that no invalid final file be visible. | [Atomic publication](../../../apps/api/app/services/local_release_revocation.py#L26), [durable intent/fence](../../../apps/api/app/services/local_release_revocation.py#L49), [root corrupt-evidence recovery](../../../apps/api/app/services/local_release_revocation.py#L62), [idempotent audit reconciliation](../../../apps/api/app/services/connector_release_acceptance.py#L178), and independent [API](../../../apps/api/app/services/local_release_authority.py#L214)/[runtime](../../../apps/runtime/ansible/atlas_runtime/local_release.py#L68) denial. [Fault injection](../../../apps/api/tests/test_local_release_recovery.py#L265), [actual process crash](../../../apps/api/tests/test_local_release_recovery.py#L301), [partial/corrupt/empty legacy evidence and DB outage](../../../apps/api/tests/test_local_release_recovery.py#L333), and [concurrent retries](../../../apps/api/tests/test_local_release_recovery.py#L402) all exercise the retained denial and eventual single audit. | Closed |

Before modifications, the initial run reported three failures: two directly at
the intended defects, and the revocation test at its expected-exception wrapper.
The store wraps filesystem errors as `ConnectorPackageError`; after accepting that
existing wrapper, the unchanged implementation was rerun and failed precisely
because the interrupted final file existed. These are negative reproduction
results, not passing test counts. Logs are retained in
`/private/tmp/atlas-4b12a-before.log` and
`/private/tmp/atlas-4b12a-before-revocation.log`.

The [isolation regression correction](../../../apps/api/tests/test_connector_release_acceptance.py#L127)
provides complete database/deployment/storage identities. Every negative case
first passes with its original report; expired/future cases reject only after
timestamp modification and pass again when only the timestamp is repaired.

### Security and transaction recheck

| Original boundary | Final regression evidence |
| --- | --- |
| Staging never admits execution | Actual runtime probe/discovery admission, including staged-only direct requests, unchanged in `test_local_release_remediation.py`. |
| Health liveness does not alter stable approval identity | Production health adapter advances timestamps; changed runtime compatibility identity still invalidates the plan. |
| Local execution is explicit manual-only | Connection creation, onboarding, schedules, worker automatic intent and direct runtime automatic requests remain covered. |
| Artifact evidence, approval and execution have distinct lifetimes | Approval expiry/consumption, failed commit, post-commit recovery, lease expiry/renewal, fresh offline processes and generation replay remain covered. Credential repair now works without issuing a lease. |
| Application RBAC cannot rewrite enrollment | Actual SystemSetting HTTP rejection remains; the new handoff setting prefix is also reserved and tested. |
| Isolation uses complete independently observed identities | Boolean-only evidence and database/deployment/store/public/private substitutions still reject. Time fixtures now independently prove expiry/future rejection. |
| Revocation denies offline and eventually audits once | Original outage/reconciliation test plus crash, corrupt evidence, concurrent publication and repeated audit reconciliation. |

Normal bundled restoration retains the original authority's binding, revocation
and artifact evidence. Root re-verifies original release signatures before
signing the exact handoff; the ordinary API authenticates the public grant,
receipt, tombstone, retained handoff and committed authorization audit. It cannot
read the private key or original root-only download directory. A real child
process drops groups/GID/UID to 10001 and proves those permission denials while
successfully completing ordinary activation.

The pending signed handoff is stored in the existing PostgreSQL SystemSetting,
with protected filesystem evidence retained in the original store. The existing
global `integration_runtime.manage` route remains authoritative. Store identity,
exact active/dependent digests, original revocation, production catalogue verifier,
runtime verification, active-run, legacy-dependent, schema, scope and mapping
guards remain mandatory. Missing handoff/revocation, wrong original/target store,
modified signature/tombstone/package, stale active/dependent state, stale review,
non-root issuance and replay are rejected. Ordinary verified activation, handoff
consumption, explicit scope changes and completion audit share one real
PostgreSQL transaction; injected commit failure retains the old activation,
scopes and pending handoff for retry. Independent Sessions verify both outcomes.

No migration was needed. The existing single Alembic head is `20261021_0031`.
There are no breaking API/UI changes. Existing scoped maintenance becomes
available after expiry; execution routes keep their lease checks. Existing
connection configuration values and encrypted credentials are not rewritten.
No automatic promotion, eligibility, catalogue publication, prerelease
qualification, signed release bytes or cryptographic trust roots changed.

### Validation for the final recovery pass

Final combined run: **1,428 passed, zero failures, zero skips**, with 908 warnings
from existing migration/dependency deprecations and expected constraint fixtures,
in 220.94 seconds. Final log: `/private/tmp/atlas-4b12a-final.log`.
Earlier checkpoints: 116 focused tests
passed; an initial expanded checkpoint found one valid incompatibility between
inventory scopes and the probe-only replacement, which is now handled by explicit
reviewed scope selection. A subsequent broad checkpoint passed 1,427 tests.
The strengthened restart/preservation/packaging checkpoint passed four tests,
including the actual UID-10001 consumer. Overlapping counts are not added.

Exact final invocation, using the existing disposable root/Linux harness:

```bash
docker run --rm --user 0:0 --name atlas-4b12a-final-runner \
  --network atlas-4b12a-tests \
  --mount type=bind,source=/Users/Ben/Code/atlas,target=/workspace,readonly \
  --mount type=bind,source=/private/tmp/atlas-4b12a-harness-w2kp2nsz,target=/harness,readonly \
  --entrypoint python atlas-b13-api:arm64 /harness/run-remediation.py \
  tests/test_local_release_recovery.py tests/test_local_release_remediation.py \
  tests/test_local_release_authority_postgres.py tests/test_connector_release_acceptance.py \
  tests/test_connector_qualification_postgres.py tests/test_connector_lifecycle_postgres.py \
  tests/test_i3_discovery.py tests/test_integration_catalogue_api.py \
  tests/test_connector_lifecycle_api.py tests/test_connector_qualification.py \
  tests/test_connector_packages.py tests/test_official_provenance.py \
  tests/test_attestation_distribution.py tests/test_runtime_packaging.py \
  tests/test_catalogue_source.py tests/test_catalogue_trust.py \
  tests/test_catalogue_publication_evidence.py tests/test_catalogue_bootstrap_authorization.py \
  tests/test_official_catalogue.py tests/test_official_catalogue_selection.py \
  tests/test_official_catalogue_ingestion.py tests/test_trusted_catalogue.py \
  tests/test_connector_bootstrap.py tests/test_i2_integrations.py tests/test_i3_runtime.py \
  tests/test_integration_runtime.py tests/test_i3_concurrency_postgres.py \
  tests/test_discovery_diagnostics_concurrency_postgres.py tests/test_administration.py \
  -q --tb=short
```

The harness migrates fresh disposable PostgreSQL databases as non-superuser
`atlas_test`, runs the single-head check and isolates committed authority tests
in separate schemas. PostgreSQL/Redis have no published host ports or production
mounts. Package signatures use the image's pinned Linux verifier and unchanged
frozen roots. Original release downloads are synthetic transport responses with
retained genuine release bytes; no live GitHub/source call is required. Runtime
health/transport are deterministic in lifecycle fixtures, but package verification
and execution admission run the actual runtime implementation. Existing worker
execution tests use synthetic worker/Ansible output. API HTTP tests inject test
principals; real scoped/global permission checks and real database operations
still execute. This is not live operational source acceptance.

Merged Compose validation ran `python3 /private/tmp/atlas-4b12a-validate-compose.py`:
base, base+local, and base+local+restoration configurations **all passed**. The
script invokes `docker compose --env-file /dev/null ... config --format json`
with generated disposable credentials, asserting selected stores, retained
read-only original authority mounts, read-only ordinary operator mount, root-only
operator capabilities and no database/private-key exposure to runtime. It starts
no Atlas deployment and prints no credentials. No frontend build/full image build
was run because no UI code changed and deployment acceptance is outside scope.

Final static checks: targeted API/runtime/operator/tests `python -m compileall -q`
**passed**; `git diff --check` and untracked text whitespace inspection **clean**;
relative documentation/code-line link check **113 links resolved**. The repository
status embedded below was compared with actual `git status --short` and matched.

### Material files changed in this follow-up

| Files | Purpose |
| --- | --- |
| `apps/api/app/services/integration_connections.py`, `apps/api/app/routes/integration_connections.py` | Separate verified installed metadata maintenance from execution admission. |
| `apps/api/app/services/local_release_restoration.py` (new), `apps/api/app/services/connector_lifecycle.py` | Root-reviewed signed original-to-ordinary handoff and exact transactional consumption by the normal lifecycle. |
| `apps/api/app/routes/system_settings.py` | Reserve the signed pending-handoff setting namespace from application writes. |
| `apps/api/app/services/local_release_revocation.py` (new), `apps/api/app/services/connector_release_acceptance.py` | Atomic tombstones, durable denial intent, forensic recovery and idempotent recovery audit. |
| `apps/api/app/services/local_release_authority.py`, `apps/runtime/ansible/atlas_runtime/local_release.py` | Independently deny pending revocation in API and runtime. |
| `apps/api/scripts/accept_connector_release.py` | Restoration planning/authorization and explicit corrupt-revocation recovery commands. |
| `apps/api/tests/test_local_release_recovery.py` (new) | 32 parametrized recovery cases, including real DB commit/rollback, faults, process exit, application UID and preserved history/ciphertext. |
| `apps/api/tests/test_connector_release_acceptance.py` | Correct complete isolation-time fixtures and independent timestamp assertions. |
| `apps/api/tests/test_runtime_packaging.py` | Preserve operator/consumer separation and validate restoration override. |
| `infra/docker/docker-compose.local-release.yml`, `infra/docker/docker-compose.local-release-restoration.yml` (new) | Read-only access to the original bundled store for root review; temporary consumer store selection retaining authority mounts. |
| `docs/decisions/0016-local-release-recovery.md` (new), `docs/decisions/README.md` | Supplemental recovery decision without rewriting accepted ADR 0015. |
| `docs/deployment/local-release-acceptance.md`, `docs/product/feature-ledger.md`, this report | Correct operator procedures, truthful capability evidence and final review record. |

### Remaining limits

Live LXC/source/Ansible qualification, native service/reboot acceptance and complete
new image builds remain outside this task. The handoff requires the same bound
database/build/deployment and original stores mounted at their original protected
paths until consumption. Its production replacement must independently remain
eligible under the unchanged bundled catalogue. Probe-only restoration requires
explicit empty discovery scopes; old selections are retained in signed evidence.
The pending handoff grants no local execution authority and can be retried after
rollback, but changed active/dependent/store state requires a fresh root review.
Already admitted jobs may finish. Root compromise, dishonest inspection, complete
privileged rollback and unreliable clock/filesystem durability remain ADR 0015
assumptions. No unresolved recovery/security issue is currently known.

### Repository state

Branch: `feature/secure-local-release-acceptance`.
HEAD: `808ee0f76f77c11e17a6c403806ce0666e30074e` (unchanged).
The status includes work that predated this follow-up. No commit, push, merge,
history rewrite or Atlas deployment was performed.

```text
$ git status --short
 M apps/api/app/routes/integration_connections.py
 M apps/api/app/routes/integration_discovery.py
 M apps/api/app/routes/integrations.py
 M apps/api/app/routes/system_settings.py
 M apps/api/app/services/connector_lifecycle.py
 M apps/api/app/services/connector_store.py
 M apps/api/app/services/discovery_orchestration.py
 M apps/api/app/services/integration_connections.py
 M apps/api/app/services/integration_runtime.py
 M apps/api/tests/test_runtime_packaging.py
 M apps/runtime/ansible/atlas_runtime/jobs.py
 M apps/runtime/ansible/atlas_runtime/probe.py
 M apps/runtime/ansible/atlas_runtime/qualification.py
 M apps/runtime/ansible/atlas_runtime/server.py
 M docs/decisions/README.md
 M docs/deployment/attestation-verification.md
 M docs/deployment/integration-runtime.md
 M docs/product/feature-ledger.md
?? apps/api/app/services/connector_release_acceptance.py
?? apps/api/app/services/local_release_authority.py
?? apps/api/app/services/local_release_restoration.py
?? apps/api/app/services/local_release_revocation.py
?? apps/api/scripts/accept_connector_release.py
?? apps/api/scripts/bind_local_release_instance.py
?? apps/api/tests/fixtures/local_release/
?? apps/api/tests/test_connector_release_acceptance.py
?? apps/api/tests/test_local_release_authority_postgres.py
?? apps/api/tests/test_local_release_recovery.py
?? apps/api/tests/test_local_release_remediation.py
?? apps/runtime/ansible/atlas_runtime/local_release.py
?? docs/architecture/integrations/local-release-acceptance.md
?? docs/architecture/integrations/local-release-security-remediation.md
?? docs/decisions/0014-local-release-acceptance.md
?? docs/decisions/0015-local-release-execution-authority.md
?? docs/decisions/0016-local-release-recovery.md
?? docs/deployment/local-release-acceptance.md
?? infra/docker/docker-compose.local-release-restoration.yml
?? infra/docker/docker-compose.local-release.yml
```

**FINAL REMEDIATION COMPLETE — READY FOR TARGETED INDEPENDENT SIGN-OFF**
