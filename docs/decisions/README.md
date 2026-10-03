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
  an API-owned derived operational graph for Release C2.1 and later analysis.

- [`0002-mistaken-entity-tombstones.md`](0002-mistaken-entity-tombstones.md) —
  distinguish mistaken-record removal from Archive while retaining evidence and
  excluding tombstones from operational reads.

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
