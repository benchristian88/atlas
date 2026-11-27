# Guided setup preview (AT-R01 / E1-A through E1-F)

## Preview operation

Set `ATLAS_ONBOARDING_PREVIEW=true` in the **API process environment** and restart
that process on a development or test installation. The web client uses the API
response to determine entry availability. With the flag unset, entry is hidden
and direct wizard routes show an unavailable state. Public activation is
reserved for E1-H.

Secure first-administrator installation and sign-in use the existing setup-code,
session and MFA flows. The initial Dashboard invitation targets the exact
Customer/Site pair created during secure setup, when Atlas has no Customer.
Renames preserve that identity. Existing databases receive no inferred marker.
Atlas offers the invitation only before setup starts and when canonical Assets,
Networks, Services, Business Functions and Integrations relevant to the pair
are empty under canonical reads, which exclude retained tombstones. Atlas checks
emptiness only when the operator can read every scope
being queried. In particular, a Site-only grant can use voluntary entry without
learning whether Customer-wide records exist.

**Set up manually** or **Dismiss invitation** dismisses the optional invitation
for the signed-in user. The compact Guided setup area below the Dashboard
heading shows **Start guided setup** for a new setup and **Resume** with the
saved profile and current stage for shared progress. It targets the active
Dashboard Site or identifies a sole resumable Site if it differs from the
workspace selection. Completed setups use a quieter **Guided setup** entry.
The authorized chooser
marks Sites with resumable progress, suggests a unique authorized pair and
requires explicit selection when there are several choices. It uses the same
Customer and Site create and rename APIs as normal administration. Each create
has its own confirmation and transaction. If creating a Site fails, the
Customer remains selected. If a create response was lost, refresh choices and
look for the record before retrying.

Choose the **Homelab** or **Blank** profile and confirm Environment to open
Capabilities. Before confirmation, **Save & exit** saves the pending profile.
A different pair has its own progress. After confirmation, **Back to
Environment** lets you inspect the fixed pair and profile or rename the
Customer or Site if authorized. Return to Capabilities to continue editing.

## Select and apply capabilities

Homelab shows one expandable card per Business Function, with Standard
(recommended) and Extended (optional) Services. The first visit recommends
eight Business Functions, 24 Standard Services and their 24 Supports
associations. Each Function can be selected on its own. Selecting a Service
adds its parent and its catalogue-defined Supports association. Deselecting a
Service removes its associations. Clearing a Function clears its Services and
associations, and choosing it again restores those choices for the editing
session. **Select all Services** selects remaining Services across both tiers.
Selection actions affect the chosen entries. The summary counts the actual
selected Functions, Services and Supports associations.

Use **Edit** on a selected entry to change its name or description. Services
also support an active managed Service Type and Criticality level. **Restore
catalogue defaults** clears one entry's overrides. **Restore recommended
selection** restores the catalogue recommendations and asks before discarding
customised values. If a classification is unavailable, the wizard identifies
the affected Services. **Edit classifications** opens the affected Service's
editor. Choose an active value if authorized, or deselect that Service.

Atlas previews the selection as it changes. Existing-name warnings identify
names that already occur in authorized Customer-wide records. You can rename,
deselect or continue with a warned entry. The canonical create validation still
applies. **Review selection** shows the selected records, classifications,
warnings and counts before the explicit **Apply capabilities** action. Expand a
customised description to inspect the text that will be saved. Services without
a selected Supports association appear under their own heading. Apply
creates new Customer-wide records, which other authorized Sites can use.
Existing records stay as they are. On success, the wizard shows the creation
counts from the API and opens Add Integrations.

**Save & exit** stores the selection and selected-entry overrides for the
confirmed Site. **Resume** restores the saved Function, Service and association
IDs and their overrides. A draft can contain a Service without its parent or
both endpoints without a Supports association. Opening, editing descriptions,
previewing, reviewing and saving preserve that membership. **Skip capabilities**
records the decision and advances to Add Integrations without creating records. It asks
before discarding selections or edits. Blank provides the manual setup path
and Skip without a starter catalogue.

