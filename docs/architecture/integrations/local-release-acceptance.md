# Phase 4B.12A — local release acceptance engineering report

**Historical pre-security-review implementation report.** The combined grant and
original test counts below describe that development checkpoint. Current
authorization, isolation, recovery, audit and validation are documented in the
[security remediation report](local-release-security-remediation.md) and
[ADR 0015](../../decisions/0015-local-release-execution-authority.md).

This record covers implementation in Atlas only. It does not record a live LXC
deployment or Proxmox operational acceptance. The complete human execution plan is
the [operator procedure](../../deployment/local-release-acceptance.md).

## A — Implementation

`scripts.accept_connector_release` implements `verify`, `stage`, `plan`, `activate`
and `revoke`, supported by `connector_release_acceptance.py` and the protected
operator-authority module. The additional one-time enrollment script binds the
isolated instance. No package version/vendor is allowlisted in production code.

`verify` retains original bytes and independent provenance without installation;
`stage` retrieves/authenticates again and uses existing PackageStore publication;
`plan` rolls back explicit mapping/scope previews; `activate` requires the exact
reviewed digest; `revoke` retains signed evidence and a durable tombstone.

## B — Verified trust

Before architecture changes, the existing `GithubAttestationVerifier.verify_package`
successfully authenticated fresh public Proxmox 0.2.2 bytes, using unchanged CLI
2.102.1, root hash
`3c2cc7f357dc064ec527fdcd78da6e9245c21a381e1abaa0f2b62b186bcac1a1`, official package
profile, fixed release workflow, issuer and numeric repository/owner identity.
The new live `verify` CLI subsequently passed too.

| Identity | Verified value |
| --- | --- |
| Release / tag | 429608780 / proxmox-v0.2.2 |
| Published / immutable / draft | 2026-10-31T01:08:09Z / true / false |
| Source commit | e58788a667c0c0006477ac149e8ad28aedda0745 |
| Archive / manifest / attestation asset IDs | 693849044 / 693848071 / 693848554 |
| Archive SHA-256 | 2d66fc69b9cf9c70d7df117fe41bff3e3e056299f1908cde965e9e3f75e59abf |
| Original build / attempt | 41147363156 / 1 |
| Rekor witness | 2026-10-30T23:58:36Z |

The existing offline verifier needs no new roots/profile or catalogue selector.
It needs an installation adapter, now implemented separately: original official
provenance and immutable release metadata remain distinct from signed **local
operator authorization**. There is no change to the official catalogue adapter.
Frozen original fixture bytes and capture metadata are retained under
`apps/api/tests/fixtures/local_release/`.

## C — Isolation

The old qualification override selects a separate store but shares the selected
project's other services/configuration; it cannot establish production isolation.
A dedicated test LXC can satisfy the boundary when the operator checks its actual
database, Redis, runtime, worker, credentials and mounts. A fresh protected report
must affirm every check. Enrollment binds a separate empty root-owned store,
outside-store public configuration, instance/store UUIDs and PostgreSQL checkpoint.
Consumers mount the store/binding read-only; only the ephemeral operator mounts
the private key. Copying a grant/store to a different bound deployment rejects.

These checks rely on honest root infrastructure inspection. They do not prove
external isolation from YAML or protect against a root administrator cloning the
complete deployment. No production configuration was inspected or modified.

## D — Authorization

Local acceptance authority requires root, possession of the protected operator
key and matching protected instance configuration. Application UID 10001, shell
access, environment flags and application sessions confer no approval. Root
operator audit events do not impersonate a user. Existing global runtime management
and scoped connection/discovery RBAC remain authoritative for their own routes.

## E — Lifecycle and database

