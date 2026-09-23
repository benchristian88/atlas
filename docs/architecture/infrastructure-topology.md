# Infrastructure Topology and managed Asset Categories

Infrastructure Topology is a read-only projection of PostgreSQL Asset,
AssetRelationship, AssetInterface and Network records. It preserves ADR-0001's
relational source of truth and does not replace the operational graph or its
Service/Business Function semantics. No positions, grouping, membership edges or
layout coordinates are persisted.

## Managed categories

Migration `20260921_0019` follows `20260912_0018` and adds `asset_categories` with
UUID identity, unique immutable API key, name, description, sort order, active
state, topology default visibility and standard timestamps. `asset_types.category_id`
is a non-null RESTRICT foreign key. The database default identifies the protected
Uncategorized record, allowing existing internal type registrations to remain valid.
API creation requires an explicit category ID; null, missing and inactive new
assignments are rejected. Existing inactive assignments may remain unchanged.

The migration reads exact distinct nonblank category strings. UUIDs derive
reproducibly from the original value; safe keys are generated in sorted order,
with deterministic suffixes for collisions. Case, whitespace and punctuation
variants are not merged. Names retain the original value. Blank/null values map
to Uncategorized; an exact existing `Uncategorized` value maps to that protected
record. Uncategorized starts hidden, and other migrated categories start visible.
A database check/trigger plus API guards protect the fallback's active state,
name, key and existence. Used categories cannot be deleted.

The original `asset_types.category` column remains a frozen upgrade snapshot for
safe rollback. It is not an editable taxonomy source. Managed API responses
resolve `category` from the category record and add `category_id`/`category_key`.
Writes use `category_id`; the old free-text write field is rejected. This is an
intentional required-assignment change to type creation/editing, while response
compatibility is retained. Downgrade copies managed names back before removing
the new schema. Discovery's unseen types use Uncategorized rather than creating
another free-text category. Existing discovery-created `discovered` categories
are migrated like any other legacy category.

Categories share the existing global Asset Type reference-data permissions.
Counts on the category management page refer to global Asset Types, never hidden
Asset inventory. Topology receives category/type presentation metadata under
`assets.view`, without requiring reference-data administration permission.

## API and authorization

`GET /api/topology` retains its six existing collections and adds category/type
metadata and explicit `platform_links`. Asset response enrichment is batched.
The route uses existing `scope_condition` and workspace context filtering.
Relationships require both Asset endpoints to pass `assets.view` and
`relationships.view`. Interfaces require visibility of their Asset and
`networks.view` for that Asset's scope. An interface's inaccessible Network ID is
redacted; neither its name nor a membership edge is emitted. Network, Customer
and Site records retain their own permission checks. Counts are derived only
from these authorized collections.

`GET /api/topology/connectivity` accepts exactly one of `focus_asset_id` or `focus_network_id`, `hops=1|2|3`,
optional repeated `category_ids`, comma-separated `topology_classes`, `show_networks` and `limit` (default and maximum
100). An inaccessible or nonexistent focus returns the same 404. Omitted category
IDs use managed visibility defaults. The domain service performs deterministic,
cycle-safe breadth-first traversal after authorization and presentation filtering.
Traversal tracks arrival state: child→parent arrival suppresses parent→child
containment expansion; Asset→Network membership arrival suppresses membership
expansion back to peer Assets. Other enabled relationship classes remain eligible.
An explicit host/Network focus has no arrival restriction. Parallel eligible
technical paths are considered separately. This is presentation connectivity,
not a claim of physical connection or failure impact. Each node adds nullable
`parent_key` discovery metadata for deterministic branch layout; that key can
only reference an authorized returned node.
Edges retain recorded direction even when traversed backwards. Nodes use
`asset:<UUID>` / `network:<UUID>` identity; edges use `relationship:<UUID>` or
`interface:<UUID>`. Network membership comes only from `AssetInterface.network_id`.
The server owns the 100-node / 500-edge safety policy; the UI uses its default.
The response reports `node_limit`, `edge_limit` and truthful `truncated` status.
Asset nodes include deduplicated `eligible_child_count` after authorization and
category/class filtering, and `returned_child_count` from returned edges. Eligible
children can be outside the hop/arrival policy or safety budget; only returned
children can be expanded. Counts never include inaccessible endpoints. The
existing scoped topology loader still loads its authorized collections before
bounded traversal; these are traversal/output limits, not SQL row limits.

