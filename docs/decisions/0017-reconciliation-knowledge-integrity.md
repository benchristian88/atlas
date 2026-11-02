# 0017 — Serialize canonical knowledge and separate acceptance history

Status: **Accepted**

Date: 2026-11-01

The dated R1–R5 clarification below supersedes incomplete lock-order and migration
details in the original record. The original wording is retained as historical
decision provenance, not a current implementation or acceptance guarantee.

## Context

Independent review reproduced five reconciliation integrity failures. Production
sessions disable autoflush. Source-row locks alone cannot serialize different
sources selecting one canonical value. The original scalar partial index covered
only eight named predicates, although the domain treats unknown scalar predicates
as single-valued. Acceptance replacement also wrote source-supersession lineage,
making legitimate still-current observations permanently ineligible for review.

## Decision

Keep PostgreSQL and the existing caller-owned transaction. Flush an accepted
identity decision before looking up its independent follow-up review. Commit the
source link, decision, review, Changes and audit together.

Use a common canonical subject row to serialize accepted knowledge across sources.
Decision lock order is DataSources by UUID, canonical models in order Asset,
Network, Interface, AssetRelationship, Service, Business Function (each by UUID),
review items by UUID, then assertions by UUID. Acquire all known subjects for a
bulk request before any assertion locks. Interface ownership precedes Interface
locking. Manual Asset PATCH locks and reloads its Asset before reading old values
and declaring changes; it does not acquire discovery source locks. Ingestion
locks its source before changing claims. Retraction shares decision ordering.
Low-level acceptance also locks its canonical subject before replacement.

Refresh prior accepted assertions after waiting for the canonical lock. Clear and
flush prior acceptance before marking the chosen claim accepted. A PostgreSQL
unique partial index enforces the entire scalar cardinality contract, including
unknown namespaced scalars. Object assertions, the six explicit multi-valued keys,
and `interface.` predicates remain multi-valued. Unresolved external identities
are source-local, not canonical subjects covered by this index.

Canonical Asset field proposal versions include the current field value. Recheck
under the same Asset lock used by manual PATCH. A reviewed value change returns
409 individually or an explicit failed entry in bulk. Fresh review can deliberately
select the original observation. Legacy requests without a version cannot bypass
an intervening canonical field change or a newer Asset update since proposal creation.

`superseded_by_id` describes source observation supersession.
`acceptance_replaced_by_id` records the latest replacement of accepted knowledge.
It is independent of freshness and eligibility; historical decisions and repeated
selections remain in reconciliation records and Changes. Reaccepting a claim does
not erase its prior replacement edge. A new source value closes the old source
claim normally. Identical current observations coalesce, retaining provenance.

Asset linking refreshes only source-local relationships referencing that exact
external identity, without persisting incidental endpoint links. It never resolves
the site's unrelated pending relationships under a held source lock. Real
relationship acceptance remains a separate explicit decision.

Expected uniqueness, serialization, deadlock and lock-timeout failures return a
safe actionable conflict. Do not retry automatically: a fresh human review may be
needed. Unknown database failures propagate rather than being labelled concurrency
conflicts. Bulk savepoints retain independent valid decisions; the group is not
atomic. No transaction is committed by a lower-level service.

## Migration and compatibility

Migration `20261101_0032` checks for duplicate accepted scalar subjects before any
DDL and aborts without choosing a winner. It adds the acceptance replacement FK
and moves still-source-current legacy replacement edges to that field, preserving
the target and source freshness. Truly superseded source rows retain their old
lineage. It then replaces the narrow index with the complete domain predicate.
No entity, assertion, evidence or decision is deleted. The index definition is a
migration snapshot: future cardinality changes must evolve it explicitly.

Routes and existing payload fields remain available. Assertion responses add
`acceptance_replaced_by_id`. No plugin, worker, signing or enrollment change is
part of this decision. The local-release exact-build restriction remains separate.

## Alternatives

Global autoflush would hide transaction ordering errors across unrelated code.
Source-only locking leaves cross-source races. Prechecks without a canonical lock
or unique index permit concurrent empty accepted sets. Silently selecting a winner
in migration would reinterpret human decisions. Reusing source lineage would
continue conflating observation freshness and canonical selection.

## Validation and consequences

Require production SessionLocal settings, real scoped HTTP decisions, independent
post-commit sessions, synchronized multi-source races and migration refusal tests.
The current [acceptance record](../testing/cross-source-reconciliation.md) reports
implementation evidence and limitations; this ADR does not assert test success.
These decisions refine the existing knowledge contract and ADR 0008's fact boundary;
they do not change accepted source authority or make discovery authoritative.

## 2026-11-01 clarification after independent review R1–R5

The earlier lock graph and legacy-lineage classification above were incomplete.
This clarification supersedes those details; the earlier text is retained as
decision provenance, not an implementation or acceptance guarantee.

