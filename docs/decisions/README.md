# Architecture Decision Records

Architecture Decision Records (ADRs) capture cross-cutting decisions that should
remain understandable after the original implementation discussion is gone.

## Status values

- **Proposed** — under review and not yet binding.
- **Accepted** — current architectural direction.
- **Superseded** — replaced by a later ADR, with a link to the replacement.
- **Deprecated** — retained for history but no longer recommended.
- **Rejected** — considered but not adopted.

## Current decisions

- [`0001-shared-operational-graph.md`](0001-shared-operational-graph.md) — preserve
  PostgreSQL accepted operational knowledge as the source of truth and introduce
  an API-owned derived operational graph for structural exploration and dependency analysis.

- [`0002-mistaken-entity-tombstones.md`](0002-mistaken-entity-tombstones.md) —
  distinguish mistaken-record removal from Archive while retaining evidence and
  excluding tombstones from operational reads.

- [0003 — Runtime-neutral AIP and isolated Ansible execution](0003-runtime-neutral-integrations.md).
- [0004 — Reuse application-key secrets with separate control and callback credentials](0004-integration-secret-lifecycle.md).
- [0005 — Three-project Integration ownership and licences](0005-connector-project-ownership.md).
- [0006 — Official immutable catalogue and protected verified execution](0006-verified-connector-supply-chain.md).
- [0007 — Global one-version packages and scoped connection lifecycle](0007-global-connector-scoped-integration.md).
- [0008 — Exact global taxonomy mapping and declared namespaced facts](0008-connector-taxonomy-and-facts.md).
- [0009 — Read-only technical discovery for official v1 Connectors](0009-read-only-official-connectors.md).

- [0011 — Pinned offline official provenance verification](0011-offline-official-provenance.md).
- [0012 — Official catalogue publication authorization](0012-official-catalogue-publication-authorization.md) — **Proposed** for the stronger future-publication evidence contract.
- [0013 — Exact sequence-one consumer bootstrap trust approval](0013-sequence-one-consumer-bootstrap-approval.md) — **Accepted**; approves the complete fixed consumer pin set and restricted historical exception.
- [0014 — Instance-bound operator acceptance of signed immutable releases](0014-local-release-acceptance.md) — local installation authority, separate from catalogue eligibility and prerelease qualification.
- [0015 — Separate local artifact evidence, approval and execution authority](0015-local-release-execution-authority.md) — partially supersedes 0014's authorization, isolation and audit lifecycle after security review.
- [0016 — Recover local maintenance, revocation evidence and bundled management](0016-local-release-recovery.md) — supplements 0015 with lease-independent maintenance, a signed ordinary-management handoff and crash-safe irreversible revocation recovery.

## ADR maintenance

Create or supersede an ADR when a change affects any of the following:

- the durable system of record;
- customer/site tenancy or authorization boundaries;
- evidence, assertion, reconciliation, or accepted-knowledge semantics;
- graph identity, direction, or traversal semantics;
- scenario isolation and intended state;
- worker or plugin trust boundaries;
- migration and compatibility strategy; or
- a major framework or persistence choice.

An ADR should not claim implementation. The feature ledger remains the audited
record of delivered capability.
