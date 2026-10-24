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
- [0012 — Official catalogue publication authorization](0012-official-catalogue-publication-authorization.md) — **Proposed**; public evidence is implemented, authorization remains blocked.

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
