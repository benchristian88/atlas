# AGENTS.md

# Atlas Impact — Repository Instructions for AI Development Agents

This file defines repository-wide development rules for Atlas Impact.

These instructions apply to all work in this repository unless a more specific nested `AGENTS.md` exists for a subdirectory.

They are architectural and engineering guardrails, not a substitute for reading the relevant code, tests, ADRs, product documentation, release plans and task-specific instructions.

---

## 1. Working Principle

Inspect before modifying.

Before implementing a task:

* inspect the relevant existing code;
* inspect applicable tests;
* inspect current database models and migrations;
* inspect relevant documentation and ADRs;
* identify existing abstractions before creating new ones;
* determine whether the requested capability already exists partially or completely.

Prefer extending an existing design over introducing a parallel implementation.

Do not infer implementation merely from roadmap or documentation text.

The checked-in repository is the primary evidence of what Atlas currently implements.

---

# 2. Source-of-Truth Order

When repository evidence conflicts, use the following authority order:

1. Current checked-in code, schema, migrations, reachable APIs/UI and passing tests.
2. Accepted Architecture Decision Records.
3. Current architecture documentation.
4. Current active product and release documentation.
5. `docs/product/feature-ledger.md`.
6. Historical design documents.
7. Old implementation plans, transcripts or assumptions.

Documentation describing future functionality must never be treated as proof that functionality already exists.

Do not silently change an accepted architectural decision merely because another implementation would be easier.

If an architectural decision genuinely needs to change, explicitly identify the conflict and follow the repository ADR process.

---

# 3. Git and Branch Safety

The normal active development branch is `dev` unless the task explicitly states otherwise.

Before significant work, inspect:

```bash
git branch --show-current
git status --short
git rev-parse HEAD
```

Do not:

* rewrite Git history;
* force-push;
* reset unrelated user work;
* discard uncommitted changes;
* rebase branches unless explicitly requested;
* commit or push unless explicitly requested by the user.

Keep changes tightly scoped to the requested task.

Do not perform opportunistic refactors unrelated to the task.

At completion, always report:

```bash
git status --short
```

and identify every material file changed.

---

# 4. Product Strategy: Manual Knowledge First

Atlas Impact is currently deliberately prioritising manually entered and curated knowledge before significant further investment in automatic discovery integrations.

This is an intentional product-development strategy.

The objective is to prove and refine:

* the knowledge model;
* Services;
* Business Functions;
* operational relationships;
* completeness;
* graph semantics;
* operational graph behaviour;
* later impact-analysis semantics;

using high-quality human-curated data first.

Do not treat manual entry as a defect that needs to be replaced automatically.

Do not introduce plugin, worker, queue, scheduling or secret-management work merely because automatic discovery would theoretically make a feature easier to demonstrate.

Automatic discovery remains an important later capability.

---

# 5. Current Release Direction

**Release C2.1 — Shared Operational Graph is implemented.** Do not reopen its
design or describe structural reachability as Impact Analysis.

The near-term product target is the **Homelab Ready Release**. The principal
sequence is C2.2 Lean Dependency Semantics, C2.3 Explainable Dependency
Analysis, C2.4 Homelab Operations Experience, F1-lite Homelab Documentation,
B2-lite Live Proxmox Discovery, and contained release hardening.

Homelab Ready does not require C3 People/Teams, C4 formal Knowledge Objects,
advanced recovery evidence, full enterprise Impact Analysis, intended-state
simulation, ITSM, production-scale orchestration, or multiple discovery
plugins. Preserve those capabilities as additive later evolution rather than
pulling them into the homelab release.

Existing integration and discovery code must remain intact and compatible.

---

# 6. Core Architectural Principles

## PostgreSQL is the system of record

PostgreSQL remains Atlas Impact's authoritative persistent data store.

Do not introduce Neo4j, another graph database, or a second operational source of truth unless an explicit approved architectural decision changes this rule.

The Atlas operational graph is a domain/application projection over authoritative Atlas data.

It is not a separate persistent truth store.

---

## The graph is not the database model

Do not couple graph API contracts directly to ORM implementation details.

Graph nodes and edges should have explicit domain representations.

Graph identity must be stable and must not depend on:

* display names;
* mutable labels;
* frontend array position;
* traversal order.

Prefer stable identity based on durable entity type plus durable entity ID.

---

# 7. Atlas Knowledge Model

Preserve the distinction between:

