export const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
export function showcaseFixture(size = "medium") {
  const customer = { id: id(1), name: "Example", status: "active" };
  const site = { id: id(2), customer_id: customer.id, name: "The Workshop", status: "active" };
  const categories = [
    { id: id(3), name: "Infrastructure", key: "infrastructure", icon_key: "server", accent_key: "blue", show_in_topology: true, sort_order: 0 },
    { id: id(4), name: "Media & Photos", key: "media", icon_key: "application", accent_key: "purple", show_in_topology: true, sort_order: 1 },
    { id: id(5), name: "Home Automation", key: "home", icon_key: "home", accent_key: "green", show_in_topology: true, sort_order: 2 },
    { id: id(6), name: "Edge Devices", key: "edge", icon_key: "device", accent_key: "teal", show_in_topology: false, sort_order: 3 },
  ];
  const positions = ["security_edge", "aggregation_network", "access_network", "physical_host", "platform", "workload", "endpoint"];
  const labels = ["Internet / Edge", "Core / Aggregation", "Access Network", "Physical Host", "Platform / Host", "Workload", "Endpoint / Device"];
  const position = key => ({ id: id(700 + positions.indexOf(key)), key, name: labels[positions.indexOf(key)], sort_order: positions.indexOf(key) * 10 });
  const asset_types = [
    ["gateway", "Gateway / Firewall", 0, "security_edge"], ["core", "Core Switch", 0, "aggregation_network"],
    ["switch", "Access Switch", 0, "access_network"], ["server", "Physical Server", 0, "physical_host"],
    ["platform", "Platform Host", 0, "platform"], ["media", "Application", 1, "workload"],
    ["infra", "Container", 0, "workload"], ["home", "Application", 2, "workload"],
    ["ap", "Wireless Access Point", 3, "endpoint"], ["camera", "Camera", 3, "endpoint"], ["device", "IoT Device", 3, "endpoint"],
  ].map(([key, name, category, pos], i) => ({ id: id(20 + i), key, name, category_id: categories[category].id, category: categories[category].name, topology_position: position(pos) }));
  const data = { categories, asset_types, assets: [], relationships: [], platform_links: [], structural_edges: [], networks: [], asset_interfaces: [], customers: [customer], sites: [site], relationship_types: [
    { key: "connects_to", topology_class: "physical_network", source_label: "Connects to", directional: false },
    { key: "runs_on", topology_class: "platform", source_label: "Runs on", directional: true },
  ] };
  let counter = 100;
  const asset = (name, type, parent, hosted = false) => {
    const node = { id: id(counter++), name, asset_type: type, customer_id: customer.id, site_id: site.id, status: "active", ip_address: "192.0.2.99", hostname: "private.example.test" };
    data.assets.push(node);
    if (parent) {
      const edge = { id: id(10000 + counter), source_asset_id: node.id, target_asset_id: parent.id, relationship_type: hosted ? "runs_on" : "connects_to" };
      data.relationships.push(edge);
      if (hosted) data.platform_links.push({ relationship_id: edge.id, parent_id: parent.id, child_id: node.id });
      data.structural_edges.push({ key: `relationship:${edge.id}`, source_key: `asset:${node.id}`, target_key: `asset:${parent.id}`, platform_parent_key: hosted ? `asset:${parent.id}` : null, topology_class: hosted ? "platform" : "physical_network", kind: "relationship", directional: hosted, label: hosted ? "Runs on" : "Connects to" });
    }
    return node;
  };
  const gateway = asset("Gateway", "gateway"), core = asset("Core Switch", "core", gateway);
  if (size === "small") {
    const host = asset("Workshop Host", "platform", core);
    asset("Photo Library", "media", host, true); asset("DNS Service", "infra", host, true);
    asset("Archive Server", "server");
    return data;
  }
  const rack = asset("Rack Switch", "switch", core);
  const access = asset("Access Switch A", "switch", rack); asset("Access Switch B", "switch", rack);
  for (let i = 0; i < 5; i++) asset(`Wireless ${i + 1}`, "ap", rack);
  for (let i = 0; i < 7; i++) asset(`Camera ${i + 1}`, "camera", access);
  for (let i = 0; i < 8; i++) asset(`Device ${i + 1}`, "device", access);
  for (const letter of ["A", "B"]) {
    const server = asset(`Physical Server ${letter}`, "server", core), host = asset(`Platform Host ${letter}`, "platform", server, true);
    const count = size === "large" ? 100 : letter === "A" ? 6 : 1;
    for (let i = 0; i < count; i++) asset(["Plex", "Immich", "Sonarr", "Radarr", "Bazarr", "Overseerr"][i] || `Media ${i + 1}`, "media", host, true);
    for (const name of letter === "A" ? ["Auth Service", "Monitoring", "Reverse Proxy"] : ["DNS Service"]) asset(name, "infra", host, true);
    if (letter === "A") for (const name of ["Home Automation", "Device Manager"]) asset(name, "home", host, true);
  }
  asset("Archive Server", "server");
  return data;
}

