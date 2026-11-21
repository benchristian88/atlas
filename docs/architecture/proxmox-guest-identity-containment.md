# Proxmox guest identity containment

## Pass 1 requirements

At `e7d4915`, a later successful Proxmox run using the same guest key can
attribute observations to a retired Asset before a review decision. A complete
run can also record that the old Asset was observed again. This occurs even if
the later observation has the same name and Interface configuration. The
Proxmox 0.2.2 key identifies a guest slot within that source. Name, MAC, Network
and node placement are comparison evidence.

| Requirement | PostgreSQL regression |
| --- | --- |
| Hold a positive LXC or QEMU observation using the exact source binding and the locked Asset lifecycle. Retain the receipts, guest, Interfaces and relationships. Preserve the retired Asset, accepted configuration, source freshness, selected assertions, Changes and audit history. Process unrelated observations. | `test_reused_key_is_held_before_attribution` |
| Hold a valid `runs_on` observation that omits the guest and its Interfaces, including when the guest was linked to a differently named Asset and its proposed source fields were never accepted. Keep the relationship membership unresolved and preserve the prior Asset, source freshness, relationship and accepted history. Process unrelated observations, replay the seal and keep one pending review across later runs and manual status edits. | `test_relationship_only_opens_hold_after_link_without_accepted_guest_fields` |
| Validate both relationship endpoints. Reject an unbound host, a guest in the host role, a guest linked only to another source and an active omitted guest without accepted source fields. An ordinary `runs_on` observation with an active omitted guest and accepted source fields still resolves through relationship review. | `test_relationship_only_rejects_invalid_bindings`, `test_relationship_only_resolves_active_guest_with_accepted_fields` |
| Hold an unchanged return as well. Preserve active guest identity through ordinary rename, Interface changes and node moves. | `test_unchanged_guest_still_requires_identity_review`, `test_active_guest_changes_follow_ordinary_review` |
| Preserve complete-snapshot comparison by coverage. Partial success may provide positive evidence. Partial and failed omissions carry no absence authority. Exact replay is idempotent. Later evidence invalidates earlier review versions, and older completions preserve the latest version. | `test_coverage_and_review_order` |
| Scope the review by customer, site and source. Block ordinary and bulk acceptance and linking of held evidence, including already-open proposals. A manual Asset status update preserves the unresolved hold. | `test_review_scope_and_decision_guards` |
| Serialize retirement and completion and commit the hold with the successful seal. Concurrent/repeated completion produces one pending review, and a rolled-back seal preserves the receipts for retry. | `test_completion_serializes_with_retirement`, `test_concurrent_exact_completions_and_database_conflict`, `test_completion_prelocks_guest_named_by_unlinked_interface_slot` |

The regression uses synthetic messages shaped by the unchanged Proxmox 0.2.2
release fixture. Separate local diagnosis exercised the same release's
normalizer with synthetic Proxmox inventory. Both run against disposable
PostgreSQL. Live Connector execution and deployment require separate validation.

## Hold before attribution

Successful AIP completion classifies held evidence after acquiring the existing
DataSource and ordered canonical subject locks. The scoped binding is the exact
DataSource, customer, site, `asset` entity type and external key. The
historical Asset's locked lifecycle determines the initial hold. The published
`guest/lxc/{vmid}` and `guest/qemu/{vmid}` keys are limited to the Proxmox
Connector. Renames, MAC changes and node moves on active guests follow ordinary
reconciliation.

The held set includes the guest, its Interface observations and relationships
with the guest at either endpoint. A matching Interface source binding also
protects its old owner when the observed owner differs. An Interface or
relationship referencing a retired guest can start the hold when the run omits
the guest payload. For a relationship, completion first classifies the hold
under the source and canonical subject locks. If the omitted endpoint has no
accepted Asset evidence, the exact scoped Proxmox guest binding and its typed
slot key can validate that endpoint for evidence retention. The relationship
must be part of the hold, the manifest must allow the guest class in that role,
and the other endpoint must also pass validation. Invalid references fail
before a review is written. Relationships proceeding to ordinary attribution
still require accepted Asset evidence for omitted endpoints. Receipts and
per-run evidence retain all original records, and held membership stays
unresolved. Held observations bypass Asset resolution,
normal assertion coalescing, Interface configuration and fact attribution,
relationship corroboration and source-link freshness. Independently observed
Networks and other entities still process normally.

