# Managing Networks

Open **Knowledge → Networks** and use **Add Network** or a row's **Edit** action.
Customer and Site scope, Network type, VLAN ID, CIDR, gateway, purpose, zone and
notes keep their existing meanings. A VLAN ID belongs to the Network record;
there is no separate VLAN entity.

**Icon** and **Accent** are optional presentation choices with Network / Blue
defaults. Select a named icon and an accent swatch to preview the combination.
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
