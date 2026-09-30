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

## Deterministic layout

`web/lib/showcase.mjs` builds a temporary presentation forest, prioritizing
server-projected hosting edges. Managed position sort order, existing name/ID
ordering and edge identity break ties. Physical adjacency determines hierarchy
within the same position. Iterative visited sets and parent-cycle checks bound
work to the returned data. Cycle and secondary/shared-parent edges remain
cross-links; the presentation forest never replaces domain relationships.
Showcase follows the eligibility rule in backend Connectivity
`show_networks=False`: construct only Asset nodes and retain accepted structural
edges between those Assets. It never adds Network/VLAN nodes or interface
membership edges. This uses the existing typed `membership` edge kind and durable
Asset keys, not labels or vendor heuristics. Filtering happens before parentage,
neighbour signatures, grouping and layout, so excluded Networks reserve no space.
The complete topology API and Connectivity toggle remain unchanged; the Python
query/traversal is not duplicated or coupled to the JavaScript layout.

Only hosted leaves assigned to the managed Workload position, or Automatic
hosted leaves, become host-local category groups when at least two eligible
members share the parent/category/neighbour signature. Singleton workloads remain
explicit Asset tiles under their actual parent. Intermediate hosts remain
explicit. Endpoint-position leaves and the existing built-in `access_point` key
can become branch-local Type groups; this stable built-in key accounts for its
existing Access Network default. No type display name or vendor is matched.
Later stages may group repetitive Automatic leaves, but named structural
positions and Types with children remain explicit. Grouping also requires
identical actual neighbour signatures, preserving multihoming/shared-host truth.
Category ordering and colors use managed category metadata. Disconnected Type
groups never get connectors or global workload-category grouping.

Managed Topology Position IDs define global vertical bands, ordered by managed
`sort_order` and captioned with the managed display name. Numeric sort-order gaps
and unused positions reserve no height. Automatic/unassigned items follow the
explicit bands. The cycle-safe presentation forest retains relationship-derived
same-position depth as local subrows. Structural peers align across different
parents, including unconnected Assets. The complete occupied band height is
measured before placing the next band; compaction cannot move a branch into a
different Position.

Within each band, workload/category and endpoint-group siblings stack under their
own parent. Horizontal subtree-contour packing retains actual branch ownership
but never changes Y. Very wide sibling sets use deterministic overflow rows
inside their band; descendants inherit the overflow row so branches can reuse
columns. Unconnected Assets occupy a separate side region aligned to their
assigned bands, without invented links.

Stages remain: endpoint grouping; four-member workload previews; other repetitive
Automatic leaf grouping; tighter spacing; wider packing and up to 14% uniform
scale reduction. Structural tiles remain 204×44, with 17px name text. Category
membership determines the grid: one Asset stays direct, 2–4 use one 204px card
column, and 5+ use exactly two 150px member columns in a 332px card. No category
uses more than two columns, including collapsed previews. Member order is the
existing name/ID order, filled row-wise left-to-right. Rows are 32px high (28px
when tightened), with 22px icons and 15px name text. Fully visible categories use
8px bottom padding; collapsed categories retain 26px for +N. Endpoint Type-group
preview columns and totals remain unchanged.

Each occupied managed band reserves an 18px caption above its content. There are
no decorative Position containers. Captions participate in routing obstacles.
The header ends at y=84 and content starts at y=100. Individual Asset tiles remain
icon/name only. Type metadata still drives grouping and fallback rules.
Text starts at 14 logical pixels, giving a 12.04px minimum after scaling.
No stage removes a branch. All stages first try the preferred 1920×1080 poster.
If height prevents a readable fit, the renderer chooses the smallest integer
height across eligible compact layouts, up to 1358; width remains 1920. Measured
route extents participate in fit calculations. Height cannot compensate for an
excessively wide scene. The same data and metadata select identical dimensions.
If geometry still cannot fit, export is unavailable with an explicit incomplete
state. Internal diagnostics record Asset/explicit-node/group/category/root
counts, measured content width/height, poster height, required scale, readability
floor, fit reason and each attempted stage. Development logs expose failure
diagnostics; production UI retains a concise message. This is a readability
boundary, not a data-fetch cap.

The existing Connectivity `orthogonalDetour` function is exported unchanged for
obstacle routing. Showcase owns its card sizes, packing and connector
consolidation. Routes use destination-row distribution rails and short drops;
stacked groups prefer a shared side trunk before obstacle detours. Routes retain
their underlying edge IDs. Tests verify orthogonal segments, node/caption
avoidance, global band ordering, bounds and complete Asset representation. The
44-Asset reference (including the office-side platform) uses 1920×1220; the
50-Asset variant uses 1920×1170, both above the unchanged 0.86 readability floor.
These taller posters preserve semantic alignment and bounded category widths.

## Rendering and export

`components/showcase.js` draws one light-only SVG with a deterministic
`viewBox="0 0 1920 H"`, where H is the selected height from 1080 through 1358.
The preview frame uses that same aspect ratio. Only its CSS size changes on
browser resize. Layout is memoized by data and Site, not viewport. Managed category palette variables resolve under
`color-scheme: light`. Labels use fixed measured text budgets and Arial, shared
by preview and rasterization. The existing light Atlas SVG is embedded in the
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
[Position-band validation](../testing/showcase-position-bands.md) and the
[original implementation record](../testing/showcase.md).