The existing reconciliation item represents an unresolved possible identity
match. Its dedicated `source_identity` type keeps its scope and workflow
distinct from ordinary Asset proposals. Each successful run affecting it records
a source-key observation in the existing assertion table. The assertion has no
canonical subject or object ID, references the run and an EvidenceRecord, and
retains the exact EvidenceRecord IDs of every held dependent. The case's prior
accepted snapshot is comparison context. Its evidence pointer and preview
update only for newer evidence. The card previews up to eight Interfaces and
eight relationships per side. Server run start orders runs, with
observation time and run UUID as tie-breakers. Earlier evidence remains
queryable in its original run and in the case's source-key assertion history.

Exactly one open case per scoped key is maintained by the existing Source
writer lock. This is application-level serialization under ADR 0017 and uses
the existing tables and receipt identity. The case, evidence version, unrelated
attribution and run seal commit in a single finalisation transaction. Exact
completion replay returns the original seal. A failure rolls back finalisation
while retaining the already committed receipts and evidence. The reviewed item
version includes the referenced observation and its payload. Ordinary decision
paths check the hold again under their source and subject locks. Generic
assertion removal or retraction cannot dispose of identity evidence.

The open queue and its counts require scoped reconciliation and Asset view
permissions. Prior accepted Interfaces and Network assignment also require
Network view. Prior accepted relationship labels require relationship view,
with both endpoints in the review scope. Source observations are labelled as
evidence. The review has no ordinary decision controls. An explicit manual
Asset edit still works and leaves any existing identity hold open. Simulations
that select a Proxmox DataSource cannot submit evidence for a held or retired
guest key.

Positive evidence from partial success can start or update a hold. Failed runs
retain staged evidence and cannot change the review. A successful comparable
complete run still compares external-key presence, while pending cases are
excluded from normal absence and re-observation decisions. This preserves the
old guest's observation state without asserting it returned.

## Pass 1 design handoff