AssetRelationship has no temporal validity fields in the current schema. The
projection uses its recorded rows; it does not read temporal Service links or
reinterpret observations/assertions as accepted connectivity.

## Managed relationship classes

`RelationshipType.topology_class` is a bounded non-null classification, default
`other`. Platform and physical/network are enabled by default; data/resilience,
logical/operational and other require explicit inclusion. The original `0021`
migration seeded exact recognized built-in keys; `0023` renames the column while
preserving every value. Unknown/custom types remain Other until explicitly edited.

Omitted `topology_classes` uses `platform,physical_network`; an explicit empty
string enables none. Unsupported values return 422. The service filters edges
before building adjacency, so disabled paths cannot affect reachability, limits
or second hops. AssetInterface membership participates only with
`physical_network` and `show_networks=true`; it remains derived structured data.
An explicitly focused Network may remain as a standalone node when that class
is off. Category filters and all existing authorization boundaries still apply.

`app/topology_classes.py` and `web/lib/topology-classes.json` define the bounded
registry/default contract, compared by a test. Filters render registry classes,
not individual Relationship Types. Their difference count includes category and
class overrides; reset restores both. Tab entry resets classes, while in-view
refocus, expansion and refresh retain them. Reference Data is never changed by
these temporary controls.

Knowledge Graph does not consult this field. Endpoint eligibility, recorded
labels/direction, Platform containment and dependency-analysis semantics remain
independent. Routes is `other`, deliberately outside default Connectivity until
Atlas has a developed L3 model; no routing inference is added.

## Platform semantics and presentation

Migration 0004 establishes stable built-in relationship keys and directions:
`runs_on` and `member_of` point from child to parent; `hosts`, `contains` and
`runs` point from parent to child. The topology domain service projects these
explicitly. It never derives parenthood from category labels, Asset Type labels,
names, IPs, or vendor metadata. Custom relationship keys participate in Connectivity
when their managed class is enabled, without acquiring containment meaning.
`hosted_on` receives the platform class but does not change the existing Platform
parent/child projection.

React only groups/filters the authorized domain projection. Platform displays
compact child previews in an auto-fitting desktop grid. Card facts show only
positive child/interface counts, with singular/plural wording and no empty line. Network & VLAN uses
vertical master/detail. Connectivity uses deterministic top-to-bottom managed
branch-local position ordering with fixed 180×88 cards. AssetType has nullable
`topology_position_id` referencing `TopologyPosition`; its joined relationship is
serialized as `topology_position` with id, immutable key, name, sort_order and
active state. Connectivity copies this summary only onto already-authorized nodes.
Relationship edges expose `topology_class` and optional `platform_parent_key`.

Configured sort_order is authoritative, even for inactive positions and unusual
ordering. There is no runtime position registry or built-in key ranking. Rank
is ordinal, not distance: only connected upper neighbours constrain a node's Y.
All eligible upper neighbours constrain placement, including secondary anchors.
Independent sibling positions can share Y. `connectivityBands` retains semantic
rank metadata for compatibility; it does not describe absolute horizontal rows.

Automatic nodes have no position assignment. Snapshot-based rounds infer rank
from recorded parent/child neighbours first, then adjacent physical/network
neighbours. The relative step comes from visible configured order gaps; no
business-specific rank or name matching exists. Rounds terminate within the
returned node count. Unanchored containment roots seed a neutral rank (the
midpoint of configured visible ranks, or zero); closed cycles and isolated Assets
use that fallback. Networks use membership rank midpoints, or just above a single
member rank, without moving multihomed Assets. These are ephemeral layout hints.

