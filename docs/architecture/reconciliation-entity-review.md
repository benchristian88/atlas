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
