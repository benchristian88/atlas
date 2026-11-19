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
complete scalar partial database index ensure a single-valued canonical subject/predicate has at most one
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
cleared and linked through `acceptance_replaced_by_id`, and a `fact_changed`
`KnowledgeChange` records the actor and before/after values. A no-op edit writes
neither an assertion nor a change event. Conflicting active observations are
preserved and receive a contradiction reconciliation item.
Pending source-supersession changes flush under the canonical subject lock
before the accepted-set refresh, so refreshing accepted flags cannot erase
source history with production autoflush disabled.

`GET /assets/{id}/knowledge-summary` provides a deterministic predicate
roll-up: accepted values, latest source observations, assertion/source/history
counts, freshness, and conflict or unresolved state. The asset page uses this
as its default Knowledge view. Human history remains available as a timeline,
and raw assertions remain available in collapsed predicate groups. These views
are bounded: Asset Raw requests 200 rows by default (API maximum 1,000), and Fact
History returns at most 500. Asset detail does not page either view. Summary may
therefore count more retained assertions than these tabs display; retained data
is not deleted. Complete History/Raw pagination is a separate feature-ledger
follow-up, not a guarantee of the current UI.

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

For a Proxmox guest key bound to a retired Asset, the
[source identity hold](proxmox-guest-identity-containment.md) retains positive
evidence before canonical attribution. These keys do not generate normal
re-observation Changes while the identity review is pending.

Every absence acceptance requires the refreshed `expected_version`; a legacy
versionless request returns 409. The reviewed status and Asset update timestamp
are validated after locking/reloading the canonical Asset, detecting intervening
manual edits and changed-back values. `mark_missing`, `mark_inactive`,
`mark_retired`/`retire` write status and select a new operator-declared status
assertion through the normal replacement path. The previous declaration and its
replacement lineage remain retained. Changes binds the new declaration and the
supporting absence assertion, with the actual locked before/after statuses.
`keep_active` preserves the current status; `exception` preserves status and
records an explicit exception. Neither changes selected status knowledge.
Bulk cannot choose any of these dispositions.

## Meaningful event rules

The timeline records discoveries, accepted entities and facts, relationships
added or removed, source identity links, missing/reobserved entities, accepted
lifecycle changes, and assertion rejection/retraction. Identical corroborating
observations only update assertion observation time and do not create noisy
`fact_changed` events. All list and summary APIs apply the normal customer/site
authorization scope.

## Entity review and explicit group acceptance

The Reconciliation page presents independent records through a generic
[entity review projection](reconciliation-entity-review.md). Assets retain their
facts, relationships and owned Interface proposals in one review, including
children whose prerequisites are unresolved. An accepted parent stays visible
while matching child work remains. Read-only presentation never resolves source
identities or mutates accepted knowledge.

Accept asset decides only the parent record. Accept all is an explicit operator
request over reviewed record IDs/versions within the same authorized group. It
uses the individual acceptance, Changes, completeness and security-audit path,
checks dependencies again, and reports blocked/failed/already-resolved records.
It never accepts another entity as an implicit prerequisite. Legacy initial
Asset configuration remains part of its parent proposal; independently reviewed
assertions are excluded from implicit matching-assertion acceptance.

