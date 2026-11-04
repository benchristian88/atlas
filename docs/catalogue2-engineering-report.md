# Catalogue 2 — Atlas Impact engineering completion report

Date: 4 November 2026 (Pacific/Auckland).

The subsequent [security remediation report](catalogue2-security-remediation-report.md)
records H1/H2/M1 corrections and validation. This original completion report remains
the historical implementation/evidence handoff; it grants no activation authority.

## A. Result and scope

**Inactive, end-to-end implementation candidate; feature closure remains blocked.**
The authorized local implementation reaches signed future-history ingestion and
administrator-reviewed remote package activation using existing Atlas stores and
flows. Both Atlas approval records are unset. No live publication, deployment,
installation, LXC access, commit, push, merge, tag or release occurred. The local
feature branch was created as explicitly requested from clean `dev`.

Do not interpret passing synthetic future tests as owner approval or genuine
Catalogue 2 signing/publication evidence. Production remains limited to the
unchanged sequence-one approval. [Proposed ADR 0018](decisions/0018-catalogue-durable-publication-evidence.md)
and the [operator runbook](deployment/catalogue2.md) are review material.

## B. Baseline and preserved work

Atlas began clean on `dev`, HEAD `9c10e96da10ebf7108c88f632d77beaab5051b6c`.
Current local branch: `feature/catalogue-v2-consumption`, same HEAD. Producer work
remains on its existing `feature/catalogue-v2-publication-evidence`, baseline
`e58788a667c0c0006477ac149e8ad28aedda0745`; its Phase 1 work was copied to local
review evidence before extension and was not discarded or restarted.

Inspection included current authorization/trust and catalogue adapters, immutable
PostgreSQL models/migrations, PackageStore, runtime/lifecycle/local acceptance,
mappings/configuration routes, UI guide/components and applicable tests/ADRs.
Existing bootstrap pins, genuine fixtures, SDK package format, native permissions,
local-release execution restrictions and installed-package offline behavior remain.

## C. Implemented consumer pipeline

- A release-owned future policy/fingerprint independently selects successor S,
  exact producer policy digest, numeric identities, original v2 signer profile,
  historical rules and decision references. An archive cannot choose its authority.
  The approved producer review revision must equal the independently selected S.
- The existing hash-pinned offline verifier/roots authenticate the original
  reusable-workflow preflight certificate and exact signed predicate/subject.
  Pure Atlas-owned observation validators preserve full privileged ruleset,
  actor/run/attempt/workflow/CI/environment checks. Verified Tlog timestamps,
  original run time, selection timing and release time are checked separately.
- Bounded single-parent Git selection history reaches the original approved root;
  every canonical pointer, digest link, catalogue signature, immutable snapshot,
  retained selection/bundle and future seven-asset archive is verified. The
  original sequence-one exception remains exact and is never used for sequence 2.
- Fresh 1→2 acceptance uses the existing PostgreSQL revision/high-water/history
  store in one transaction. Rejected later revisions roll back a new prefix.
  Retained pointer identities detect substitutions; withdrawal cannot reactivate
  historical versions or mutate their identity. Restore clears currentness.
- Separate release-owned remote-installation approval binds to the exact Atlas
  publication policy. Explicit request confirmation binds source, connector path,
  version, package digest, catalogue sequence/digest and numeric package asset.
  The current selection ref and immutable package release are freshly checked,
  the genuine package signature is verified, and a final locked DB recheck
  precedes the existing store/runtime/activation/audit transaction.
- Existing archive path/member/decompression/digest checks, mappings, dependent
  configuration and local operator-authority restrictions remain authoritative.
  Mapping forms can resolve accepted remote and already-installed manifests.
  No runtime store writer, new secret manager, queue or scheduler was added.
- Existing Catalogue UI provides review/confirmation, permission and error states,
  with shared Buttons/native modal/checkbox patterns. Backend authorization is
  still authoritative. Installed ordinary Connectors use local integrity checks
  without catalogue access. Native remote installation is explicitly unsupported.

Bounds: 32 history commits, 32 MiB total artifact input, 8 MiB retained evidence
per revision, 240 seconds network/crypto retrieval budget and 300-second refresh
lease. Exceeding a bound rejects; arbitrary long future histories need a later
reviewed incremental adapter.

## D. Files and compatibility

The exact inventory below is generated from the final working tree. No database
migration was required: existing immutable revision/evidence/state columns suffice.
The existing single migration head remains `20261101_0032`; no committed migration
was edited. No public route was removed or renamed. Existing bootstrap selection
bodies still work. Remote fields are additive and strict; the `source: official`
branch requires all exact confirmation fields and separate approvals.

