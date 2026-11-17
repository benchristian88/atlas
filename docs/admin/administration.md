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

Global System Settings administrators manage session lifetime and view installed
version/channel/build identity. Global Master Administrators can use encrypted
Backup & Restore. The Updates card checks release availability and links to
manual upgrade guidance. About shows installed identity, licence and project
links. See [backup/restore](../deployment/backup-restore.md) and
[upgrades](../deployment/upgrades.md).

**System → Audit Log** is read-only and permission-filtered. **Changes** presents
meaningful knowledge changes separately. Account preferences, password changes,
appearance and optional MFA are under **My profile**. See
[local MFA](../deployment/mfa.md) and
[authentication/access architecture](../architecture/authentication-and-access-control.md).
