# I3 — Discovery orchestration and AIP ingestion

12 October 2026. **Acceptance: PASS WITH DOCUMENTED FOLLOW-UPS.**

Generic I3 execution/ingestion is implemented and locally validated. Actual live
Docker/LXC operator acceptance was completed after the original report and is
recorded below. Native Debian/systemd LIVE acceptance has not been performed and
remains outstanding. No production discovery Connector or I4 qualification is claimed.

The Git metadata, implementation file inventory and repository-state snapshot
below describe the original implementation report. The subsequent operator
acceptance is recorded separately from the original local validation.

Starting branch: `feature/integrations-i3-orchestration-aip-ingestion`.
Starting HEAD: `78d1c0e4592eaee0310b2bfad63b6e5c4ed53c47`.
Starting Atlas working tree: clean. Starting single migration head: `20261012_0028`.

## Baseline audit and initial implementation plan

| Responsibility | Classification | Existing owner / planned extension |
| --- | --- | --- |
| Integration, DataSource and Customer/Site ownership | REUSE | Existing one-source-per-Integration and composite scoped FKs; persisted ownership is ingestion authority. |
| Scoped view/manage/run permissions | REUSE | `Principal`, `scope_condition`, existing `integrations.run`; independent archive/delete permissions. |
| DiscoveryRun history/status/coverage | EXTEND | Existing pending/running/completed/failed/cancelled, timestamps, summary, full intent and complete/partial/failed/unknown fields. Add exact execution identity and dispatch state. |
| Evidence and run observation membership | REUSE | `EvidenceRecord`, `record_observed_entity`, existing run/type/external-ID uniqueness. |
| Source-current assertions and reconciliation | EXTEND | Existing simulated-discovery, entity-resolution, assertion, reconciliation and Changes owners; adapt canonical technical observations without legacy direct synchronization. |
| Complete snapshot absence and re-observation | REUSE | `reconcile_complete_snapshot`; completed + full + complete and matching source/scope/coverage only. Asset-only absence remains the boundary. |
| Canonical AIP and Manifest validation | REUSE | Hash-pinned Apache SDK 1.1.0; AIP 1.0 unchanged. Canonical discovery capability is `read_only`, not boolean true. |
| Taxonomy mappings | EXTEND | Existing global versioned exact mappings; run must retain mapping identity and reject unresolved classes. |
| Durable receipt/finalisation ledger | NEW | Canonical `(run_id, batch.sequence)` plus canonical JSON body hash; completion seals `last_sequence`. |
| Ingestion authentication | NEW | Separate run/Integration/audience/JTI/expiry surface with deployment-local signing credential and persisted eligibility. |
| Worker and Redis | EXTEND | Worker currently only sleeps and observes maintenance; Redis is deployed, but no queue consumer, retries or scheduler exists. PostgreSQL must retain durable dispatch intent. |
| Scheduling and overlap prevention | NEW | Fixed PostgreSQL schedule presets, transactional cross-process serialization and bounded missed-run policy. |
| Runtime transport / exact verified store | EXTEND | Existing private authenticated client/server, baseline checks and independent tuple/content verification; add bounded start/status/cancel jobs. |
| SecretProvider | EXTEND | Existing AES-GCM provider and required-field in-memory lease; retain application-key/rewrap lifecycle and terminal cleanup. |
| Backup maintenance and recovery | EXTEND | Existing shared normal-operation guard and durable maintenance marker; worker mutations must participate. |
| Integration detail and Discovery Runs UI | EXTEND | Existing pages, shared UI primitives and scoped permissions; capability-gated actions and additive safe run metadata. |
| Docker / native packaging | EXTEND | Existing one-shot provisioners, private runtime/source topology and native loopback service; intentional minimum worker/credential wiring. |
| Deterministic discovery Connector | NEW | Test harness only, isolated verified bundles; never production catalogue/bootstrap/install sources. |

## Baseline evidence

- `apps/api/.venv/bin/alembic heads`: one head, `20261012_0028`.
- From `apps/api`, `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest ../../docs/architecture/integrations/contracts/tests -q --tb=short`: **77 passed**.
- SDK reference repository: `main`, HEAD `8b0518c462289cca4758c3b9bf362f1130928a1c`, clean.
- Connector reference repository: `main`, HEAD `995366985f429d232f3d3acd851dbb18b1bb3c35`; pre-existing untracked `.DS_Store` retained.
- Official Proxmox 0.1.0 still advertises discovery/scheduling/complete-snapshot false. No production discovery Connector is shipped.

The baseline audit above predates implementation. Final implementation and
validation evidence follows; historical I1/I2 live evidence is not I3 live acceptance.


## Final result and architecture

- Starting/final branch: `feature/integrations-i3-orchestration-aip-ingestion`.
- Starting/final HEAD: `78d1c0e4592eaee0310b2bfad63b6e5c4ed53c47`.
- Final single Alembic head: `20261012_0029`; additive migration from I2 `0028`.
- All work remains uncommitted in Atlas. No commit, push, merge, tag or publication.
- Canonical SDK repository unchanged at `8b0518c462289cca4758c3b9bf362f1130928a1c`.
- Canonical Connector repository unchanged at `995366985f429d232f3d3acd851dbb18b1bb3c35`;
  its pre-existing untracked `.DS_Store` was retained.
