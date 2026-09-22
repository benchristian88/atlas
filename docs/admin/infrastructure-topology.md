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
  Child Asset and interface facts appear only for positive recorded counts, with
  singular/plural wording; cards with neither omit the metadata line.
- **Network & VLAN** has a vertically scrollable Network list and selected
  Network detail. Membership comes only from explicit Asset interface records.
  A multihomed Asset can appear in several Networks, with each interface's IP
  and MAC where recorded. Gateway is a stored value, never a synthesized device.
- **Connectivity** starts with one focused Asset. Search and choose another,
  then select **1 hop** or **2 hops** to explore a bounded graph.
  Solid lines show recorded Asset relationships;
  dashed lines show interface membership. A workload → host → sibling path is
  suppressed, as is Asset → Network → peer membership. Other recorded paths,
  such as workload → host → switch, can still continue. Focus the host itself
  to see its directly hosted Assets, or focus a Network to see its recorded
  members. Single-click an Asset or Network to inspect it without changing focus
  or rearranging the graph. Double-click its card, or choose **Focus Connectivity**
  in the inspector, to explore that entity. Keyboard users can Tab to a node,
  press Enter or Space to select it, then activate the inspector action.
  The **Focus** selector displays the focused Asset or Network; selection is
  separate. Refocusing selects the new focus, retains hops and filters,
  and fits/recentres the new graph, clearing previous zoom and pan. Search-result
  selection clears search and closes its popup. If the focused Asset’s category
  is hidden, enable it in Filters to show its connectivity. The inspector action
  is hidden for the current focus. Network detail is available from its inspector.
  **Fit** restores fitted zoom and clears pan, centring the graph horizontally
  near the top with roughly 28px below the internal toolbar. Automatic Fit uses
  the same placement. Zoom buttons and canvas scrolling support closer inspection.
  Each Type's Topology Position remains authoritative for vertical placement.
  Empty positions collapse; no infrastructure is invented.
  Recorded relationships group related cards horizontally, with parents centred
  over visible branch footprints. Connections use vertical trunks, shared horizontal
  rails and vertical drops. Long connections use clear tracks around intervening
  cards; sharing an upstream neighbour never moves an Asset into another position.
  Relationship labels are shown in the details panel, which also retains canonical
  direction and related Assets. Focused hosts show
  the first eight returned children in name/ID order, followed by a connected
  circular **+N more** control for the remainder. A collapsed neighbour's **+N**
  badge opens its first eight children; any remainder gets its own **+N more**
  control. Both support Enter/Space. Expansion preserves focus, selection, hops,
  filters and Networks, including in full screen; changing focus or leaving
  Connectivity resets it. These controls and their connectors are presentation
  only, never Assets or recorded Relationships. Direct focus connections and
  ancestors remain visible. Hosted children use a grid and branching rails; select a child to
  inspect its individual canonical relationships.

  In expanded Connectivity, the compact **Hide details panel** / **Show details
  panel** icon releases/restores the inspector's width. Selection continues while
  hidden, and reopening shows the latest selection. This never refetches the graph.
  Closing expanded mode restores the embedded inspector. Canvas dimensions and
  Fit respond to the available width.

[Managed Topology Positions](topology-positions.md) determine ordered presentation bands; actual
accepted relationships determine connectivity. Automatic assignments use relationship
context and otherwise a neutral band. Names and vendors never
infer placement. Networks use actual interface memberships to find an intermediate
position; multihomed Assets retain their own position. Network icon/accent and dashed
membership semantics are unchanged. Persisted manual positioning is intentionally
deferred; layout positions are ephemeral presentation output. Background position
containers are also deferred.

Connectivity retrieves at most 100 nodes and 500 edges while keeping initial
child presentation compact. A safety warning appears only when that technical
limit is reached; intentionally collapsed branches are not truncation. **+N**
counts only returned children that can actually be revealed, never unavailable
children beyond the safety or hop limits. Category, relationship-class and Network filters apply before traversal,
so a disabled relationship cannot introduce a node, create a second-hop path or
consume a node-limit slot.

**Filters** opens a compact temporary selector beside the button. Asset categories
appear in every view, including administrator-created and inactive categories with their configured
icons and accents. Choices apply immediately; click outside or press Escape to
close it. Tab moves through the checkboxes and back into the page. Initial choices
follow **Show in Infrastructure Topology by default** in managed Asset Categories.
You can enable Uncategorized or another hidden category temporarily. The button
counts category and relationship-class values that differ from defaults.
**Reset to defaults** restores the managed category choices and default classes,
keeping the selector open. These changes never edit Atlas knowledge or Reference
Data.

Connectivity adds **Relationship classes**:

- **Platform / containment** — on by default.
- **Physical / network** — on by default, including derived AssetInterface → Network membership.
- **Data / resilience** — off by default.
- **Logical / operational** — off by default.
- **Other** — off by default.

This starts with infrastructure placement and technical connections. Application
and logical relationships belong primarily in Knowledge Graph; enable their
class temporarily when needed. Disabling Physical / network also disables
interface-membership traversal; the existing Networks checkbox separately
controls Network visibility. Disabling Physical / network and enabling Logical /
operational counts as two changed values.

[Relationship Type administration](relationship-types.md) assigns these classes.
New custom types default to Other until an administrator deliberately classifies
them. Routes remains Other because Atlas does not yet model full L3 routing;
enabling it does not infer routers, gateways or routing paths.

Clicking a different topology view starts it with fresh defaults: blank search,
managed category choices, closed Filters and no previous inspector selection.
Platform returns to its child previews and normal ordering. Network & VLAN selects
the first Network in VLAN/name/ID order. Connectivity returns to one hop, Networks
enabled, default relationship layers, its first visible Asset in name/ID order,
and a fitted viewport.
Explicit refocusing inside Connectivity, Expand/close and Refresh preserve layer
choices. Customer, Site and theme stay unchanged. Clicking the current view does not reset
it. **Focus Connectivity** from another view and **Open Network detail** navigation
honour the requested Asset or Network as the new initial context. An explicitly
focused Asset's category is enabled for that view if needed.

Search finds Platform Assets and children, or Networks and their connected Assets.
In Connectivity, **Search assets** finds an authorised Asset by name, hostname or
interface IP and makes it the Connectivity focus. It shows up to ten matches
from the current authorized topology after one character; typing does not filter
the graph or the separate Focus selector. Select a result with the pointer, or
use Arrow Up/Down and Enter. Escape closes results; Tab moves to Focus. Search,
inline Focus, hops and Networks share one compact toolbar that wraps at narrower
widths, including expanded mode.

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
uses a slightly stronger configured background tint in both themes, with the
same neutral border as unselected rows. Keyboard focus retains its dashed outline.

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