<!-- INVENTORY_START -->
| File | Purpose |
| --- | --- |
| `apps/api/app/routes/integration_connections.py` | Reuse accepted/installed manifests for mapping forms. |
| `apps/api/app/routes/integrations.py` | Strict exact remote selection, Docker gate, locked recheck and existing activation flow. |
| `apps/api/app/services/catalogue_source.py` | Bounded reader budget and typed future adapter dispatch; bootstrap routing preserved. |
| `apps/api/app/services/connector_catalogue.py` | Approved remote eligibility projection and mapping manifest lookup. |
| `apps/api/app/services/official_catalogue_ingestion.py` | Reuse strict commit/tree and release validation across bootstrap/future snapshots. |
| `apps/api/app/services/trusted_catalogue.py` | Atomic chain acceptance, retained pointer checks and truthful policy status. |
| `apps/api/tests/test_catalogue_backup_postgres.py` | Retain future original archive/high-water through encrypted restore; invalidate currentness. |
| `apps/api/tests/test_integration_catalogue_api.py` | Remote global RBAC and missing-owner-policy regressions. |
| `apps/web/app/integrations/page.js` | Reload existing catalogue/installed view after remote activation. |
| `apps/web/components/integration-panels.js` | Approved remote review and mapping actions within existing catalogue presentation. |
| `apps/web/components/official-catalogue.js` | Native exact-identity confirmation and safe installation feedback. |
| `apps/web/lib/integrations.mjs` | Bounded exact request projection from eligible accepted metadata. |
| `apps/web/tests/integrations.test.mjs` | Exact identity and hostile/ineligible selection projection regression. |
| `docs/decisions/README.md` | Index proposed ADR. |
| `docs/deployment/official-catalogue.md` | Link inactive candidate while retaining active bootstrap boundary. |
| `docs/product/feature-ledger.md` | Truthful Partially implemented candidate status. |
| `apps/api/app/services/catalogue_chain.py` | Bounded complete authenticated chain and seven-asset retrieval. |
| `apps/api/app/services/catalogue_future_authorization.py` | Independent unset owner pins, original signed profile and historical authorization. |
| `apps/api/app/services/publication_contracts/__init__.py` | Atlas-owned pure publication/security validators; no privileged transport. |
| `apps/api/app/services/publication_contracts/authorization.py` | Atlas-owned pure publication/security validators; no privileged transport. |
| `apps/api/app/services/publication_contracts/contract.py` | Atlas-owned pure publication/security validators; no privileged transport. |
| `apps/api/app/services/publication_contracts/rulesets.py` | Atlas-owned pure publication/security validators; no privileged transport. |
| `apps/api/app/services/remote_connector_packages.py` | Separate unset executable approval, immutable genuine download and PackageStore adapter. |
| `apps/api/tests/fixtures/future_publication/README.md` | Explicitly synthetic unsigned future policy/verified-output fixture and provenance notice. |
| `apps/api/tests/fixtures/future_publication/policy.json` | Explicitly synthetic unsigned future policy/verified-output fixture and provenance notice. |
| `apps/api/tests/fixtures/future_publication/preflight.json` | Explicitly synthetic unsigned future policy/verified-output fixture and provenance notice. |
| `apps/api/tests/fixtures/future_publication/verified-output.json` | Explicitly synthetic unsigned future policy/verified-output fixture and provenance notice. |
| `apps/api/tests/test_catalogue_future.py` | Explicit synthetic future policy/chain/tamper tests with genuine bootstrap crypto. |
| `apps/api/tests/test_remote_connector_packages.py` | Genuine 0.2.2 download/store/activation/mapping/offline and rejection regressions. |
| `apps/web/scripts/check-catalogue2-browser.mjs` | Production-build confirmation/RBAC/error/responsive acceptance. |
| `docs/catalogue2-engineering-report.md` | Atlas A–J report and exact evidence/remaining actions. |
| `docs/decisions/0018-catalogue-durable-publication-evidence.md` | Proposed decisions only; existing accepted ADRs unchanged. |
| `docs/deployment/catalogue2.md` | Separate approvals and exact future publication/new-instance acceptance order. |
| `infra/ci/run-catalogue2-tests.py` | Disposable Python 3.12 Docker acceptance plus existing root security suites. |
<!-- INVENTORY_END -->

## E. Security, tenancy and authority decisions

Global `integration_runtime.manage` is required before remote package lookup or
network access; scoped customer/site grants cannot manage instance-global code.
Existing configured connection/customer/site authorization is unchanged. Downloads
use fixed anonymous official GitHub numeric endpoints, bounded responses and the
existing checked public redirect/DNS rules. No provider URL becomes a routing input.
No credentials are requested for catalogue retrieval; errors do not echo remote
bodies, URLs, subprocess details, file paths or secrets.

