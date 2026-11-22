# Guided setup foundation (AT-R01 / E1-A)

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
then opens Capabilities, the saved cursor for the next packet. Use **Back to
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
  E1-A writes only the Environment decision. Last actor and ordinary Atlas audit
  events record authenticated mutations. Per-user invitation dismissal is held
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

## Later packets

Catalogue application and its provenance belong at Customer scope. Integration
setup, discovery review, Service linking, readiness and Showcase will use
canonical authorized records from the fixed Site context. Later packets can add
explicit stage commands, with the same scope, concurrency and attribution
contract. E1-A persists workflow decisions without copying operational records.