Recorded upper neighbours anchor horizontal groups, preferring projected platform
parents. Strictly increasing rank makes this presentation forest cycle-safe.
Local siblings with the same position share a baseline after their upper
neighbours; leaf grids reserve only actual rows. The renderer packs occupied
subtree/card/container contours before centring parents over descendants.
Different sibling positions reserve separate horizontal space but may share Y.
Each branch reserves 16px from its parent card/container bottom to an external
rail and another 16px from that rail to its child card/container top. This uses
actual local bounds, including footer and disclosure space, rather than global
ranks. Managed-position sibling grids use four aligned columns at every viewport
size, including fullscreen: eight children form 4+4; eighteen form 4+4+4+4+2.
Cards have 32px horizontal and vertical gaps (212px horizontal and 120px vertical
centre spacing). An expanded descendant does not restore a single-row sibling
layout. Descendant forests start below their complete parent group's bounds.
The optional five-column mode is not used; zoom and inspector resizing do not
change grid membership or column count.

`connectivityPositionMembership` derives semantic identities from the primary
upstream anchor and durable Position ID. Coordinates, proximity, member names
and descendant counts never split these groups or enter their identity.
Different anchors remain separate. Singleton identities are retained internally,
while `connectivityPositionGroups` draws backgrounds only for two or more Assets.
Automatic nodes, Networks and disconnected roots remain unboxed.

Groups wrap actual cards, consistent padding and a bottom-left label footer.
Matching +N more controls attach by parent anchor and Position ID, centred beneath
the final visible grid row. Their actual dimensions extend the bounds without
entering Asset membership or counts. Packing works on complete semantic sibling
groups so unrelated cards are kept outside, rather than dissolving a group when
its members spread apart. Footer labels retain a clear vertical exit lane.
The managed position name labels the group; a stable hash of its ID selects a
subtle existing Atlas palette tint, independent of Category and label/order edits.
Borders and text identify groups without colour. Containers are ephemeral and
never enter persistence, accepted knowledge, traversal or API responses.

A local preview limits focused-parent direct children to eight in name/ID order.
A collapsed neighbour has a circular +N badge when returned eligible children
are hidden; it opens the first eight. Once children are visible, a connected
circular +N more control reveals the remainder. Only one control exists per
parent, and its count includes only children actually available in the response.
Direct focus neighbours and ancestors remain visible. Shared children are counted
once per parent and remain visible if another expanded branch reveals them.
Disclosure nodes/edges are separate presentation collections merged only for
layout/rendering; they never enter API, inspector, traversal or accepted knowledge.
Children retain their managed position identity and local order; the more
control follows the child grid inside its matching container’s visual bounds. Native sibling buttons isolate expansion from card inspection and
refocus; Enter/Space work for both controls. Expansion preserves selection,
hops, filters and Networks, survives Refresh/fullscreen, and resets on focus
change or leaving Connectivity. No extra request or write occurs. Intentional
collapse does not set truncation; the server safety warning remains separate.
All Connectivity edges use orthogonal trunks, horizontal distribution rails and
vertical drops, including physical relationships and dashed Network membership.
Routes check padded cards, footer labels and containers. External horizontal
segments stay outside containers; unrelated containers block vertical segments
too. Individual overlays terminating on an interior grid card may use orthogonal
card gaps within their endpoint containers when a direct vertical drop is blocked.
Cards and footer labels remain obstacles on every route.
Relationships wholly within one local container may use internal tracks, still
avoiding cards and labels. Source rails are below the parent’s complete bounds;
child drops enter from above the child container with a visible gap. Container
bounds include members, disclosure controls, padding and labels, never rails.

Two or more Assets sharing a backend-projected platform parent and matching
relationship metadata use one presentation connector ending at the group border.
It has no domain arrow or relationship label. All original edge records remain
available to the inspector; no synthetic domain relationship is created.
Single children, mixed relationship semantics, physical links and dashed Network
membership retain individual routes. Matching disclosure controls share the group
connector. Selecting any member highlights the shared connector.

Simple shared trunks/rails/drops are preferred. If an obstacle intervenes,
deterministic exterior tracks preserve these endpoint zones. Dense overlays
that need more bends use a bounded rectilinear visibility search over obstacle
boundary coordinates. Every returned segment undergoes the same obstacle checks;
there is no diagonal fallback. Shared rails retain individual relationship
records and canonical arrow direction.
Graph bounds include routes, cards, local containers and disclosure controls. Relationship text is
shown in the details inspector, not on the canvas. Other graph renderers are
unchanged. Expansion and available viewport width recompute geometry while
preserving semantic selection and disclosure state.

