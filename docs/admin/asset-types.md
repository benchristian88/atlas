# Asset Types

Use **System → Reference Data → Asset Types → Add / Edit** to manage inventory
Types. Changes require global `asset_types.manage`; reading uses
`asset_types.view`. Every Type belongs to a managed Asset Category.

**Topology position** controls default placement in Infrastructure Topology.
Choose **Automatic** or an active [Topology Position](topology-positions.md),
listed in administrator-configured order. Custom positions appear dynamically.
The API writes only `topology_position_id` (nullable UUID) and returns the nested
`topology_position` identity, name, key, order and active state.

New Types default to Automatic (`topology_position_id = null`). Automatic uses
recorded parent/child relationships and neighbouring physical/network positions,
then a neutral fallback. It never parses Type names, Asset names, vendors, icons,
hostnames or descriptions. Existing explicit assignments survive migration;
subsequent choices are administrator-controlled, including for inactive Types.

Deactivating a position preserves its placement and shows its name with an
inactive label when editing an assigned Type. It cannot be newly assigned.
Select another position or Automatic to reassign explicitly.

Category controls taxonomy, filtering, accent, category icon and broad grouping.
Asset icons retain cached Asset → Type default → generic precedence. Position
changes affect presentation without creating Assets or relationships, changing
traversal, inferring failure, or rewriting accepted operational knowledge.
See the [Infrastructure Topology guide](infrastructure-topology.md).