- Proxmox 0.1.0 still advertises `discover=false`, scheduling/complete-snapshot
  false and unqualified source versions. Proxmox 9.2.11 was not qualified.
- No production discovery Connector exists. Test-only bundles are generated under
  `apps/api/tests`, absent from production catalogue/bootstrap/release packages.
- No real secret/token value was printed or committed. Test credentials are
  generated ephemerally; protected disposable database environment files are
  outside the repository. No live credentials or literal ingestion tokens were
  added to fixtures. PostgreSQL stores generations/hashes, never raw run tokens.
- Accepted absence/reconciliation policy remains unchanged. New canonical adapters
  extend existing review services and technical source identity. Connector source
  matches require deliberate identity linking rather than automatic name merging.

See [implementation detail](i3-implementation.md) and [operator workflow](../../deployment/discovery-runs.md).
No accepted ADR was rewritten and neither canonical contract repository needed a change.

## Database, contracts and lifecycle

DiscoveryRun retains existing statuses, coverage/completeness, history, archive
and timestamp fields. New fields record immutable execution provenance, bounded
attempt/dispatch state, deadline, private ingestion generation, opaque runtime job,
cancellation intent, final seal hash, source version and batch/observation/warning
counters. A trigger freezes provenance/scope/coverage and checks the persisted
Integration/DataSource context. A scoped Integration FK and partial unique index
prevent overlapping executable owners, including terminal cleanup. Historical
legacy runs retain null provenance and their existing behavior.

The additive migration also adds schedule presets/due/last-run/success/error to
Integration, immutable `(run_id, sequence)` receipts, fact metadata and specialized
scoped Network/Interface source-link targets. Asset links retain their existing
Asset FK and conditional target invariants. PostgreSQL upgrade from I2, fresh
migration, preserved legacy records, single head, receipt immutability, provenance
immutability and separate-process overlap are tested. Downgrade was not executed;
repository policy does not require it. The downgrade refuses generic/technical
history rather than silently destroying it.

Existing APIs/routes remain compatible; response metadata is additive. New scoped
administration routes are Run Now, initial discovery, fixed schedule update and
run cancellation. Separate `/api/integration-ingestion/{run_id}/batches`,
`completion` and `failure` authenticate only run credentials. They do not accept
user sessions as ingestion authority or expose private provenance/configuration.
The technical identity link endpoint extends existing reconciliation decisions.

Receipts use canonical SDK JSON hashes, not alternate batch IDs. Identical batch
retry acknowledges one evidence transaction; conflicting replay fails closed.
Out-of-order receipts are allowed but completion seals contiguous 1..last_sequence.
Successful/failure seals are idempotent. Terminal acknowledgment permits only the
identical seal until token expiry; arbitrary new/replayed batches are unauthorized
once final. Cancellation revokes the generation immediately.

Limits: 1 MiB/body, 256 batches, 5,000 observations, 20,000 facts and 32 MiB canonical
JSON/run, plus canonical SDK field limits. These are conservative application
bounds, not empirical large-inventory performance qualification. Unknown fields,
classes/facts, invalid mappings/endpoint references, changed tuple/scope/source,
secret/JWT/private-key values and payload-selected tenancy fail closed.

EvidenceRecord and RunObservedEntity are written with each receipt. Valid evidence
from failed/cancelled runs remains immutable. Successful finalization reuses:

- `simulated_discovery.ingest_observations` and its technical observation extension;
- `entity_resolution`, `ensure_asset_link` and scoped technical link extension;
- `knowledge_assertions.record_assertion`/acceptance/history;
- `reconciliation.create_item`, `accept_item`, explicit asset/technical linking;
- `knowledge_changes.record_assertion_change` and existing audit conventions;
- `discovery_observations.record_observed_entity`/`reconcile_complete_snapshot`.

No legacy direct-overwrite synchronization path is used or removed. Namespaced
facts preserve type/class/cardinality; multi-values remain one atomic list claim,
not independently accepted members. Material accepted configuration conflicts are
reviewed, and linking a manual technical entity preserves its configuration.
Only successful full/complete finalization invokes existing Asset-only absence;
partial/failed/cancelled/timeout/interrupted/missing-completion never evaluate
absence. Re-observation/source identity/history and legacy simulations remain green.

## Execution, signing, scheduling and recovery

API and scheduler reuse Connector advisory/Integration row locks. PostgreSQL owns
intent/history; Redis is a bounded disposable hint queue, with durable pending and
recovery scans even after loss/restart. Three availability/capacity attempts use
bounded backoff; deterministic configuration/authentication/compatibility failures
pause schedules. Missed ticks coalesce. Presets are Manual, Hourly, Every 6 hours,
Every 12 hours, Daily and Weekly; no cron or new broker/framework was introduced.
Authorized creation queues onboarding and hourly default when supported; manage
permission cannot replace scoped run authorization.

Worker dispatch revalidates the exact frozen tuple/configuration/credential
revision, leases only declared visible fields, commits token generation before
runtime callback and uses run ID as idempotency identity. A 15-second start grace
avoids false interruption from another worker. Runtime disappearance and success
without completion fail safely. Pending intent expires at 15 minutes. Runtime
execution has a ten-minute deadline and safe bounded polling/cancellation.