// Distinct branch shapes matter more than repeating hundreds of workload leaves.
function structuralBuilder() {
  const data = showcaseFixture("small");
  data.assets = []; data.relationships = []; data.platform_links = []; data.structural_edges = [];
  data.asset_types.push({ ...data.asset_types.find(t => t.key === "platform"), id: id(40), key: "container_host", name: "Container Host", topology_position: { id: id(740), key: "container_host", name: "Container host", sort_order: 45 } });
  data.asset_types.push({ ...data.asset_types.find(t => t.key === "server"), id: id(41), key: "appliance", name: "Storage Appliance", topology_position: { id: id(741), key: "infrastructure", name: "Infrastructure appliance", sort_order: 46 } });
  const add = (name, type, parent, hosted = false) => {
    const asset = { id: id(100 + data.assets.length), name, asset_type: type, site_id: id(2), customer_id: id(1), status: "active", ip_address: "192.0.2.99", hostname: "private.example.test" };
    data.assets.push(asset);
    if (parent) {
      const relationship = { id: id(10000 + data.relationships.length), source_asset_id: asset.id, target_asset_id: parent.id, relationship_type: hosted ? "runs_on" : "connects_to" };
      data.relationships.push(relationship);
      if (hosted) data.platform_links.push({ relationship_id: relationship.id, parent_id: parent.id, child_id: asset.id });
      data.structural_edges.push({ key: `relationship:${relationship.id}`, source_key: `asset:${asset.id}`, target_key: `asset:${parent.id}`, platform_parent_key: hosted ? `asset:${parent.id}` : null, topology_class: hosted ? "platform" : "physical_network", kind: "relationship", directional: hosted, label: hosted ? "Runs on" : "Connects to" });
    }
    return asset;
  };
  return { data, add };
}

function realShapeFixture({ workloads, accessPoints, sideBranch }) {
  const { data, add } = structuralBuilder();
  const gateway = add("Gateway", "gateway"), aggregation = add("Aggregation Switch", "core", gateway);
  const distribution = add("Distribution Switch", "switch", aggregation);
  const access = add("Access Switch A", "switch", distribution); add("Access Switch B", "switch", distribution);
  for (let i = 0; i < accessPoints; i++) add(`Wireless ${i + 1}`, "ap", access);
  if (sideBranch) {
    const sideHost = add("Office Platform", "platform", access);
    add("Office Automation", "home", sideHost, true);
  }
  const hosts = ["A", "B", "C"].map(letter => add(`Platform Host ${letter}`, "platform", distribution));
  add("Storage Appliance", "appliance", distribution); add("Backup Appliance", "appliance", distribution);
  for (let i = 0; i < workloads; i++) add(`Workload ${String(i + 1).padStart(2, "0")}`, ["infra", "media", "home"][i % 3], hosts[0], true);
  for (const letter of ["A", "B"]) {
    const container = add(`Container Host ${letter}`, "container_host", hosts[0], true);
    add(`Photo Library ${letter}`, "media", container, true); add(`Auth Service ${letter}`, "infra", container, true);
  }
  for (const host of hosts.slice(1)) for (let i = 0; i < 3; i++) add(`${host.name.at(-1)} Service ${i + 1}`, i ? "media" : "infra", host, true);
  for (const letter of ["A", "B"]) {
    const physical = add(`Physical Host ${letter}`, "server", aggregation);
    const platform = add(`Isolated Platform ${letter}`, "platform", physical, true);
    add(`DNS Service ${letter}`, "infra", platform, true);
  }
  add("Archive Server", "server");
  return data;
}

export function showcaseRealShapeFixture() {
  return realShapeFixture({ workloads: 16, accessPoints: 5, sideBranch: false });
}