After an initial decision, use the Capabilities entry in the progress rail or
**Open capability catalogue** to start an additional import. The selection
starts empty unless an additional-import draft exists. An additional Apply
creates new records and preserves the current stage and other decisions.

If another administrator changes progress, **Reload saved progress** fetches the
shared state and asks before discarding local changes. Review the refreshed
selection before applying. If the saved draft uses another catalogue version,
**Review current catalogue** enables review of the installed version. Saving or
applying then explicitly replaces the stale draft. If the Apply response is
lost, use **Retry this Apply** in the same browser tab, including after a page
reload. Atlas keeps only the submission UUID and the requested workflow version
in per-tab storage and replays that exact command to recover its outcome.

## Persistence, tenancy and writes

- PostgreSQL stores at most one attached `site_onboarding` row per Site. A
  composite foreign key enforces the Customer/Site pair. Draft-only rows detach
  if the Site is reassigned or deleted. Explicitly started or confirmed progress
  prevents either operation. The bootstrap invitation marker clears if that
  pair is removed or transferred.
- The workflow stores draft and confirmed profiles, cursor, explicit stage decisions, and
  lifecycle with started, updated and completed timestamps. An absent row means
  `not_started`. Stage decisions can represent completion, skip or attention.
  The Environment and Capabilities commands write their respective decisions.
  Last actor and ordinary Atlas audit events record authenticated mutations. Per-user invitation dismissal is held
  separately in `onboarding_invitation_dismissals`.
- Status reads and personal dismissal require `customers.view` and the pair's
  `sites.view`. The chooser and shared progress mutations also require the
  relevant `sites.manage` grant. The scoped API uses UUIDs in the path
  and reloads grants after waiting for mutation locks. Scoped failures return
  Atlas's nondisclosing 404. Ordinary authentication and permission failures
  preserve their standard responses. Workspace headers confer no wizard
  authority. The canonical Customer and Site routes continue to enforce their
  own creation and rename permissions.
- Start uses PostgreSQL's unique Site key and conflict-safe insertion. A repeat
  returns the current state, including saved progress. The first draft save
  supplies version 0 and inserts only if progress is absent. Stage, save and resume
  writes serialize on the row and require its current version. Duplicate resume
  while already active returns current progress without writing. A stale write
  returns 409 and the wizard offers **Reload progress**. Reads preserve all
  timestamps and version. The preview exposes no Finish transition.
- Site progress and invitation preferences participate in Atlas's PostgreSQL
  backup and restore. Migration `20261122_0034` adds empty tables and nullable
  bootstrap markers. Its downgrade removes these E1-A records and markers.

## API surface

All paths below use the `/api/onboarding` prefix. The pair prefix is
`/{customer_id}/{site_id}`.

| Method and path | Contract |
| --- | --- |
| GET `/contexts` | Authorized setup choices and context creation eligibility |
| GET pair | Canonical context names, status, optional progress, Site management capability and the current user's invitation state |
| POST pair `/start` | Create or return shared progress |
| PATCH pair `/environment` | Confirm `environment_profile` with `version` |
| POST pair `/save` | Save with `version` and optional `draft_profile`. Supply version 0 and the profile for the first draft save |
| POST pair `/resume` | Resume saved progress with `version` |
| POST pair `/invitation/dismiss` | Dismiss the optional invitation for the authenticated user |

## Capabilities API (E1-B)

Each endpoint uses the same authenticated preview gate and exact Customer/Site
pair as Environment. The confirmed profile remains fixed. All paths in the
table are relative to `/api/onboarding/{customer_id}/{site_id}/capabilities`.

| Method and path | Request and response |
| --- | --- |
| GET root | Returns the fixed profile, current workflow `version`, permissions, catalogue, recommended selection, optional shared draft and `draft_stale`. Blank returns null catalogue, defaults and draft. |
| POST `/preview` | Takes `{version, selection}`. Validates the selection and returns `{warnings}` without saving or creating records. |
| PUT `/draft` | Takes `{version, selection, save_and_exit?, replace_stale_draft?}` and returns updated progress. Both flags default to false. |
| POST `/apply` | Takes `{version, submission_id}`. Applies the saved draft for that version and returns `{submission_id, version, current_stage, created: {functions, services, associations}}`. |
| POST `/skip` | Takes `{version}` and returns updated progress. Available at the initial Capabilities stage for either profile. |

