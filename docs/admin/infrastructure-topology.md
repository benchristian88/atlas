# Exploring Infrastructure Topology

Open **Knowledge → Topology**. The page is named **Infrastructure Topology**. It shows where infrastructure runs,
which recorded Networks it belongs to, and its recorded connections. The
Knowledge Graph remains the place for Service and Business Function context.
Both views use Atlas knowledge; topology adds no separate truth store.

Choose a Customer and Site using the normal workspace context. Counts and details
include only records you may view. **Refresh** reloads the current records while
preserving valid search, filters, focus, selection and graph viewport. No
live monitoring or freshness estimate is implied.

- **Overview** summarises visible Assets, Networks, interfaces and represented
  categories. Each category previews up to six Assets in name/ID order; **+N**
  shows how many more visible Assets it contains. **View all** opens Assets
  filtered by that category. An Asset preview opens its normal detail page;
  Overview does not expand inline details. Select a Network to open its detail.
- **Platform** groups top-level Assets by managed category in a wrapping card
  grid. Recorded hosting, running and containment relationships supply compact
  child tiles. A card shows eight children initially; **Show all** expands the
  full list without pagination. **View platform** opens a child's own recorded
  children. Standalone Assets remain visible. A closed relationship cycle is
  explicitly labelled and remains navigable. Cards and child tiles show IPs from
  recorded interfaces only. A primary interface is preferred; otherwise the first
  interface in name/ID order is used. **+N** counts additional distinct addresses,
  including when a primary exists. Assets without interface IPs omit that line.
- **Network & VLAN** has a vertically scrollable Network list and selected
  Network detail. Membership comes only from explicit Asset interface records.
  A multihomed Asset can appear in several Networks, with each interface's IP
  and MAC where recorded. Gateway is a stored value, never a synthesized device.
- **Connectivity** starts with one focused Asset. Search and choose another,
  then select **1 hop** or **2 hops**. The Asset remains centred in a bounded
  graph. Solid lines show recorded Asset relationships with canonical labels;
  dashed lines show interface membership. A workload → host → sibling path is
  suppressed, as is Asset → Network → peer membership. Other recorded paths,
  such as workload → host → switch, can still continue. Focus the host itself
  to see its directly hosted Assets, or select/focus a Network to see its recorded
  members. Network detail is available from its inspector. Select an Asset to
  inspect it.
  **Focus Connectivity** explores the selected Asset. **Fit** restores the
  fitted zoom, and the zoom buttons and canvas scrolling support closer inspection.
  The focus stays central, with second-hop nodes outside their first-hop branch.
  Layout space grows to avoid overlapping cards.

Connectivity shows at most 25 nodes and 150 edges, with a truncation notice when
necessary. Category and Network filters apply before traversal, so a hidden node
cannot connect two otherwise disconnected visible nodes.

**Filters** opens a compact temporary category selector beside the button,
including administrator-created and inactive categories with their configured
icons and accents. Choices apply immediately; click outside or press Escape to
close it. Tab moves through the checkboxes and back into the page. Initial choices
follow **Show in Infrastructure Topology by default** in managed Asset Categories.
You can enable Uncategorized or another hidden category temporarily. The button
counts only choices changed from those defaults. **Reset to defaults** restores
the managed choices and keeps the selector open. These changes never edit Atlas
knowledge or Reference Data.

Clicking a different topology view starts it with fresh defaults: blank search,
managed category choices, closed Filters and no previous inspector selection.
Platform returns to its child previews and normal ordering. Network & VLAN selects
the first Network in VLAN/name/ID order. Connectivity returns to one hop, Networks
enabled, its first visible Asset in name/ID order, and a fitted viewport.
Customer, Site and theme stay unchanged. Clicking the current view does not reset
it. Explicit **Focus Connectivity** and **Open Network detail** navigation honour
the requested Asset or Network as the new initial context. An explicitly focused
Asset's category is enabled for that view if needed.

Search finds Platform Assets and children, Networks and their connected Assets,
or Assets in the Connectivity selector.

The inspector includes recorded status, type, category, visible Site, hostname,
interfaces and key relationships. **Open Asset** opens its detail page; **View in
Knowledge Graph** opens broader recorded context. Asset artwork uses the shared
cached Asset icon, then the type default, then the generic Asset icon.

Category icons and accents come from [managed Asset Categories](asset-categories.md).
They identify Overview summaries, Filters and Platform headings. Asset cards
use a subtle category accent while keeping the Asset's own icon. Child tiles use
the child's category, even when the parent belongs to another category. The four
top Overview metrics use fixed Atlas icons and accents.

Platform cards, child tiles and category headings use neutral Atlas borders.
Network & VLAN list rows and detail surfaces also use neutral borders; configured
colours remain in icon tiles and subtle background tints. The selected Network
keeps its stronger neutral outline and inset marker in both themes.

Network icons and accents come from [Network presentation settings](networks.md).
They repeat in the Network list, detail header and Connectivity nodes. Dashed
interface membership lines use their Network's accent; solid technical
relationships retain their existing styling. A multihomed Asset keeps its
category accent regardless of its Networks. Repeated Network colours are normal;
names, VLAN IDs and CIDRs distinguish the records.

Accents express identity, never health or status. Focused Connectivity nodes have
a heavier border; selected nodes have an outer ring, and keyboard focus uses a
dashed outline. These remain distinct from the category or Network accent in
both themes. Refresh after editing presentation settings to reload them.

The four-arrow **Expand Infrastructure Topology** button fills the Atlas viewport without using browser
fullscreen. Close with the button or Escape. Tab, selection, filters, expanded
child lists, graph zoom/pan and Network detail remain intact, and page scrolling
is restored. Expand and Refresh do not apply the tab-switch reset rule.
This surface is designed for desktop and laptop use; narrower windows retain a
usable stacked layout.

**Recorded status is not live health.** Atlas does not infer devices, links or
Network membership from subnets, gateway addresses, names, or similar metadata.
CPU, memory, traffic, uptime, backup freshness and other monitoring telemetry are
not shown. Missing fields are omitted rather than invented.

The Assets table shows hostname rather than the legacy top-level Asset IP. IP
search matches recorded interface addresses where you have permission to view
interfaces; legacy Asset IPs no longer supply search matches.

## Record an IP address

IP addresses belong to Asset Interfaces. Create the Asset with its identity and
inventory details, then open its detail page and use **Interfaces and networks →
Add interface**. Enter the interface name, IP address and optional Network. Mark
an interface primary when appropriate. Asset editing does not change interface
addresses. Assets without an Interface IP show no address in topology.
