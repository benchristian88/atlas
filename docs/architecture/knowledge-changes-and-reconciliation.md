# Knowledge changes and reconciliation

Atlas keeps four related concepts separate:

1. **Evidence** is the immutable raw observation from a discovery run.
2. **Assertions** are sourced claims, including historical, superseded, and
   retracted claims.
3. **Reconciliation items** are human decisions required before discovered
   knowledge changes the operational model.
4. **Knowledge changes** are concise, user-meaningful timeline events. They are
   not security audit events.

`AuditEvent` remains the security and administration record. `KnowledgeChange`
drives `/changes`, recent dashboard activity, and asset history links. The
central knowledge-change service normalizes JSON values and writes within the
caller's transaction; it never commits independently.

## Source freshness and accepted knowledge

An assertion carries two independent lifecycle signals:

- `is_source_current` means the assertion is the latest valid claim from its
  data source for that subject and predicate. The legacy `is_current` column is
  retained as a compatibility mirror of this meaning.
- `is_accepted` means the assertion is the canonical value Atlas currently
  uses as knowledge. Operational `Asset` fields represent these accepted
  values.

A fresh discovery observation is source-current but is not accepted
automatically. Reconciliation may accept it and update the operational model.
Rejecting a proposed conflicting change keeps the observation source-current
and visible as conflicting while leaving the declared value accepted.

Predicate cardinality is defined centrally. `name`, `hostname`, `asset_type`,
`status`, `operational_state`, `observation_state`, `platform`, and
`lifecycle_state` are initially single-valued; interfaces, network membership,
relationships, owners, and dependencies are multi-valued. Service logic and a
partial database index ensure a single-valued subject/predicate has at most one
non-retracted accepted assertion. Multi-valued predicates may accept several
claims.

The `20260719_0011` migration copies legacy `is_current` into
`is_source_current`. It backfills acceptance only when exactly one confirmed,
source-current assertion matches an operational Asset value. Ambiguous legacy
claims remain unaccepted and surface as unresolved; no assertion or evidence
row is removed.

## Manual declarations and roll-up

Creating or changing a knowledge-bearing manual Asset field writes the
operational value and a confirmed, accepted, source-current `declared`
assertion in the same transaction. The previous accepted single value is
cleared and linked through `superseded_by_id`, and a `fact_changed`
`KnowledgeChange` records the actor and before/after values. A no-op edit writes
neither an assertion nor a change event. Conflicting active observations are
preserved and receive a contradiction reconciliation item.

`GET /assets/{id}/knowledge-summary` provides a deterministic predicate
roll-up: accepted values, latest source observations, assertion/source/history
counts, freshness, and conflict or unresolved state. The asset page uses this
as its default Knowledge view. Human history remains available as a timeline,
and complete raw assertions remain available in collapsed predicate groups.

## Discovery completeness and coverage

Every discovery run may declare a `coverage_key`, whether it is a complete
snapshot, and a completeness status. Each observed external identity is stored
in `run_observed_entities`. Evidence rows alone are not used as the coverage
index because an evidence payload can contain multiple entity kinds and is not
a stable statement of run completeness.

Absence detection runs only after a successful complete snapshot. Its baseline
is the latest prior successful complete run with the same data source,
customer, site, and coverage key. A first baseline, partial run, failed run, or
different coverage key cannot mark anything absent.

For each asset identity present in the baseline but omitted from the new run,
Atlas records an `observation_state=not_observed` assertion and one open
`no_longer_observed` reconciliation item. Repeated omissions do not duplicate
an open episode. The operational asset is never deleted or mutated by
detection.

## Absence decisions and re-observation

A reviewer can choose:

- mark missing;
- mark inactive;
- retire;
- keep active; or
- record an exception, optionally with a review date.

Accepting a lifecycle disposition records a meaningful change. Rejecting or
deferring does not mutate the asset. If the source identity is observed again,
Atlas supersedes the missing observation state, resolves any open/deferred
missing item, and records `entity_reobserved`. Missing or inactive assets get a
reviewable proposal to return to active. Retired assets remain retired until a
human explicitly changes them.

## Meaningful event rules

The timeline records discoveries, accepted entities and facts, relationships
added or removed, source identity links, missing/reobserved entities, accepted
lifecycle changes, and assertion rejection/retraction. Identical corroborating
observations only update assertion observation time and do not create noisy
`fact_changed` events. All list and summary APIs apply the normal customer/site
authorization scope.
