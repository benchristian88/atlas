# Managing Networks

Open **Knowledge → Networks** and use **Add Network** or a row's **Edit** action.
Customer and Site scope, Network type, VLAN ID, CIDR, gateway, purpose, zone and
notes keep their existing meanings. A VLAN ID belongs to the Network record;
there is no separate VLAN entity.

**Icon** and **Accent** are optional presentation choices with Network / Blue
defaults. Under **Presentation**, open either compact dropdown to choose a named
icon or accent swatch. The small Network-name preview updates immediately.
Arrow keys browse choices; Enter or Space selects and closes the menu, and
Escape closes without changing the value. Save to persist the combination.
Atlas supplies a bounded infrastructure icon set and ten accents: Blue, Green,
Purple, Orange, Red, Teal, Cyan, Amber, Slate and Rose. Arbitrary colours, uploads
and icon URLs are not supported by these fields.

The same identity appears in [Infrastructure Topology](infrastructure-topology.md):
the Overview Network list, Network & VLAN list and detail, Connectivity Network
nodes, and dashed interface membership lines. Colours adapt to light and dark
themes. Networks may share an accent; names, VLAN IDs and CIDRs remain visible.
VLAN numbers and Network names do not determine colours automatically.

An accent does not indicate health, success, failure or live monitoring. Assets
connected to multiple Networks retain their own Asset Category accent and Asset
icon. Editing presentation changes no membership, address, scope or recorded
operational status. Save, then refresh topology to see the changes.

## Interface observations and assignment

The **Networking** card on Asset detail shows the recorded **Hostname** for
Asset readers. Manage it through **Edit asset**. When an evaluated required
Hostname gap is visible to the viewer, a missing value reads **Required, not
recorded**. Viewing the **Interfaces** subsection requires Network access.

**Assigned Atlas Network** shows the Network name and canonical VLAN or **Not
assigned**. **Observed Proxmox attachment** shows the latest recorded bridge
(`proxmox.bridge_name`) and VLAN tag (`proxmox.vlan_tag`) independently. The
assigned VLAN and observed tag can differ. Topology membership and the graph's
`contextual_vlan` use the canonical Interface → Network link.

Expand **Discovery details** to see each observation's acceptance state,
authorised source name, last-observed time and acceptance time when recorded.
The view selects at most one accepted and one latest unaccepted observation per
fact. A later run omitting a fact leaves its original timestamp and retained
knowledge intact. The observations represent recorded evidence at those times.

Users with scoped `networks.edit` can use **Edit** on the Interface row. The
editor updates the name, IP, MAC, primary flag, notes or assigned Network.
Choose **Unassigned** and save to unlink an existing assignment. Observed
bridge, VLAN tag and evidence are read-only in this editor.

Whole-Interface configuration acceptance preserves the current Network assignment
when the source omits `network_external_id`; other accepted configuration fields
still apply. Preview and Changes retain that assignment. A new Interface without
membership information remains unassigned. A nonempty reference must resolve
through an approved source identity in the same customer/site before acceptance;
an unresolved reference blocks acceptance. VLAN numbers, names and bridge labels
never select a Network. Automatic membership for tagged guests requires a separate
source-contract decision. Deliberate unlinking remains the existing operator
Network assignment workflow (`PATCH /api/asset-interfaces/{id}` with
`network_id: null`). No new unlink action is introduced. AIP explicit null is
invalid; older Atlas assertions normalised omission to null internally.

Proxmox guest Interface observations held for an
[identity review](cross-source-reconciliation.md#proxmox-guest-identity-review)
remain source evidence. Reactivate keeps the existing Interface bindings.
Replacement ends applicable bindings in the reviewed DataSource while the old
Asset retains its Interface UUIDs and Network assignments. A replacement Asset
starts without Interfaces or inherited assignments. Review released Interface
observations independently. An explicit source Network reference must resolve
in the same scope before acceptance. An omitted reference leaves a newly
accepted Interface unassigned.

The additive Asset-detail read is
`GET /api/asset-interfaces?asset_id={id}&include_knowledge=true`. It retains the
existing limit/offset bounds (default 500, maximum 1,000 Interfaces), adding
`assigned_network: {id, name, vlan_id} | null` and `observed_facts` entries with
`predicate`, scalar `value`, `is_accepted`, `source_name`, `last_observed_at` and
`accepted_at`. It requires both `assets.view` and `networks.view` on the owning
Asset, respects active customer/site scope, and hides invalid or unauthorised
Network links and foreign-source facts. Local/site-wide source attribution follows
the existing Asset Knowledge rules. Source IDs, run IDs and evidence payloads
are excluded. Without `include_knowledge`, the existing list shape is unchanged.
Retired Asset detail and retained-history deletion protection are unchanged.
