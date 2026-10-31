# 0014 — Instance-bound operator acceptance of signed immutable releases

Status: **Accepted for Phase 4B.12A, explicit operator task**

Authorization/isolation/audit lifecycle partially superseded by
[ADR 0015](0015-local-release-execution-authority.md). The text below records the
original decision and must not be used as the current execution procedure.

Date: 2026-10-31

## Decision

Add a generic local operator CLI for verifying, staging, planning, activating and
revoking an official signed immutable release before catalogue selection. This
is an additive local exception to the installation authority in
[ADR 0006](0006-verified-connector-supply-chain.md). It does not change the package
trust profile in [ADR 0011](0011-offline-official-provenance.md), publication
policy, [ADR 0013](0013-sequence-one-consumer-bootstrap-approval.md), or the
prerelease qualification exception in [ADR 0010](0010-local-connector-qualification.md).

The exact original archive is authenticated by the existing pinned
`GithubAttestationVerifier.verify_package`, fixed GitHub repository/workflow,
numeric identity and frozen roots. Live public GitHub observations separately
bind a published non-draft, non-prerelease, immutable release, exact lightweight
tag commit and exact release/asset IDs and digests. Detached manifest domain
content must equal the manifest inside the signed archive. These observations
establish release identity, not authenticated catalogue eligibility.

Only root under the deployment operator's control can enroll or authorize this
workflow. In Docker, control of the explicit root operator container is therefore
part of installation authority. The ordinary application UID, API bearer/session
credentials and an environment flag confer no local acceptance authority. Root
does not impersonate an application principal; audit records identify local root
operator authority and leave the application actor unset. Existing global
`integration_runtime.manage` and scoped Test Connection/discovery permissions
retain their independent meanings and enforcement.

Enrollment binds a root-owned public file outside the package store, a fresh
store UUID/instance UUID and a PostgreSQL SystemSetting checkpoint. The store must
be empty, separate and root owned. API, worker and runtime mount it and the public
binding read-only. Only the ephemeral root operator mounts the private signing
key. Its Ed25519 signature authenticates **local authorization**, never the
Connector build or a replacement Sigstore root. The original provenance remains
retained and distinct. A signed grant binds the complete manifest, immutable
release evidence, exact archive tuple, instance binding and fixed 48-hour expiry.
API and runtime independently validate it offline, including revocation.

Activation requires the reviewed deterministic plan digest. It binds the runtime
baseline, prior active identity, mapping choices and resolution, dependent
Integration state, encrypted credential identity, taxonomy and fresh explicit
isolation inspection. Existing advisory/row locks, active-run protection,
configuration validation, runtime package verification and transactional
activation remain authoritative. Planning rolls back its preview; staging never
activates. Revocation creates a retained tombstone and blocks subsequent package
verification/execution without deleting grants, packages, credentials or discovery
evidence. Already admitted work is settled through the existing lifecycle.

## Isolation and limitations

A dedicated test LXC can be the deployment boundary; another nested Atlas stack
is unnecessary if database, Redis, runtime, worker, credentials and storage are
actually independent. A Compose override cannot prove this. The authorized root
operator must inspect those resources and supply a protected, explicit inspection
record. Enrollment and activation checks reject missing, negative, stale or
wrong-deployment inspection. The application verifies its database checkpoint;
the runtime deliberately receives neither database access nor operator keys.

This trust boundary assumes honest infrastructure administration and trusted root
configuration. It does not defend against root deliberately cloning the complete
binding, private key, store and database, a full-system rollback, a compromised
GitHub/provider/workflow, frozen-root revocation blindness or a dishonest isolation
inspection. It does not qualify a source version or grant production eligibility.
Renewal, key/build rotation and cross-instance restore require a separately
reviewed procedure; no automatic reenrollment, renewal or updates are added.

See the [operator procedure](../deployment/local-release-acceptance.md) and
[engineering evidence](../architecture/integrations/local-release-acceptance.md).
