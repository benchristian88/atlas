# Exploring the Knowledge Graph

The Knowledge Graph shows recorded connections between Business Functions,
Services and Assets. Select a node to read its details in the inspector.
For hosting, Networks, VLANs and technical connectivity, use the separate
[Infrastructure Topology](infrastructure-topology.md) surface.

Use **Expand Knowledge Graph** beside **Fit** to fill the application viewport.
The same graph, filters, selected entity and inspector remain available. On a
wide screen the inspector sits alongside the graph; on mobile it occupies a
scrollable panel below it. Close with the top-right X or Escape. Keyboard focus
returns to Expand and the page returns to its previous scroll position.

**Focus** shows a neighbourhood around one entity. Depth means relationship hops
from that entity, in either direction; it does not mean outage impact.
The normal graph offers depths **1** and **2**. Expanded Focus also offers
**3**, which can reveal another layer of recorded infrastructure and may be
denser. Overview has no depth control.

Closing at depth 3 returns to depth 2, retaining focus and filters. Reopening
stays at depth 2; select depth 3 again when needed. A copied depth-3 link opens
at depth 2 in the normal view and makes depth 3 available when expanded.
Expand and Close do not add browser history entries.

Filters still determine which entity types and relationships are visible.
Structural Asset relationships are hidden by default. Hiding relationships in
Focus also removes nodes whose only visible connection used those relationships.
If filtering or lowering depth removes the selected entity, the inspector falls
back to the focused entity.

**Find in graph** offers matches in the visible graph for selection and location,
plus authorized Customer matches that can become a new Focus. Use **Fit** to
reframe the canvas, and scroll, pan or zoom to explore. Dense lanes retain their
existing “more” controls. A warning indicates when the server truncated a graph.

**Preview unavailable** remains a hypothetical scenario with explanations in the
inspector. Expand and Close preserve the scenario; **Exit analysis** returns to
recorded knowledge. Analysis may show explanation context beyond the structural
Focus depth and retains that context when relationship lines are filtered.
Neither depth nor expansion changes recorded dependencies or predicts live
availability. Asset artwork uses the same cached icon and fallback rules as the
normal graph.

Expanded Knowledge Graph automatically Fits on entry, details-panel hide/show,
viewport resize, and return to the embedded view. Expanded lanes spread across
the measured graph area, excluding the inspector, with tighter row spacing and
uniform card scaling. Leaving expanded mode restores the embedded layout and Fit.
**Hide/Show details panel** preserves the selected entity.
Manual zoom and pan remain undisturbed until a structural viewport change or
explicit **Fit**. Fit measures both available width and height.