export function showcaseReferenceFixture() {
  const data = realShapeFixture({ workloads: 10, accessPoints: 3, sideBranch: true });
  data.networks = ["Default", "Apps VLAN", "IoT VLAN"].map((name, i) => ({ id: id(900 + i), name, site_id: id(2), customer_id: id(1) }));
  for (const [i, asset] of data.assets.entries()) {
    const network = data.networks[i % data.networks.length];
    const iface = { id: id(950 + i), asset_id: asset.id, network_id: network.id, name: "eth0", ip_address: "192.0.2.99" };
    data.asset_interfaces.push(iface);
    data.structural_edges.push({ key: `interface:${iface.id}`, source_key: `asset:${asset.id}`, target_key: `network:${network.id}`, kind: "membership", topology_class: "physical_network", directional: false });
  }
  return data;
}

export function showcasePosterFixture(branches, extraSpine = 0) {
  const { data, add } = structuralBuilder();
  let gateway = add("Gateway", "gateway");
  for (let i = 0; i < extraSpine; i++) gateway = add(`Gateway Transit ${i + 1}`, "gateway", gateway);
  const core = add("Aggregation Switch", "core", gateway);
  for (let i = 0; i < branches; i++) {
    const host = add(`Host ${String(i + 1).padStart(3, "0")}`, "platform", core);
    add(`Service ${String(i + 1).padStart(3, "0")}`, "infra", host, true);
  }
  return data;
}

// Tall category exercises the retained poster fallback without widening branches.
export function showcaseTallFixture(workloads = 60) {
  const { data, add } = structuralBuilder();
  const gateway = add("Gateway", "gateway"), core = add("Aggregation Switch", "core", gateway);
  const host = add("Platform Host", "platform", core);
  for (let i = 0; i < workloads; i++) add(`Task ${String(i + 1).padStart(2, "0")}`, "media", host, true);
  add("Archive Server", "server");
  return data;
}

// Many parallel hosting branches, plus an independent root: horizontal forest
// pressure comes from recorded ownership, rather than a large workload count.
export function showcaseWideFixture(branches = 18, tallWorkloads = 0, firstBranchWorkloads = 2) {
  const { data, add } = structuralBuilder();
  const gateway = add("Gateway", "gateway");
  let core;
  for (let i = 0; i < branches; i++) {
    const suffix = String(i + 1).padStart(2, "0");
    // Independent recorded fabrics with four host branches apiece. No invented
    // link joins disconnected components just to make a poster-wide forest.
    if (i % 4 === 0) core = add(`Fabric ${String(i / 4 + 1).padStart(2, "0")}`, "core", i === 0 ? gateway : null);
    const host = add(`Host ${suffix}`, "platform", core);
    for (let j = 0; j < (i === 0 ? firstBranchWorkloads : 2); j++) add(`Task ${suffix} ${String.fromCharCode(65 + j)}`, "media", host, true);
  }
  add("Archive Server", "server");
  if (tallWorkloads) {
    const host = add("Tall Host", "platform");
    for (let i = 0; i < tallWorkloads; i++) add(`Tall Task ${String(i + 1).padStart(2, "0")}`, "media", host, true);
  }
  data.networks = [{ id: id(900), name: "Apps VLAN", site_id: id(2), customer_id: id(1) }];
  for (const [i, asset] of data.assets.entries()) {
    const iface = { id: id(950 + i), asset_id: asset.id, network_id: id(900), name: "eth0" };
    data.asset_interfaces.push(iface);
    data.structural_edges.push({ key: `interface:${iface.id}`, source_key: `asset:${asset.id}`, target_key: `network:${id(900)}`, kind: "membership", topology_class: "physical_network", directional: false });
  }
  return data;
}

// A five-member category changes one branch footprint naturally; the routed
// forest comes within three logical pixels of the supported width ceiling.
export function showcaseUltrawideFixture() {
  const data = showcaseWideFixture(23, 0, 5);
  // Isolate near-limit structural width from the independent root's label width.
  data.assets.find(n => n.name === "Archive Server").name = "Archive";
  return data;
}

function routingLink(data, source, target) {
  const relationship = { id: id(10000 + data.relationships.length), source_asset_id: source.id, target_asset_id: target.id, relationship_type: "connects_to" };
  data.relationships.push(relationship);
  data.structural_edges.push({ key: `relationship:${relationship.id}`, source_key: `asset:${source.id}`, target_key: `asset:${target.id}`,
    topology_class: "physical_network", kind: "relationship", directional: false, relationship_type: "connects_to", label: "Connects to" });
}

