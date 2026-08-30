# Atlas documentation

This directory separates implementation evidence, future planning, architecture,
decisions, testing, deployment, and administrator guidance.

## Which document is authoritative?

Use the documents for different purposes:

- [`product/feature-ledger.md`](product/feature-ledger.md) is the audited record of
  what the repository implements at the commit named in that document.
- [`product/development-roadmap.md`](product/development-roadmap.md) is the
  forward-looking product and release plan.
- [`product/mvp-brief.md`](product/mvp-brief.md) is the historical product brief
  for the foundation through Release C1.
- [`architecture/architecture-v0.md`](architecture/architecture-v0.md) describes
  the implemented architecture baseline through Release C1.
- [`architecture/operational-graph.md`](architecture/operational-graph.md)
  describes the planned Release C2 graph architecture. It must not be read as an
  implementation claim until the feature ledger is updated after delivery.
- [`decisions`](decisions) contains accepted Architecture Decision Records
  (ADRs). An ADR explains why a cross-cutting architectural direction was chosen.
- [`testing`](testing) contains release and security test plans. A test plan is
  not evidence that the tests have passed.

The feature ledger and roadmap intentionally remain separate. Updating a roadmap
status does not prove implementation, and adding code does not automatically
update the audited ledger.

## Current release position

| Release area | Repository-grounded position |
| --- | --- |
| Platform and inventory foundation | Implemented |
| Release A — Knowledge Foundation | Implemented |
| Release B — Discovery and Reconciliation | Simulation and reconciliation implemented; live plugin operation and worker orchestration remain partial |
| Release B.5 — Knowledge Completeness | Implemented for Assets and Services; broader entity coverage remains future work |
| Release C1 — Homelab Service MVP | Implemented |
| Release C2 — shared graph and later analysis foundations | C1 provides focused projections; C2.1 itself is planned, not implemented |
| Release C3 — People, Teams and structured ownership | Planned |
| Release C4 — formal Knowledge Objects | Planned |
| Release D — Backup and Recovery | Planned |
| Release E — full Impact Analysis | Planned; existing structural projections are prerequisites, not partial Impact Analysis |
| Release F — Documentation and intended state | Generated-document foundation partial; user-facing product and intended-state workflow not implemented |
| Production and community packaging | Not established |

The selected next increment is **Release C2.1 — Shared Operational Graph**.
Atlas will deliberately use manually entered and curated accepted knowledge
while it proves the graph model. B2 — Operational Integrations and live
discovery remains an incomplete parallel workstream, but it is not a C2.1
prerequisite and automatic discovery investment is deliberately postponed for
the immediate development period.
See [`product/release-c2-plan.md`](product/release-c2-plan.md).

## Product documents

- [`product/mvp-brief.md`](product/mvp-brief.md) — historical product outcome and
  foundation constraints.
- [`product/feature-ledger.md`](product/feature-ledger.md) — implementation audit
  at a named repository commit.
- [`product/development-roadmap.md`](product/development-roadmap.md) — canonical
  roadmap from the completed foundation through impact, recovery, intended
  state, and packaging.
- [`product/release-c2-plan.md`](product/release-c2-plan.md) — implementation-ready
  plan for C2.1, followed by C2.2 and C2.3.
- [`product/c2-readiness-audit.md`](product/c2-readiness-audit.md) — current
  baseline, review reconciliation, prerequisites, and go/no-go decision.
- [`prompts/c2-1-shared-operational-graph-codex-prompt.md`](prompts/c2-1-shared-operational-graph-codex-prompt.md)
  — executable Codex prompt constrained to C2.1 and aligned with the ledger,
  roadmap, ADR, architecture, and test plan.

## Architecture documents

- [`architecture/architecture-v0.md`](architecture/architecture-v0.md) — current
  baseline through C1.
- [`architecture/data-model-v0.md`](architecture/data-model-v0.md) — foundation
  relational model plus the current C1 extension.
- [`architecture/knowledge-changes-and-reconciliation.md`](architecture/knowledge-changes-and-reconciliation.md)
  — evidence, assertions, reconciliation, and meaningful changes.
- [`architecture/knowledge-completeness.md`](architecture/knowledge-completeness.md)
  — deterministic requirements and knowledge gaps.
- [`architecture/service-model.md`](architecture/service-model.md) — Service,
  Asset, Business Function, ownership labels, and recovery fields.
- [`architecture/service-dependencies.md`](architecture/service-dependencies.md)
  — current temporal dependency records and focused graphs.
- [`architecture/operational-graph.md`](architecture/operational-graph.md) —
  planned shared graph projection for C2.1 and extension points for later
  analysis.

## Decisions

- [`decisions/0001-shared-operational-graph.md`](decisions/0001-shared-operational-graph.md)
  — preserve PostgreSQL and accepted operational knowledge as the source of
  truth while introducing a derived, API-owned operational graph projection.

## Release testing

- [`testing/release-c2-operational-graph.md`](testing/release-c2-operational-graph.md)
  — C2.1 contract, authorization, temporal, compatibility, performance, and UI
  validation.
- Existing release-specific and security test plans remain applicable and must
  continue to pass.

## Documentation maintenance rules

1. Label planned architecture explicitly. Do not describe a proposed route,
   model, worker, integration, metric, or product screen as implemented before
   the code and tests exist.
2. Update the feature ledger only after inspecting the delivered repository at a
   named commit and running the checks claimed by the ledger.
3. Add or supersede an ADR when a change affects the system of record,
   authorization boundary, tenancy model, provenance model, graph semantics,
   scenario isolation, or migration strategy.
4. Keep API calculations that affect impact, confidence, security, severity, or
   readiness in the API/domain layer. The web UI may format and visualize those
   results but must not become the authority for operational conclusions.
5. Preserve additive Alembic migrations and existing data. Do not use a roadmap
   release as a reason to reset the database or silently convert legacy records.
6. Keep B2 operational integration, F1 Documents, Interface-first IP cleanup, and
   legacy Service Asset association outside C2.1 unless the release plan and ADR
   are deliberately changed first.