API atomically provisions an independent private installation signing file,
`discovery-ingestion.secret`, mode 0600. API/worker need it; runtime/web do not.
HS256 credentials have fixed issuer/audience, run/Integration, issued-at/expiry and
UUID generation, normally 11 minutes and at most 15. They cannot authenticate
normal APIs or private runtime control. Ownership is re-derived from persisted
Atlas state. Configuration/credential changes, disable/retirement and cancellation
revoke active intent. Restore blocks unsettled destination execution, revokes all
imported generations and fails active imported runs; signing state stays local and
outside database backups. Existing credential rewrap remains green.

Runtime adds private verified start/status/cancel, four bounded discovery slots,
opaque jobs and safe timestamps/categories only. It independently verifies exact
bundle/content identity and executes fixed `discover.yml`; no arbitrary path,
command, Git/Galaxy or callback URL is accepted. Private pipes and 0700/0600
workspaces carry ephemeral secrets; source execution receives no ingestion,
control, session or database credential. Parent transport emits fixed Atlas HTTP
callbacks through another bounded child with redirects/proxies disabled.

The stronger cancellation acceptance exposed Ansible's independent descendant
sessions. The final implementation freezes/collects the bounded process tree with
pinned psutil before root/group kill, and reaps/cleans on every terminal path.
The same helper strengthens existing I2 probe cleanup. Docker init reaps orphaned
children; startup cleans abandoned owned workspaces. No physical memory zeroization
is claimed. Runtime baseline is `atlas-ansible-i3-v1` 1.1.0 / runtime 0.3.0, with
21 exact Python dependency pins, canonical SDK artifact, reference hashes/SBOM and
verbatim upstream licence notices. API production code does not import Ansible.

## Deployment, UI and security

Docker adds worker private runtime connectivity, read-only state/control/store
mounts and the existing data key for its SecretProvider. API provisions signing
state before health; worker waits for API health. Only runtime joins source
network; gateway remains sole public ingress. Runtime stays non-root, read-only,
no-capabilities/no-new-privileges with no DB/auth authority, Docker socket or host
root mount. One-shot bootstrap/init and read-only executable store are retained.
Runtime memory/tasks/temporary storage and shutdown grace are bounded.

Native worker uses a filtered root-owned environment and control reader group.
The existing API/worker Atlas UID remains for shared maintenance locks; web masks
installation state. This is intentional service exposure reduction, not complete
host-user isolation from the pre-existing shared Atlas account. Runtime retains
its dedicated account, separate venv and fixed loopback control/callback. Upgrades
preserve local credentials/state and regenerate the filtered environment safely.

Existing Integration detail and Discovery list/detail expose capability-gated
Run Now, preset, last/next/current state, cancel, history, safe counters/warnings,
source/version/trigger, duration and subdued job/provenance detail. Polling keeps
unsaved configuration/credential edits. Probe-only Proxmox retains Test Connection
and has no fake Run Now/schedule. Existing primitives/status/table/permissions
and responsive/theme/accent/focus contracts are reused. Normal technical review
uses existing reconciliation; an additional association picker is future polish,
while explicit technical linking is available through the documented scoped API.

All new administration and review operations enforce existing permissions and
Customer/Site boundaries in the backend. Run tokens use a separate security
surface, exact persisted binding/generation and no-store responses. Payload scope,
counts, reference metadata and private source material do not authorize access.
Package/mapping lifecycle guards protect active exact executable ownership.

## Original local validation actually executed

Host: macOS/Darwin; API/runtime acceptance interpreter Python 3.14, PostgreSQL
17.11, isolated Redis 7.4.6 and test nginx 1.28.3. CI installs Python 3.12 and the
separate pinned runtime, supplies all 15 isolated database URLs, and rejects skips.
Commands below ran from the stated directories using protected disposable env;
no credential values are reproduced.

