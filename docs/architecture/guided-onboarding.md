# Guided setup preview (AT-R01 / E1-A and E1-B)

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
for the signed-in user. **Guided setup** opens the authorized chooser for Site managers.
**Continue setup** opens progress for the active Dashboard Site or identifies
a sole resumable Site if it differs from the workspace selection. The chooser
marks Sites with resumable progress, suggests a unique authorized pair and
requires explicit selection when there are several choices. It uses the same
Customer and Site create and rename APIs as normal administration. Each create
has its own confirmation and transaction. If creating a Site fails, the
Customer remains selected. If a create response was lost, refresh choices and
look for the record before retrying.

Choose the **Homelab** or **Blank** profile and confirm Environment. The wizard
then opens the Capabilities placeholder. E1-B supplies the catalogue and
workflow commands through the preview API. The selection, review and Apply
controls are scheduled for E1-C. Use **Back to
Environment** to inspect the confirmed pair or rename it if authorized. **Save
& exit** saves the pending profile and returns to Atlas. On resume, Atlas
reselects the draft profile at Environment. Confirmation is a separate action.
A different pair has its own progress. A previously confirmed profile and
context stay fixed when you resume.

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
with an empty default selection. Associations are individually selectable and
eligible only when both endpoints are selected.

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
  The draft clears on success. The first decision advances to Add Integrations,
  which is pending. Later imports preserve the cursor and other stage
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

## Later packets

E1-C will expose the Capabilities workflow through the wizard. Later packets
own integration setup, discovery review, Service linking, readiness and
Showcase using authorized records in the fixed Site context.
