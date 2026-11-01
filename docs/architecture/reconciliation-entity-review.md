# Generic reconciliation entity review

Atlas presents reconciliation as an entity review without merging or replacing
its independent records, assertions, evidence, Changes or audit history. This is
a read-only projection over PostgreSQL; it adds no persistent grouping state and
requires no migration. Existing granular listing/decision routes remain compatible.

## Ownership and identity

The backend groups accepted entities by their durable type and ID. Unresolved
identities use exact customer/site/source/type/external-ID equality. External IDs
are opaque: their syntax and Connector identity never establish ownership.
Relationships belong to their source Asset; Interface proposals and facts belong
to the Asset identified by their configuration assertion or accepted source link.
Networks with independent review work retain their own entity card.

The oldest entity record provides the group's UUID anchor. Endpoints also accept
other scoped member IDs as aliases. Acceptance alone does not dismiss or replace
the parent. Existing manually curated Assets do not need a parent decision; linked
observations from different sources share their accepted Asset's group. Unlinked
identical external IDs from different sources remain separate identities.

Managed Asset/Relationship Type names provide labels. Fact presentation uses a
bounded `fact_metadata.label` when present, otherwise the generic humanized final
predicate segment. The complete source key remains in Evidence and details. No
Connector manifests, ingestion schemas or discovery behavior change.

## Additive API

- `GET /reconciliation-entities` accepts status/category/source/run/entity-type
  filters, entity-name search, section, limit and cursor. It returns entities,
  `record_total`, `entity_total`, matching status/category counts and next/previous
  cursors, including a snapshot-preserving return to the first page.
- `GET /reconciliation-entities/{id}` opens an authorized prerequisite with its
  open/deferred work and parent context, including across queue/page boundaries.
- `GET /reconciliation-entities/{id}/section` continues a bounded section using
  section, status/category and offset. Each response contains at most 20 items.
- `POST /reconciliation-entities/{id}/accept` accepts an explicit list of reviewed
  item IDs and proposal versions, with an optional reason. At most 1,000 records
  may be requested; larger groups remain individually reviewable.

A group contains parent context, matching counts, default expansion state,
Facts/Relationships/Network sections and the exact proposed bulk decision set.
Each item carries friendly labels/values, source details, a proposal version,
accept/reject/defer eligibility and named blockers with scoped entity jump IDs.
The browser renders this contract; it does not infer reconciliation dependencies.

Filtering chooses groups containing matching work. Only matching records appear
in sections and totals; the parent remains context even after acceptance or when
outside the category filter. Accept all includes an unresolved parent explicitly
and the matching unresolved children; it does not include hidden sibling work.
Deferred and resolved queues preserve their existing separate meanings.

Queue cursors bind the filters/context, snapshot upper record position and last
entity anchor. The deterministic order includes historical dependency metadata
within that snapshot, so changing a decision status does not shift subsequent
pages. New arrivals are included on refresh. Relationships and technical
prerequisites determine review order; stable UUID tie-breaking breaks cycles.
The order expresses prerequisites for review, not an infrastructure tree or an
operational impact conclusion. Identity linking/merging or changes to underlying
proposal ownership may require refreshing a cursor.

## Decisions, prerequisites and concurrency

Accept asset calls the existing individual operation. It accepts the parent
record, preserving independent fact, Interface and relationship decisions. The
existing initial Asset configuration remains part of its proposal. Independently
reconciled assertions are excluded from automatic matching-assertion confirmation.

Accept all verifies every supplied ID belongs to the same authorized group,
locks records/assertions in a deterministic order, checks proposal versions and
rebuilds eligibility between Asset, technical configuration, fact and relationship
phases. Every accepted record uses the same authorization, acceptance, Changes,
completeness and audit code as an individual acceptance. Per-item savepoints
retain successful decisions when a later child fails. The response reports
`accepted`, `already_resolved`, `blocked` and `failed` with explicit reasons.

A relationship waiting on another Asset never creates or accepts that Asset.
An Interface waits for its Asset and any referenced Network; its facts wait for
the Interface. No-longer-observed records require an individual lifecycle choice
and remain unresolved by Accept all. Reject and Defer stay individual operations.

Individual decisions use row locks and optionally accept `expected_version`.
The new UI always sends it. Versions cover item status/proposal and assertion
content/freshness, preventing a coalesced or concurrently decided proposal from
being accepted using an outdated review. Retracted, superseded and source-stale
proposals cannot be accepted. Source identity attachment stays scoped to its
customer, site and source.

## Authorization and performance

Every projection, parent, prerequisite, total, search and focused lookup uses
backend reconciliation scope plus the active customer/site context. Accepted
entity and source lookups use that same scope. Group decisions independently
validate membership and decision permissions, including relationship/network
permissions. Cross-scope IDs return no names or existence details. No raw evidence,
receipts, diagnostics, Integration configuration or credentials are loaded by the
projection. GET requests do not persist identity resolutions.