Existing connector advisory locks, dependent Integration row locks, active-run
protection, managed mappings/configuration validation and transactional activation
are reused. The plan hashes prior active identity, runtime baseline, complete
dependent state including ciphertext revision, mapping choices/resolution, taxonomy
and isolation report. Fresh reads after runtime verification catch stale ORM
identity-map state. Runtime independently verifies the staged package before the
existing active row changes. Credentials, DataSources and discovery evidence are
retained. Signed grants expire after 48 hours; restart/offline reuse is supported
within that interval. Revocation fsyncs the tombstone and parent directory.

No migration is required. PostgreSQL remains authoritative for active package
identity and audit; the existing SystemSetting model holds the enrollment
checkpoint. Protected files supply installation authority, as existing root-owned
release policy/qualification files do, without a second operational database.
The migration graph remains at `20261021_0031`.

## F — Negative tests

New real-crypto tests reject wrong tag/version/commit/digest, altered repository,
workflow, signer/signature, malformed/oversized evidence and oversized packages.
Provider-policy tests reject draft/prerelease/mutable/substituted releases,
asset identity/digest/URL substitution and contradictory detached declarations.
Root/PostgreSQL tests cover missing/altered/expired/revoked/copied/writable grants,
cross-store/binding failures, production-store rejection, missing operator authority,
stale plan/dependency/credential/runtime/mapping/database state, failed runtime
verification and previous Integration preservation. Existing archive-security
tests cover malformed tar/gzip and member/expansion limits.

## G — Regressions and validation

Actual completed validation:

- Direct existing `GithubAttestationVerifier.verify_package()` on fresh public
  release bytes: **PASS**, before architecture changes.
- `PYTHONPATH=apps/api apps/api/.venv/bin/python -m scripts.accept_connector_release verify --connector-id proxmox --version 0.2.2 --release-id 429608780 --package-asset-id 693849044 --source-commit e58788a667c0c0006477ac149e8ad28aedda0745 --sha256 2d66fc69b9cf9c70d7df117fe41bff3e3e056299f1908cde965e9e3f75e59abf --evidence-directory /private/tmp/atlas-4b12a-live-cli-verification`: **PASS**.
- macOS `PYTHONPATH=apps/api:apps/runtime/ansible apps/api/.venv/bin/python -m pytest apps/api/tests/test_connector_release_acceptance.py apps/api/tests/test_official_provenance.py apps/api/tests/test_attestation_distribution.py apps/api/tests/test_connector_packages.py apps/api/tests/test_connector_qualification.py -q`: **224 passed** at that development checkpoint.
- macOS `PYTHONPATH=apps/api:apps/runtime/ansible apps/api/.venv/bin/python -m pytest apps/api/tests/test_connector_release_acceptance.py apps/api/tests/test_runtime_packaging.py -q`: **51 passed**.
- Final broad Linux/root regression: **1,267 passed**, six existing warnings,
  no skips. Exact container invocation below. The harness copied source into its
  disposable filesystem, retained the cached API image's integrity-checked pinned
  Linux verifier, and called `pytest.main` on package, local acceptance, original
  qualification, lifecycle, I3 discovery, global/scoped API, runtime packaging,
  official catalogue/source/trust/publication/selection/ingestion/bootstrap and
  trusted-catalogue suites. PostgreSQL used a fresh database owned by a
  non-superuser; Redis was separate, with no host ports or production volumes.
- After adding the final offline execution-admission test, the same container
  command with `tests/test_local_release_authority_postgres.py -q --tb=short`
  appended: **19 passed**. This suite overlaps the broad regression; counts must
  not be added. It uses a fresh runtime object and synthetic fixed-worker output,
  exercises private materialization, then proves revocation blocks a new launch.
  It does not execute Ansible or contact a Proxmox source.
- Harness `python -m alembic upgrade head` and `python -m alembic heads`: **PASS**,
  one head `20261021_0031`. No new migration.
- `docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.local-release.yml config --format json`, captured privately with generated disposable values, plus assertions on merged mounts/UIDs/key isolation: **PASS**. No configuration/credentials printed.
- Relative documentation link check: **8 links resolved**. `git diff --check`:
  **clean**.

