# Local acceptance of signed immutable Connector releases

Read [ADR 0014](../decisions/0014-local-release-acceptance.md) and its security
remediation [ADR 0015](../decisions/0015-local-release-execution-authority.md), with
the recovery supplement [ADR 0016](../decisions/0016-local-release-recovery.md). This procedure is
for an independently isolated test deployment. It is explicit, temporary local
installation authority. It does not publish, select, qualify or automatically
update a Connector. **Proxmox 0.2.2 has not been operationally accepted on the LXC
by this implementation task. No live deployment was performed.**

## Operator boundary and preparation

The authorized operator controls root on the test host, its Docker daemon and
deployment configuration. API/worker UID 10001 and an Atlas login cannot approve
local packages. Do not share Docker access or the private operator volume with
application users. The root-only CLI does not inherit application RBAC or name an
application user. API package management still requires global runtime management;
Test Connection and discovery still require the existing scoped permissions.

Before proceeding, inspect `atlas-test-docker` using its established project,
environment and override selectors. Do not assume isolation from
`docker-compose.qualification.yml`. Check, without printing credentials:

1. The LXC is the intended dedicated test deployment, with no production services.
2. Database URL, PostgreSQL cluster/database and data volume are independent.
3. Redis endpoint, volume, queue consumers and schedules are independent.
4. Runtime endpoint, control volume, source network and worker are test-only.
5. Encryption, authentication, control and source credentials belong to the test
   instance. Do not copy production credentials into the test instance.
6. All state/store/backup volumes and host bind mounts are independent. No
   external volume is shared with production. Inspect actual mounts, not just YAML.
7. Existing generic connections are manual; disable them and settle pending,
   running and unsettled jobs. Retain their credentials, DataSources and history.

If any inspection is uncertain, stop before enrollment/activation. An honest
infrastructure inspection is the root operator's responsibility; the application
cannot independently prove remote Redis/host/credential isolation. No environment
flag substitutes for the protected binding, signed grant and database checkpoint.

Have a human review and record the complete implementation commit first. This
task leaves Git uncommitted. Deploy only the reviewed clean commit and use its
actual `ATLAS_BUILD_ID`; do not label modified files with an old reviewed commit.
Back up the test database/state using the established Atlas backup procedure.
Do not change production selectors, credentials, releases or catalogue files.

## Docker/LXC checkpoints (human execution only)

Use the existing test project's exact environment/project/override selectors.
The following `dcl` array is an example; add any established test selectors before
the final local-release override. Do **not** add the qualification override. No
second nested stack is required.

```bash
git status --short
git rev-parse HEAD
export ATLAS_BUILD_ID="$(git rev-parse HEAD)"
export ATLAS_LOCAL_RELEASE_DEPLOYMENT_FILE=/root/atlas-local-deployment.json
dcl=(docker compose --env-file .env -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.local-release.yml)
"${dcl[@]}" build api worker runtime release-operator
```

1. Start/retain the test instance's existing PostgreSQL, Redis and runtime-control
   infrastructure using its normal procedure. Keep API/worker/runtime stopped
   during first enrollment. The normal `runtime-init` and `connector-bootstrap`
   services keep using the **original** store; they must never chown the new local
   acceptance store to UID 10001. The acceptance volume is root-owned, application
   mounts are read-only, and the private key is mounted only into `release-operator`.

2. Independently identify this deployment on the host. Create a root-owned 0444
   `/root/atlas-local-deployment.json`, under protected root-owned ancestors,
   with `{"schema":1,"deployment_id":"<fresh UUID>","name":"atlas-test-docker"}`.
   Generate the UUID locally once; retain the file across restarts. It must identify
   the selected inspected deployment. All consumers and the operator mount this
   same public file read-only. Native installs use
   `/etc/atlas-local-release-deployment/identity.json`.

   The isolated database administrator must grant the Atlas database role
   `EXECUTE ON FUNCTION pg_control_system()` in the selected database, so it can
   read the non-secret PostgreSQL cluster identifier without becoming a superuser.
   Keep that role's other privileges unchanged. Missing access fails closed.

   Create the empty root-owned store/public/private directories (Compose creates
   the dedicated volume roots). Observe the actual selected resources:

   ```bash
   "${dcl[@]}" run --rm --no-deps --entrypoint python release-operator -m scripts.bind_local_release_instance --inspect-resources
   ```

   Save the returned report at `/root/atlas-local-isolation.json` as root, mode
   0444. It starts with every human check **false**. Compare its database name/OID/
   cluster ID, deployment UUID/name, and store/public/private directory path,
   device and inode against the independently inspected host resources and actual
   container mounts. Complete the mandatory database/Redis/runtime/worker/
   credentials/storage/production-exclusion inspection above. Only then set each
   check true and record the actual inspection time in `checked_at`. No credential
   values belong in this report. Enrollment freshly obtains the resource
   identities again and compares them before writing anything. Booleans alone,
   reports older than one hour, future timestamps, omitted/false checks or
   substituted resources reject. These checks bind the inspection; they do not
   prove physical isolation or the honesty of human attestations.