The request-local review index uses eight batched SELECTs, independent of card
count. It reads scoped reconciliation history and only the referenced source
links, Assets, Interfaces, Networks and source names, plus managed taxonomy, to
compute whole-queue totals and global cycle-safe ordering. Work and memory are
linear in this scoped index; returned pages are bounded to 50 entities by default
(maximum 100), with at most 20 initial items per section. This targets queues of
hundreds or thousands of records without an N+1 label/dependency lookup. Very
large retained histories may justify an SQL metadata projection or caching later;
neither a second source of truth nor persistent group state is introduced here.

## UI and navigation

New unresolved entity cards expand initially; existing/accepted entities start
compact. Both use one component with shared identity, status and Button primitives.
Small sections open directly; larger sections collapse independently. Blocked
counts and conflict/warning summaries remain visible while collapsed. Technical
keys and full normalized proposals live in Evidence and details.

Queue/search/section/cursor/focus state lives in the URL. Review prerequisite
links expand and focus a target even on another page. Refresh and browser Back
retain the destination; Return to previous entity restores the original query,
cursor and entity focus. Same-route query changes use Next's integrated native
History API; review data is fetched by the client. Workspace changes invalidate
outstanding UI responses.

Automated evidence lives in the backend entity/listing tests, frontend component
and navigation tests, and `apps/web/scripts/check-reconciliation-browser.mjs`.
The browser script intercepts all API calls and never decides operator data.

## Cross-source identity review

One accepted Asset, Network or Interface may have independent source-scoped
`EntitySourceLink` records. External IDs and bridge names are opaque source keys;
matching display names never authorize a connector identity merge. Explicit
`link-asset` and `link-technical` decisions retain canonical UUIDs and the other
sources' links. No schema migration or additional identity subsystem is required.

The review projection exposes `technical_identity`, `can_link_technical`,
`link_asset_id` and `link_blocked_reason`. The Interface owner is resolved from
the configuration assertion's source-specific Asset link. Linking needs that
owner, but does not require a referenced Network to have been resolved already.
The UI lazily pages the existing `/asset-interfaces?asset_id=…` or `/networks`
API. Interface choices belong to the accepted owner; Network choices match the
exact customer/site. Candidate APIs require `networks.view`, while linking
requires `reconciliation.decide` and `networks.edit`. The mutation independently
checks customer, site, source, entity type and Interface ownership. Active
customer/site context also constrains individual decisions and linking; hidden
targets return generic errors without their identifying details.

Linking accepts the identity decision, not the observed technical configuration.
It retains an open `changed` proposal with accepted and observed values. Current
source claims receive the canonical subject ID, without accepting their facts.
MAC/IP, primary status, Network membership, VLAN/CIDR/gateway changes still need
explicit acceptance; rejection/defer preserve operational values. Source facts
such as bridge names and VLAN tags remain independent assertions and never
silently map a bridge to an Atlas Network. An Asset's conflicting observed name
also remains a separate proposed change after linking.

After every mutation the UI refreshes the current queue/focus. Backend eligibility
uses authoritative scoped links, not an accepted parent badge. An Interface
configuration can therefore still wait for a Network after its identity is
linked, while facts about that existing Interface are eligible independently.
The existing duplicate-name checks intentionally return HTTP 409 directing the
operator to link. Bulk acceptance reports that guard as an individual failure,
retains independent successes, and never performs the link automatically.

Link requests optionally accept `expected_version` for existing API consumers;
the UI always supplies it. Technical configuration versions also include the
current accepted fields, preventing an older review from overwriting intervening
manual or source decisions. Individual and bulk version checks lock existing
technical targets before comparing these values. Both link services reject retracted, superseded,
source-stale and mismatched assertion identities even without a version. Decision
routes lock relevant DataSources in UUID order before canonical subjects, items and assertions;
bulk requests use the same order and refresh eligibility during processing.
Source-link helpers also lock their DataSource before checking or inserting a
link. This serializes competing decisions even when the source identity has no
link yet. Existing source/type/external uniqueness and scoped target foreign keys
remain the database integrity boundary. Interface creation locks its accepted
owner around duplicate-name checking; configuration updates lock their target.
Concurrent database failures return a reviewable conflict. Per-item savepoints
remain intentionally non-atomic at group level. Source-link knowledge changes
and reconciliation security audit events commit with the decision.

See the [operator procedure](../admin/cross-source-reconciliation.md) and
[regression acceptance record](../testing/cross-source-reconciliation.md).