* evidence;
* observations;
* assertions;
* accepted operational knowledge;
* declared knowledge;
* intended knowledge;
* inferred knowledge;
* reconciliation decisions.

These concepts must not be collapsed for implementation convenience.

Discovery must never silently overwrite accepted Atlas knowledge.

Observed source data and accepted canonical knowledge are different concepts.

Manual edits that represent accepted operational knowledge should continue to participate correctly in provenance, assertions, history and meaningful Changes where the existing architecture requires this.

Historical information must not be destroyed merely because a newer value becomes current.

---

# 8. Manual Data Is First-Class Knowledge

Manually created Assets, Services, Business Functions, Interfaces, Networks and relationships are valid Atlas knowledge.

C2 graph functionality must work correctly with manually curated data.

A graph feature must not require an automatic discovery source unless the product requirement specifically requires source evidence.

Do not artificially distinguish manually entered entities as second-class entities.

---

# 9. Core Domain Boundaries

Atlas currently distinguishes several important concepts.

Do not merge these merely because they may appear related.

## Asset

An Asset represents infrastructure, a deployed technical object or another inventory entity represented by the Asset model.

## Application Asset

An Application Asset is a technical/deployed software Asset.

It is not automatically equivalent to a first-class Service.

## Service

A Service represents an operational capability.

Services are first-class domain objects.

Do not replace Services with Application Assets.

Do not automatically convert existing legacy Service Assets or Application Assets into first-class Services.

Any future association or assisted migration must be deliberate and preserve user control.

## Business Function

A Business Function represents business context supported by Services.

Do not collapse Business Functions into Services.

---

# 10. Managed Reference Data

Atlas uses database-managed reference data in areas where administrators need configurable taxonomy.

Do not hard-code taxonomy names when the repository already provides managed records.

Examples include concepts such as:

* Asset Types;
* Relationship Types;
* Service Types;
* Criticality Levels;
* Custom Fields.

Use stable identifiers and existing database relationships rather than assuming specific human-readable names.

Seed values may provide defaults, but application logic should not unnecessarily depend on their labels.

---

# 11. C2.1 — Shared Operational Graph Boundary

C2.1 establishes a reusable operational graph substrate over accepted Atlas knowledge.

It should support structural questions such as:

* what is connected to this entity;
* which Services use an Asset;
* which Assets support a Service;
* which Services depend on another Service;
* which Business Functions are connected to a Service;
* what known dependency paths connect entities;
* bounded upstream and downstream traversal.

C2.1 must preserve clear graph semantics.

---

# 12. C2.1 Is Not Full Impact Analysis

Structural reachability is not automatically operational impact.

Do not infer:

> X is connected downstream from Y

as:

> X will fail if Y fails.

Unless explicitly part of a later approved impact-analysis implementation, C2.1 must not claim:

* outage blast radius;
* service failure probability;
* business impact severity;
* single-point-of-failure conclusions;
* recovery readiness;
* recovery ordering;
* change safety;
* protection adequacy;
* confidence-qualified outage conclusions.

Full Impact Analysis belongs to a later product increment.

Keep graph traversal mechanics reusable so later impact analysis can build on them without corrupting C2.1 semantics.

---

# 13. Graph Semantics

Graph edge meaning must be explicit.

Do not assume that:

* stored database direction;
* semantic dependency direction;
* traversal direction;
* UI presentation direction;

are automatically identical.

When implementing graph behaviour, determine the canonical semantic meaning of each relationship.

Reverse traversal must not mutate the underlying semantic meaning of an edge.

Where relevant, preserve:

* relationship type;
* source entity;
* target entity;
* semantic direction;
* temporal validity;
* required-for-operation semantics;
* future provenance/evidence compatibility.

Avoid introducing ambiguous generic `"connected_to"` semantics when a more precise existing relationship exists.

---

# 14. Temporal Relationships

Atlas preserves historical relationship information in relevant models.

Current operational graph projections should normally include relationships that are currently valid.

Do not destroy historical links merely because they have ended.

Where models contain values such as:

```text
valid_from
valid_to
```

respect the existing temporal model.

A future historical/time-travel graph may use past relationships, but do not silently mix historical and current graph state.

---

# 15. Graph Traversal

Traversal must be bounded.

Do not implement unrestricted recursive traversal.

Traversal logic should be:

* deterministic;
* cycle-safe;
* authorization-safe;
* testable independently of frontend rendering;
* bounded by explicit depth and/or result constraints.

