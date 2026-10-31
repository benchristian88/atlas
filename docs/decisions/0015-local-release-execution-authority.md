# 0015 — Separate local artifact evidence, approval and execution authority

Status: **Accepted for Phase 4B.12A security remediation**

Date: 2026-10-31

Partially supersedes [ADR 0014](0014-local-release-acceptance.md): its combined
48-hour staging/execution grant, stateless approval, isolation attestation and
revocation-audit lifecycle. Its official package trust, operator boundary,
instance binding, catalogue separation and knowledge-preservation decisions remain.

## Decision

Staging authenticates and retains the original immutable artifact and permits
integrity inspection. It grants no execution authority and does not expire with
an execution lease. The existing fixed Sigstore verifier, frozen roots, repository,
workflow, archive/digest checks, catalogue policy and prerelease qualification are
unchanged.

A root-issued signed plan approval is unique, valid for ten minutes, bound to the
exact plan and operation, and single use at the commit boundary. Its signed
consumption record is durable even when the database commit fails. Runtime health
must independently be healthy; stable version/protocol/baseline/dependency/
collection/operation identities are compared, while timestamps and job capacity
are excluded. Changed compatible identities still invalidate the plan.

PostgreSQL remains authoritative for the active package and approved activation
generation. The existing active row carries additional local activation metadata;
its audit commits in the same transaction. Immutable artifact receipts are not
rewritten. A protected root-owned current execution lease is an offline
authorization derived from that committed state, not another operational store.
The runtime independently checks its signature, package, manifest/evidence,
instance/store/database binding digest, activation generation, lease identity,
manual trigger, time window and revocation. Request replay across generations or
leases fails. Both runtime execution entry points enforce admission independently
of the safe package-integrity endpoint.

Root store locking serializes activation, renewal, recovery and revocation.
PostgreSQL connector/row locks are acquired outside rolled-back previews and
retained through verification and commit. Old execution is durably fenced before
changing the database active identity. Only after commit does an independent
database session recheck the active generation, consumed original approval and
committed audit before publishing a lease. Failure leaves execution denied.
Recovery requires a new reviewed approval and audit and cannot extend the
committed lease. Renewal requires another exact reviewed plan, retains the same
generation/artifact, changes the lease ID, and grants at most 48 hours from renewal.
Revocation is final for the artifact authorization and blocks recovery/renewal.
Application lifecycle transitions from local authority require root revocation
first. Already admitted work settles through the existing lifecycle.

Local acceptance is manual-only at connection creation, schedule changes, run
creation, worker dispatch and runtime admission. Explicit scoped Test Connection
and Run Now remain available after approval. Catalogue connectors retain their
existing scheduling/onboarding behavior. Effective execution status is reported
separately from the database active record.

The enrollment SystemSetting is reserved from application modification. The
operator inspects actual database name/OID/PostgreSQL cluster ID, an independently
provisioned protected deployment UUID/name, and physical store/public/private
directory identities. Human isolation evidence must include those identities;
enrollment obtains them again and compares them before writing. Consumers also
check the protected deployment and mounted store/public identities. Root human
inspection of database, Redis, runtime, worker, credentials and mounts remains
mandatory; configuration or identity checks cannot prove physical isolation.

Revocation publishes/fsyncs signed filesystem evidence before attempting any
database access. PostgreSQL audit is immediate when available and otherwise
explicitly pending, with idempotent reconciliation against the bound database.
No evidence or operational history is removed.

## Limits

Trusted root configuration, reliable filesystem fsync/atomic-rename semantics,
PostgreSQL durable commit, an honest inspection and a trustworthy system clock
are assumptions. Complete privileged rollback/cloning, malicious root or direct
database compromise are outside this boundary. The runtime deliberately receives
neither the database nor the private operator key. A correct offline signature
cannot determine live provider revocation or a database rollback after issuance.
Build/key rotation and cross-instance restore remain separate reviewed work.
Pre-remediation authority files fail closed; no automatic authority upgrade or
evidence rewrite is authorized. There was no live enrolled LXC deployment in this
implementation task.

See the [operator procedure](../deployment/local-release-acceptance.md) and
[remediation evidence](../architecture/integrations/local-release-security-remediation.md).
