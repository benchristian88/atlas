# Topology Positions

Use **System → Reference Data → Topology Positions** to control vertical ordering
in Infrastructure Topology. Reading requires `asset_types.view`; adding, editing,
moving and deleting require global `asset_types.manage`, like Asset Categories.

- **Category** is broad Asset taxonomy, filtering and visual identity.
- **Topology Position** is managed ordered Reference Data controlling where Assets
  of an Asset Type normally sit vertically in Infrastructure Topology.
- **Topology Class** is bounded Relationship Type classification controlling how
  relationship edges participate in Connectivity.
- **Relationships** determine actual connectivity.

Add a name, immutable lowercase key, optional description and active state.
New positions append at the bottom. Use the accessible **Move up / Move down**
buttons to change order; numeric ranks are internal. Boundary buttons are disabled,
changes persist, and ranks remain unique even across concurrent writes.
Custom positions such as Storage Fabric work without code changes.

Assign positions in [Asset Types](asset-types.md). **Automatic** is a null
assignment, not a Reference Data record. Automatic placement uses recorded
relationships and neighbours' configured positions, with a neutral fallback.
It never parses vendor, Asset name, Asset Type name, hostname, icon or description.

Deactivation preserves existing assignments and their layout placement. An
inactive assignment remains visible in the Asset Type editor but is unavailable
for new assignments. Deletion is rejected while any Asset Type references the
position; explicitly reassign those Types to another position or Automatic first.
The usage count counts global Asset Types, not customer/site operational records.

Changing order changes presentation only: it does not modify accepted Asset or
relationship knowledge, dependency semantics, traversal or impact conclusions.
Only positions represented by visible nodes consume graph space; empty positions
produce no empty bands. Background band decoration is not implemented.

The initial positions preserve the former registry's labels and sequence:
External / Internet, Security / edge, Routing, Core / aggregation network,
Access network, Platform / host, Infrastructure appliance, Workload,
Endpoint / device. The former Platform/Infrastructure and Workload/Endpoint
rank ties are resolved in that sequence into independently ordered bands.
Administrators control all subsequent ordering, including unusual arrangements.
