# Showcase: one knowledge model, a presentation projection

Showcase v1 is a read-only tab on the existing `/topology` page. It is separate
from Overview, Platform, Network & VLAN and Connectivity. No new route, persistence,
background worker or domain topology model is introduced. ADR-0001 remains intact.

## Authorized data and semantic contracts

The existing `GET /api/topology` loads complete authorized collections, without
pagination or Connectivity's traversal caps. Showcase uses those collections
under the current workspace's customer/site headers. Every returned site Asset
participates regardless of category visibility defaults. The client additionally
requires a current Site and rejects foreign-site Assets from its scene; backend
`scope_condition` remains the security boundary.

`TopologyResponse.structural_edges` is an additive complete edge projection using
the existing `ConnectivityEdge` contract. The service projects only platform and
physical/network relationship classes, plus authorized interface memberships.
It runs after the existing endpoint authorization and Network-ID redaction.
Counts and layout cannot receive hidden endpoints through this projection.

Canonical direction stays in `source_key`/`target_key`. `platform_parent_key`
resolves the existing runs_on/member_of/hosts/contains/runs semantics and the
explicit child-to-parent `hosted_on` relationship. The legacy `platform_links`
field and Connectivity implementation are unchanged: `hosted_on` therefore does
not silently alter Platform's existing presentation. Custom Platform-class
relationships do not acquire inferred containment semantics. AssetRelationship
has no temporal validity columns; this continues to project accepted recorded
rows, without interpreting observations or temporal Service relationships.

## Shared Connectivity geometry

`web/lib/topology-geometry.mjs` is the single pure topology placement and routing
implementation. It was extracted from Connectivity, retaining its default card
metrics, position containers, contour packing, focus-origin handling and routing.
`infrastructure-topology.mjs` re-exports the existing operational API; its Platform
preparation, search and progressive disclosure remain separate and unchanged.
Neither view imports React UI or another view's interaction state for geometry.

`buildTopologyLayoutModel` resolves managed ranks, Automatic positions and primary
recorded upper anchors. Topology Position IDs and sort orders are authoritative;
labels, vendor names, categories, focus and traversal arrival do not choose parents.
Same-rank physical chains use local distance from recorded upper neighbours.
This shared correction fixes the formerly unanchored distribution-to-access-switch
chain without changing its managed rank. Closed unanchored cycles remain level;
anchored cycles and bidirectional/parallel records terminate deterministically.
Secondary relationships remain cross-links, with canonical edge endpoints intact.

`calculateTopologyGeometry` performs Connectivity's branch-local vertical
clearance, sibling grids, subtree contour packing, ancestor centering and collision
avoidance. `routeTopologyEdges` reuses its trunks, rails, drops, shared group
connectors, exterior tracks and bounded `orthogonalDetour` search.
`topologyBounds` measures both nodes and route extents. Connectivity compatibility
wrappers retain 180×88 cards, four-column grids, operational position containers,
focus origin, preview controls and Fit behavior. All 29 existing Connectivity
layout tests remain unchanged.

Showcase passes the complete current-site Asset graph without a focus or hop
limit. `topologyGraphEligibility(..., false)` keeps Asset nodes and edges with
eligible Asset endpoints and rejects typed `membership` edges. Networks/VLANs and
interface nodes never enter layout; network device Assets remain. Backend
Connectivity already applies the same Networks-off domain eligibility before its
bounded traversal; its API, toggle and authorization remain unchanged.

`showcase.mjs` owns only site input adaptation, local category presentation,
compact metrics, poster fitting and last-resort preview policy. Categories are
assigned **after** complete-site ranks and branch ownership are established.
Only hosted workload/Automatic leaves sharing their actual parent, position,
category and neighbour signature can share a wrapper. One member stays a direct
tile, 2–4 use one column, and 5+ use two columns. All intermediate hosts stay
individual; a category never changes parentage. Geometry receives the original
ownership model even for an enormous-site preview. The planned two-category
stacking enhancement is not implemented.

Compact Asset tiles are 124×32, with a 22px icon and one 15px name line. Category
members use 112×22 tiles, 4px column spacing and 32px row spacing. Repetitive
terminal Asset siblings use a one-column grid; structural branch owners retain
Connectivity's four-column policy. Smaller footprints may share unused contour
space across positions, using the same packer. Showcase omits operational
Position containers and does not impose separate global Y bands. Managed ranks,
local same-position depth, parent ownership and horizontal branch order are the
same as Connectivity; pixel coordinates and leaf presentation may differ.

All Assets are attempted first. Normal sites never use workload or endpoint
roll-ups. The generic 44-Asset and 50-Asset fixtures fit 1920×1080 with all current
workloads explicitly visible. The first platform host's two container hosts and
their children retain their real ownership. Both physical-server/platform-host
branches match Connectivity. Node and category rectangles are routing obstacles;
category headers have reserved space and shared incoming group connectors retain
all accepted edge identities.

Poster fitting first tries 1920×1080 at the existing 0.86 readability floor, then
the minimum integer taller height up to 1358. Only sites exceeding 100 Assets may
attempt four-member workload previews, after the complete compact geometry fails
at every allowed height. A preview requires uniform hosting semantics and no
secondary neighbours; mixed or multihomed groups remain explicit. If geometry
still cannot fit, export is unavailable and no partial scene is returned.
Internal diagnostics record explicit/group/Asset counts, measured route-inclusive
bounds, required scale, chosen height, stage attempts and failure reason.

See [shared-geometry acceptance](../testing/showcase-shared-geometry.md). Earlier
independent packers and global bands are preserved in historical test records.

## Rendering and export

`components/showcase.js` draws one light-only SVG with a deterministic
`viewBox="0 0 1920 H"`, where H is the selected height from 1080 through 1358.
The preview frame uses that same aspect ratio. Only its CSS size changes on
browser resize. Layout is memoized by data and Site, not viewport. Managed category palette variables resolve under
`color-scheme: light`. Labels use fixed measured text budgets and Arial, shared
by preview and rasterization. Long Asset names preserve both ends around a
middle ellipsis, keeping numbered peer names distinguishable. The existing light Atlas SVG is embedded in the
header; Site name supplies the title.

`lib/showcase-export.mjs` reuses `assetIconSources` for cached/type URL validation.
It resolves only displayed members, deduplicates URLs, uses six workers and a
five-second overall optional-resource deadline, and embeds data URLs before
export readiness. Cached API requests include authentication credentials;
external Type images do not. External SVG is excluded because it could reference
other resources; the trusted bundled logo SVG is allowed. Raster images are
frozen to a decoded PNG, including animated Type fallbacks. Missing images use
managed local SVG artwork.

Export waits for fonts, clones the displayed SVG, freezes its computed SVG
presentation styles, verifies all image references are data URLs, and rasterizes
the clone to a canvas exactly twice its logical viewBox dimensions: 3840×2160
for 16:9, up to 3840×2716 for the tallest allowed poster. It never stretches a
taller scene back to 16:9. A data URL avoids the application's image CSP
restriction on blob image sources. The downloadable PNG uses an object URL that
is revoked after use. There is no hidden second renderer, alternative layout,
external request during export, or theme-dependent export mode.

See [operator guidance](../admin/showcase.md),
[shared-geometry validation](../testing/showcase-shared-geometry.md) and the
[original implementation record](../testing/showcase.md).