The original approval in ADR 0013 remains unchanged. Future publication and remote
installation are independently disabled by their unset code-owned records and
fingerprints. Proposed historical bounds/selection correlation are not approved.
Production recovery is deliberately disabled until its permanent audit disposition
is accepted; if a separate recovery archive is required, more code is required.
This is a real closure blocker, not a claim of implemented permanent recovery audit.

## F. Validation and evidence

All detailed logs/XML/screenshots are local under
`/private/tmp/atlas-catalogue2-completion`. Test evidence is not signed authority.
Genuine sequence-one signatures and immutable Proxmox 0.2.2 artifacts are used
unchanged. Future-only verified output/provider metadata are explicitly synthetic;
no Catalogue 2 publication was performed to obtain test fixtures.

| Command/check actually executed | Result |
| --- | --- |
| `cd apps/api; .venv/bin/python -m pytest -q tests --tb=short --junitxml=WORK/atlas-full-ready.xml` with disposable PostgreSQL/H3 source/target and ready Redis URLs | **2,599 passed, 233 skipped, 0 failures/errors**; 388.04 s |
| Final focused `pytest` on `test_catalogue_future.py`, `test_remote_connector_packages.py`, `test_integration_catalogue_api.py`, `test_catalogue_backup_postgres.py`, same services | **104 passed, 0 skipped/failures/errors**; includes last status/adapter adjustments and future archive restore |
| Test-only Docker Compose, unique `atlas-catalogue2-review` project, `infra/ci/run-catalogue2-tests.py` | **184 passed, 0 skipped/failures/errors**, Python 3.12; includes all 83 existing root/security cases |
| Narrow final Docker consumer recheck after last two adapter adjustments | **101 passed, 0 skipped/failures/errors**; 25.47 s; `docker-consumer-final.xml` |
| Production API Docker build with existing Dockerfile, integrity-checked verifier and final source | **PASS**; `docker-api-build-complete.log` |
| `npm test --prefix apps/web` | **331 passed, 0 skipped/failures**; `web-tests-final2.log` |
| `npm run build --prefix apps/web` | **PASS**; `web-build-final.log` |
| `node apps/web/scripts/check-integrations-browser.mjs` with existing Playwright/Chrome against localhost production build | **576 existing state/theme/accent/viewport checks passed** |
| `node apps/web/scripts/check-catalogue2-browser.mjs`, final production build | **8 manager/viewer/withdrawal/error/confirmation scenarios passed** at 1440/390 px; screenshots visually reviewed, shared checkbox layout corrected and rechecked |
| `pytest -q tests/test_repository_docs.py` | **14 passed**; final link inventory valid |
| `cd apps/api; .venv/bin/alembic heads` plus fresh full upgrade and PostgreSQL migration/history regressions | **PASS**, one head `20261101_0032`; no new migrations |
| `compileall` for new services; `git diff --check`; both `git diff --cached --quiet`; frozen-control/Phase 1 preservation audit | **PASS**; 27 producer controls byte-exact, Phase 1 retained, no staged changes |

`WORK` is `/private/tmp/atlas-catalogue2-completion`. The host's 233 skips are
explicitly recorded in `host-skip-reasons.json`: 83 require root in a disposable
container (all passed separately in Docker); 68 need nginx; 27 need specific
installed Ansible environments; 45 are setup/MFA cases requiring separately
configured migrated test databases; 10 require separate empty migration databases.
These host-only/optional suites were not silently claimed as executed. Fresh
schema creation and the relevant migration/history and catalogue restore suites
did execute. No native/systemd, live GitHub publication, LXC or live Proxmox
qualification is claimed.

There are 72 new permanent API regressions (47 future policy/chain, 21 remote
package, 3 API permission/approval, 1 archive restore) and one frontend identity
regression, in addition to the new browser harness. The complete producer result
is **2,869 passed**; see its separate A–J report.

Earlier diagnostics are retained rather than hidden: `initial-atlas-tests.log`
(274 passed/20 DB skips); two synthetic fixture development runs (35 passed,
9 failed, 2 skips each; missing/misqualified helper names corrected); next pure
future run (44 passed/2 DB skips); initial PG install run (65 passed/1 mapping
prerequisite failure, corrected by explicit test-operator reference data);
`atlas-focused.log` (206 passed); `atlas-full.log` (2,591 passed/2 environment
failures/233 skips); `atlas-full-final.log` (2,581 passed/18 failures/233 skips,
including 15 unavailable-Redis failures, two pre-existing intermittent ordering/
subprocess-cleanup failures and one documentation link observed before its new
report file existed). The ready-service final full run above passed all executed
cases. No existing test or production permission gate was weakened.