| Validation | Command / result |
| --- | --- |
| Full backend / database / legacy plugins | From `apps/api`, `.venv/bin/python -m pytest tests ../../plugins/sdk/tests ../../plugins/proxmox/tests -q -rs --tb=short --junitxml=/private/tmp/atlas-i3-validation/backend-final.xml`: **1,152 passed**, **0 skipped**, 195.19 s. Includes I1/I2, authorization, lifecycle, migrations, restore/rewrap, worker/Redis, runtime and deployment/documentation suites. |
| Final affected paths and docs | `.venv/bin/python -m pytest tests/test_i3_discovery.py tests/test_i3_live_runtime.py tests/test_i3_runtime.py tests/test_i2_runtime.py tests/test_repository_docs.py tests/test_markdown_docs.py -q --tb=short`: **89 passed**, 22.02 s. Executed after final request/known-secret/accepted-evidence/shared-probe cleanup changes. |
| Canonical contracts | `.venv/bin/python -m pytest ../../docs/architecture/integrations/contracts/tests -q --tb=short`: **77 passed**. Canonical consumption tests also passed in full matrix. |
| Shared release critical | `PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=.:../../plugins/sdk:../../plugins/proxmox bash ../../infra/ci/release-critical.sh`: **469 passed**, 28.28 s. Final probe cleanup also passed in the affected-path run. |
| Frontend | From `apps/web`, `npm test`: **291 passed**, **0 skipped**; `npm run build`: successful production build. Latest additional no-secret configuration assertion: `node --test tests/discovery.test.mjs`: **2 passed**. |
| I3 production browser | `node scripts/check-i3-discovery-browser.mjs` using installed Playwright/Chrome and production build on loopback: **24 combinations passed**, final build. 1440/1024/800/390 px, light/dark, default/blue/purple accents, real links, pending/running/completed/failure, preset/cancel/history/detail, focus, scoped hiding and preservation of unsaved credentials/config. API state is intercepted deterministically, not a production source. |
| I2 production browser | `node scripts/check-i2-integrations-browser.mjs`: **12 complete workflows passed**; configured probe-only navigation, TLS modes, saved write-only replacement/clear, probe outcomes, responsive/themes/accents and scoped permission hiding. |
| Clean exact runtime and fixture closure | Fresh venv, hash-pinned SDK and `pip install --no-deps -r apps/runtime/ansible/requirements.lock`; **pip check passed**, baseline **healthy**. All I3 lifecycle/runtime tests with the final AGPL test-only Manifest/SPDX metadata: **58 passed**, 19.97 s; fresh-runtime real Ansible scenarios separately **6 passed**, 15.61 s. API `pip check` also passed. |
| Real runtime acceptance | Six deterministic scenarios pass via actual Ansible children, private runtime HTTP and fixed callback HTTP into actual ingestion routes/PostgreSQL. Running-source cancellation additionally proves the descendant PID disappears and workspaces are removed. Runtime installed baseline reports **healthy**. |
| Migration head | From `apps/api`, `.venv/bin/python -m alembic heads`: sole **20261012_0029**. Fresh and I2 -> I3 executed on real PostgreSQL. |
| Release artifacts | `apps/api/.venv/bin/python infra/release/release.py build --dry-run --worktree --output /private/tmp/atlas-i3-validation/packages` and `verify --output ...`: both methods built/verified; independent `shasum -a 256 -c SHA256SUMS`: all **OK**. These are explicitly non-publishable working-tree artifacts. |
| Metadata / workflow / compilation | `release.py metadata`, actionlint **1.7.7** for both workflows, and `python -m compileall -q` over API/app/scripts/migrations/tests, worker, runtime, install/release/CI and plugins: successful. |
| Whitespace / repository docs | `git diff --check`: clean; current/untracked Markdown/link/whitespace suites pass (**18 passed** after the detailed report was written). |

Initial intermediate failures were corrected and retained as regressions:
updated schema/operation/CI-count expectations, corrected test fixture fields,
native test configuration isolation and real Ansible descendant termination.
The first sandbox-only runtime attempt could not bind loopback; acceptance then
ran with authorized loopback access. A release-critical attempt lacked `python`
on PATH; the explicit venv invocation above passed. A root-directory Alembic
invocation had the wrong script location; the correct API-directory command passed.
The reused I2 temporary runtime venv contained an unrelated AnyIO extra with a
typing-extensions mismatch. It was replaced for final acceptance by a clean
`/private/tmp/atlas-i3-runtime-venv`; the exact production lock passed pip check and
all real runtime scenarios passed there. No production dependency pin was weakened.
No unavailable checks are presented as successful. Existing dependency/deprecation
warnings remain; final JUnit contains no failures/errors/skips.

## Actual live Docker/LXC operator acceptance (post-report)

The operator performed the following acceptance on the real existing Atlas Docker
test LXC using the I3 feature branch, after the original report. These are actual
live deployment observations supplied by the operator, separate from the local
deterministic tests above and the historical I1/I2 acceptance.

| Acceptance check | Actual live result |
| --- | --- |
| Clean branch checkout | The I3 feature branch, `feature/integrations-i3-orchestration-aip-ingestion`, was checked out cleanly on the existing Docker test LXC. |
| Build, deployment and service health | `docker compose up -d --build` successfully rebuilt and deployed `api`, `web`, `worker`, `runtime`, `runtime-init` and `connector-bootstrap`. PostgreSQL and Redis were healthy; API and web were healthy; runtime and worker started successfully. `runtime-init` and `connector-bootstrap` exited **0**, as expected. |
| Live PostgreSQL migration | Both `current` and `heads` reported **`20261012_0029 (head)`**. The API startup log showed the successful upgrade **`20261012_0028 -> 20261012_0029`**. |
| Existing I2 Proxmox Integration regression | The saved Integration remained present and its encrypted credentials remained usable. Test Connection succeeded without re-entering credentials. Detected Proxmox **9.2.11** remained explicitly **unqualified/untested**, and Connector **0.1.0** remained **probe-only**. The UI correctly showed inventory discovery unavailable and exposed no fake Run Now or schedule controls. |
| Inspected deployment logs and responses | Worker logged `Atlas worker is ready`; API startup completed normally. Health endpoints and the saved Proxmox Test Connection returned **200**. No runtime error was observed in the inspected runtime/worker/API logs. |
| Ingestion signing state and restart preservation | API and worker both saw `/var/lib/atlas/discovery-ingestion.secret`; their SHA-256 hashes matched. After restarting `api`, `worker` and `runtime`, the hash remained unchanged and the saved Proxmox Test Connection still succeeded. In the API container, file mode/ownership was `600 atlas:atlas /var/lib/atlas/discovery-ingestion.secret`. The actual hash value is intentionally omitted. |
| Runtime Docker isolation | No published host ports: `Ports={}`. `/run/atlas-runtime-control` and `/var/lib/atlas-connectors` were mounted read-only. Runtime joined `atlas_runtime_private` and `atlas_runtime_source`; the source network contained only `atlas-runtime-1`. |
| Worker Docker isolation | Worker joined `atlas_default` and `atlas_runtime_private`, and was **not** attached to `atlas_runtime_source`. Runtime-control state, Atlas state/signing state and Connector store mounts were all read-only. No Docker socket or host-root mount was present. |
| Runtime hardening | Live inspection reported `User=atlas-runtime`, `ReadonlyRootfs=true`, `CapDrop=["ALL"]`, `SecurityOpt=["no-new-privileges:true"]`, `PidsLimit=128` and `Memory=1073741824` (1 GiB). |