Legitimate dependency cycles may exist.

Do not reject valid domain relationships solely because they create a graph cycle.

Cycle handling belongs in traversal logic.

---

# 16. Authorization and Tenancy

Backend authorization is authoritative.

Frontend filtering is never a security boundary.

All new functionality must preserve the existing Atlas authorization model.

Graph traversal must not leak inaccessible entities.

Specifically:

* inaccessible starting entities must not be disclosed;
* traversal must not cross customer/site boundaries in violation of existing authorization;
* reverse traversal must enforce the same permissions as forward traversal;
* counts must not reveal inaccessible records;
* path metadata must not reveal inaccessible records;
* graph summaries must not leak inaccessible entity existence;
* frontend code must not receive unauthorized graph data and merely hide it.

Reuse existing authorization/scoping services where possible.

Do not create a parallel graph-specific authorization model unless absolutely necessary.

---

# 17. API Design

Prefer explicit domain contracts.

Do not expose ORM objects directly as public API contracts.

Preserve existing API behaviour unless the task explicitly authorises a breaking change.

When extending an existing response:

* favour additive changes;
* maintain existing fields where feasible;
* update tests;
* update documentation.

Existing focused Service, Business Function and Knowledge Graph/topology APIs should be evaluated before introducing new overlapping endpoints.

C2.1 should favour a reusable graph/query service internally with compatibility adapters where appropriate rather than duplicating graph logic across endpoints.

---

# 18. Database Migrations

Database migrations must be safe, additive and reviewable.

Do not rewrite committed migration history.

Do not edit an old migration merely to make a new schema state easier.

Create a new migration for schema changes.

Before adding a migration:

* inspect the current Alembic head;
* inspect recent migrations;
* follow existing repository naming conventions;
* consider existing production data.

Migrations should preserve existing data wherever practical.

Backfills should be deterministic and safe.

Do not silently delete, remap or reinterpret existing user data.

At completion, verify that the migration graph has the expected single head unless the repository explicitly uses another pattern.

---

# 19. Destructive Behaviour

Atlas is knowledge-preserving by design.

Avoid destructive automation.

Do not automatically:

* delete Assets merely because they are no longer observed;
* overwrite accepted knowledge from discovery;
* convert legacy Service Assets into Services;
* remove historical assertions;
* remove ended historical relationships;
* merge entities without an explicit approved workflow.

Prefer reviewable lifecycle transitions and retained provenance.

---

# 20. Knowledge Completeness

Knowledge Completeness and Reconciliation are separate concerns.

Do not turn missing information into Reconciliation Items where the current architecture uses Knowledge Gaps.

Knowledge Gap evaluation should remain:

* deterministic;
* idempotent;
* based on supported structured rules;
* safe to reevaluate;
* isolated from unrelated evaluator failures.

Do not add arbitrary executable rule expressions without an explicit architecture change.

Do not introduce opaque AI-generated remediation as authoritative system logic.

---

# 21. Reconciliation

Reconciliation exists to resolve differences between observations and accepted Atlas knowledge.

Preserve operator control.

Do not silently auto-accept material source changes unless the task explicitly introduces a reviewed policy allowing it.

Where reconciliation decisions exist, preserve their auditability and history.

No-longer-observed is not equivalent to deletion.

Re-observation should preserve historical continuity.

---

# 22. Integrations and Plugins

Atlas uses vendor-neutral plugin boundaries.

Core domain logic must not become coupled to Proxmox or another vendor.

Existing plugin code should normalise vendor data into Atlas-compatible structures.

Do not move identity, tenancy, accepted-knowledge decisions or reconciliation policy into vendor plugins.

Unless explicitly requested, do not expand plugin scope during C2 work.

Current product development is intentionally validating Atlas using manually curated data first.

---

# 23. Secrets and Credentials

Never place credentials, tokens or secrets in:

* source code;
* tests;
* fixtures committed to the repository;
* documentation examples;
* logs;
* error messages;
* generated frontend bundles.

Preserve credential-safe representations in integration code.

Do not invent a new production secret-store architecture as an incidental part of another feature.

---

# 24. Worker and Async Infrastructure

Do not assume that the existence of Redis or a worker container means mature asynchronous job processing exists.

Verify actual reachable behaviour before depending on worker functionality.

Do not introduce:

* new queues;
* scheduling;
* retry frameworks;
* cancellation systems;
* distributed job-control infrastructure;

