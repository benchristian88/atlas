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
  the implemented architecture baseline through Release C2.1.
- [`architecture/operational-graph.md`](architecture/operational-graph.md)
  describes the implemented C2.1 graph architecture and additive extension
  boundaries.
- [`decisions`](decisions) contains accepted Architecture Decision Records
  (ADRs). An ADR explains why a cross-cutting architectural direction was chosen.
- [`testing`](testing) contains release and security test plans. A test plan is
  not evidence that the tests have passed.
- [`history/product-reviews`](history/product-reviews) contains dated historical
  review evidence. Those reviews preserve the reconciliation trail but are not
  current specifications or implementation-status authorities.
- [`history/implementation-prompts`](history/implementation-prompts) contains
  completed prompts retained as historical delivery evidence, not active work.

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
| Release C2 — shared graph and Homelab Ready product foundations | C2.1 complete; C2.2 complete; C2.3 complete; C2.4 implemented; manual acceptance pending |
| F1-lite — Homelab Documentation | Planned; generated Markdown renderer and Document storage exist |
| B2-lite — Live Proxmox Discovery | Partially implemented foundation; configure/test/Run Now/reconcile journey planned |
| Homelab Ready Release | Planned near-term product target |
| Release C3 — People, Teams and structured ownership | Planned after Homelab Ready |
| Release C4 — formal Knowledge Objects | Planned after Homelab Ready |
| Release D — Backup and Recovery | Planned |
| Release E — full Impact Analysis | Planned; existing structural projections are prerequisites, not partial Impact Analysis |
| Release F — Documentation and intended state | Generated-document foundation partial; user-facing product and intended-state workflow not implemented |
| Production and community packaging | Not established |

**Release C2.1 — Shared Operational Graph** is complete and merged to `dev`.
**C2.2 — Lean Dependency Semantics** and **C2.3 — Explainable Dependency
Analysis** are implemented with live LXC acceptance complete for their respective
scopes. C2.4 is implemented with manual acceptance pending; C2.5 Entity Detail
UX Polish, F1-lite, B2-lite, and release hardening remain on
the path to a polished, secure, self-hosted **Homelab Ready Release**. See the
[C2.3 acceptance record](testing/release-c2-explainable-dependency-analysis.md).
See [`product/development-roadmap.md`](product/development-roadmap.md).

The [C2.4 architecture](architecture/homelab-operations-experience.md) and
[validation record](testing/release-c2-homelab-operations-experience.md) describe
the Dashboard, Knowledge Graph and pending manual acceptance.

## Product documents

- [`product/mvp-brief.md`](product/mvp-brief.md) — historical product outcome and
  foundation constraints.
- [`product/feature-ledger.md`](product/feature-ledger.md) — implementation audit
  at a named repository commit.
- [`product/development-roadmap.md`](product/development-roadmap.md) — canonical
  roadmap from the completed foundation through impact, recovery, intended
  state, and packaging.
- [`product/release-c2-plan.md`](product/release-c2-plan.md) — C2.1 implementation
  history and current C2.2, C2.3, and C2.4 release scope.
- [`product/c2-readiness-audit.md`](product/c2-readiness-audit.md) — historical
  pre-C2.1 readiness, reconciliation, prerequisites, and go/no-go record.
- [`history/implementation-prompts`](history/implementation-prompts) — archived
  C2.1 Codex prompts; not current specifications.

## User and administrator guides

- [Topology Positions](admin/topology-positions.md): managed vertical order, Automatic, lifecycle and reordering.
- [Relationship Types](admin/relationship-types.md): managed labels, endpoints and Connectivity topology classes.
- [Infrastructure Topology](admin/infrastructure-topology.md): four infrastructure views, filtering, focus and expansion.
- [Asset Types](admin/asset-types.md): managed inventory taxonomy and topology presentation roles.
- [Asset Categories](admin/asset-categories.md): managed taxonomy, presentation, lifecycle and default topology visibility.
- [Networks](admin/networks.md): Network records, bounded icons/accents and topology presentation.

- [Exploring the Knowledge Graph](admin/knowledge-graph.md): expanded view, Focus depth, filters and inspector.

## Architecture documents

- [UI architecture and design system](architecture/ui-architecture.md) — canonical tokens, shared components, identity, status, responsive and contributor standards.
- [September 2026 UI system review](history/product-reviews/atlas-ui-system-review-2026-09.md) — historical audit and rationale, not the current specification.

- [Infrastructure Topology and managed categories](architecture/infrastructure-topology.md): contracts, migration, scoping and projection semantics.

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
  implemented shared graph projection for C2.1 and extension points for later
  analysis.

## Decisions

- [`decisions/0001-shared-operational-graph.md`](decisions/0001-shared-operational-graph.md)
  — preserve PostgreSQL and accepted operational knowledge as the source of
  truth while introducing a derived, API-owned operational graph projection.

## Release testing

- [UI system acceptance](testing/ui-system.md) — responsive/theme matrix and shared component, icon, detail and topology checks.

- [`testing/release-c2-operational-graph.md`](testing/release-c2-operational-graph.md)
  — C2.1 contract, authorization, temporal, compatibility, performance, and UI
  validation.
- [`testing/release-c2-lean-dependency-semantics.md`](testing/release-c2-lean-dependency-semantics.md)
  — C2.2 automated validation and subsequent live LXC acceptance.
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
6. Keep C2.2/C2.3/C2.4, B2-lite, F1-lite, Interface-first IP cleanup, and legacy
   Service Asset association distinct from the completed C2.1 scope.