Docker/LXC live acceptance for the deployment, migration, retained I2 probes,
signing-state restart preservation and inspected isolation/hardening is complete.
This does not establish production Proxmox inventory discovery, source-version
qualification or native/systemd live acceptance. Overall acceptance remains
**PASS WITH DOCUMENTED FOLLOW-UPS**.

## Documented follow-ups and I4 hand-off

- Native Debian/systemd **LIVE acceptance remains outstanding** and has not been
  performed. Static topology/security, package build/verification and native
  install/upgrade tests passed, but do not substitute for native operator evidence.
  Validate API/worker/runtime health, I3 migrations, retained I2 encrypted probes,
  signing-state preservation, restart/recovery and native service isolation on the
  supported host. Docker/LXC live acceptance is complete as recorded above.
- Remote GitHub/Sigstore provenance qualification remains the inherited closed
  boundary. No remote executable was installed or claimed qualified.
- I4 must implement and qualify actual Proxmox inventory, source API/ACL/capability
  coverage, explicit object/relationship/fact contracts and dated source versions.
  9.2.11 remains unqualified. Production discovery capability must stay false until
  that reviewed release; do not ship the test fixture as a substitute.
- Empirical real-source large-inventory performance/resource tuning and final
  image/native licence qualification remain later release acceptance, not claims
  inferred from deterministic I3 tests.

## Material files changed

Every material working-tree path is listed below. No sibling repository file was
changed; generated acceptance artifacts reside outside the repository.

