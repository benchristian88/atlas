# Managing Asset Categories

Open **System → Reference Data → Asset categories**. Categories organise Asset
Types and supply the category filters on Assets and Infrastructure Topology.
They are global reference data, managed with the existing Asset Type permissions:
`asset_types.view` for reading and global `asset_types.manage` for changes.

Add a name, stable key, optional description, sort order, active state and
**Show in Infrastructure Topology by default**. Keys use lowercase letters,
numbers and underscores, starting with a letter; they cannot change after
creation. Categories sort by sort order, then name.

Every Asset Type requires a category. Its create/edit form offers active
categories and retains its current category even if that category is inactive.
To try a custom taxonomy, create **Workload**, enable its topology default, then
create **Docker Compose** under Asset types and assign Workload. Assets of that
type automatically participate in filters and topology without code changes.

**Uncategorized** is the protected fallback. It remains active, retains its name,
and cannot be deleted. It starts hidden in topology but remains available in
Filters; Assets assigned to it remain normal inventory. Administrators can
change its topology default. New types registered by discovery use this fallback.

Deactivating a category preserves its assignments and display names. It prevents
new assignments but does not hide existing Assets. To delete a category, first
reassign all its Asset Types. Deletion never silently reassigns them.

Topology's checkbox means **default visibility**, not eligibility. Operators can
temporarily enable or hide any category, including inactive categories and
Uncategorized. These view filters do not edit reference data or accepted knowledge.
Categories control grouping and filtering; recorded relationships control where
Assets run or are contained.

Upgrades retain distinct legacy category values, including similar names such as
Network and Networking. Blank values become Uncategorized. Existing nonblank
categories start visible in topology, except the protected Uncategorized fallback.
Review duplicates deliberately through reference-data management.