Asset identity linking now makes unaccepted core-field claims independently
reviewable, including matching Asset Types. It does not silently accept them.
This closes the earlier path where an accepted Asset badge coexisted with an
operational type but no accepted matching type assertion and no field proposal.
The Asset knowledge summary reports operational/assertion discrepancies explicitly;
see [knowledge-state semantics](knowledge-changes-and-reconciliation.md#asset-knowledge-state-and-relationship-presentation).

## F1–F5 transaction and integrity correction

Production `SessionLocal` uses `autoflush=False` and `expire_on_commit=False`.
Linking flushes the accepted identity decision before `create_item()` checks for
an open review of the same assertion. The follow-up, immutable source association,
Changes and audit commit together; a failure rolls the whole link back. Linking
never accepts a conflicting name or technical configuration implicitly.

Asset field versions now include the current canonical operational field under
review. Individual and group decisions lock/reload that Asset before checking the
version. Manual Asset PATCH uses the same Asset lock before deriving declarations.
All eight supported fields participate. A stale review returns 409 or a failed
bulk entry and preserves the newer value. Fresh review is required to deliberately
select the observation. A versionless Asset field request must match its retained original field/value
and exact canonical update timestamp. New items retain that timestamp as private
proposal context; older items lacking it require a reviewed version. Comparing
`updated_at > created_at` is insufficient because PostgreSQL timestamps use
transaction start: overlapping PATCHes can commit after proposal creation with
earlier timestamps. A versioned fresh review can supersede the original snapshot.

R1 correction: the backend derives `current` and `current_value_json` from the
authorized canonical Asset, using the same `canonical_asset_snapshot` function
used by the version and acceptance Changes. The stored item snapshot is the
original proposal context, not the current operational value. A refresh displays
the actual manually changed value being approved. Under the Asset lock, Changes
records the actual predecessor and persisted successor for all eight fields.
An additional PATCH, including a changed-back value, invalidates that review.
Unavailable or out-of-context canonical targets return null current values,
never the original proposal as current. The frontend renders the supplied current values and forwards the supplied
version for individual and bulk decisions; it does not reconstruct a snapshot.

R2 correction: every acceptance of `no_longer_observed` requires
`expected_version`, including `keep_active` and `exception`. Versionless legacy
absence acceptance returns 409 even when the original snapshot still matches.
Refresh and send the displayed version. Status-writing dispositions are
`mark_missing`, `mark_inactive`, `mark_retired` and its `retire` alias. They select
an explicitly accepted operator status declaration through normal assertion
replacement, even when the operational column already matches the choice.
Matching current manual declarations coalesce; mismatched historical declarations
remain retained. `keep_active` preserves the current status
(despite its legacy name); `exception` records a lifecycle exception without
changing status. Neither silently promotes status to active. All remain
individual lifecycle choices and are blocked by bulk acceptance.

The complete lock and concurrency contract is [ADR 0017](../decisions/0017-reconciliation-knowledge-integrity.md).
Canonical subject locks serialize different sources. Prior accepted rows are
refreshed after waiting so a bulk request cannot retain pre-lock accepted flags.
The complete scalar uniqueness index is a final database boundary. Two serialized
namespaced decisions may both succeed; the later selection replaces the earlier
one, with both decisions retained. Canonical-field versions may instead reject
the later stale request. Identical scalar selections still have one effective
accepted assertion; independent observations remain visible.

Asset linking refreshes only relationships from the same DataSource whose subject
or object is the newly linked external identity. It uses `persist_links=False` and
never acquires an unrelated source lock. The review projection still resolves
current prerequisites read-only. Unknown database failures propagate; SQLSTATE
23505, 40001, 40P01 and 55P03 produce a safe reviewable conflict. No automatic retry
or partial identity-link transaction is allowed. Group savepoints continue to
retain independent successes.

R4 correction: source rows use **FOR NO KEY UPDATE**, including ingestion,
source-link helpers, decisions and assertion retraction. This serializes source
writers while permitting implicit foreign-key **KEY SHARE** locks from new
manual assertions. Canonical subjects retain **FOR UPDATE**. Using FOR UPDATE
on a source before waiting for an Asset would form a cycle with a manual PATCH
holding that Asset and inserting an assertion. Manual PATCH shares the expected
transaction-conflict guard. Both request orders and rollback after flushed
writes are covered by `test_reconciliation_final_integrity.py`.

Ingestion prelocks only already-linked Assets referenced by its current batch,
including relationship endpoints, before changing claims. Later corroboration of
an existing relationship may declare manual knowledge and reacquire that Asset;
it must never first hold an assertion and then wait for the canonical Asset.
The synchronized cross-source ingestion/acceptance race and a held unreferenced
source-linked Asset verify ordering and limited lock scope. Identity resolution
and discovery decisions remain unchanged.

DiscoveryRun writer rows use FOR NO KEY UPDATE as well. Upstream control retains
its Integration → Run → Source ordering; reconciliation references the immutable
Run through FK KEY SHARE without acquiring a run writer lock. This prevents a
Run → Source → Run provenance cycle while retaining exclusive run state writers.
Lease/admission/authorization policy is unchanged.

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