| File | Purpose |
| --- | --- |
| [.github/workflows/ci.yml](../../../.github/workflows/ci.yml) | Complete isolated I3/runtime/database and release-critical CI coverage. |
| [.github/workflows/release.yml](../../../.github/workflows/release.yml) | Complete isolated I3/runtime/database and release-critical CI coverage. |
| [apps/api/app/main.py](../../../apps/api/app/main.py) | Register narrow routes, provision signing state/maintenance lock and suppress sensitive responses. |
| [apps/api/app/models.py](../../../apps/api/app/models.py) | Add durable provenance/receipts/schedules and scoped technical source identities. |
| [apps/api/app/routes/integration_connections.py](../../../apps/api/app/routes/integration_connections.py) | Capability metadata/onboarding, lifecycle cancellation and active mapping guard. |
| [apps/api/app/routes/integration_discovery.py](../../../apps/api/app/routes/integration_discovery.py) | Scoped asynchronous run/schedule/cancel and separate ingestion authentication. |
| [apps/api/app/routes/knowledge.py](../../../apps/api/app/routes/knowledge.py) | Add safe run history/filter metadata and scoped technical link review. |
| [apps/api/app/schemas.py](../../../apps/api/app/schemas.py) | Additive safe run/fact and explicit technical review contracts. |
| [apps/api/app/services/aip_ingestion.py](../../../apps/api/app/services/aip_ingestion.py) | Canonical bounded receipts/seals and existing lifecycle adaptation. |
| [apps/api/app/services/backup_runtime.py](../../../apps/api/app/services/backup_runtime.py) | Read-only worker participation in shared maintenance locks. |
| [apps/api/app/services/backups.py](../../../apps/api/app/services/backups.py) | Quiescent restore, generation revocation and restored-run failure. |
| [apps/api/app/services/connector_lifecycle.py](../../../apps/api/app/services/connector_lifecycle.py) | Active exact-run package ownership guards. |
| [apps/api/app/services/discovery_orchestration.py](../../../apps/api/app/services/discovery_orchestration.py) | Eligibility, immutable run intent, Redis hints, lease/dispatch/recovery. |
| [apps/api/app/services/discovery_tokens.py](../../../apps/api/app/services/discovery_tokens.py) | Independent private signing file and one-run expiring JWTs. |
| [apps/api/app/services/entity_resolution.py](../../../apps/api/app/services/entity_resolution.py) | Scoped technical links and explicit Connector source association. |
| [apps/api/app/services/integration_connections.py](../../../apps/api/app/services/integration_connections.py) | Add safe scheduling/last-run response metadata. |
| [apps/api/app/services/integration_runtime.py](../../../apps/api/app/services/integration_runtime.py) | Safe runtime-neutral start/status/cancel transport and metadata. |
| [apps/api/app/services/integration_secrets.py](../../../apps/api/app/services/integration_secrets.py) | Bounded discovery lease duration with unchanged crypto/rewrap. |
| [apps/api/app/services/knowledge_assertions.py](../../../apps/api/app/services/knowledge_assertions.py) | Preserve typed/cardinality metadata without changing existing rollup. |
| [apps/api/app/services/knowledge_lifecycle.py](../../../apps/api/app/services/knowledge_lifecycle.py) | Technical link deletion safety and retained generic run history. |
| [apps/api/app/services/reconciliation.py](../../../apps/api/app/services/reconciliation.py) | Existing explicit technical acceptance/link/configuration review. |
| [apps/api/app/services/simulated_discovery.py](../../../apps/api/app/services/simulated_discovery.py) | Share existing observation/review lifecycle while preserving simulation behavior. |
| [apps/api/migrations/versions/20261012_0029_discovery_orchestration.py](../../../apps/api/migrations/versions/20261012_0029_discovery_orchestration.py) | Additive I2 -> I3 migration; preserve historical rows and enforce immutable scoped intent. |
| [apps/api/requirements-dev.txt](../../../apps/api/requirements-dev.txt) | Runtime process-inspection dependency for the test harness; no API production Ansible dependency. |
| [apps/api/tests/i3_fixtures.py](../../../apps/api/tests/i3_fixtures.py) | Focused I3 acceptance harness/regression. |
| [apps/api/tests/test_backup_postgres.py](../../../apps/api/tests/test_backup_postgres.py) | Preserve and update applicable I1/I2/lifecycle/security/release regression expectations. |
| [apps/api/tests/test_ci_workflow.py](../../../apps/api/tests/test_ci_workflow.py) | Preserve and update applicable I1/I2/lifecycle/security/release regression expectations. |
| [apps/api/tests/test_i2_integrations.py](../../../apps/api/tests/test_i2_integrations.py) | Preserve and update applicable I1/I2/lifecycle/security/release regression expectations. |
| [apps/api/tests/test_i2_migration_postgres.py](../../../apps/api/tests/test_i2_migration_postgres.py) | Preserve and update applicable I1/I2/lifecycle/security/release regression expectations. |
| [apps/api/tests/test_i2_runtime.py](../../../apps/api/tests/test_i2_runtime.py) | Preserve and update applicable I1/I2/lifecycle/security/release regression expectations. |
| [apps/api/tests/test_i3_backup_postgres.py](../../../apps/api/tests/test_i3_backup_postgres.py) | Focused I3 acceptance harness/regression. |
| [apps/api/tests/test_i3_concurrency_postgres.py](../../../apps/api/tests/test_i3_concurrency_postgres.py) | Focused I3 acceptance harness/regression. |
| [apps/api/tests/test_i3_discovery.py](../../../apps/api/tests/test_i3_discovery.py) | Focused I3 acceptance harness/regression. |
| [apps/api/tests/test_i3_live_runtime.py](../../../apps/api/tests/test_i3_live_runtime.py) | Focused I3 acceptance harness/regression. |
| [apps/api/tests/test_i3_migration_postgres.py](../../../apps/api/tests/test_i3_migration_postgres.py) | Focused I3 acceptance harness/regression. |
| [apps/api/tests/test_i3_runtime.py](../../../apps/api/tests/test_i3_runtime.py) | Focused I3 acceptance harness/regression. |
| [apps/api/tests/test_integration_catalogue_api.py](../../../apps/api/tests/test_integration_catalogue_api.py) | Preserve and update applicable I1/I2/lifecycle/security/release regression expectations. |
| [apps/api/tests/test_integration_runtime.py](../../../apps/api/tests/test_integration_runtime.py) | Preserve and update applicable I1/I2/lifecycle/security/release regression expectations. |
| [apps/api/tests/test_models.py](../../../apps/api/tests/test_models.py) | Preserve and update applicable I1/I2/lifecycle/security/release regression expectations. |
| [apps/api/tests/test_release_distribution.py](../../../apps/api/tests/test_release_distribution.py) | Preserve and update applicable I1/I2/lifecycle/security/release regression expectations. |
| [apps/api/tests/test_runtime_packaging.py](../../../apps/api/tests/test_runtime_packaging.py) | Preserve and update applicable I1/I2/lifecycle/security/release regression expectations. |
| [apps/runtime/ansible/atlas_runtime/callback_worker.py](../../../apps/runtime/ansible/atlas_runtime/callback_worker.py) | Verified bounded job/callback/process cleanup behind the private runtime boundary. |
| [apps/runtime/ansible/atlas_runtime/discovery_worker.py](../../../apps/runtime/ansible/atlas_runtime/discovery_worker.py) | Verified bounded job/callback/process cleanup behind the private runtime boundary. |
| [apps/runtime/ansible/atlas_runtime/jobs.py](../../../apps/runtime/ansible/atlas_runtime/jobs.py) | Verified bounded job/callback/process cleanup behind the private runtime boundary. |
| [apps/runtime/ansible/atlas_runtime/probe.py](../../../apps/runtime/ansible/atlas_runtime/probe.py) | Verified bounded job/callback/process cleanup behind the private runtime boundary. |
| [apps/runtime/ansible/atlas_runtime/server.py](../../../apps/runtime/ansible/atlas_runtime/server.py) | Verified bounded job/callback/process cleanup behind the private runtime boundary. |
| [apps/runtime/ansible/baseline.json](../../../apps/runtime/ansible/baseline.json) | Exact I3 runtime dependency identity, pins, artifact hashes and SBOM. |
| [apps/runtime/ansible/notices/attrs/LICENSE](../../../apps/runtime/ansible/notices/attrs/LICENSE) | Verbatim upstream licence notice for exact new runtime dependency. |
| [apps/runtime/ansible/notices/jsonschema-specifications/COPYING](../../../apps/runtime/ansible/notices/jsonschema-specifications/COPYING) | Verbatim upstream licence notice for exact new runtime dependency. |
| [apps/runtime/ansible/notices/jsonschema/COPYING](../../../apps/runtime/ansible/notices/jsonschema/COPYING) | Verbatim upstream licence notice for exact new runtime dependency. |
| [apps/runtime/ansible/notices/psutil/LICENSE](../../../apps/runtime/ansible/notices/psutil/LICENSE) | Verbatim upstream licence notice for exact new runtime dependency. |
| [apps/runtime/ansible/notices/referencing/COPYING](../../../apps/runtime/ansible/notices/referencing/COPYING) | Verbatim upstream licence notice for exact new runtime dependency. |
| [apps/runtime/ansible/notices/rpds-py/LICENSE](../../../apps/runtime/ansible/notices/rpds-py/LICENSE) | Verbatim upstream licence notice for exact new runtime dependency. |
| [apps/runtime/ansible/notices/typing_extensions/LICENSE](../../../apps/runtime/ansible/notices/typing_extensions/LICENSE) | Verbatim upstream licence notice for exact new runtime dependency. |
| [apps/runtime/ansible/requirements.lock](../../../apps/runtime/ansible/requirements.lock) | Exact I3 runtime dependency identity, pins, artifact hashes and SBOM. |
| [apps/runtime/ansible/sbom.cdx.json](../../../apps/runtime/ansible/sbom.cdx.json) | Exact I3 runtime dependency identity, pins, artifact hashes and SBOM. |
| [apps/web/app/discovery-runs/[id]/page.js](../../../apps/web/app/discovery-runs/[id]/page.js) | Existing capability-gated discovery UI, shared behavior and browser/unit regression. |
| [apps/web/app/discovery-runs/page.js](../../../apps/web/app/discovery-runs/page.js) | Existing capability-gated discovery UI, shared behavior and browser/unit regression. |
| [apps/web/app/integrations/[id]/page.js](../../../apps/web/app/integrations/[id]/page.js) | Existing capability-gated discovery UI, shared behavior and browser/unit regression. |
| [apps/web/lib/discovery.mjs](../../../apps/web/lib/discovery.mjs) | Existing capability-gated discovery UI, shared behavior and browser/unit regression. |
| [apps/web/scripts/check-i3-discovery-browser.mjs](../../../apps/web/scripts/check-i3-discovery-browser.mjs) | Existing capability-gated discovery UI, shared behavior and browser/unit regression. |
| [apps/web/tests/discovery.test.mjs](../../../apps/web/tests/discovery.test.mjs) | Existing capability-gated discovery UI, shared behavior and browser/unit regression. |
| [apps/worker/Dockerfile](../../../apps/worker/Dockerfile) | Non-root worker with canonical SDK/API domain code and baseline. |
| [apps/worker/worker/main.py](../../../apps/worker/worker/main.py) | Existing worker owns bounded scheduling, dispatch and durable recovery. |
| [docs/README.md](../../../docs/README.md) | Truthful current implementation, deployment/operator guidance and validation evidence. |
| [docs/architecture/integrations/contracts/README.md](../../../docs/architecture/integrations/contracts/README.md) | Truthful current implementation, deployment/operator guidance and validation evidence. |
| [docs/architecture/integrations/contracts/integration-runtime.md](../../../docs/architecture/integrations/contracts/integration-runtime.md) | Truthful current implementation, deployment/operator guidance and validation evidence. |
| [docs/architecture/integrations/contracts/secret-provider.md](../../../docs/architecture/integrations/contracts/secret-provider.md) | Truthful current implementation, deployment/operator guidance and validation evidence. |
| [docs/architecture/integrations/i3-completion-report.md](../../../docs/architecture/integrations/i3-completion-report.md) | Truthful current implementation, deployment/operator guidance and validation evidence. |
| [docs/architecture/integrations/i3-implementation.md](../../../docs/architecture/integrations/i3-implementation.md) | Truthful current implementation, deployment/operator guidance and validation evidence. |
| [docs/architecture/integrations/integration-roadmap.md](../../../docs/architecture/integrations/integration-roadmap.md) | Truthful current implementation, deployment/operator guidance and validation evidence. |
| [docs/deployment/backup-restore.md](../../../docs/deployment/backup-restore.md) | Truthful current implementation, deployment/operator guidance and validation evidence. |
| [docs/deployment/discovery-runs.md](../../../docs/deployment/discovery-runs.md) | Truthful current implementation, deployment/operator guidance and validation evidence. |
| [docs/deployment/installation.md](../../../docs/deployment/installation.md) | Truthful current implementation, deployment/operator guidance and validation evidence. |
| [docs/deployment/integration-runtime.md](../../../docs/deployment/integration-runtime.md) | Truthful current implementation, deployment/operator guidance and validation evidence. |
| [docs/product/feature-ledger.md](../../../docs/product/feature-ledger.md) | Truthful current implementation, deployment/operator guidance and validation evidence. |
| [docs/product/status.md](../../../docs/product/status.md) | Truthful current implementation, deployment/operator guidance and validation evidence. |
| [docs/testing/continuous-integration.md](../../../docs/testing/continuous-integration.md) | Truthful current implementation, deployment/operator guidance and validation evidence. |
| [infra/ci/prepare-postgres.py](../../../infra/ci/prepare-postgres.py) | Complete isolated I3/runtime/database and release-critical CI coverage. |
| [infra/ci/release-critical.sh](../../../infra/ci/release-critical.sh) | Complete isolated I3/runtime/database and release-critical CI coverage. |
| [infra/docker/docker-compose.yml](../../../infra/docker/docker-compose.yml) | Intentional worker read-only/private access and bounded/reaping runtime. |
| [infra/install/native.py](../../../infra/install/native.py) | Filtered worker environment and installer parity. |
| [infra/install/upgrade.py](../../../infra/install/upgrade.py) | Retain state and refresh filtered worker configuration on upgrade. |
| [infra/release/release.py](../../../infra/release/release.py) | Verify root worker Docker build context in packages. |
| [infra/systemd/atlas-runtime.service](../../../infra/systemd/atlas-runtime.service) | Bound runtime memory/tasks/shutdown. |
| [infra/systemd/atlas-web.service](../../../infra/systemd/atlas-web.service) | Mask private installation/signing state. |
| [infra/systemd/atlas-worker.service](../../../infra/systemd/atlas-worker.service) | Private dispatch reader group, filtered environment and API domain path. |