Automatic and manual Fit centre the complete graph horizontally and align its
upper bound near the toolbar (16px viewport inset plus the 12px toolbar gap).
Scale accounts for both dimensions and padding; large graphs retain scroll/pan
and zoom. Refocus and disclosure size changes reset Fit; resizing the fullscreen
inspector preserves layout coordinates and follows existing zoom/pan rules.

A uniform Fit transform scales the complete layout rather than compressing node
positions. Cards live in an HTML layer over SVG edges, so shared AssetIcon's
positioned image layers share the card's normal HTML containing block instead
of an SVG foreignObject. Network cards use the shared semantic Network icon. Cycles remain selectable and do not disappear. The existing
`ExpandedGraphSurface` now accepts a title while retaining Knowledge Graph's
default, modal focus/scroll handling and a single mounted tree. Shared AssetIcon
preserves cached Asset → type default → generic precedence. Existing Atlas
branding and theme tokens remain authoritative.

The topology workbench has one explicit view-entry initializer. Ordinary clicks
on a different tab clear category and relationship-class overrides, search, inspector/parent/Network
selection, child expansions and Connectivity focus/hops/Network-toggle state.
The destination graph mounts at Fit; Network and Asset fallback ordering remains
deterministic. A shared category-selection helper resolves temporary overrides
against current `show_in_topology` values and counts only differences. Filters
uses Atlas dropdown styling with native labelled checkboxes in an anchored,
non-modal popover; it never changes document flow or persists Reference Data.
Expand retains the mounted tree and viewport state. Refresh retains current data
while refetching and replaces the authorized projection without clearing valid
controls or remounting an unchanged Connectivity graph.

Inspector focus from another view and Network detail navigation supply new
initial context to view entry, including visibility of the requested Asset's
category. Within Connectivity, a separate refocus handler serves the Focus
selector, Asset search, native node double-click and inspector action. It retains
hops and category/relationship-class/Network filters. Search selection clears its
text and popup; other refocus actions retain search text. A hidden focus category
remains hidden with an explanatory message. Explicit Network refocus enables
Network visibility when necessary. The compact focus finder matches at most ten
Assets by name, hostname or interface IP from the existing backend-authorized
projection, independent of presentation category filters. It issues no extra
Asset-list request and never uses the legacy Asset IP. Asset and Network single-click selection
never changes the query or layout input. Selection uses entity identity separately
from focus, including Network inspectors; an already-focused selection has no
refocus action. Node buttons retain native Enter/Space selection, with the
inspector action providing keyboard refocus. Connectivity is keyed by focus so
navigation fits a fresh viewport, while selection and expand retain the canvas.

The topology route currently has no URL/query-state or Asset-detail deep-link contract; this
polish does not add one. Existing `/knowledge-graph?focus=…&depth=1` inspector links
are unchanged. Temporary controls and ordinary topology tabs do not write history.

## Bounded presentation identity

Migration `20260921_0020` adds non-null `icon_key` and `accent_key` strings to
AssetCategory and Network, preserving IDs and existing fields. Server/API
defaults are infrastructure/slate for categories and network/blue for Networks.
Exact known category names receive one-time migration defaults: Compute
server/blue, Software and Workload cube/green, Network network/cyan, Storage
database/purple, Backup archive/orange, Data database/teal. Other/custom names
and Uncategorized receive infrastructure/slate. No runtime category-name or
VLAN-based presentation rules exist. Downgrade removes only the four new fields.

`app/presentation.py` defines the API write contract, mirrored by the shared
frontend `presentation-registry.json`; a contract test compares every key.
Fourteen icon choices resolve through NavigationIcon. Ten predefined accents
resolve through `presentation.css` to theme-aware foreground, tile, border,
tint and emphasis variables, independently of workspace branding and status
tokens. Invalid writes (including explicit null) are rejected. Omitted fields
use defaults on creation and remain unchanged on PATCH. Response strings permit
historical values; renderers fall back to infrastructure/network and slate.

Existing category/Network response schemas carry the metadata through the
authorized topology projection without additional queries or permissions.
Asset presentation resolves through its type's category once during projection.
AssetIcon's cached/type/generic precedence remains intact. Membership edges
resolve the target Network's accent; relationship edges retain their styling.
Neither this metadata nor its colour affects graph traversal, scope, status,
membership or dependency semantics. Both admin forms use the shared compact
PresentationPicker with labelled menu buttons, checked menu choices, keyboard
navigation and a live preview. Text labels, checkmarks, checkboxes, heavier focus
borders and selection rings keep colour secondary.