3. Enroll once with the same test database configuration. The new store must be
   empty; ordinary production-store paths and existing enrollment reject.

   ```bash
   "${dcl[@]}" run --rm --no-deps -v /root/atlas-local-isolation.json:/tmp/isolation.json:ro --entrypoint python release-operator -m scripts.bind_local_release_instance --isolation-report /tmp/isolation.json
   "${dcl[@]}" up -d api worker runtime
   "${dcl[@]}" ps
   ```

   Inspect Runtime health and actual mounts/UIDs. Require the existing compatible
   approved baseline and the same public build identity in all three processes.
   Enrollment creates a separate root-owned Ed25519 **operator** key, public
   binding/store marker and PostgreSQL checkpoint. It never changes Sigstore roots.
   Do not copy these identities between deployments or expose the private volume
   to API/worker/runtime. Partial provisioning/DB commit failure fails closed;
   retain the files and inspect them rather than resetting/retrying blindly.

4. Set the independently reviewed public release identity. Initial candidate:

   ```bash
   candidate=(--connector-id proxmox --version 0.2.2 --release-id 429608780 --package-asset-id 693849044 --source-commit e58788a667c0c0006477ac149e8ad28aedda0745 --sha256 2d66fc69b9cf9c70d7df117fe41bff3e3e056299f1908cde965e9e3f75e59abf)
   ```

   `verify` can also run without root in a development environment with the
   pinned verifier prepared. It needs GitHub access and a new evidence directory:

   ```bash
   python -m scripts.accept_connector_release verify "${candidate[@]}" --evidence-directory /absolute/new/evidence-directory
   ```

   This retains original package/manifest/attestation/release/ref/result bytes and
   grants no installation authority. Retain its output. Fixed public-origin
   retrieval checks repository/owner, immutable release, asset IDs/lengths/digests
   and tag commit; exact original package provenance is independently verified.
   Arbitrary repositories, workflows, package paths and roots are not selectable.

5. Stage explicitly. This fetches and authenticates the official release again;
   caller-edited verify results cannot grant authority.

   ```bash
   "${dcl[@]}" run --rm --no-deps release-operator stage "${candidate[@]}"
   ```

   Retain the returned artifact authorization UUID. Staging writes immutable
   files through PackageStore plus signed artifact-staging evidence. That evidence
   has no execution lifetime and conveys no Test Connection/discovery authority.
   Integrity inspection stays possible before activation and after a lease expires.
   Renewal never rewrites the tuple or its receipt.

6. Preview and review mappings, dependent Integration IDs/customer/site context,
   runtime baseline and previous active identity:

   ```bash
   "${dcl[@]}" run --rm --no-deps -v /root/atlas-local-isolation.json:/tmp/isolation.json:ro release-operator plan "${candidate[@]}" --isolation-report /tmp/isolation.json
   ```

   If mappings are unresolved, review/create the managed target records in Atlas
   Administration, then provide explicit choices in a non-secret local JSON file:
   `[{"kind":"asset","source_key":"proxmox.node","target_key":"hypervisor_node"}]`.
   Include all required choices from the plan; the example alone is incomplete.
   Normal catalogue APIs do not acquire unlisted-package eligibility. The CLI
   accepts only declared source keys and active managed targets, with existing
   relationship direction/endpoint checks. No implicit ignore or schema conversion
   is provided. Update dependent configuration/credentials through normal scoped
   UI permissions if necessary; do not clear them to install a package.

   Mount the reviewed file at `/tmp/mappings.json` in subsequent operator runs
   and add `--mappings /tmp/mappings.json`. If needed, repeated `--scope inventory`
   explicitly changes the scopes of **every listed live dependent integration**.
   Preview changes roll back. Require `ready: true`, inspect the complete plan,
   and retain its exact `approval_digest`, approved operation, lease duration and
   approval expiry. Each plan issues a unique signed approval, valid for ten
   minutes, consumed by one activation attempt that reaches the commit boundary.
   A failed commit still consumes it; inspect the database and review a fresh plan.
   Use `--lease-seconds` on `plan` to select up to 172800 seconds (48 hours, the default).