unless required by the specific task.

Keep C2 graph development independent of future worker orchestration.

---

# 25. Frontend Engineering

Read and follow [the canonical UI architecture guide](docs/architecture/ui-architecture.md) before UI work. Reuse its tokens, PageHeader, Button/IconButton, EntityIdentity, status registry, collection/filter and table contracts. Preserve recognisable Asset icons and the accepted Service/Business Function catalogue interaction; share architecture without forcing identical domain rows. Keep tenant context, entity identity and operational status separate.

Before creating a new component:

* search for an existing equivalent;
* reuse existing spacing, typography and form patterns;
* reuse existing filter and card patterns where appropriate;
* preserve responsive behaviour.

Do not introduce a visually unrelated design system for a single feature.

Avoid excessive decorative UI, unnecessary gradients, oversized cards, placeholder dashboard clutter or generic AI-generated visual patterns.

Functionality should remain clear at normal desktop widths and reasonable mobile/tablet widths where the existing application supports them.

Do not rely on colour alone to communicate state.

Maintain accessibility semantics.

---

# 26. Graph UI

Graph rendering is a presentation layer.

Business traversal logic must not live exclusively in frontend graph code.

The backend/domain layer should determine authorized graph content and semantics.

Frontend graph code may determine:

* layout;
* visual grouping;
* focus;
* labels;
* interaction state;
* presentation filtering over already-authorized results.

It must not independently reconstruct authoritative dependency semantics from raw database-shaped data.

---

# 27. Testing Expectations

Do not claim a test passed unless it was actually executed successfully.

Use existing repository test conventions.

For substantive backend/domain changes, add or update tests covering the changed behaviour.

For graph work, tests should normally cover relevant cases such as:

* stable node identity;
* stable edge identity;
* forward traversal;
* reverse traversal;
* depth bounds;
* cycles;
* duplicate suppression where applicable;
* temporal relationship eligibility;
* unauthorized starting entities;
* traversal across authorization boundaries;
* deterministic output;
* compatibility with existing graph endpoints.

Frontend changes should include appropriate regression/unit tests where the repository already uses them.

Do not remove a failing test simply to make the suite green unless the test is demonstrably obsolete because of an explicitly approved requirement change.

---

# 28. Validation

Run the narrowest useful validation during development and the appropriate broader validation before completion.

Where applicable, inspect or run:

```bash
git diff --check
```

along with relevant:

* backend tests;
* frontend tests;
* plugin tests;
* production frontend build;
* migration-head checks;
* documentation/link checks.

If full validation cannot run because of the environment, state exactly what was not run and why.

Never manufacture validation evidence.

---

# 29. Documentation Is Part of the Feature

When a substantive product capability changes, inspect whether corresponding documentation must change.

Relevant documentation may include:

```text
docs/product/feature-ledger.md
docs/product/development-roadmap.md
docs/product/release-*.md
docs/architecture/*
docs/decisions/*
README.md
```

Do not update documentation merely to create churn.

Do update documentation when leaving it unchanged would make the repository materially misleading.

---

# 30. Feature Ledger

`docs/product/feature-ledger.md` should describe repository reality.

Do not mark a product feature Implemented merely because:

* a model exists;
* a route stub exists;
* a component exists;
* a roadmap promises it;
* a Codex prompt previously requested it.

For a normal end-to-end product capability, implementation evidence should include the layers actually required by that capability.

Use classifications consistently:

```text
Implemented
Partially implemented
Planned but not implemented
Deferred
Abandoned / superseded
Unknown
```

Internal components may be identified as implemented components while the broader user journey remains partial.

Be particularly careful not to overstate operational integrations merely because plugin components exist.

---

# 31. ADR Discipline

Architecture Decision Records describe decisions, not implementation status.

Do not rewrite an accepted historical ADR merely because the product has subsequently evolved.

If a decision changes:

* identify the existing ADR;
* follow the repository's ADR supersession convention;
* create a new decision record if appropriate;
* link the new decision to the superseded decision.

Do not back-edit history to imply that the new decision was always the architecture.

---

# 32. Historical Documentation

Do not casually delete historical design documentation.

Historical documents may explain:

* migrations;
* architectural decisions;
* rejected alternatives;
* compatibility behaviour.

If a document is obsolete:

* determine whether the repository has an archive convention;
* clearly mark it superseded or historical where appropriate;
* preserve important decision provenance.

Avoid leaving obsolete documents presented as current active requirements.

