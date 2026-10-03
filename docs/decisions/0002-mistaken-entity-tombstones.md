# 0002 — Preserve mistaken entities as tombstones

Status: **Accepted**

Date: 2026-09-10

## Context

Service creation immediately records accepted manual declarations, a creation
change, audit history and automatic completeness results. Business Functions
also record creation audits. These automatic artefacts must not force an
operator to Archive an accidental record.

The approved C2.6 policy is **Delete mistakes. Archive history.** Delete means
that a record was created by mistake and must leave the operational model.
Archive means that the entity genuinely participated and is no longer active.

## Decision

Use an additive nullable `deleted_at` timestamp on Services and Business
Functions. Retain their rows, accepted initial declarations, gaps and immutable
history. Record a deletion audit and a named change snapshot. Do not provide a
normal restore path for deleted mistakes.

The API must authorize the target and recheck deletion eligibility in its
transaction. Creation-only artefacts may be retained without blocking deletion;
substantive participation, including ended relationships and later edits, must
block deletion. Expose only a generic blocker explanation to avoid disclosing
related entities outside the caller's permissions.

Exclude tombstones and their automatic knowledge artefacts from operational
reads, including counts and graph focus. Retain audit and Changes snapshots,
without navigation to deleted entity detail. Internal retained-record access is
explicit and is not a public API option.

A PostgreSQL row lock and reference-write guards serialize deletion with
operational writes. Name/slug uniqueness excludes tombstones. Archive continues
to use Service archive fields and the Business Function `active` flag.

## Consequences

User-facing Delete is permanent removal from the operational model, not physical
purging or erasure of evidence. Retained records consume storage. A migration
downgrade must refuse to discard tombstone state once used; otherwise it would
resurrect mistakes and could create name collisions.

New reference-bearing models must participate in eligibility, read filtering
and database write guards. Existing typed FKs are inspected conservatively;
polymorphic references require explicit review.

This extends, and does not supersede,
[0001 — Shared Operational Graph](0001-shared-operational-graph.md): PostgreSQL
remains authoritative, the graph remains a projection, and semantic identities
remain stable. Implementation status belongs in the feature ledger.
