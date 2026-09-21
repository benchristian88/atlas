# Asset Types

Use **System → Reference Data → Asset Types → Add / Edit** to manage inventory
Types. Changes require global `asset_types.manage`; reading uses
`asset_types.view`. Every Type belongs to a managed Asset Category.

**Topology role** controls default placement in Infrastructure Topology. It is
presentation metadata, not an Asset's operational meaning or a dependency rule.

| Role | Placement |
| --- | --- |
| External / Internet | Above edge infrastructure |
| Security / edge | Above routing |
| Routing | Above network fabric |
| Core / aggregation network | Above access network |
| Access network | Above platform infrastructure |
| Platform / host | Platform band |
| Infrastructure appliance | Platform band; does not imply hosted children |
| Workload | Below platforms |
| Endpoint / device | Workload / endpoint band |
| Automatic | Relationship context, otherwise neutral infrastructure |

New custom Types default to **Automatic**. Choose an explicit role for predictable
placement. Automatic uses recorded parent/child relationships and neighboring
known physical/network roles. It never parses Type names, Asset names, vendors,
icons or descriptions. Existing recognized built-ins receive one-time migration
defaults; custom Types and unknown built-ins remain Automatic. Subsequent changes
are administrator-controlled, including for inactive Types.

Category still controls category filtering, accent, category icon and broad
grouping. Asset icons retain cached Asset → Type default → generic precedence.
Role changes do not create Assets or relationships, change traversal, infer
operational failure, or rewrite accepted knowledge. See the
[Infrastructure Topology guide](infrastructure-topology.md).
