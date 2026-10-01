# Showcase v1

Open **Topology → Showcase** after selecting a Site in the workspace context.
Showcase is a deterministic presentation/export projection of existing Atlas
knowledge. Its subject and title are the current Site, with the existing Atlas
light-background logo. **Export PNG** produces an image at exactly twice the
poster dimensions, named from the Site, for example `the-workshop-atlas-showcase.png`.

The preferred composition is 1920×1080 (16:9), exporting at 3840×2160. Wide site
structures select the minimum readable width up to 3024 logical
pixels, allowing an ultrawide poster up to 2.8:1 at the preferred height. Height
stays 1080 unless the structure also needs vertical space; it may increase to
1358. For example, 2400×1080 exports at 4800×2160, and 2400×1240 exports at
4800×2480. Width and height adapt independently only when needed.

The complete composition scales proportionally to the browser width; wider
and taller posters preserve their selected proportions, with no internal
scrolling or cropping. Resizing
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

Difficult connections can use an outer gutter around the recorded topology,
keeping every Asset in its existing position. Category-connected edges can enter
or leave their own category box while avoiding names and cards. If a safe route
cannot be constructed, the message identifies a routing problem rather than
claiming that the poster is too large.

All individual tiles show only an icon and Asset name. Names exceeding their
fixed text budget use a middle ellipsis to preserve distinguishing endings,
with the full name in the SVG's accessible
title. No Asset Type, IP, hostname, status, count or secondary line appears in an
individual tile.

Showcase uses the same topology geometry as Connectivity, with smaller cards.
Managed Topology Position controls broad order; recorded relationships determine
branch ownership and same-position hierarchy. Placement remains branch-local,
so independent branches can compact vertically without changing their Position
or parent. Operational Position containers and global poster bands are omitted.

Showcase permanently uses Networks-off semantics. Logical Network/VLAN entities
and interface memberships are absent; gateways, routers, switches, access points
and other network-device Assets remain. There is no Networks toggle. Disconnected
Assets remain independent roots with no invented connections.

Physical hosts, platform hosts, container hosts and their child workloads retain
the same branches as Connectivity. Category wrappers organize hosted workload
leaves locally after topology ownership is established. A singleton stays direct;
2–4 members use one column and 5+ use two, in stable name order. Categories never
move a workload to another host or combine different hosts' children. The future
category stacking enhancement is not included.

Normal-size sites show all current Assets, including every workload and access
point. The 44- and 50-Asset reference shapes fit 16:9 with no **+N** roll-ups.
Showcase first attempts complete compact geometry, widening the poster and
adding bounded height only as needed. Only genuinely enormous sites (over 100
Assets) may try
four-member workload previews after complete geometry fails throughout the
supported width and height envelope. Those local groups
show **+N** for every represented member outside the preview; shared or mixed
connections remain explicit. Unreadable structures show **Showcase incomplete**
and disable export. The unchanged 0.86 scale floor keeps 15px Asset names at
least 12.9 logical pixels. Narrow-browser preview scaling does not alter the
logical poster or export.

Cached Asset icons take priority, followed by the existing safe Asset Type icon
source and managed category/generic artwork. Optional images have a bounded
loading window and failures fall back to local artwork. Export becomes available
once resources have resolved. Images are embedded before export, so PNG creation
makes no external requests and works offline once the preview is ready.

Showcase has no filters, focus, hops, inspector, fullscreen, drill-down, manual
layout, editing, cluster inference, title settings or saved diagram state.
Platform remains unchanged. Connectivity retains its controls and card styling;
same-position network hierarchy is corrected in the shared geometry engine. PostgreSQL remains the system of
record; no Showcase entities, relationships, coordinates or migrations are added.