Explicit cross-source Asset/Network/Interface links retain canonical IDs and
source-specific provenance. A technical identity link records `source_linked`
and a reconciliation `linked` security audit, then opens a separate configuration
review with accepted values. It neither confirms configuration nor accepts source
facts. Current claims receive the canonical subject ID so subsequent observations
coalesce against the same identity. Conflicting Asset names likewise remain
unaccepted proposals. Independent acceptance/rejection/defer decisions preserve
the evidence and existing accepted configuration until an operator changes it.
See [cross-source review](reconciliation-entity-review.md#cross-source-identity-review).

## Asset knowledge state and relationship presentation

The summary distinguishes operational Asset fields from explicitly accepted
assertions. Identical source-current scalar values do not create ambiguity merely
because several assertions exist. With no accepted value, agreeing observations
are **Observed / Awaiting acceptance**; differing values remain **Unresolved**.
An accepted value that differs from a current observation is **Conflicting**.
Source agreement never grants acceptance. Rejected, retracted and non-current
observations do not contribute to active disagreement or active source counts.

The summary exposes `canonical_value`, its managed display label and
`canonical_consistency` (`matches`, `missing_acceptance`, `mismatch`, or
`not_applicable`). A legacy operational Asset Type may exist without an accepted
assertion: legacy direct sync wrote Asset columns without the assertion acceptance
path, and identity linking previously accepted only its name anchor. Historical
records are not backfilled or assigned fabricated decisions. Current linking now
opens explicit core-field proposals, including matching values. Subsequent
matching but unaccepted discovery fields also remain reviewable. Accepting such
corroboration records assertion confirmation rather than a fictitious field
change. Newly accepted Assets retain the existing initial-field acceptance
contract, and manual creation/editing retains declared accepted assertions.

Relationship presentation resolves canonical `object_id`, known historical JSON
target IDs, or exact source-scoped external links. It never resolves by target
name or trusts a name embedded in JSON. Managed Relationship Types supply labels;
the authorized target supplies its current name and internal link. Resolution
requires the subject's customer/site and the caller's `assets.view` scope.
Missing, inaccessible and malformed targets receive safe fallbacks without target
IDs, names or links. Fact History uses the same scoped relationship resolution.
Each returned Raw assertion retains its complete original value; no evidence is
rewritten. The bounded tabs do not expose every retained row without pagination.

The API retains per-assertion `accepted_values` and `latest_observations`, adding
`accepted_groups` and `observation_groups` for presentation. Relationship values
use safe semantic target data rather than unverified legacy JSON. A logical group
requires the same canonical subject, verified target, relationship type and scope.
Distinct same-named targets remain distinct. Unresolved external references never
merge across assertions. Every group retains its individual assertions, source
names, timestamps, acceptance actor and assertion IDs for provenance. Source counts
count distinct known contributing DataSources, not assertion rows or labels.

For example, two Proxmox sources may report one accepted LXC and one `runs_on`
relationship to the same verified host. The summary shows one accepted logical
relationship with two provenance entries; both assertions, evidence, Changes and
audits remain independently retained. Relationship cardinality remains multi-valued.
Metadata and target lookups are batched independently of assertion count.

## Observation lineage and acceptance replacement

Source observation supersession (`superseded_by_id`, source-current false) is
separate from accepted-value replacement (`acceptance_replaced_by_id`). Selecting
Source B does not close Source A's still-current observation or make it stale.
A repeated identical observation coalesces into the eligible current assertion;
a changed observation creates a new source claim with normal supersession lineage.
Retracted observations are not reused. Rejected proposals retain their explicit
decisions until a fresh human review; repetition never grants acceptance.
Replacement edges record the most recent replacement; the full history of
selections, including reselection of an older current claim, remains in Changes
and reconciliation decisions. Lifecycle safety checks count both kinds of lineage.

Migration 0032 classifies only provable retained legacy lineage and refuses
ambiguous or overwritten history, as well as conflicting retained scalar
acceptances, before DDL. It never invents a source successor from later matching
observations. See the [migration contract](../deployment/upgrades.md#reconciliation-integrity-migration-0032)
for conservative classification and downgrade limits. The database index follows the complete
`predicate_cardinality` contract, including unknown scalar predicates, rather
than only the eight initial keys. Object assertions, explicit multi-valued keys
and `interface.` predicates remain multi-valued. Accepted source-stale knowledge
remains selected until explicit replacement or retraction; freshness alone never
silently changes canonical knowledge.

The original proposal's `current_value_json` is retained historical context in
storage. For canonical Asset fields, API review values and tokens use the live
authorized Asset snapshot. Acceptance uses that same snapshot under lock and
records the actual persisted predecessor/successor in Changes. A fresh token
must never be paired with an old displayed value. Source evidence is unchanged.

Canonical subject locks, refresh-after-lock ordering, explicit flushes with
production autoflush disabled, and conflict responses are specified in
[ADR 0017](../decisions/0017-reconciliation-knowledge-integrity.md) and verified by
the [remediation acceptance record](../testing/cross-source-reconciliation.md).

New canonical-field proposals retain their exact original Asset update timestamp
in private proposal context for safe versionless validation. Field, value and
timestamp must all match under lock. Transaction timestamps are not commit-order
clocks, so a greater-than comparison against proposal creation is not sufficient.
Older proposals without that baseline require `expected_version`; no historical
baseline is guessed or backfilled. Unavailable/out-of-context canonical records
produce null current values rather than falling back to an original snapshot.

Changes and assertion inserts retain DiscoveryRun provenance through FK KEY SHARE.
Run writer serialization therefore uses FOR NO KEY UPDATE, allowing those FK
references while still excluding another state writer. This removes the upstream
Run/source provenance cycle; no lease fields or authorization policy change.

## R4-N1 technical ingestion serialization

Network/Interface ingestion uses the same canonical subject ordering as review
decisions. Before claim writes, `lock_ingestion_subjects` locks the scoped source
FOR NO KEY UPDATE, then only referenced existing Assets, Networks and Interfaces
FOR UPDATE in model/UUID order. Interface owner Assets and referenced Networks
participate; no identity is inferred or written by the prelock. Standalone
technical ingestion locks its operation before `record_assertion`.

AIP finalisation collects references across **all batches and domains** before
its first Asset or technical claim. This avoids acquiring a later Network UUID
or Interface owner under earlier claim locks. Complete-snapshot baseline and
current Asset identities join that set before absence/re-observation work.
Unreferenced entities remain independently writable; source-local writer
serialization and FK-compatible source/Run lock modes are preserved.

The corrected order prevents the cross-source cycle where ingestion holds A's
assertion and waits to mark B conflicted while acceptance holds B and waits to
replace A. It does not grant ingestion acceptance authority. Source observation
supersession, acceptance replacement, selected knowledge and evidence remain
distinct. If ingestion commits first and changes the reviewed proposal's epoch,
the old decision token returns 409; an operator must explicitly refresh.

The authenticated ingestion request, including admission locks and commit, also
uses the existing transaction-conflict boundary: SQLSTATE 23505/40001/40P01/55P03
rolls back the request and returns generic HTTP 409 without automatic retry.
Unknown database failures propagate. A failed completion does not seal the Run,
advance source success, publish partial claims or create a success audit.
The [current acceptance report](../testing/cross-source-reconciliation.md) records
natural concurrent races, real HTTP lock-timeout and post-flush rollback evidence.
