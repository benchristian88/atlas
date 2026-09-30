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
Membership may anchor a recorded Network card, but never parents peer Assets.

Only hosted leaves assigned to the managed Workload position, or Automatic
hosted leaves, become host-local category groups. Intermediate hosts remain
explicit. Endpoint-position leaves and the existing built-in `access_point` key
can become branch-local Type groups; this stable built-in key accounts for its
existing Access Network default. No type display name or vendor is matched.
Later stages may group repetitive Automatic leaves, but named structural
positions and Types with children remain explicit. Grouping also requires
identical actual neighbour signatures, preserving multihoming/shared-host truth.
Category ordering and colors use managed category metadata. Disconnected Type
groups never get connectors or global workload-category grouping.

Each increasingly compact attempt measures occupied subtree contours and packs
children deterministically, following Connectivity’s geometry approach. Short
side branches can share horizontal space with deeper branches at different
heights; empty bounding rectangles do not reserve entire columns. Managed
ordering and actual parentage remain authoritative. Stages are: endpoint
grouping; four-member workload previews; other repetitive Automatic leaf grouping; tighter spacing and local
category packing; wider packing and up to 14% uniform scale reduction.
Structural tiles are 204×44, with 17px name text. Workload/endpoint members use
150px columns, 32px rows (28px when tightened), 22px icons and 15px name text.
Single-member groups are 204px wide. Larger groups use two through five 150px
columns as their membership permits (3–5 for dense categories), with 8px gaps
and 12px side insets. Host-local packing uses a bounded width, allowing category
grids and intermediate host branches to occupy different vertical depths. Every
individual Asset tile is icon/name only. Type metadata still drives the existing grouping
and fallback rules. Position headings reserve only 18px at local position
transitions and are shared within sibling rows. They are outside Asset tiles and
participate in routing obstacles. The header ends at y=84, content starts at
y=100, and the disconnected region wraps its actual content.
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
consolidation. Routes retain their underlying edge IDs. Tests verify orthogonal
segments, node non-overlap, bounds and complete Asset representation. Both the
44-Asset Connectivity-shaped reference (including the office-side platform) and
a 50-Asset variant fit 1920×1080 at native scale. Adaptive height remains for
structures that genuinely need more depth.

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
[compact poster validation](../testing/showcase-compact-poster.md) and the
[original implementation record](../testing/showcase.md).