During setup, an initial API run from repository root had two infrastructure
failures: the backup subprocess could not import `scripts` from that working
directory, and the real Redis test had no server. Final validation uses the API
working directory plus disposable PostgreSQL and Redis. The first Docker run
passed 164 tests but had 19 API-lifespan setup errors because the production
service-owned state directory was deliberately inaccessible to the root test
process. The final harness creates a private root-owned **test-only** directory;
production permissions were not changed. Early focused development failures were
fixed before final validation; no test was removed or weakened.

## G. Documentation and ledger

New Proposed ADR 0018 records the unresolved historical, selection, recovery and
separate executable-eligibility decisions. `deployment/catalogue2.md` gives the
approval/pinning/publication/new-instance acceptance order. Existing deployment
and ADR indexes link the candidate without changing accepted historical ADRs.
The feature ledger marks Catalogue 2 **Partially implemented**, explicitly inactive
and awaiting security/live operational qualification. Existing Phase 4A describes
its still-active default behavior; the new candidate row explains the extension.

## H. Independent review and outstanding owner approvals

Required: explicit seven-asset/historical 900/300/witness semantics acceptance;
selection binding acceptance or stronger signed binding; disabled-recovery
acceptance or a new permanent recovery-archive implementation; reviewed frozen
producer S and exact policy/numeric pins; genuine successor signing/isolation
acceptance; separate Atlas future-policy and executable-eligibility approvals;
reviewed producer workflow/trust changes and separate catalogue live-gate approval.
None is supplied by this report or by the owner's authorization to develop.

The public Proxmox 0.2.2 release was observed read-only and matches existing genuine
local artifacts: release `429608780`, package asset `693849044`, source
`e58788a667c0c0006477ac149e8ad28aedda0745`, package digest
`2d66fc69b9cf9c70d7df117fe41bff3e3e056299f1908cde965e9e3f75e59abf`.
That evidence does not approve a future catalogue or new installation.

## I. Operator actions and closure blockers

Follow the [exact staged procedure](deployment/catalogue2.md): review two coherent
implementation PRs; decide contracts; freeze S; prepare/review both workflow
outputs; separately approve pins and gates; obtain genuine successor evidence;
build/sign at final C; publish once; independently verify seven immutable assets
and full history; then separately approve deployment/rebuild of `192.168.3.220`.
Install through normal Catalogue review, resolve managed taxonomy mappings, use
normal scoped forms and qualify actual source discovery/offline/restart/restore.
The old `atlas-test-docker` installation must never be selected or touched.

No approved future S/C, catalogue release ID, new Atlas release/build identity or
live operational results exist in this candidate. Native remote writing and
permanent recovery audit remain unsupported. Local Docker tests cover security,
genuine package/store/runtime verification and synthetic HTTP; they do not prove
live GitHub controls, LXC networking, Proxmox ACLs or source operational fitness.
Do not declare the feature complete until these blockers are resolved.

## J. Repository state

All changes remain uncommitted and unstaged. No SDK files changed. Local branch
creation was the explicitly requested exception to the otherwise read-only Git
work; no commit/push/merge/tag/release/publication operation occurred.

Final `git status --short`:

```text
 M apps/api/app/routes/integration_connections.py
 M apps/api/app/routes/integrations.py
 M apps/api/app/services/catalogue_source.py
 M apps/api/app/services/connector_catalogue.py
 M apps/api/app/services/official_catalogue_ingestion.py
 M apps/api/app/services/trusted_catalogue.py
 M apps/api/tests/test_catalogue_backup_postgres.py
 M apps/api/tests/test_integration_catalogue_api.py
 M apps/web/app/integrations/page.js
 M apps/web/components/integration-panels.js
 M apps/web/components/official-catalogue.js
 M apps/web/lib/integrations.mjs
 M apps/web/tests/integrations.test.mjs
 M docs/decisions/README.md
 M docs/deployment/official-catalogue.md
 M docs/product/feature-ledger.md
?? apps/api/app/services/catalogue_chain.py
?? apps/api/app/services/catalogue_future_authorization.py
?? apps/api/app/services/publication_contracts/
?? apps/api/app/services/remote_connector_packages.py
?? apps/api/tests/fixtures/future_publication/
?? apps/api/tests/test_catalogue_future.py
?? apps/api/tests/test_remote_connector_packages.py
?? apps/web/scripts/check-catalogue2-browser.mjs
?? docs/catalogue2-engineering-report.md
?? docs/decisions/0018-catalogue-durable-publication-evidence.md
?? docs/deployment/catalogue2.md
?? infra/ci/run-catalogue2-tests.py
```