The bundled Homelab catalogue is available offline and has its own schema
version (1) and content version (1.0.0). The fixture retains the approved
wording, display taxonomy, order and readable definition and association IDs.
First entry recommends eight independently selectable Business Functions,
24 Standard Services and their associations. All 18 Extended Services are
available. After a Capabilities decision, the full catalogue remains available
with an empty default selection. The API accepts eligible association IDs and
allows either endpoint to be selected independently. The wizard uses approved
association IDs for linked selection actions and preserves the association
membership supplied by a saved draft.

Authored Business Function names in the bundled English catalogue must contain
only ASCII characters after the canonical whitespace trim. The offline validator
checks those names case-insensitively. This comparison matches PostgreSQL 17
with the `en_US.utf8` locale for ASCII names. Other locales can case-map ASCII
letters differently, including `I` in Turkish. PostgreSQL remains authoritative
for uniqueness at write time. Catalogue descriptions, user-edited names in
Apply, and ordinary Business Function names can contain Unicode.

Send `catalogue_id`, `schema_version`, `content_version`, `functions`,
`services` and `associations` in each selection. Function and Service arrays
contain objects with a definition `id` and optional `name` and `description`
overrides. Services also accept `service_type_key` and `criticality_key`.
Omit overrides to use the definition values. A null description clears that
field. Association entries are definition IDs. The API returns the stable
defaults in `default_service_type_keys` (keyed by the approved label) and
`default_criticality_key` (`medium`). Offer alternative active keys through the
ordinary Service Type and Criticality reference APIs, which enforce their
own read grants. The import resolves global active records by key at runtime.
An administrator can rename a display label without changing lookup behavior.

The request schema bounds counts, text and identifier lengths and rejects extra
fields. Requests over 12 MiB return 413. Invalid definitions, endpoints, values
or inactive reference keys return 422. Field errors may carry
`{code: "invalid_selection", definition_id, message}` in `detail`.
Preview may return `{code: "existing_name", definition_id}` warnings when
canonical name comparison finds a Customer-wide record visible to the caller.
The database enforces canonical uniqueness for each create, including Service
slugs. A conflict returns 409 and the selection remains available for edits.

### Draft, Apply and replay

- To apply, first PUT the reviewed selection, then send the returned workflow
  version and a new client-generated UUID. The version identifies the exact
  shared snapshot and prevents applying a draft another Site manager changed.
  Save & exit sets the Site workflow to saved. Use the existing `/resume`
  command before applying or skipping saved progress.
- When a draft has a different installed catalogue version, GET exposes the
  saved content with `draft_stale: true`. Review against the current catalogue
  and send the new version tuple with `replace_stale_draft: true` to replace
  the old draft. Apply rejects stale drafts. Skip can discard one.
- Apply creates ordinary Customer-wide records. Selected links connect only
  Functions and Services created in the same transaction and use Atlas's
  standard Supports association. The ordinary create and association
  operations write audit, declared knowledge, Changes and completeness state.
  Apply, ordinary Customer-wide Service creates, and Service edits ending at
  Customer scope use the same transaction lock before claiming unique names or
  slugs. This also serializes imports from different Sites within the Customer.
  Apply and ordinary Service creation take shared locks on their selected
  Service Types and Criticality levels before any Customer inventory lock.
  A reference edit that changes completeness rules waits for in-flight
  creations before finding the Services to reevaluate. The reference edit and
  the resulting completeness changes commit together.
  The draft clears on success. The first decision advances to Add Integrations.
  Later imports preserve the cursor and other stage
  decisions. Skip and the Blank profile create zero operational records.
- If the Apply response is lost, resend the same UUID and the same version.
  Authorized replay returns the original outcome, even after progress or
  catalogue versions have advanced. A UUID used with a different workflow
  version returns 409. Using it against a different Site returns a
  nondisclosing 404. A deliberate later import uses a fresh UUID and the current
  version. Repeated definitions can create additional records with names valid
  under ordinary Atlas rules.

