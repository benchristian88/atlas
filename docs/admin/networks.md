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

Asset detail shows **Assigned Network** and its **Canonical VLAN** separately
from **Observed VLAN** (`proxmox.vlan_tag`) and **Observed bridge**
(`proxmox.bridge_name`). An unlinked Interface says **No Network assigned** even
when it has an accepted observed tag. Differing observed and canonical VLANs stay
visible; neither value is automatically changed. Topology membership continues
to use only the canonical Interface → Network link. `contextual_vlan` in graph
responses remains derived from that link.

Each displayed observation has its own acceptance state, authorised source name
and last-observed time. The view selects at most one accepted and one latest
unaccepted observation for each of these two facts. Acceptance does not mean a
fact was observed again: a later run omitting a fact leaves its original timestamp
and retained knowledge intact. This view does not claim current confirmation or
fact withdrawal, and does not show full history or raw evidence.

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