// Grouped workloads have legitimate secondary links. Their fixed bottom ports
// land in the next member's six-pixel clearance, although the cards don't touch.
export function showcaseDenseRoutingFixture() {
  const { data, add } = structuralBuilder();
  const gateway = add("Gateway", "gateway"), core = add("Core Switch", "core", gateway);
  const workloads = [];
  for (const letter of ["A", "B", "C", "D"]) {
    const host = add(`Host ${letter}`, "platform", core);
    for (let i = 0; i < 8; i++) {
      const node = add(`Task ${letter} ${i + 1}`, "media", host, true);
      if (letter === "A") workloads.push(node);
    }
  }
  const client = add("Media Client", "device", core);
  for (const workload of workloads) routingLink(data, workload, client);
  return data;
}

export function showcaseLiveRoutingFixture() {
  const { data, add } = structuralBuilder();
  const gateway = add("Gateway", "gateway"), core = add("Core Switch", "core", gateway);
  const distribution = add("Distribution", "switch", core), access = add("Access Switch", "switch", distribution);
  const hosts = ["A", "B", "C"].map(letter => add(`Platform ${letter}`, "platform", distribution));
  add("Storage", "appliance", distribution); add("Backup", "appliance", distribution);
  const container = add("Container Host", "container_host", hosts[0], true);
  const clients = [add("Media Client", "device", access), add("Office Client", "device", access)];
  add("Wireless 1", "ap", access); add("Wireless 2", "ap", access);
  const media = [];
  for (const [index, host] of hosts.entries()) for (let i = 0; i < [12, 8, 6][index]; i++) {
    const type = i < 6 ? "media" : i < 9 ? "infra" : "home";
    const node = add(`Task ${String.fromCharCode(65 + index)} ${String(i + 1).padStart(2, "0")}`, type, host, true);
    if (index === 0 && type === "media") media.push(node);
  }
  for (let i = 0; i < 4; i++) add(`Container Task ${i + 1}`, "infra", container, true);
  for (const workload of media) routingLink(data, workload, clients[0]);
  return data;
}


export function showcaseExteriorRoutingFixture() {
  const { data, add } = structuralBuilder();
  const gateway = add("Gateway", "gateway"), core = add("Core Switch", "core", gateway);
  const host = add("Platform Host", "platform", core);
  const workloads = Array.from({ length: 6 }, (_, i) => add(`Task ${i + 1}`, "media", host, true));
  const client = add("Media Client", "device", core);
  for (const workload of workloads) routingLink(data, workload, client);
  return data;
}

// The supplied 44-Asset poster's structural shape, using synthetic IDs and
// explicit recorded links. Names are fixture data, never production heuristics.
export function showcaseReadableFixture() {
  const { data, add } = structuralBuilder();
  data.sites[0].name = "Homelab";
  data.categories[0].name = "Compute";
  const gateway = add("UDM-Pro", "gateway"), aggregation = add("USW-Aggregation", "core", gateway);
  const distribution = add("USW-16-POE (Rack)", "switch", aggregation);
  const office = add("US-8-60W (Office)", "switch", distribution);
  add("USW-16-POE (Garage)", "switch", distribution);
  const proxmox = add("Proxmox", "platform", office);
  add("homeassistant", "home", proxmox, true);
  const hosts = ["PVE1", "PVE2", "PVE3"].map(name => add(name, "platform", distribution));
  add("pbs01", "platform", distribution); add("synology-nas", "appliance", distribution);
  const apps = add("Docker Apps", "container_host", hosts[0], true);
  const infrastructure = add("Docker Inf", "container_host", hosts[0], true);
  add("homebox", "infra", apps, true); add("Music Assistant", "infra", apps, true);
  add("Homarr", "media", infrastructure, true); add("unpoller", "infra", infrastructure, true);
  for (const name of ["AdGuard Home", "authentik", "cloudflared", "esphome", "grafana", "immich", "influxdb", "Mealie",
    "N8N", "Netbox", "Nginx Proxy Manager", "outline", "paperless", "Patchmon", "Proxmox Data Center Manager", "Uptime Kuma"]) add(name, "infra", hosts[0], true);
  for (const [index, names] of [[1, ["AdGuard Home 2", "Atlas DNS", "scrypted"]], [2, ["Atlas Impact", "HCR Website", "Roadcycling"]]])
    for (const name of names) add(name, "infra", hosts[index], true);
  for (const number of [1, 2]) {
    const physical = add(`Dell Server ${number}`, "server", aggregation);
    add(`Proxmox Dell ${number}`, "platform", physical, true);
  }
  return data;
}