### Permissions

| Operation | Required grants |
| --- | --- |
| Read Capabilities and preview | `customers.view` for the Customer and `sites.view` for the Site |
| Read, save or replace the shared draft; Apply; Skip | The above and `sites.manage` for the Site |
| Apply or replay with Business Functions | Additionally `business_functions.manage` at Customer scope |
| Apply or replay with Services | Additionally `services.create` at Customer scope |
| Apply or replay with associations | Additionally `business_functions.manage` and `business_functions.view` at Customer scope |
| Validation of alternate Service Type or criticality keys | The corresponding `service_types.view` or `criticality_levels.view` grant required by the ordinary reference list |
| Existing-name warnings | The relevant `services.view` or `business_functions.view` at Customer scope |

GET returns `can_manage`, `can_create_functions`, `can_create_services`,
`can_create_associations`, `can_view_service_types` and
`can_view_criticality_levels` under `permissions`. Mutation requires the
applicable flags together. A Site grant cannot authorize Customer-wide creates.
Canonical pair checks use path UUIDs. Workspace headers do not grant or
override access. Apply rechecks grants under Site, workflow, submission and
reference locks and before commit. Draft and Skip recheck under the Site and
workflow locks.

### Storage and release

Migration `20261125_0035` adds a nullable versioned draft to `site_onboarding`
and an Apply receipt keyed by submission UUID and attached to the same
workflow row. A receipt stores the requested version and aggregate outcome.
It contains zero canonical record IDs and is retained for the life of the
workflow. Confirmed progress continues to protect the Site from deletion or
transfer. Whole-database backup and restore preserve draft and replay state.
Downgrade to E1-A removes drafts and receipts while preserving canonical
records, workflow versions and decisions. After re-upgrade, a former committed
submission's original version is stale and cannot create objects on replay.

The fixture lives at `apps/api/app/onboarding_data/homelab-v1.json`. Update the
content version and approved-fixture test when approved content changes.
Docker and native archives require the same file. The API image and the
catalogue tests validate its structure, check Business Function name uniqueness
after trimming and lowercasing, and reject duplicate generated Service slugs.
The fixture is independent of the signed Connector Catalogue and Atlas release
metadata.

## Add integrations (E1-D)

Add Integrations shows the confirmed Customer and Site, followed by
**Configured integrations** and **Available connectors**. The first section
shows the connection's enabled state, recorded connection test when available,
and the active or latest discovery run. Opening or resuming the stage reads
current records. Use **Reload integration status** to pick up concurrent
administration changes. Atlas polls active discovery while the stage is open
and stops when the run settles, when you leave, or after five minutes.

The **Connector Catalogue** lists executable connectors and their package
status. The **Capability Catalogue** in Step 2 contains starter Business
Functions and Services. Installed connectors and applicable bundled packages
are available offline. **Refresh catalogue** explicitly checks the official
source for operators with global runtime management access. Atlas applies the
standard verification and refresh cooldown rules. A failed official check
leaves local options available.

Use **Install** for an eligible bundled package or **Review & install** for
an eligible official package. Review the exact package, source and available
qualification evidence and confirm activation. Installation and updates apply
to the entire instance and require global `integration_runtime.manage`.
Installed packages remain available to configure while eligible updates can
be reviewed separately. Connector verification, runtime compatibility,
mapping requirements and update preflight use the standard catalogue commands.

**Configure** opens the standard integration creation form with the Customer,
Site and connector fixed. Fill the connector's connection fields and run
**Test Connection**. Configuration changes clear the successful test. Atlas
checks the same package identity at the probe and save. Unsaved credentials
are transient masked inputs. Leaving an edited form discards its entries
after confirmation. A saved integration uses Atlas's existing encrypted
storage. The preview probe is audited. Saved-card test history comes from
the integration's recorded test fields.