---

# 33. Scope Control

Implement the requested task, not every adjacent idea discovered while investigating it.

If a useful future improvement is discovered but is outside scope:

* record it in the completion report;
* do not implement it opportunistically.

Particularly during C2 work, do not accidentally expand into:

* C3 People and Teams;
* formal Knowledge Objects;
* Backup and Recovery;
* full Impact Analysis;
* NetBox intended state;
* plugin expansion;
* production worker orchestration.

---

# 34. Compatibility

Prefer backward-compatible evolution.

Before changing:

* database fields;
* API responses;
* routes;
* navigation;
* graph response shapes;
* Service semantics;
* relationship semantics;

identify existing consumers and tests.

Do not silently break existing C1 functionality while creating C2 infrastructure.

Where a shared abstraction replaces existing internal logic, preserve existing externally observable behaviour unless the task explicitly changes it.

---

# 35. Security Review

Treat authorization and data isolation failures as high priority.

For every new API or service consider:

* authentication;
* permission key;
* customer scope;
* site scope;
* object ownership/context;
* indirect data leakage;
* enumeration;
* unsafe error details.

Do not expose secrets or sensitive integration configuration through serialization.

Do not rely solely on UI visibility to prevent access.

---

# 36. Error Handling

Errors should be useful without exposing sensitive implementation details.

Do not swallow failures silently.

Do not return raw credentials, connection strings, secrets or stack traces to users.

Prefer existing error-response conventions.

Where a background/internal component fails, preserve sufficient structured information for diagnosis without leaking secrets.

---

# 37. Performance

Do not prematurely introduce infrastructure complexity to optimize hypothetical scale.

However, graph queries must be bounded by design.

Avoid obvious N+1 query patterns.

Prefer indexed access using durable identifiers and existing foreign keys.

Any recursive or iterative traversal must have explicit termination controls.

Performance optimizations must preserve authorization semantics.

---

# 38. Generated or AI-Assisted Conclusions

Atlas is intended to be explainable and evidence-oriented.

Do not introduce opaque scores or operational conclusions that cannot be traced to structured Atlas knowledge.

Future AI features may summarize or assist, but authoritative operational state must remain grounded in Atlas data.

Generated text must not invent unsupported infrastructure, dependencies, recovery capabilities or operational claims.

---

# 39. Definition of Done

A task is not complete merely because code was written.

For the requested scope, confirm as applicable:

* implementation is reachable;
* migrations are correct;
* authorization is enforced;
* customer/site boundaries are preserved;
* tests are added or updated;
* relevant tests pass;
* frontend build passes where relevant;
* documentation remains truthful;
* feature ledger is updated where appropriate;
* `git diff --check` is clean;
* no unrelated work was changed.

---

# 40. Completion Report

At the end of substantial work, provide a concise report containing:

### Summary

What was implemented or changed.

### Files changed

Identify material files and why they changed.

### Database

Identify migrations or explicitly state that none were required.

### API / UI compatibility

State whether existing contracts or routes changed.

### Security and tenancy

State how authorization/customer/site boundaries were handled.

### Tests and validation

List commands actually executed and their results.

Do not claim validation that was not run.

### Documentation

Identify documentation and feature-ledger changes.

### Remaining issues

List only genuine unresolved issues or deliberately deferred follow-ups.

### Repository state

Include:

```bash
git status --short
```

---

# 41. Current Architectural Guardrails Summary

When in doubt, preserve these rules:

**PostgreSQL remains the system of record.**

**The operational graph is a projection, not a second truth store.**

**Manual knowledge is first-class and is deliberately being used to mature Atlas before further plugin investment.**

**C2.1 is complete; B2-lite is a separate Homelab Ready increment.**

**C2.1 built the Shared Operational Graph; it did not implement full Impact Analysis.**

**Structural reachability does not automatically mean operational failure impact.**

**Backend authorization is authoritative.**

**Graph traversal must never leak unauthorized customer/site data.**

**Observed evidence must not silently overwrite accepted knowledge.**

**Services, Assets and Business Functions remain distinct domain concepts.**

**Do not automatically convert legacy Service/Application Assets into first-class Services.**

**Preserve history and provenance instead of using destructive automation.**

**Prefer existing abstractions and backward-compatible evolution.**

**Tests, documentation and the Feature Ledger are part of substantive product work.**

**Do not expand task scope merely because adjacent roadmap work is visible.**