7. Recheck isolation and use the **same** mapping/scope/report inputs. If the
   report expires, repeat the inspection and plan with the updated report first.
   Activate with the digest copied from the reviewed plan:

   ```bash
   "${dcl[@]}" run --rm --no-deps -v /root/atlas-local-isolation.json:/tmp/isolation.json:ro release-operator activate "${candidate[@]}" --isolation-report /tmp/isolation.json --approve-plan "$REVIEWED_PLAN_DIGEST"
   ```

   Include the same optional mapping mount/arguments as the reviewed plan.
   Missing approval, changed dependency/credential/taxonomy/mapping state, changed
   prior active identity, instance, runtime, expired/consumed approval, revoked artifact or failed
   independent runtime verification rejects activation. Locks and the existing
   transaction preserve the previous active version on failure. Runtime identity
   compares stable compatibility fields; timestamps and available capacity are
   liveness. Health must independently remain healthy. Obsolete execution authority
   is durably fenced before the transaction changes the active row. The active
   generation and audit must commit and be visible to an independent PostgreSQL
   session before the root operator publishes its signed execution lease.
   Activation itself performs no source discovery.

8. In the existing scoped UI, perform Test Connection and manual discovery using
   test-only source credentials. Follow the Connector's original 0.2.2 acceptance
   checklist. Record source version, TLS policy, exact runtime/package identity,
   coverage, observations/assertions/reconciliation, failure behavior and retained
   evidence. Do not mark operational acceptance until those live LXC checks pass.
   Restart API/worker/runtime and verify identity/execution again; optionally block
   GitHub egress to demonstrate offline reuse **within the execution lease**.
   Only explicit manual Test Connection and Run Now are allowed. New connections
   stay manual with no onboarding run. Schedule changes, initial discovery, worker
   automatic intents and direct runtime automatic requests are denied for local
   acceptance; catalogue-installed connectors keep their existing behavior.

9. Disable the test connections and settle jobs, then revoke explicitly:

   ```bash
   "${dcl[@]}" run --rm --no-deps release-operator revoke --authorization-id "$AUTHORIZATION_ID"
   ```

   Confirm subsequent Test Connection/Run Now are unavailable. The signed grant,
   original provenance, tombstone, package, database audit and discovery history
   remain. Revocation does not terminate previously admitted jobs. The CLI returns
   `audit: recorded` when PostgreSQL is available. If it returns
   `audit: reconciliation_required`, denial is already effective and durable;
   restore the bound database and run `reconcile-revocation --authorization-id`
   with the same UUID. Repeating reconciliation creates no duplicate audit event.

## Expiry, renewal and execution recovery

Authorized scoped administrators can inspect the installed form, repair connection
configuration and replace credentials after lease expiry. These operations still
verify package integrity, the original artifact receipt and database/instance
binding, and enforce the existing RBAC, source-identity and schema rules. Repair
does not create or extend authority. Test Connection and discovery remain denied
until the normal reviewed renewal below succeeds.

An execution lease starts at approved activation, lasts at most 48 hours, and is
checked for each new operation. Expiry or revocation denies new operations; it
does not interrupt previously admitted work, remove the active database record,
delete evidence, or require restaging. Installed-package responses expose
`local_execution` separately: `authorized`, `expired`, `revoked`,
`activation_required`, `recovery_required` or `denied`, with the effective lease
identity/expiry when available. Runtime admission independently checks the exact
package, instance/database/store binding, generation, lease and manual trigger.

For renewal, settle active runs and repeat the infrastructure inspection. Capture
a fresh resource report with `--inspect-resources`, inspect it and complete the
human checks. Review `plan --operation renew --lease-seconds 172800` with the same
complete candidate identity and fresh isolation report. Within ten minutes run
`renew` with that candidate, report and `--approve-plan` digest. No mapping/scope
inputs are allowed. The new bounded lease retains the generation, changes the
lease ID and invalidates old requests; the immutable artifact receipt is unchanged.
Renewal requires PostgreSQL and healthy compatible runtime verification, but no
GitHub contact. Offline execution across restarts remains possible within the lease.
Revoked artifacts cannot be renewed or recovered.

If activation/renewal commits but execution publication fails, the CLI returns
`local_release_committed_execution_denied_recovery_required`. Inspect the active
database row, committed audit, consumed approval and retained files. Execution
stays denied. For an unexpired lease, obtain/review `plan --operation recover`
and run `recover` with the complete candidate, fresh report and new approval digest.
Recovery audits the request and rechecks the committed original approval in an
independent database session; it restores only that exact lease and cannot extend
expiry. Use reviewed renewal for an expired lease. Never copy a historical lease
to the current path, bypass approval, or delete immutable evidence.

A crash before commit leaves the previous database identity; a consumed approval
is never replayed. A crash after fencing can leave its previous execution denied
even when the database rolls back. Inspect the retained approved generation and
use the same reviewed recovery procedure, or renew if it has expired. Crashes
after commit and before publication also leave execution denied. Ordinary package
replacement/uninstall must first obtain root revocation, so no old offline lease
survives an application lifecycle change.

## Recovery and native deployment

