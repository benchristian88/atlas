# Exploring Infrastructure Topology

Open **Knowledge → Infrastructure Topology**. It shows where infrastructure runs,
which recorded Networks it belongs to, and its recorded connections. The
Knowledge Graph remains the place for Service and Business Function context.
Both views use Atlas knowledge; topology adds no separate truth store.

Choose a Customer and Site using the normal workspace context. Counts and details
include only records you may view. **Refresh** reloads the current records. No
live monitoring or freshness estimate is implied.

- **Overview** summarises visible Assets, Networks, interfaces and represented
  categories. Select a category to focus Platform, or a Network to open its detail.
- **Platform** groups top-level Assets by managed category in a wrapping card
  grid. Recorded hosting, running and containment relationships supply compact
  child tiles. A card shows eight children initially; **Show all** expands the
  full list without pagination. **View platform** opens a child's own recorded
  children. Standalone Assets remain visible. A closed relationship cycle is
  explicitly labelled and remains navigable.
- **Network & VLAN** has a vertically scrollable Network list and selected
  Network detail. Membership comes only from explicit Asset interface records.
  A multihomed Asset can appear in several Networks, with each interface's IP
  and MAC where recorded. Gateway is a stored value, never a synthesized device.
- **Connectivity** starts with one focused Asset. Search and choose another,
  then select **1 hop** or **2 hops**. The Asset remains centred in a bounded
  graph. Solid lines show recorded Asset relationships with canonical labels;
  dashed lines show interface membership. Two hops through a Network can reveal
  another member without claiming a direct physical connection between members.
  Select an Asset to inspect it; select a Network to open Network detail.
  **Focus Connectivity** explores the selected Asset. **Fit** restores the
  initial zoom, and the zoom buttons support closer inspection.

Connectivity shows at most 25 nodes and 150 edges, with a truncation notice when
necessary. Category and Network filters apply before traversal, so a hidden node
cannot connect two otherwise disconnected visible nodes.

**Filters** lists managed Asset Categories, including administrator-created and
inactive categories. Initial choices follow **Show in Infrastructure Topology by
default**. You can enable Uncategorized or another hidden category temporarily.
These changes apply only to the current view and never edit Atlas knowledge.
Search finds Platform Assets and children, Networks and their connected Assets,
or Assets in the Connectivity selector.

The inspector includes recorded status, type, category, visible Site, hostname/IP,
interfaces and key relationships. **Open Asset** opens its detail page; **View in
Knowledge Graph** opens broader recorded context. Asset artwork uses the shared
cached Asset icon, then the type default, then the generic Asset icon.

**Expand Infrastructure Topology** fills the Atlas viewport without using browser
fullscreen. Close with the button or Escape. Tab, selection, filters, expanded
child lists and Network detail remain intact, and page scrolling is restored.
This surface is designed for desktop and laptop use; narrower windows retain a
usable stacked layout.

**Recorded status is not live health.** Atlas does not infer devices, links or
Network membership from subnets, gateway addresses, names, or similar metadata.
CPU, memory, traffic, uptime, backup freshness and other monitoring telemetry are
not shown. Missing fields are omitted rather than invented.
