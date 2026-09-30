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