## Final repository state

`git status --short` (Atlas):

```text
 M .github/workflows/ci.yml
 M .github/workflows/release.yml
 M apps/api/app/main.py
 M apps/api/app/models.py
 M apps/api/app/routes/integration_connections.py
 M apps/api/app/routes/knowledge.py
 M apps/api/app/schemas.py
 M apps/api/app/services/backup_runtime.py
 M apps/api/app/services/backups.py
 M apps/api/app/services/connector_lifecycle.py
 M apps/api/app/services/entity_resolution.py
 M apps/api/app/services/integration_connections.py
 M apps/api/app/services/integration_runtime.py
 M apps/api/app/services/integration_secrets.py
 M apps/api/app/services/knowledge_assertions.py
 M apps/api/app/services/knowledge_lifecycle.py
 M apps/api/app/services/reconciliation.py
 M apps/api/app/services/simulated_discovery.py
 M apps/api/requirements-dev.txt
 M apps/api/tests/test_backup_postgres.py
 M apps/api/tests/test_ci_workflow.py
 M apps/api/tests/test_i2_integrations.py
 M apps/api/tests/test_i2_migration_postgres.py
 M apps/api/tests/test_i2_runtime.py
 M apps/api/tests/test_integration_catalogue_api.py
 M apps/api/tests/test_integration_runtime.py
 M apps/api/tests/test_models.py
 M apps/api/tests/test_release_distribution.py
 M apps/api/tests/test_runtime_packaging.py
 M apps/runtime/ansible/atlas_runtime/probe.py
 M apps/runtime/ansible/atlas_runtime/server.py
 M apps/runtime/ansible/baseline.json
 M apps/runtime/ansible/requirements.lock
 M apps/runtime/ansible/sbom.cdx.json
 M apps/web/app/discovery-runs/[id]/page.js
 M apps/web/app/discovery-runs/page.js
 M apps/web/app/integrations/[id]/page.js
 M apps/worker/Dockerfile
 M apps/worker/worker/main.py
 M docs/README.md
 M docs/architecture/integrations/contracts/README.md
 M docs/architecture/integrations/contracts/integration-runtime.md
 M docs/architecture/integrations/contracts/secret-provider.md
 M docs/architecture/integrations/integration-roadmap.md
 M docs/deployment/backup-restore.md
 M docs/deployment/installation.md
 M docs/deployment/integration-runtime.md
 M docs/product/feature-ledger.md
 M docs/product/status.md
 M docs/testing/continuous-integration.md
 M infra/ci/prepare-postgres.py
 M infra/ci/release-critical.sh
 M infra/docker/docker-compose.yml
 M infra/install/native.py
 M infra/install/upgrade.py
 M infra/release/release.py
 M infra/systemd/atlas-runtime.service
 M infra/systemd/atlas-web.service
 M infra/systemd/atlas-worker.service
?? apps/api/app/routes/integration_discovery.py
?? apps/api/app/services/aip_ingestion.py
?? apps/api/app/services/discovery_orchestration.py
?? apps/api/app/services/discovery_tokens.py
?? apps/api/migrations/versions/20261012_0029_discovery_orchestration.py
?? apps/api/tests/i3_fixtures.py
?? apps/api/tests/test_i3_backup_postgres.py
?? apps/api/tests/test_i3_concurrency_postgres.py
?? apps/api/tests/test_i3_discovery.py
?? apps/api/tests/test_i3_live_runtime.py
?? apps/api/tests/test_i3_migration_postgres.py
?? apps/api/tests/test_i3_runtime.py
?? apps/runtime/ansible/atlas_runtime/callback_worker.py
?? apps/runtime/ansible/atlas_runtime/discovery_worker.py
?? apps/runtime/ansible/atlas_runtime/jobs.py
?? apps/runtime/ansible/notices/attrs/
?? apps/runtime/ansible/notices/jsonschema-specifications/
?? apps/runtime/ansible/notices/jsonschema/
?? apps/runtime/ansible/notices/psutil/
?? apps/runtime/ansible/notices/referencing/
?? apps/runtime/ansible/notices/rpds-py/
?? apps/runtime/ansible/notices/typing_extensions/
?? apps/web/lib/discovery.mjs
?? apps/web/scripts/check-i3-discovery-browser.mjs
?? apps/web/tests/discovery.test.mjs
?? docs/architecture/integrations/i3-completion-report.md
?? docs/architecture/integrations/i3-implementation.md
?? docs/deployment/discovery-runs.md
```