For a discovery-capable connector, **Save & discover** creates the connection
and explicitly requests one manual discovery run. For a probe-only connector,
**Save integration** creates the connection. The wizard creates manual
schedules. A rejected save keeps the editable form. When a save succeeds
and discovery is rejected, use **Retry discovery** on the saved integration.
The discovery service serializes concurrent execution for the same
integration. Atlas shows queued, running, completed, failed or cancelled
status and recorded observation counts. Accepted knowledge changes through
the ordinary reconciliation workflow.

After a lost save response, the wizard looks up the canonical creation key.
After a lost discovery response, **Check operation status** reloads the
Site's discovery records. The browser session retains the unresolved
request across reload and resume and blocks further dispatch from that
session. A visible run can be used for setup while the earlier request's
outcome remains unknown. **Use available run and continue** acknowledges
the unresolved local operation after the Site decision succeeds. Manual
continuation is also available. The manual start API guards against
overlapping active runs. Exact request attribution after a lost response
is unavailable through its history reads.

**Save & exit** saves the shared Site progress. Resume reloads canonical
integrations and discovery. **Back to Capabilities** opens the previous
step with its decision preserved. **Continue to Discovery Review** records
the decision when Atlas has a queued, running or completed run from a
non-retired integration in the confirmed Site. Displayed discovery history
can include a different run. If a concurrent change makes the candidate
ineligible, the wizard refreshes status so you can choose how to continue.
**Continue without integrations** records a skip in either profile and
preserves configured integrations and their history. Both decisions open
Discovery Review. Reopening Add Integrations preserves
the current workflow stage and later decisions.

### API contracts

- `GET /api/integrations?include_discovery=true` adds bounded discovery
  readiness, a credential-free status summary and an eligible
  `continuation_run_id` (or null) for each returned integration. Atlas
  chooses the newest eligible run per integration with an ID tie-breaker.
  The wizard uses the first eligible integration in the scoped list.
  `GET /api/integrations?creation_key=<uuid>` looks up an existing create
  request. Both options require the confirmed Customer and Site context
  headers and retain the existing integration visibility checks.
- The creation and unsaved test input accepts an optional
  `expected_connector_digest`. A different active digest returns 409.
  Integration creation accepts `start_initial_discovery`, defaulting to
  `true` for existing callers. Onboarding passes `false` before issuing
  the existing explicit discovery action. The ordinary form, package
  activation, discovery start and discovery read endpoints handle their
  respective permissions and persistence.
- `POST /api/onboarding/{customer_id}/{site_id}/integrations/decision`
  accepts `{version, decision, discovery_run_id?}` and returns existing
  progress. The preview gate and scoped Site management apply.
  `completed` requires a current authorized run for a live integration in
  that exact Site. `skipped` carries no run ID. Shared version conflict
  returns 409 and the wizard offers **Reload progress**. The existing
  onboarding row stores the decision and the audit event records the actor.

## Discovery Review (E1-E)

Step 4 uses the confirmed Customer and Site and shows the active or latest
discovery status per visible integration. Review available discoveries while
other runs are queued or running. The proposal queue spans completed runs
from the Site's visible reconciliation sources, including still-current
proposals from earlier runs. Observations, outstanding proposals, and
accepted decisions have separate counts or labels. Retired integrations and
stale source claims are excluded from the outstanding queue.

Search by entity name and filter by source and proposal category. The Site
summary covers all visible outstanding work. Each section reports matching
totals and the number displayed on the current page. Open **Review proposal**
to inspect accepted and observed values, provenance and prerequisite decisions.
Use the same versioned individual actions as Reconciliation. **Needs review**
includes blocked proposals, deferred decisions, identity conflicts, possible
duplicates, contradictions and lifecycle decisions. Retiring an Asset requires
an explicit lifecycle selection and confirmation.

**Accept all eligible on this page** freezes the exact eligible proposal IDs
and versions shown in the current filtered page. Its confirmation names the
Site, scope, proposal types and exclusions. Asset review shows whether the
proposal will create an Asset or associate with an existing one. The
confirmation shows the target of each reviewed association. An operator needs
Asset view access to review that identity outcome for bulk acceptance.

