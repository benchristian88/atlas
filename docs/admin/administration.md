# Administration

The API authorizes every operation through explicit permission keys and separate
global, customer or site assignments. The header context narrows the current
workspace; it does not grant access to other customers or sites.

Under **System → Organisation**, authorized administrators manage Users,
Roles & permissions, Customers and Sites. Built-in role definitions are protected.
Atlas blocks removing or disabling the final usable global Master Administrator.
Passwords and MFA secrets are never readable through administration.

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