## Source audit and deliberate omissions

The old UI hard-coded Asset Type sets and five relationship lenses. Assets already
used dynamic Asset Type selectors, not a hard-coded category selector. A managed
category selector was added without removing those type filters.

Repository legacy category values: `Other`, `Network`, `Compute`, `Software`,
`Data`, `Storage`, `Backup` (built-in seeds), `Migrated` (legacy migration), and
`discovered` (discovery registration). Tests and fixtures supplied no additional
literal Asset Type categories before this change. Migration tests now cover
custom names and collisions explicitly.

Network VLAN/CIDR/gateway and interface name/IP/MAC/membership are stored fields.
Proxmox normalization records runs_on relationships, bridge Assets, selected
metadata and observed facts. Arbitrary vendor fact/metadata fields are not a
universal canonical telemetry contract. This surface deliberately omits vendor
VM identifiers and all utilization/uptime/traffic/backup-health telemetry rather
than assigning cross-vendor meaning or freshness to those fields. No new telemetry
fields, inferred gateway devices, physical links or shared-subnet relationships
were introduced.

## Interface-first display and search

Overview shows twelve authorized Asset previews per category, plus an explicit
remainder and category-filtered Assets link. Preview links open canonical Asset
detail routes and never create an Overview inspector. The sidebar label is
Topology; the product/page name remains Infrastructure Topology.

Platform cards and child tiles use a shared deterministic interface IP helper:
primary interfaces first, then interface name/ID; distinct additional IPs appear
as +N. No recorded interface IP means no IP line. The legacy Asset field is not
used by topology presentation or search. The Assets table retains hostname and
removes the legacy IP value. Assets API search uses a correlated EXISTS over
AssetInterface IPs, with networks.view scoped to the owning Asset, matching
existing interface visibility. This avoids duplicate rows/pagination distortion
and prevents interface existence leaking through search. Asset/customer/site
scoping remains authoritative. The legacy schema/API field is retained; no
migration is needed.


## Managed position migration and lifecycle

Migration `20260921_0023` follows `0022`. It creates TopologyPosition with timestamps,
seeds nine explicit former registry entries, then backfills a nullable restrictive
AssetType FK directly from the former `topology_role`. Automatic becomes null.
Distinct unexpected legacy values become additional positions; no assignment is
silently discarded. It removes the old role column and renames RelationshipType's
`topology_layer` to `topology_class`, preserving classification values. These old
names exist only in migration history and migration regression tests.

Seed labels and registry sequence are frozen in the migration. The former shared
Platform/Infrastructure and Workload/Endpoint ranks become unique adjacent ranks
in registry order, resolving the conflicting exact-layout/unique-rank requirements.
All other ordering is retained; administrators can reorder every position.

The Reference Data API uses existing asset_types.view/global asset_types.manage
permissions and audit events. Create appends; move swaps adjacent ranks under a
PostgreSQL table lock and deferred unique constraint. Key and numeric rank are
not editable through PATCH. Inactive positions remain readable and retain all
assignments. New assignments must be active. Deletion is restricted by both API
validation and the FK. Counts concern global Asset Types, never scoped Assets.

Downgrade reconstructs the old role from each assigned key, null as Automatic.
The rollback check includes actually-used custom keys; the older application's
bounded API may not recognize those custom keys even though the database retains
them. Assigned keys longer than
the former varchar(32) capacity block downgrade before any changes, requiring
explicit reassignment rather than truncation. A re-upgrade preserves those keys;
managed-only names/order/lifecycle customizations are not representable in the
old schema. Application and API field/query renames deploy together; there is
no parallel writable compatibility field. Exactly one Alembic head remains.

Expanded Connectivity's inspector visibility is local workbench state. Hiding it
removes its grid track while retaining selection and the mounted graph. Existing
ResizeObserver updates canvas dimensions; hiding/showing does not change query
inputs. Closing expanded mode restores the embedded inspector. Knowledge Graph
and the shared expanded surface behavior are unchanged.