Canonical review display, version and locked Changes predecessor share one
authorized Asset snapshot. Original proposal snapshots remain historical storage.
Every absence acceptance requires a reviewed version, including legacy clients.
Status-writing lifecycle choices select an explicit operator declaration through
normal acceptance replacement; keep/exception choices preserve status. Evidence
and old manual declarations are never rewritten to conceal disagreement.

Source locks use **FOR NO KEY UPDATE**, which conflicts with another source
writer but permits implicit FK **KEY SHARE** from manual assertion creation.
Canonical subjects retain **FOR UPDATE**. The complete order is source writer
locks by UUID; Assets, Networks, Interfaces, AssetRelationships, Services,
Business Functions by UUID in that model order; review items; assertions.
Interface owners and all known bulk subjects precede item/assertion locks.
Ingestion also prelocks already-linked Assets referenced by its current batch,
including relationship endpoints, in UUID order before updating any claims.
This prevents claim → Asset inversion when corroborating an existing relationship
creates accepted manual knowledge later in ingestion. It resolves no new identity
and locks neither unrelated source records nor unreferenced source-linked Assets.
Insertion of assertions/source links also takes FK KEY SHARE on their referenced
sources, canonical entities, runs, evidence, customer/site and actor rows; normal
non-key source updates retain the compatible NO KEY UPDATE mode. Manual PATCH
holds its Asset and may take compatible source KEY SHARE, never a source writer
lock. Replacement updates old assertions and takes FK KEY SHARE on the successor
assertion; subject serialization precedes that work. Retraction uses source writer
lock → canonical subject → assertion. Source keys/identities are immutable in
these operations. Source deletion/key changes and maintenance migrations require
their own lifecycle/maintenance boundary, not escalation of this request order.

Manual PATCH shares expected transaction conflict handling. Genuine unexpected
database errors propagate. The existing CRUD helper still separately maps
IntegrityError to 409. No automatic retry or global mutex is introduced.
Before refreshing prior accepted rows, flush pending source supersession under
the canonical lock. Refresh must not discard intentional pending history when
production sessions disable autoflush.

Migration 0032 takes a maintenance table lock before preflight. It moves only
provable current acceptance edges and preserves only provable source edges;
ambiguous, erased or overwritten history refuses atomically with operator
diagnostics. Accepted decision records alone cannot recover an overwritten source
successor. Downgrade refuses dual or otherwise non-round-trippable lineage before
any mutation. The [migration contract](../deployment/upgrades.md#reconciliation-integrity-migration-0032)
defines the intentionally conservative supported cases. The same head is retained
because 0032 remains untracked/unmerged/unreleased at this handoff, with no live
deployment authorized or performed.

Versionless canonical-field compatibility requires an exact retained original
field/value/update-timestamp baseline. New proposals store that private context;
older proposals without it require a reviewed version. PostgreSQL `now()` is
transaction start, so `Asset.updated_at > item.created_at` cannot prove freshness
under overlapping PATCH transactions. No old baseline is invented. Missing or
out-of-context canonical records render null current values, not proposal history.

Upstream discovery control retains its existing Integration writer lock, then
locks immutable DiscoveryRun identities **FOR NO KEY UPDATE** before source work.
That mode still excludes concurrent run state writers while permitting provenance
FK KEY SHARE from reconciliation already holding a source. FOR UPDATE would create
a Run → Source → Run cycle. Only lock mode changes; lease fields, admission,
authorization, cancellation and state-transition checks remain unchanged. A real
PostgreSQL race and a second-writer NOWAIT refusal verify both properties.

## 2026-11-02 implementation clarification after R4-N1

The independent acceptance found the Asset-only ingestion prelock did not enforce
this ADR's canonical order for Networks and Interfaces. Technical ingestion now
uses the same source → Asset → Network → Interface model/UUID serialization
before any claim writes. AIP collects the full referenced set across batches,
including Interface owners/Networks, relationship endpoints and complete-snapshot
Asset identities, before entering any domain writer. Later per-observation calls
reacquire subsets rather than discovering lower-order locks under claim locks.
The prelock resolves only existing scoped source links; it does not merge or
accept identities. Unrelated entities remain outside that set.

This implements the existing ordering decision; it changes neither PostgreSQL's
authority nor domain acceptance, identity, lease or admission policy. No migration
change is required. Source and Run FOR NO KEY UPDATE modes remain compatible with
implicit provenance/identity FK KEY SHARE. The authenticated ingestion request
now shares expected-conflict rollback/409 behavior through commit, with no blanket
retry and no masking of unknown database failures. The prior natural claim-row
cycle must be absent in both transaction orders; rollback tests alone are not
sufficient evidence. See the [latest verification](../testing/cross-source-reconciliation.md).