The canonical operation rechecks current eligibility and versions before the
first decision and again for each item. Asset versions bind the canonical
resolver's outcome and existing target identity where applicable. Canonical
inventory writers take a shared Site advisory lock before source and subject
locks. A batch that can change Asset identity takes the Site lock exclusively
so an absent or existing match stays stable through the canonical write.
Existing source locks protect source links. Later items see successful writes
and savepoint rollbacks from earlier items. A changed Asset outcome requires
fresh confirmation. A conflict that requires individual review remains open
and appears in Needs review. Newly eligible proposals require a separate
explicit acceptance.

The batch refreshes the initiating operator's effective grants after lock
waits, before each decision and immediately before commit. At PostgreSQL's
default READ COMMITTED isolation these checks can see committed revocations.
If required authority is lost, Atlas rolls back the entire uncommitted batch
and returns a scoped authorization error without proposal outcomes. The
checks read current grants at each checkpoint. Grant administration remains
independent of the decision transaction, so a revocation committed after the
final check can race with commit. Other per-item failures use the existing
savepoints and preserve successful independent decisions. The transaction
still records accepted assertions, Changes, completeness and actor-attributed
audit through canonical reconciliation. Results distinguish accepted, already
resolved, waiting or needing individual review, and failed or changed items.

If a response is lost, **Check proposal status** reads current canonical
decisions without attributing them to the lost request. The browser session
retains affected proposal IDs and blocks another decision on them while
their status is unresolved. Reloading or resuming does not dispatch another
decision. The server stores canonical decisions and their actor through the
ordinary reconciliation records and audit trail.

**Back to Add Integrations** opens the existing configuration and discovery
stage. **Save & exit** saves the Site workflow and keeps committed decisions
and independent discovery work. Resume reloads the canonical queue. In a
manual setup, continue with an empty queue. **Continue to Link Services**
requires acknowledgement when proposals remain, discovery is active or the
operator cannot inspect the required status. **Skip Discovery Review** records
a separate decision and advances directly. Outstanding proposals remain
available in Reconciliation. Revisiting Step 4 after advancement preserves
the saved cursor and stage decisions.

### API contracts

- `GET /api/reconciliation-entities/discovery-review` is a preview-gated
  proposal view over the existing entity-review projection. A confirmed
  Customer/Site context and its canonical view permissions are required.
  `search`, `source_id`, `category`, `offset` and `limit`
  narrow the page. The response contains matching counts, the unfiltered
  Site summary, and exact displayed items. Repeated `decision_id` parameters
  return authorized canonical decision statuses for local recovery. Counts
  are null when the caller lacks the relevant view grant.
- `POST /api/reconciliation-entities/discovery-review/accept` extends
  canonical bulk acceptance from one entity to one reviewed Site page.
  Send `{items: [{id, version}], reason?}` with up to 100 distinct items.
  Use the `batch_version` supplied with each eligible item. The version
  binds the reviewed proposal, applicable relationship endpoints, and the
  canonical Asset identity outcome. Existing
  per-entity acceptance contracts and prerequisite behavior continue to
  work in Reconciliation. The Site batch retains canonical eligibility,
  role checks and locking. Its result adds the newly eligible count and
  up to 100 examples to the existing four outcome groups.
- Individual reconciliation, identity and lifecycle decisions call existing
  endpoints and use their specialized reviewed versions. Access to Site
  progress does not confer reconciliation, integration or domain permissions.
- `POST /api/onboarding/{customer_id}/{site_id}/discovery-review/decision`
  accepts `{version, decision, review_version?}`. With `completed` or
  `attention`, send the Site summary version. Atlas rechecks the live
  summary and returns a reviewable conflict when it changes. `skipped`
  omits the review version. The existing workflow version and Site manager
  grant apply to all three decisions. Success advances to `link_services`
  and records the actor. The workflow stores no copy of review data.

## Link Services (E1-F)

Step 5 uses the confirmed Customer and Site for either profile. Search by
Service name or filter by **All Services**, **Unlinked** or **Linked**. The list
includes visible Customer-wide Services and Services for this Site. The summary
counts visible, current Asset dependencies at this Site across the full eligible
Service population. Mappings that were saved before guided setup count. Where
permissions limit the projection, the affected mapping status is unavailable.