This section records the original Pass 1 handoff. The current implementation is
described in the [operator decision contract](#operator-decision-contract).

Pass 1 retains evidence and preserves the historical source binding. Pass 2
needs explicit **Reactivate** and **Accept as replacement** decisions, binding
history and versioned application of reviewed evidence. The policy for deliberate
manual reactivation before the first hold is a separate Pass 2 question. Pass 1
uses the Asset status read under lock to decide whether to open the first hold.
Correction of previously affected inventory, including the reported `1029`
case, requires a separate, non-destructive review.

For owner review, **Reactivate** should keep the original Asset and Interface
identities, write an explicit lifecycle declaration with Change and audit, then
release the reviewed observations to ordinary field, Interface and relationship
review. **Accept as replacement** needs a new Asset UUID and a single transaction
to end the old Asset and Interface source bindings and attach current bindings
to the new guest. Existing bindings have lifetime uniqueness on
`(data_source_id, entity_type, external_id)`. A proposed migration would add
binding validity and decision provenance, preserve existing rows as current,
and enforce at most one current binding per key with partial uniqueness.

Review every operational alias lookup for current-only behaviour. Historical
reads and deletion protection need access to ended bindings. Tie released
observations, reopened proposals, replay and absence comparisons to the binding
they were reviewed against. Broad attachment by external key today can retarget
assertions, particularly on Interface acceptance. A migration and its deployment
and restore strategy need independent review, including PostgreSQL tests for
data preservation, competing decisions, stale proposals and rollout compatibility.
An active replacement between scans still requires stronger source identity
evidence or explicit operator intervention.

## Operational cutover contract

Checkpoint 2 builds on [ADR 0019](../decisions/0019-proxmox-guest-identity-resolution.md)
and revision `20261119_0033`. The scope of a source alias is its DataSource,
Customer, Site, entity type and external key.

| Lookup | Binding rule |
| --- | --- |
| Asset resolution, technical linking and freshness | Use the current scoped binding. Creating a successor Interface through ordinary review requires its current Asset owner and normal Network prerequisites. |
| AIP prelocks, omitted endpoints, holds, simulations and absence comparison | Prelock current targets before claims. Proof for an omitted relationship endpoint belongs to the current canonical target. Simulations on a live source cannot apply evidence for held, unacknowledged or decided guest slots. |
| Ordinary reconciliation and conflict detection | Use the latest decision for the relevant guest family, including typed relationship endpoints and Interface aliases and owners. Earlier proposals remain visible in history and leave the actionable queue. Unrelated guest proposals retain their boundary. |
| Historical summaries and reconciliation | Prefer recorded canonical IDs. Resolve a retained alias at the recorded attribution epoch if proven. Leave an ambiguous historical reference unresolved. Apply existing Customer and Site read scope before displaying targets. |
| Provenance and deletion guards | Check all retained links, including ended Asset and Interface bindings. Keep the existing typed ownership constraints and deletion restrictions. |

Admission captures the DataSource epoch under its writer lock. Dispatch and
unsealed completion compare the stored epoch under the same lock. An obsolete
run fails in full with `identity_epoch_changed` and preserves committed
receipts and staged evidence. A terminal callback failure reaches the existing
runtime settlement path. An exact sealed replay returns the stored result.

Live guest-family assertions use the run epoch. A later run can coalesce an
equal observation only within its guest-specific decision boundary. The first
complete, comparable live membership for the current binding supplies the new
absence baseline. A simulated, held or partial membership cannot supply it.
An unacknowledged retirement continues to trigger review after manual activation.
Reactivate acknowledgement is keyed by the binding ID and retirement revision.

The [PostgreSQL cutover regressions](../../apps/api/tests/test_proxmox_guest_cutover_postgres.py)
use explicit decision and binding storage fixtures. They exercise existing
discovery and reconciliation entry points following fixture cutovers.

## Operator decision contract

The [operator action](reconciliation-entity-review.md#additive-api) gets its
DataSource, Integration, scope, guest key, binding and reviewed evidence from the
case. The transaction takes Integration, DataSource, ordered canonical subjects,
review item and assertion locks. It reads the sealed run without a Run writer
lock. It compares a version covering the selected evidence, canonical row
revisions and relevant mappings after reloading the scoped grants and records.

Both identity decisions compare qualifying sealed, successful Proxmox runs for
the same Integration, DataSource, Customer, Site, coverage key and guest object
class. Complete and partial runs can supply positive evidence for a guest
explicitly observed in that run. A held Asset membership confirms presence even
when its Asset UUID is unassigned. Verified relationship-only evidence can
supply a Reactivate comparison without an Asset membership. Only a qualifying
complete run can establish an omission. Failed and simulated runs are outside
this comparison. The evidence window begins
at the current binding's opening epoch or the latest identity decision for this
guest slot, whichever is later. Reactivate keeps the Asset binding and starts a
new evidence window. Replacement ends the old binding and opens the successor's
window, including when it reuses the same VMID. An unrelated guest decision
leaves this window intact, so comparable runs can span multiple source epochs.
At seal, Atlas records whether each hold establishes positive guest evidence
alongside the retained receipt and claims. Diagnostic holds stay in history.
The preview prefers a qualifying positive and orders qualifying positives by
server run start time. When two qualifying runs tie, ingestion keeps the
current preview and both claims. GET and locked POST compare the same sealed
evidence and require a fresh discovery for a tie or a newer complete omission.

Current ownership, mappings and accepted corroboration determine what the
selected comparison can release. Retraction changes release eligibility and
preserves any established conflict. The confirmation version includes the
sealed conflict, scoped Changes and sealed observations of corroborating
Assets. A previously used proof cannot restore an earlier version after
retraction or discovery refresh. Assertion retraction
and identity decisions serialize on the DataSource writer lock. A later
unambiguous positive supplies a new comparison for explicit confirmation.
The post-decision absence baseline continues to require an attributed complete
run.

Read-only review responses recheck the selected case evidence after building
the comparison. A concurrent update to the selection returns HTTP 409 with a
refresh message. This recheck uses a plain read and takes no writer locks.

The release checks hashes for the original receipt and each held payload, exact
run membership, pinned Connector manifest and mappings, typed owners and
relationship roles. A guest with reviewed relationship-only evidence can
establish its own side of a relationship in Reactivate. The other endpoint needs
positive run evidence or an accepted assertion on its exact binding. An unlinked
host remains a normal prerequisite. Each eligible record yields fresh proposals
at the decision epoch.
The original run, receipt, membership and presence assertion are preserved.
Changes record released and withheld evidence; the card applies Network and
relationship visibility when explaining withheld observations.

Only the Replace branch ends links. It checks the exact case guest, verifies that
only one current guest slot owns the old Asset in this source, and checks Interface
alias ownership before ending applicable links. The database guarantees one
current source key and a decision FK for an ended epoch. The application verifies
that those records belong to this exact Replace. The epoch, decision, lifecycle or
binding changes, proposals, Changes and audit commit together.

The [application decision tests](../../apps/api/tests/test_proxmox_identity_decisions_postgres.py)
use the scoped HTTP routes and disposable PostgreSQL. Browser fixture checks,
hosted CI, deployed upgrades and live Connector acceptance are separate.
Previously misattributed data still requires its own review.
