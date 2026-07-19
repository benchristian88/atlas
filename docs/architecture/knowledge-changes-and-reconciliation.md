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