Select a Service to view its linked Assets. Existing visible mappings to retired
Assets show their lifecycle. Visible mappings at other Sites provide read-only
context. Search available Assets by name and filter by managed Asset Type.
Check up to 25 Assets, including across pages, and choose **Add selected Assets**.
The picker, linked rows and confirmations show each Asset's name, type and
full canonical UUID, with its hostname when available. Picker checkbox labels
include the same identifying information. Confirm the Service and the selected
Asset identities. Each confirmed Asset is saved independently using the
canonical `depends_on` type and the ordinary required dependency default. A
mapping leaves the failure effect unknown. An Asset can support several Services.

Result messages identify added, already-linked, rejected and unconfirmed
requests. Atlas stops sending new requests for that confirmation when a response
is uncertain. **Check current mappings** reloads the canonical state before a
new explicit attempt. The browser tab remembers the unconfirmed operation for
that Service across reloads. A current link may have been created by another
operator. Its presence alone gives no attribution for the unconfirmed request.
To end a mapping at this Site, choose **Remove** and confirm the Service, Asset
and relationship type. If the relationship changes, Atlas refreshes the mappings
and requires a fresh confirmation. Canonical relationship history and its
provenance remain available.

**Save & exit** saves shared Site progress and keeps all committed changes.
Unsubmitted selections are cleared when changing Services or leaving the step.
**Resume** loads live canonical mappings. **Continue to Review & Ready** allows
outstanding work after acknowledgement. **Skip** preserves existing mappings
and records an explicit decision. After advancing, reopen Link Services from
the progress rail to view or edit its current mappings and return to the saved
cursor. Shared version conflicts use **Reload progress**. Existing mapping
commits survive a conflict.

### API and write contract

All paths are relative to `/api/onboarding/{customer_id}/{site_id}/link-services`.
Reads and writes use the authenticated preview gate and the confirmed pair.

| Method and path | Contract |
| --- | --- |
| GET root | Returns the authorized Site summary and a deterministically ordered Service page. `search`, `mapping`, `offset` and `limit` filter or page the list. |
| GET `/services/{service_id}` | Returns visible Site and other-Site mappings, mapping permission, managed Asset Type options, and a page of eligible, unlinked Assets. `search`, `asset_type`, `offset` and `limit` affect the available Asset page. |
| POST `/services/{service_id}/assets/{asset_id}` | Adds one selected Asset via the canonical operation. The result distinguishes `added` and `already_exists`. |
| DELETE `/services/{service_id}/mappings/{dependency_id}` | Requires `{removal_version}` from the reviewed mapping. Ends the dependency through the canonical operation. Returns `409 link_mapping_changed` for stale confirmation and `404` if the dependency is no longer available. |
| POST `/decision` | Accepts `{version, action, acknowledge_attention?}`. `continue` checks current visible totals and requires acknowledgement of outstanding or unavailable mappings. `skip` records an explicit skip. Both advance to `review_ready`. |

The read projection counts canonical current relationships with endpoint and
relationship view checks. Archived Services are excluded from the picker.
Retired Assets are excluded from new mappings. Other-Site context also requires
access to that Site. A null projection or count indicates lack of visibility.
Pagination does not cap the Site summary. Read scope and count rules are shared
by the page and progression command.

Writes require Site setup management, Service and Asset view, and dependency
view and management at the canonical scopes. Customer-wide Service permissions
must apply at Customer scope. Writes use the existing Asset then Service row
locks, load current endpoints and effective grants after waiting, and recheck
grants before commit. Like Discovery Review, the check sees committed
revocations at its checkpoint. Grant administration remains independent. Link
Services does not change Asset identity or acquire the identity inventory lock.
The endpoint locks serialize it against changes made by inventory writers.
Atlas compares the reviewed removal version with the current relationship and
endpoint identity under those locks, before any canonical removal side effects.
Relationship provenance, Changes, audit and Knowledge Completeness use existing
canonical code. Progress writes use the existing Site workflow lock and
optimistic version. The preview uses the existing database schema.

## Later packets

Review & Ready and Showcase remain pending.
Public activation remains gated pending E1-H.
