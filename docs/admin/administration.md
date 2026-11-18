# Administration

The API authorizes every operation through explicit permission keys and separate
global, customer or site assignments. The header context narrows the current
workspace; it does not grant access to other customers or sites.

Under **System → Organisation**, authorized administrators manage Users,
Roles & permissions, Customers and Sites. Built-in role definitions are protected.
Atlas blocks removing or disabling the final usable global Master Administrator.
Passwords and MFA secrets are never readable through administration.

Customers and Sites can be deleted when unused. Deletion retains creation and
deletion audit snapshots. Other records or retained history can prevent deletion,
including access assignments and history retained after a Service or Business
Function is deleted. The refusal gives one explanation without identifying
dependencies the operator might not be allowed to read. Use **Edit → Status →
Inactive** to stop using a record while preserving its dependencies and history;
Inactive does not make a used record deletable. A disabled Delete action explains
missing permission. A refused deletion keeps the loaded rows and shows an action
error rather than reporting a failed table load.

**System → Reference Data** holds managed taxonomy, custom fields and knowledge
profiles. Deactivate used definitions to retire them while retaining history.
See [Service Types and Criticality](service-types-and-criticality.md),
[Asset Types](asset-types.md) and [Knowledge profiles](knowledge-profiles.md).

Global System Settings administrators manage session lifetime and can see the
installed version in the navigation footer when available. The Updates card
shows installed version, channel, build and installation method, checks release
availability and links to manual upgrade guidance. About opens the page with a
product overview, licence and project links. Global Master Administrators can
use encrypted Backup & Restore. See [backup/restore](../deployment/backup-restore.md)
and [upgrades](../deployment/upgrades.md).

**System → Audit Log** is read-only and permission-filtered. Use **Previous**
and **Next** below the table to browse up to 30 events per page, newest first.
The count above the table is for the current page, and the footer shows
the position of those events among the matches.
Applying or clearing filters, or changing the workspace customer or site,
returns to the first page. Expand an event to see its recorded details and
identifiers.

**Changes** presents meaningful knowledge changes separately. Account preferences,
password changes, appearance and optional MFA are under **My profile**. See
[local MFA](../deployment/mfa.md) and
[authentication/access architecture](../architecture/authentication-and-access-control.md).