Retain all three local-release volumes and test database history for review.
Do not use `down -v`, delete Integrations or reset the database as rollback.
Removing the override alone does not restore management: the retained local
activation still requires authenticated original revocation and a signed handoff.
Use the following explicit procedure; do not delete the active row or its evidence.

### Return to ordinary bundled management

1. Settle all runs and revoke the local authorization as above. Keep the same
   bound test database, Atlas build, deployment identity and all original volumes.
   The ordinary store must already contain its original production-bootstrap
   package, staged by the existing trusted bootstrap procedure. The operator mounts
   this separate store read-only; it cannot install a missing replacement there.
2. With the original local-release Compose configuration still selected, inspect
   the bundled catalogue version/digest and review a restoration plan. The
   original bundled Proxmox probe is version `0.1.0`; use its catalogue digest,
   never the local candidate digest. For a probe-only replacement, explicitly
   select `--clear-scopes`. Original discovery-scope selections are retained in
   signed evidence; configuration values and credentials are retained unchanged.

   ```bash
   "${dcl[@]}" run --rm --no-deps release-operator plan-restoration --connector-id proxmox --version 0.1.0 --sha256 "$BUNDLED_DIGEST" --replacement-store /var/lib/atlas-connectors --clear-scopes
   "${dcl[@]}" run --rm --no-deps release-operator authorize-restoration --connector-id proxmox --version 0.1.0 --sha256 "$BUNDLED_DIGEST" --replacement-store /var/lib/atlas-connectors --clear-scopes --approve-plan "$REVIEWED_RESTORATION_DIGEST"
   ```

   Review the complete plan, including dependent scope changes, target store and
   exact revoked active identity. Use the returned `plan_digest` for approval.
   Other replacement packages may use explicit `--scope` arguments or retain
   compatible scopes. Incompatible configuration/mappings or active runs reject
   the handoff; no credentials or configuration are rewritten to make them pass.
3. For the controlled deployment configuration change, merge
   `infra/docker/docker-compose.local-release-restoration.yml` **after** the base
   and local-release files, in the same existing isolated project. This points
   API/worker/runtime to the ordinary store and retains the original local store,
   public binding and deployment identity read-only. The operator retains its
   original local-store context. Keep the exact build ID. Verify the merged
   configuration before applying it through the existing deployment procedure.
   During this transition the old local active row is unavailable for execution.
4. A globally authorized package administrator selects that exact bundled version
   in the existing install/activate workflow. Normal catalogue verification,
   runtime inspection, configuration, scope, mapping and active-run guards still
   apply. Activation consumes the persisted handoff and commits its completion
   audit atomically. A failed PostgreSQL transaction can retry the same handoff;
   a changed store, active identity or dependent state needs a fresh reviewed plan.
5. Confirm ordinary activation and `connector.local_restoration_completed` audit
   from a fresh session. Only then remove both temporary overrides through normal
   deployment management. Retain the detached original volumes and evidence for
   review. Local revocation remains final across restarts and store switches.

### Interrupted or corrupt revocation evidence

Revocation publishes a durable denial intent before signed evidence. Interrupted
writes leave either no final tombstone or a complete one. Retry `revoke`; it
finishes publication and audit reconciliation without restoring execution.
Concurrent operations may report `package_operation_in_progress`; retry after
the other root operation exits. Protected orphan temporary files are evidence,
not execution authority, and need not be removed to retry.

For a historical malformed final tombstone, ordinary revocation reports
`local_release_corrupt_revocation_recovery_required`. Root must inspect and retain
its exact SHA-256 (without printing raw evidence), then explicitly recover:

```bash
"${dcl[@]}" run --rm --no-deps release-operator recover-revocation --authorization-id "$AUTHORIZATION_ID" --corrupt-sha256 "$REVIEWED_CORRUPT_SHA256"
```

The operator checks the original binding/grant, preserves exact corrupt bytes as
an immutable `.corrupt-evidence` file and atomically publishes signed denial
referring to that evidence. A changed digest rejects recovery. The durable denial
intent remains. Recovery cannot renew or restore execution. If PostgreSQL is
unavailable, repeat `reconcile-revocation` after restoring the bound database;
revocation and evidence-recovery audit events are idempotent.

Native root may use the same scripts with protected fixed paths
`/etc/atlas-local-release/instance.json` and
`/etc/atlas-local-release-private/operator.key`, and a separate root-owned store.
Only the operator can write these files; API/worker/runtime retain read-only
access and the same public build identity. Never give the runtime the API/DB
environment or operator private key. Native service ownership/reboot/upgrade
acceptance remains outstanding. A changed build, copied deployment, expired lease
or lost identity fails closed. Key/build rotation and cross-instance
restore require separate reviewed procedures; do not delete evidence to bypass
one-time enrollment or immutable receipts.
