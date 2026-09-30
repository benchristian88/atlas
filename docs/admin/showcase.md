# Showcase v1

Open **Topology → Showcase** after selecting a Site in the workspace context.
Showcase is a deterministic presentation/export projection of existing Atlas
knowledge. Its subject and title are the current Site, with the existing Atlas
light-background logo. **Export PNG** produces an image at exactly twice the
poster dimensions, named from the Site, for example `the-workshop-atlas-showcase.png`.

The preferred composition is 1920×1080 (16:9), exporting at 3840×2160. If compact
grouping still needs more vertical space, Showcase selects the minimum readable
height up to 1358 logical pixels, approximately A3 landscape proportions. Width
stays 1920. For example, a 1920×1240 poster exports at 3840×2480.

The complete composition scales proportionally to the browser width; taller
posters have taller previews, with no internal scrolling or cropping. Resizing
does not rearrange the diagram or change its selected dimensions. The PNG
rasterizes that same SVG scene at 2× resolution, including its header, grouping,
icons, text and connectors. It is always light, including when the surrounding Atlas application is dark. App
navigation and the Export button are outside the image.

Every authorized Asset in the current Site is represented individually or in a
truthfully counted local group. Showcase includes categories hidden by default
in the operational topology views. It does not use Connectivity's hop, 100-node
or 500-edge limits. No current Site, no Assets, a failed data load, or an
unreadable composition has no export action. A site with too many independent
structural branches for the readability floor shows **Showcase incomplete**;
it never exports a partial diagram.

All individual tiles show only an icon and Asset name. Asset Type remains
internal to grouping, classification and icon fallback; it is not a second line
in the tile. Managed Topology Positions define shared horizontal bands in their configured
order, with small headings outside nodes and no large position containers.
Physical and platform hosts align across branches; explicit same-position chains
retain local subrows. Empty positions reserve no space. Names that exceed a fixed text budget
are ellipsized; the full name is available in the SVG's accessible title. No IPs, hostnames,
status, telemetry, timestamps, evidence or source metadata appear in the image.

Recorded Asset-to-Asset relationships determine the branches. Platform and
physical/network classes supply structure. Showcase always uses Networks-off
semantics: logical Network/VLAN entities and interface-membership edges are
excluded before layout. Gateway, router, switch and other network-device Assets
remain eligible. There is no Showcase Networks toggle; the operational
Connectivity toggle is unchanged.
The diagram adds no Internet node unless Atlas already records it as an Asset.
Disconnected Assets appear in **Unconnected / Other**, aligned to their Position
bands without an invented link.

Hosting relationships take priority over compactness. Physical hosts, platform
hosts, intermediate container hosts and their children retain their actual
branches. Workload leaves use their Asset Type's managed Asset Category inside
that specific host's branch when two or more eligible workloads share the local
category. A singleton appears directly under its actual host, without a category
wrapper. Two hosts with the same category remain separate; a singleton never
moves into another host's group. Categories with 2–4 Assets use one column;
5+ use exactly two, filled in stable name order row-wise from left to right.
Categories stack within their host's workload band, preferring a taller poster to
wide strips. Relationships determine horizontal branch placement; compaction
moves entire bands while preserving their order. Very wide sets of peers can
occupy multiple rows within their band. Categories do not define domain parentage. No cluster membership
or cluster containers are inferred.

Repetitive endpoints are grouped by Asset Type within the same actual branch.
This includes the managed Endpoint position and the existing built-in access
point type (which defaults to Access Network). Structural parents remain named.
A group shows its authorized total, up to four compact icon/name previews, and **+N**
for the remaining members. Relationships into the same presentation group share
a connector; individual accepted relationships are unchanged. Extra or shared
connections remain represented, and differently connected leaves are not merged.
Disconnected endpoints may share a Type group in Unconnected / Other.

Category groups omit redundant workload-count footers. Collapsed category groups
retain **+N** for the members outside the visible preview; endpoint Type groups
retain their existing truthful device totals.

When needed, Showcase progressively collapses large workload categories,
then repetitive Automatic leaf siblings, then tightens spacing and applies
modest scale compaction. It tries 16:9 before allowing extra poster height;
**Showcase incomplete** is the final fallback if the complete scene still cannot
fit. No Assets are silently omitted. The minimum scale remains 0.86: workload
names stay at least 12.9 logical pixels, structural names 14.62, and secondary
headings/counts 12.04. The preview naturally appears smaller on a narrow browser;
its logical composition remains identical.

Cached Asset icons take priority, followed by the existing safe Asset Type icon
source and managed category/generic artwork. Optional images have a bounded
loading window and failures fall back to local artwork. Export becomes available
once resources have resolved. Images are embedded before export, so PNG creation
makes no external requests and works offline once the preview is ready.

Showcase has no filters, focus, hops, inspector, fullscreen, drill-down, manual
layout, editing, cluster inference, title settings or saved diagram state.
Platform and Connectivity remain unchanged. PostgreSQL remains the system of
record; no Showcase entities, relationships, coordinates or migrations are added.
