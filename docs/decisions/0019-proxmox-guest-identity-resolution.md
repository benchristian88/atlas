# 0019 — Resolve Proxmox guest identity reviews with retained source bindings

Status: **Proposed**

Date: 2026-11-19

## Context

The design baseline is `9f328be60f88a05fc7a546653845534683a19863` on
`design/proxmox-guest-identity-resolution`. The checkout and local `dev` were
at the merge of [Pass 1, PR #71](https://github.com/benchristian88/atlas/pull/71).
The [Pass 1 requirements](../architecture/proxmox-guest-identity-containment.md)
and its merged regression include the omitted-guest `runs_on` correction. The
PR discussion contains no independent review artifact. The baseline below
comes from the merged code and tests.

Signed Proxmox Connector `0.2.2` reports `guest/lxc/{vmid}` and
`guest/qemu/{vmid}`. Each key identifies a slot within one DataSource. Names,
MACs, Network attachment and node placement are comparison evidence. A replacement
of a still-active guest between scans can look exactly like an ordinary edit.
Keep ordinary active-guest reconciliation and leave Connector, AIP and
Catalogue 2 contracts as published. Previously misattributed observations,
including guest `1029`, require a separate owner-reviewed investigation.
[Catalogue 2 release reference](../deployment/catalogue2.md), [0.2.2-shaped PostgreSQL fixture](../../apps/api/tests/test_proxmox_guest_identity_postgres.py#L125).

### Current storage and boundaries

| Record or path | Pass 1 at the design baseline |
| --- | --- |
| Receipt and raw evidence | `accept_batch()` stages `DiscoveryBatchReceipt` keyed by `(discovery_run_id, sequence)` with body hash and payload, a scoped `EvidenceRecord` for each row, and `RunObservedEntity` keyed by `(discovery_run_id, entity_type, external_id)`. Held membership has `entity_id = NULL`. A successful seal keeps original receipt and payload history. [AIP staging and finalisation](../../apps/api/app/services/aip_ingestion.py#L109), [models](../../apps/api/app/models.py#L1218). |
| Case | One open `ReconciliationItem` per scoped guest slot, serialized by the source writer lock. `entity_type = source_identity`, `category = possible_duplicate`, `entity_id` is the existing Asset UUID and `candidate_external_id` is the guest key. `current_value_json` captures the accepted preview at first hold. `assertion_id` and `observed_value_json` track the latest held evidence by server run start, anchor observation time and run UUID. [Pass 1 review writer](../../apps/api/app/services/proxmox_guest_identity.py#L151). |
| Evidence lineage | Per affected successful run, a `source_key_present` assertion with `subject_type = source_identity` and no canonical subject or object links to the run and an anchor EvidenceRecord. `value_json` holds `guest_observed` and all `held_evidence_ids`. Older assertions retain their evidence and source-supersession lineage. Exact replay returns the original seal. Failed runs provide no eligible hold evidence. [Review writer](../../apps/api/app/services/proxmox_guest_identity.py#L187), [completion](../../apps/api/app/services/aip_ingestion.py#L210). |
| Relationship-only case | The guest can be manually linked to a differently named Asset and retired while its own source fields remain unaccepted. A valid `runs_on` record can be the only evidence. Its membership remains unresolved, its EvidenceRecord anchors the hold assertion, and `guest_observed` is false. During hold validation the exact scoped guest binding and typed slot can provide the missing endpoint class. The other endpoint still needs valid same-source evidence and the manifest must permit each role. [Reference validation](../../apps/api/app/services/aip_ingestion.py#L172), [LXC/QEMU regression](../../apps/api/tests/test_proxmox_guest_identity_postgres.py#L291). |
| Decision and lifecycle | Ordinary decisions reject Identity items and recheck dependent proposals, including links, under source and canonical locks. Manual Asset PATCH uses the Asset row lock. The first hold currently depends on the locked retired status. An open hold survives a manual status edit. Absence uses comparable complete runs, with held guest keys excluded. [Identity guards](../../apps/api/app/services/proxmox_guest_identity.py#L34), [manual PATCH](../../apps/api/app/routes/assets.py#L335), [complete snapshot](../../apps/api/app/services/discovery_observations.py#L217). |

## Decision

### Operator decisions and comparison

Add one dedicated item decision action with `{outcome, expected_version, reason}`,
where the server requires a reviewed version and a nonblank reason. Infer the
source, scope, key and targets from the case. Apply the existing request context
and exact customer/site scoping with `reconciliation.view`, `reconciliation.decide`
and `assets.view` for either decision. Existing individual, linking, generic
reject/defer and group acceptance routes keep their Identity guards. The case
closes through the dedicated action with `accepted` item status and a separately
recorded outcome. Its presence assertion remains observed evidence.

| Outcome | Before and permission | Confirmation text | After, including records changed and retained | Audit and next discovery |
| --- | --- | --- | --- | --- |
| **Reactivate existing Asset** | Open case, matching current binding, verified latest successful evidence and Asset retired or already active. Requires `assets.edit`. An eligible relationship-only hold is sufficient. | “Confirm this is the same guest and set the existing Asset to active. Changes to name, MAC, Network assignment and relationships will require separate review.” If already active, show “This Asset is already active. Confirm it is the same guest to release the held evidence.” | Retired becomes active through an explicit declared status and normal acceptance replacement. For an already active Asset, retain the status and its accepted declaration and record the explicit identity confirmation. Keep the original UUID, binding, Interfaces, assigned Networks, relationships and historical records. Release the eligible reviewed payload as ordinary proposals. | Commit a lifecycle or identity-confirmation Change and a dedicated audit with the case, actor, reason, original binding and reviewed run. Subsequent eligible runs use the original UUID and normal review. A later retirement can start a fresh hold. |
| **Accept as replacement** | Open case, matching current binding, old Asset still retired and a guest Asset observation in the latest reviewed evidence with a valid name and active scoped Asset type mapping. Requires `assets.edit`, `assets.create`, `networks.view` and `networks.edit` in the case scope, consistently even when there are zero Interface bindings. | “Create a new Asset for this guest slot. The retired Asset and its history will be retained. The previous guest and applicable Interface source bindings will end. Review the new guest’s Interfaces and relationships separately.” | Allocate a fresh UUID and establish a current guest binding. End the old guest and applicable same-source Interface bindings together. Retain the old retired Asset, Interfaces, assigned Networks, relationships, prior accepted records and every other DataSource's links. Seed the new Asset from required creation fields only, using the reviewed name, mapped type, scope/workspace and existing active default. Put optional observations and eligible dependants into ordinary review in the same commit. | Record the replacement and new Asset creation in Changes and one identity audit containing old/new Asset and binding IDs, ended binding IDs, actor, reason and reviewed run. The next eligible run resolves the key to the new UUID. Interface and relationship proposals use that new owner and still require their normal decisions. |
| **Leave pending** | Open case. Read access requires `reconciliation.view` and `assets.view` in the case scope. | “Leave the identity review open.” Closing or leaving the review is sufficient. | Keep the item open, bindings intact and evidence staged. Atlas needs no dedicated Defer write. | A non-decision produces no Change or decision audit. Later successful evidence can update the same case and invalidate a reviewed version. Held evidence remains ineligible for ordinary and bulk decisions. |

Reuse the validation and construction rules behind ordinary discovered Asset
creation, including active customer/site and managed type checks. Factor the
construction step from `_accept_new_asset()` for the explicit fresh-UUID branch.
That helper currently runs duplicate resolution, creates optional Interfaces
and broadly attaches assertions. The replacement branch takes no name, hostname
or `Asset.external_id` match and invokes no bulk acceptance of matching fields.
Use the existing discovery convention of `source_integration_id = NULL`. The
legacy `uq_assets_source_external_id` is on `(source_integration_id, external_id)`.
Record the creation attributes and their reviewed evidence as part of the new
Asset's creation Change. The scoped source link is the binding authority.
[Existing creation](../../apps/api/app/services/reconciliation.py#L251), [manual scope and lifecycle checks](../../apps/api/app/routes/assets.py#L229), [Asset constraint](../../apps/api/app/models.py#L1689).

If the latest hold omits the guest, disable replacement and say “Run discovery
with this guest included to review it as a replacement.” An earlier staged
guest or the old Asset's name and type cannot fill in the missing observation.
If the current Asset is already active, disable replacement and say “This Asset
is active. Confirm the same guest, or review its lifecycle before choosing a
replacement.” Other manually chosen statuses such as inactive or missing keep
the hold pending until the operator deliberately chooses active or retired via
the normal lifecycle workflow. Show the actual current status and reason for
unavailability. An unmapped or inactive type requires valid mapped inventory
before replacement. The server rechecks every prerequisite.

Manual activation **before** a hold changes status only. Propose an Asset
retirement revision that survives subsequent status edits. A positive observation
opens a hold when its current guest binding has an unacknowledged retirement
revision, including after an operator has already set the Asset to active.
Ack is specific to the binding and revision, with a successful Reactivate
decision as its record. Existing proposals also check the unacknowledged
retirement guard before applying, even before new discovery opens a case.
Manual status edits **after** a hold leave the case open
and invalidate an earlier version. Reactivate in the already-active case records
the explicit confirmation without reapplying or undoing the lifecycle change.
Retirement and discovery keep the [AT-B01 boundary](../admin/asset-retirement.md).

Show **First-hold snapshot**, **Current source evidence**, and the live accepted
Asset status separately. The first snapshot is the state captured when Pass 1
or Pass 2 first held that case. It may already contain earlier incorrect
attribution. Keep the snapshot immutable and use the latest held assertion's
run and anchor timestamp to label source evidence. Include a clear missing-guest
indicator when its payload was absent, with Interface and `runs_on` sections
labelled as observations. Preserve preview bounds of eight entries per section.
Apply `networks.view` to Interface and Network details and `relationships.view`
plus readable scoped endpoints to relationship details on both sides, including
counts, labels and links. New snapshots retain scoped record/endpoint IDs for
authorization. When a legacy snapshot lacks identifiers to prove current
relationship visibility, retain it in storage and withhold those historical
labels and counts. Never resolve a historical key through its new binding for
display. Current evidence previews use typed fields and case-scoped lookups,
with no raw receipt or credentials in the response. Apply the same rules to
flat and grouped reads and omit unauthorized evidence from decision responses.

### Binding history and versioning

Retain ended rows in `entity_source_links`. The alternative is a current-only
link table with a separate archive of copied bindings. That reduces changes to
some lookup queries, but every historical consumer must consult two stores and
an existing link UUID would move or be duplicated at cutover. Interface owner
and scope constraints would also have to be maintained in both stores. It
would still need a run and proposal boundary. Retained rows keep the same
binding UUID and typed foreign keys for current and historical attribution.

Today `uq_entity_source_links_source_type_external` enforces lifetime uniqueness
on `(data_source_id, entity_type, external_id)`. `target_identity` selects one
typed target. `fk_entity_source_links_asset_context` references
`assets(id, customer_id, site_id)` with `CASCADE`. Technical links have
`fk_entity_source_links_network_context`, `fk_entity_source_links_interface_owner`
to `asset_interfaces(id, asset_id)`, and `fk_entity_source_links_interface_context`
to the scoped owning Asset, all with `RESTRICT`. The link's source FK currently
cascades from `data_sources.id` and its site FK restricts via `sites(customer_id, id)`.
The latter does not enforce source scope. Connectors have a unique Integration
DataSource and the Integration's scoped source FK. Generic sources can have a
null `DataSource.site_id`. Preserve the existing uniqueness key and existing
generic source behavior. For this action insist on the exact site-bound
Proxmox Integration, source, case and target scopes. [0007](../../apps/api/migrations/versions/20260719_0007_entity_source_links.py#L22), [0029](../../apps/api/migrations/versions/20261012_0029_discovery_orchestration.py#L16), [Integration and source link models](../../apps/api/app/models.py#L862), [link checks](../../apps/api/app/services/entity_resolution.py#L35).

| Proposed storage | Constraints and purpose |
| --- | --- |
| `data_sources.identity_epoch`, `discovery_runs.identity_epoch` | `bigint NOT NULL DEFAULT 0`, each nonnegative. Advance the source counter on either dedicated outcome. Persist the run epoch at Atlas admission under its source writer lock and keep it fixed through dispatch, retries and callback. Epoch zero represents the pre-upgrade baseline. |
| `entity_source_links.opened_epoch`, `ended_epoch` | Opened `bigint NOT NULL DEFAULT 0`, ended nullable `bigint`. Check `opened_epoch >= 0` and `ended_epoch IS NULL OR ended_epoch > opened_epoch`. Replace the lifetime unique constraint with `uq_entity_source_links_current_source_type_external` on the same tuple `WHERE ended_epoch IS NULL`. Add unique `uq_entity_source_links_source_type_external_epoch` on the tuple plus `opened_epoch` for historical lookup. Add partial index `(data_source_id, customer_id, site_id, interface_owner_id) WHERE entity_type = 'asset_interface' AND ended_epoch IS NULL` for cutover. Links keep immutable source key and target. The locked writer controls interval boundaries. |
| `assets.identity_retirement_revision` | Nonnegative `bigint NOT NULL DEFAULT 0`. A narrow PostgreSQL trigger initializes new retired Assets to 1 and increments only when status transitions into `retired`. It touches only the row being written, so manual PATCH never takes a discovery source lock. |
| `proxmox_guest_identity_decisions` | `reconciliation_item_id uuid PRIMARY KEY` FK to the item, `data_source_id uuid NOT NULL` FK to the source, `identity_epoch bigint NOT NULL CHECK (identity_epoch > 0)`, `old_binding_id uuid NOT NULL` and `replacement_binding_id uuid NULL` FKs to source-link rows, `reviewed_assertion_id uuid NOT NULL` FK to the selected presence assertion, `retirement_revision bigint NOT NULL` nonnegative and `outcome` constrained to `reactivate` or `replace`. `UNIQUE (data_source_id, identity_epoch)`. Require a distinct new binding exactly for `replace`. Use `RESTRICT` FKs. Index `(old_binding_id, identity_epoch DESC)` for retirement acknowledgements and proposal boundaries, and index replacement binding and reviewed assertion FKs. Reuse the item's actor, time and reason. A deferred FK from links `(data_source_id, ended_epoch)` to decision `(data_source_id, identity_epoch)` ties every ended link to the exact decision. End time comes from the decision's item. |
| `knowledge_assertions.identity_epoch` | Nullable nonnegative `bigint` stamped when applying Proxmox guest-family evidence. It records the epoch at which evidence became eligible for attribution. In normal ingestion it comes from the run. For the explicitly released set it comes from the identity decision, while the original evidence and run FKs remain. Legacy Proxmox observations with no stamp have epoch zero. Other assertions need no stamp. |

For replacement, end the old binding and current same-source, same-scope
Interface bindings owned by its Asset. Require that the old Asset has one
current guest slot in this source before ending its owner links. If another
current guest slot shares that Asset, or an observed slot Interface is already
bound to a different owner, refuse replacement with an actionable conflict and
leave the case open for source/ownership review. A typed Interface key whose
explicit observed owner disagrees with the key prefix is ineligible for
release. Preserve the Interfaces and their owner and Network IDs. Leave all
other sources, Networks and Asset relationships intact. The replacement gets
only the new Asset binding in the identity decision. Later explicit Interface
acceptance or linking uses the normal owner and Network prerequisites.

Current-only reads cover Asset resolution and link creation/freshness, technical
lookup and linking, ingestion prelocks, Proxmox hold detection, relationship
and Interface resolution, current reconciliation grouping/eligibility,
simulation guards and absence/re-observation. Historical reads use recorded
canonical IDs first, then a source link from the original attribution epoch
where the provenance proves it. Keep unresolved legacy data unresolved where
this cannot be established. Update `SummaryValues.identifier()` and historical
reconciliation rendering so an external key fallback cannot show a new Asset
against old evidence. An unreadable recorded endpoint stays unresolved.
A historical read applies the same rules when a replacement commits between
statements at PostgreSQL's default isolation level. Keep historical reads
free of writer locks and resolve eligible live discovery against the current
binding. Source association histories, provenance and deletion
checks can see all retained rows. In particular, keep Asset DELETE's all-link
guard and the restrictive Interface owner FK. The proposed decision FKs also
prevent cascading deletion of a decision's old/new Asset link or its source.
There is no routine binding deletion path. Preserve old assertion subject/object
IDs, receipts, decisions, Changes and audits. [Operational lookups](../../apps/api/app/services/entity_resolution.py#L93), [read aliases](../../apps/api/app/services/reconciliation_entities.py#L138), [summary fallback](../../apps/api/app/services/knowledge_summary.py#L61), [Asset deletion](../../apps/api/app/routes/assets.py#L448), [Interface deletion](../../apps/api/app/routes/asset_interfaces.py#L174), [retained provenance protection](../../apps/api/app/services/knowledge_lifecycle.py#L278).

### Cutover and evidence release

1. Validate an already sealed exact completion replay as today and return the
   stored result without applying facts again. Before domain writes on any
   unsealed Proxmox completion, lock the source and compare the admitted run
   epoch to the current one. If different, retain already committed receipts
   and evidence, fail the run through the existing terminal lifecycle with a
   safe “Identity changed during this run. Run discovery again” diagnostic,
   and do no attribution or absence comparison. Use the same check before
   dispatching an obsolete pending run. The whole obsolete run is ineligible
   for attribution, including unrelated rows. Later runs proceed normally.
   A retry submitted by the operator creates a new run. Reject conflicting
   replays and honor existing callback authorization and settlement rules.
   [Admission](../../apps/api/app/services/discovery_orchestration.py#L90), [callback locks](../../apps/api/app/routes/integration_discovery.py#L176), [seal check](../../apps/api/app/services/aip_ingestion.py#L210).
2. Assign an ordinary proposal to the epoch of its attribution. The source
   link with `opened_epoch <= epoch` and no end or `epoch < ended_epoch`
   identifies its binding as of that decision boundary. Determine affected
   slots from the Asset subject, both typed relationship endpoints and an
   Interface's explicit owner, slot syntax and historical link owner.
   Interface fact claims use the underlying EvidenceRecord for their owner.
   Reject a proposal if any relevant slot or Interface alias crossed a newer
   decision or if its pinned canonical IDs disagree with the eligible binding.
   Check the Interface binding's opening epoch even when no earlier Interface
   binding exists. Accepting or linking the fresh Interface may attach only
   facts with a provable eligible owner. An opaque key cannot supply that
   proof by itself.
   Proposals with unbound Interface targets can still receive their first
   explicit link under the same owner and boundary, even if an unrelated guest
   decision advanced the source counter. Fail closed for ambiguous legacy
   provenance on a cut-over key. Historical proposals remain readable
   as stale and stay out of the actionable queue. Apply identical checks to
   individual, versionless, link and bulk paths, and to automatic proposal
   updates. Scope the fence to affected keys so other guests' existing
   proposals remain actionable.
3. Partition coalescing, supersession, conflict detection and refresh by the
   relevant guest binding and latest decision at the assertion epoch. An
   unrelated source epoch increment does not split that guest's observations.
   Equal source keys and values across a decision cannot coalesce or change
   old provenance or acceptance. Narrow the broad `_attach_external_identity`,
   `_accept_technical` and technical linking updates to eligible unresolved
   assertions and items at the same identity boundary. Include relationship
   object identity as well as subject identity. Apply the same guard when
   manual editing exposes pending contradictions. Legacy summaries may still
   show the accepted state of the old Asset historically. [Assertion coalescing](../../apps/api/app/services/knowledge_assertions.py#L79), [Asset attachment](../../apps/api/app/services/reconciliation.py#L209), [technical attachment](../../apps/api/app/services/reconciliation.py#L794), [relationship corroboration](../../apps/api/app/services/simulated_discovery.py#L365).
4. Release only the reviewed assertion's exact `held_evidence_ids`. Verify
   sealed successful run, immutable hash and matching receipt membership,
   customer/site/source, typed ownership/endpoints, and the run's pinned
   manifest/mappings. Apply current scope, active managed types, owner locks
   and ordinary prerequisite checks. Stage new unaccepted assertions and
   granular proposals inside the decision transaction using proposal-building
   logic. Preserve original evidence, memberships and run seal. Avoid the
   normal ingestion shortcuts that accept matching claims, corroborate
   relationships into manual knowledge or close absences automatically.
   Even an existing matching relationship receives ordinary review on release.
   Older held sets and dependants that belong to another unresolved or
   changed identity remain evidence. Use a fresh eligible run for those
   dependants and show why release was withheld to users with the relevant
   view scope. Record released EvidenceRecord IDs and any withheld IDs with
   reason codes in the identity Change metadata so later observation
   coalescing cannot erase the release record. No async release job is required.
5. For a relationship-only Reactivate, the decision plus the validated held
   relationship supplies the exact guest side of that one released proposal.
   Revalidate the other endpoint against the pinned manifest's allowed role
   using a positive host observation in the original sealed run or accepted
   evidence at its exact scoped host binding. A valid, unlinked host observed
   in that run leaves the relationship proposal blocked pending ordinary host
   resolution. Whenever ordinary validation uses accepted
   evidence for an omitted endpoint, require the assertion to belong to the
   same canonical target and binding. A previous guest's accepted assertions
   cannot satisfy the replacement's omitted endpoint. Release never creates
   an Asset payload or an accepted guest assertion from relationship evidence.
   An independent ordinary run omitting an active guest with no accepted
   qualifying fields still fails that reference check. A full valid guest
   observation proceeds normally. [Pass 1 rules](../../apps/api/app/services/aip_ingestion.py#L172), [invalid-reference regressions](../../apps/api/tests/test_proxmox_guest_identity_postgres.py#L355).
6. Keep coverage comparison by DataSource, customer/site and coverage key.
   For a decided guest only, a baseline member must have the current Asset UUID,
   belong to its binding and come from a comparable successful complete run
   at or after that guest's decision epoch. The first qualifying attributed
   complete membership is the new baseline. A held membership, old complete
   run or partial positive cannot seed an absence for that guest. Scope
   observation-state lookup and automatic re-observation closure to the same
   binding and decision boundary. Pre-decision absence items stay historical
   and non-actionable. Pending holds still suppress comparison. Other slots
   keep their own comparable baselines. [Current baseline and state selection](../../apps/api/app/services/discovery_observations.py#L70), [absence and re-observation](../../apps/api/app/services/discovery_observations.py#L132), [AIP coverage](../architecture/integrations/contracts/README.md#existing-lifecycle-mapping).

7. Preserve the simulation guard for pending holds and extend it to an
   unacknowledged retirement or a decided guest family in a live Proxmox
   DataSource. Simulated presence and omission cannot refresh those links,
   obsolete real proposals or establish a post-decision baseline. Use the
   existing simulation DataSource for synthetic inventory. [Simulation selection and locking](../../apps/api/app/services/simulated_discovery.py#L50).

### Transaction and scope

Use the caller-owned transaction and [ADR 0017](0017-reconciliation-knowledge-integrity.md)
order. Preliminary lookups establish visible case context. Lock its Integration
writer row, then its DataSource `FOR NO KEY UPDATE`. An AIP callback already
takes Integration then Run `FOR NO KEY UPDATE` before source work. The identity
action reads immutable sealed runs and evidence without taking a Run writer
lock after the source. Reload source, Integration and case identifiers after
waiting. Enumerate all touched bindings, guest and host Assets, Network and
Interface targets, and any affected relationship subjects before writing.
Take canonical `FOR UPDATE` locks in model/UUID order, owner Assets before
Interfaces. Then take affected item and assertion locks in UUID order. Source
serialization covers binding writes and the scoped case even when no successor
row exists yet. Manual PATCH continues to take only its canonical write locks
and compatible source FK locks. [Existing helpers](../../apps/api/app/services/knowledge_locks.py#L42), [decision target ordering](../../apps/api/app/routes/knowledge.py#L801).

Under locks, reauthorize principal and request context and reload exact source,
open case, current link, Asset state, retirement revision, reviewed assertion and
scoped evidence, plus the applicable Interface targets and dependencies. Bind
the review version to case ID and status, presence assertion ID, run, evidence
hashes, binding UUID, current Asset status and row revision (`xmin` used only
inside the opaque review token), and the references
and mappings required by the action. Recompute with locked rows and compare
before writes. Refresh on staleness. Inaccessible scope returns a non-disclosing
404. Privileges used for the operation are checked using existing scoped
permission helpers. Subsequent field, Interface and relationship decisions
enforce their own mutation grants. Reuse the existing conflict handling for
known contention failures. Propagate unexpected database errors through
normal error handling.

Allocate one epoch, stage binding/lifecycle and proposal changes, set the item
outcome and write Changes and audit in the same transaction. On replacement,
flush ended links before inserting the new current row and insert the decision
before the deferred FK check at commit. On Reactivate use the Asset UUID for
the lifecycle Change and link it to the decided item. Ordinary lifecycle helpers
already use declared status and independent acceptance lineage. Flush before
dependent proposal lookups with production autoflush disabled. Release only
through this transaction using fresh assertions in the new boundary. The case
primary key, source lock and partial unique index give one winner. A second
submission refreshes or sees the resolved case and creates no duplicate audit,
Asset or proposals. Any failure rolls back the counter, binding ends, new
Asset, status change, proposals, decision and success audit together. Already
committed evidence stays available for a deliberate refresh and retry.
[Lifecycle declaration pattern](../../apps/api/app/services/reconciliation.py#L381), [decision commit](../../apps/api/app/routes/knowledge.py#L950).

## Migration, deployment and recovery

1. Start at single Alembic head
   [`20261101_0032`](../../apps/api/migrations/versions/20261101_0032_knowledge_acceptance_integrity.py#L10).
   Add one revision. Under maintenance, preflight scope, target/owner
   integrity and open-case/evidence joinability for affected Proxmox sources.
   Allow the documented relationship-only shape. Refuse contradictory scope or
   duplicate open cases with safe diagnostics. If individual reviewed evidence
   is incomplete, preserve the item and keep the decision unavailable until
   fresh valid evidence arrives. Populate the new columns and decision table,
   build the current and historical indexes and validate new constraints before
   dropping lifetime uniqueness. Existing link IDs and targets become current
   at epoch zero. Existing open case IDs, unresolved memberships and evidence
   pointers carry forward. No historic attribution is inferred or repaired.
2. Seed retirement revision 1 for currently retired Assets. For an existing
   bound Proxmox Asset that is active or otherwise non-retired, seed 1 only
   when an exact same-scope canonical status Change proves a previous retirement
   (`predicate = status` and recorded old or new value `retired`, from a manual
   declaration or explicit accepted status decision). Keep unprovable legacy
   histories at zero and document that protection starts with the next proven
   retirement. Keep the scoped revision backfill independent of receipt or MAC
   evidence. Install the status trigger after seeding. [Manual status Changes](../../apps/api/app/services/manual_knowledge.py#L69), [retirement Changes](../../apps/api/app/services/reconciliation.py#L435).
3. Stop admission, settle or cancel active runs with the existing lifecycle,
   stop old API/worker and other writers, and take a verified encrypted backup
   with the matching pre-upgrade build retained. Expect a write outage while
   PostgreSQL validates/backfills and builds indexes. `ALTER TABLE` and dropping
   lifetime uniqueness take strong locks, including `ACCESS EXCLUSIVE` on the
   link table for applicable DDL. Use transactional DDL, bounded lock wait and
   a populated rehearsal to measure the maintenance window. New API and worker
   must start on the same upgraded schema and build before reopening callbacks.
   Old readers/writers can see ended links, omit epoch checks or misattribute a
   delivery. The schema cannot make an old binary apply the new checks. Keep
   old processes stopped and verify the active API and worker build before
   restoring service. The new processes check the expected revision before
   serving or dispatching. Keep the signed Connector and Catalogue 2 artifacts
   in place. [Upgrade contract](../deployment/upgrades.md), [architecture](../architecture/deployment-and-upgrades.md#recovery).
4. A failed transaction leaves the pre-upgrade schema usable with the matching
   build. Before any identity decision, a guarded downgrade can restore lifetime
   uniqueness and remove additive metadata after confirming no decision rows,
   ended bindings or nonzero epochs exist. Use it only before service reopening
   or when the retirement backfill can be reproduced from retained status
   history. Otherwise use the pre-upgrade backup and its matching build. After
   any identity decision, refuse downgrade. After replacement history exists,
   recover forward on a compatible build or restore an encrypted backup to a
   compatible build. Restoring the pre-upgrade backup to its matching old build
   loses **all writes after that backup**, across the installation. Never
   flatten bindings, delete the replacement or rewrite history to make a
   downgrade succeed. [Encrypted restore procedure](../deployment/backup-restore.md#compatibility-and-resource-policy).
5. Rehearse a populated PostgreSQL upgrade from 0032 with Pass 1 holds, receipts,
   linked/unlinked Interfaces, assigned Networks, absence items, historical
   assertions and a second source sharing an Asset. Compare IDs, accepted values,
   unresolved memberships and history before and after. Exercise the existing
   full-database encrypted backup/restore path for both the retained pre-upgrade
   backup on its matching build and a new backup with ended/current bindings and
   decisions on the upgraded build. Verify schema revision, keys/FKs/indexes,
   restored case resolvability, decision/provenance access, stale fencing and
   first post-restore discovery. This uses the existing compatibility policy.
   No archive-format or separate binding import/export feature is required.
   [Restore mechanics](../architecture/encrypted-backup-restore.md#native-database-behavior-and-compatibility), [PostgreSQL restore tests](../../apps/api/tests/test_backup_postgres.py).

### Schema checkpoint

[Revision 0033](../../apps/api/migrations/versions/20261119_0033_proxmox_guest_identity_storage.py)
implements the storage contract. It uses a five-second PostgreSQL lock timeout
per lock acquisition. The preflight checks the Integration scope of existing
Proxmox source links and the recorded scopes of open items, their canonical
targets, source, run, assertion, anchor, held evidence and run membership. The
existing typed-target and Interface-owner foreign keys enforce the link
targets. Conflicting context and duplicate open scoped keys abort before DDL.
Missing references, malformed evidence IDs or incomplete receipt membership
produce an aggregate diagnostic and preserve the review for fresh evidence.
Receipt joinability uses the held payload and unresolved membership, including
the relationship-only shape. Decision-time checks still verify evidence hashes,
the pinned manifest and the exact reviewed set.

Retirement backfill recognizes the manual `fact_changed` declaration with
`origin = manual_asset_edit` and `accepted = true`, and the accepted absence
`lifecycle_changed` declaration with a status-writing disposition. Their
`previous_value_json` and `new_value_json` store status strings. An ordinary
accepted canonical status change stores `{field, value}` in those columns and
requires the Change and accepted item to point to the same scalar status
assertion for the canonical Asset in the exact Customer and Site. Historical
assertions can prove retirement after supersession. Manual and absence Changes
also check the subject and scope of any retained status assertion. A retained
declared Change can still prove retirement if its assertion was deleted. An
absence decision also requires its selected observation to match the item's
scope and any recorded canonical Asset subject. Only these proofs count for
non-retired Assets with a scoped Proxmox guest binding. The migration preserves
the Change, item and assertion records. A manual edit to Active leaves an
unresolved retirement revision in place.

The deferred foreign key proves that an ended link has a decision at the same
source and epoch. The decision's cardinality and binding references are enforced
separately. The operator transaction must prove that the decision is **Replace**
for the exact locked guest and its applicable same-source Interface bindings.
**Reactivate**, or a decision for another guest on the same source, must never
end those bindings. That transaction also enforces interval continuity, exact
scope, binding immutability, reviewed evidence and scoped `networks.edit` for
Replace. The schema checkpoint supplies storage for these rules.

The schema downgrade checks decision rows even if all bindings are current
and the other epochs are zero. Before service reopens, use a guarded downgrade
only within the pre-decision boundary above. After a decision, recover forward
or restore the pre-upgrade encrypted backup on its matching build. A restore
to that backup discards every write made after it. During the eventual rollout,
halt admission, settle or cancel runs, hold callbacks, stop old processes,
and verify the API and worker are on the matching upgraded build and revision
before reopening. Local timings from synthetic data cannot size that window.

The [storage tests](../../apps/api/tests/test_proxmox_guest_identity_migration_postgres.py)
use fixture decisions to exercise PostgreSQL and encrypted restore.

### Operational checkpoint

The [developer contract](../architecture/proxmox-guest-identity-containment.md#operational-cutover-contract)
records the live, historical and retained-link lookup rules. The [cutover tests](../../apps/api/tests/test_proxmox_guest_cutover_postgres.py)
use committed storage fixtures to verify run settlement, exact replay, scoped
attribution, proposal fencing, retirement acknowledgement and absence coverage.

### Operator decision checkpoint

The dedicated `POST /reconciliation-items/{item_id}/identity-decision` action
implements both outcomes and returns the resolved case and outcome. Readiness,
current Asset status, and the reviewed version are available on flat and grouped
reads. The [application decision tests](../../apps/api/tests/test_proxmox_identity_decisions_postgres.py)
exercise both outcomes, scoped permissions, Identity and completion contention,
rollback and retry, and encrypted restore of a database with a real replacement
decision on the matching upgraded build. The fixture-based browser harness
checks the comparison, reason entry, stale refresh and leaving a review pending.
The migration and earlier storage-fixture checks remain separate evidence.
This ADR remains proposed for independent review. Hosted CI, deployed maintenance
and live Connector acceptance remain pending.

## Implementation acceptance

Use production `SessionLocal` settings and real scoped HTTP routes. The race
tests use independent PostgreSQL connections, explicit synchronization on
observed locks and post-commit assertions from a third session.

| Requirement | Existing evidence to extend | Observable new regression |
| --- | --- | --- |
| Reactivate and leave pending | [Pass 1 hold and scope cases](../../apps/api/tests/test_proxmox_guest_identity_postgres.py#L259), [AT-B01](../../apps/api/tests/test_asset_retirement_postgres.py) | Confirm same UUID and binding, lifecycle declaration or already-active confirmation, Change and audit. Held field, Interface and relationship evidence yields independent unaccepted proposals. Closing the panel changes zero records. All generic decision routes refuse Identity items. |
| Replace | [Retained Interface and Asset protection](../../apps/api/tests/test_asset_retirement_postgres.py#L93), [AT-B02](../../apps/api/tests/test_interface_observations_postgres.py) | Same slot resolves to a distinct UUID on next eligible discovery. Old records and other sources remain intact. Verify ended and current FK targets and preserved historical attribution. New Interface gets no old assignment on omission and an observed VLAN alone gives no assignment. Exercise actual explicit Network reference acceptance. No copied relationships or manual data. |
| Migrated Pass 1 cases | [Relationship-only and LXC/QEMU cases](../../apps/api/tests/test_proxmox_guest_identity_postgres.py#L291), [0032 populated upgrade discipline](../../apps/api/tests/test_knowledge_integrity_migration.py) | Resolve the original item IDs after upgrade. Reactivate from the omitted-guest case, including the absent accepted guest assertion. Replacement stays unavailable until a fresh held guest payload. Validate role, source and owner mismatch controls. |
| Retirement revision backfill | [PostgreSQL upgrade from 0032](../../apps/api/tests/test_proxmox_guest_identity_migration_postgres.py#L213) | An active linked guest with an in-scope Change and accepted item pointing to the same cross-site assertion stays at revision 0. A missing Site or mismatched canonical subject also leaves it at 0. The same-scope historical assertion seeds revision 1. Manual and absence evidence with cross-site assertions leaves the revision at 0. Compare all retained Change, item and assertion values before and after upgrade. |
| Lifecycle and read scope | [Retirement vs. completion](../../apps/api/tests/test_proxmox_guest_identity_postgres.py#L555), [existing scoped Interface reads](../../apps/api/tests/test_interface_observations_postgres.py#L238) | Manual activation before first hold still requires identity review for provable retirement. An edit after the hold invalidates stale confirmation and never closes it. Verify both sides of comparison, queue counts, details and direct decisions across customer/site, with missing general, Asset, Network and relationship permissions. |
| Historical relationship reads during cutover | [PostgreSQL cutover tests](../../apps/api/tests/test_proxmox_guest_cutover_postgres.py) | Pause a run-filtered read after its source lookup while an independent transaction commits a replacement. Verify the recorded or epoch-proven original endpoint in flat and grouped history. An unreadable or unproven endpoint stays unresolved. Verify the next eligible live observation resolves to the replacement. |
| Opaque Interface ownership at first binding | [PostgreSQL cutover tests](../../apps/api/tests/test_proxmox_guest_cutover_postgres.py) | Accept and explicitly link a fresh Interface whose opaque key was previously observed under a different owner. Verify versionless individual and versioned bulk acceptance reject the old fact. Compare the old claim, item and evidence and check for stale Changes and success audits. A first link for the same eligible owner still works after an unrelated guest decision. |
| Replay, stale proposals and absence | [Pass 1 replay/coverage and active change controls](../../apps/api/tests/test_proxmox_guest_identity_postgres.py#L408), [reconciliation integrity](../../apps/api/tests/test_reconciliation_integrity_postgres.py) | Race a stale completion, replay exact and conflicting seals, and submit stale or versionless Asset, Interface config/fact/link, relationship in either endpoint role, bulk and absence requests. Verify original IDs and claims never retarget or coalesce with replacement observations. Old complete/partial/failed/held and simulated runs cannot establish new absence. Unrelated proposals remain valid. Ordinary active rename, NIC change and node migration continue through normal review. |
| Atomicity and concurrency | [HTTP rollback tests](../../apps/api/tests/test_reconciliation_ingestion_http_postgres.py#L139), [technical lock graph](../../apps/api/tests/test_reconciliation_technical_locking_postgres.py#L92) | Race two decisions and decision vs. completion in both lock orders. Check one current binding and one success audit. If completion wins with newer evidence, the stale reviewed version fails. If decision wins, the older run cannot apply. Inject a failure after ends/new Asset and after release writes, test deferred FK failure and refresh/retry. Confirm no deadlock, partial state or duplicate release. |
| Maintenance and restore | [Full backup tests](../../apps/api/tests/test_backup_postgres.py), [active-run restore controls](../../apps/api/tests/test_i3_backup_postgres.py) | Rehearse the populated upgrade, pre-decision downgrade and post-decision refusal. Restore both backups to matching builds and exercise constraints and review/discovery behavior. Verify obsolete execution is settled, the old services stay stopped and the new services check schema before taking traffic. |

The implementation should first establish the schema and prove upgrade/restore,
then fence attribution and migrate all affected lookups, then add the atomic
decisions, review presentation and operator documentation. Update the
[operator reconciliation guide](../admin/cross-source-reconciliation.md),
[retirement](../admin/asset-retirement.md), [Networks](../admin/networks.md),
[entity review contract](../architecture/reconciliation-entity-review.md),
[upgrade guide](../deployment/upgrades.md) and
[feature ledger](../product/feature-ledger.md) when implementation is verified.