```bash
docker run --rm --user 0:0 --name atlas-4b12a-runner --network atlas-4b12a-tests --mount type=bind,source=/Users/Ben/Code/atlas,target=/workspace,readonly --mount type=bind,source=/private/tmp/atlas-4b12a-harness-w2kp2nsz,target=/harness,readonly --entrypoint python atlas-b13-api:arm64 /harness/run-tests.py
```

The temporary harness and databases are validation infrastructure, not shipped
product. Earlier attempts exposed test-runner/environment setup issues, an invalid
new taxonomy fixture field, omitted new adapter error codes and an overly broad
PostgreSQL `FOR UPDATE` join. Those were corrected; the final runs above passed.
The original tests were preserved.

The work uses the unchanged genuine verifier, not a mocked signature success.
Synthetic runtime health/worker results in lifecycle tests are not runtime
baseline, actual Ansible execution or source-operation acceptance. No frontend
build, full new image build, LXC deployment, live source run, native install,
reboot or cross-architecture deployment acceptance was performed in this task.

## H — Documentation and material files

- New services: `connector_release_acceptance.py`, `local_release_authority.py`.
- New operator entry points: `accept_connector_release.py`, `bind_local_release_instance.py`.
- Existing `apps/api/app/services/connector_store.py`, `connector_lifecycle.py`
  and `integration_connections.py`: additive local authorization,
  active-record/database binding and explicit operator lifecycle gate.
- Runtime: new `local_release.py` independent checker and additive dispatch in
  `qualification.py`; original qualification checks remain.
- Tests: new release/authority suites, original frozen release fixtures and
  additive deployment assertions in `test_runtime_packaging.py`.
- Deployment: opt-in `docker-compose.local-release.yml`, with private operator key
  isolation and read-only consumers; ordinary Compose/qualification files unchanged.
- Documentation: ADR 0014/index, operator procedure, this report, feature-ledger
  entry and links/clarifications in runtime/provenance deployment documentation.

No SDK/Connector repository, signed package, root snapshot, trust profile, GitHub
release/catalogue publication or production credential/configuration was changed.
API/UI routes and response contracts remain unchanged.

New test files are `apps/api/tests/test_connector_release_acceptance.py` and
`apps/api/tests/test_local_release_authority_postgres.py`. The fixture directory
contains `README.md`, `manifest.json`, `package.sigstore.json`,
`proxmox-0.2.2.tar.gz`, `release.json` and `tag-ref.json`. Documentation files are
`docs/decisions/0014-local-release-acceptance.md`, `docs/decisions/README.md`,
`docs/deployment/local-release-acceptance.md`,
`docs/deployment/attestation-verification.md`,
`docs/deployment/integration-runtime.md`, `docs/product/feature-ledger.md` and this
engineering report.

## I — Risks and limits

Root/operator-key and provider/workflow compromise remain trust risks. Frozen
Sigstore roots do not provide current revocation awareness. Complete database plus
protected-authority rollback is outside this boundary. Enrollment is one-time;
partial filesystem/DB provisioning fails closed and requires inspection. Regrant
of an already-staged tuple, automatic renewal, key/build rotation and cross-instance
restore are deliberately absent and need separate reviewed procedures. Runtime
revocation blocks new admission, not jobs already authorized. No automatic rollback
or production catalogue eligibility is added.

## J — Acceptance readiness

Human review, exact clean implementation commit selection, actual LXC isolation
inspection and the documented enrollment/staging/approval/activation procedure
remain required. Run scoped Test Connection and manual discovery, inspect real
source coverage/evidence, exercise restart/offline reuse and revoke on the test
LXC before claiming operational acceptance. Native/systemd and other architecture
live deployment acceptance remain outstanding. **No live deployment was performed.**

Base `dev` and feature branch started at
`808ee0f76f77c11e17a6c403806ce0666e30074e`;
branch `feature/secure-local-release-acceptance`. No commit, push, merge or PR was
created. The implementation remains in the working tree for manual Git review.
