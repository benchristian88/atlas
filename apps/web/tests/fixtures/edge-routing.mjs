import { impactGraph } from "./dependency-impact.mjs";
const node = (type, id, name) => ({ key: `${type}:${id}`, entity_type: type, entity_id: id, name, href: `/${type === "asset" ? "assets" : type === "service" ? "services" : "business-functions"}/${id}` });
const edge = (key, source, target, family, group = null) => ({ key, source_key: source, target_key: target, edge_family: family, label: family === "service_business_function" ? "Supports" : family === "service_asset" ? "Provided by" : "Depends on", ...(family === "service_business_function" ? {} : { dependency_group_id: group, dependency_group_name: group ? "Required provider" : null, dependency_strategy: group ? "all" : null, dependency_requirement: "required", failure_effect: group ? "unavailable" : "unknown" }) });
const select = (nodeKeys, edgeKeys) => ({ nodes: impactGraph.nodes.filter(n => nodeKeys.includes(n.key)), edges: impactGraph.edges.filter(e => edgeKeys.includes(e.key)), truncated: false, warnings: [] });
export const singletonGraph = { nodes: [node("business_function", "smart", "Smart Home"), ...impactGraph.nodes.filter(n => ["service:home", "asset:ha"].includes(n.key))], edges: [edge("smart", "service:home", "business_function:smart", "service_business_function"), impactGraph.edges.find(e => e.key === "home")], warnings: [], truncated: false };
export const dnsGraph = select(["business_function:home", "service:dns", "asset:adguard1", "asset:adguard2", "asset:atlas"], ["context", "adguard1", "adguard2", "control"]);
export const denseRoutingGraph = {
  ...dnsGraph,
  nodes: [...dnsGraph.nodes, node("service", "dhcp", "DHCP"), node("service", "firewall", "Firewall Protection"), node("service", "internet", "Internet Access"), node("service", "proxy", "Reverse Proxy"), node("asset", "udm", "UDM-Pro"), node("asset", "nginx", "Nginx Proxy Manager"), ...singletonGraph.nodes],
  edges: [...dnsGraph.edges, ...singletonGraph.edges,
    ...["dhcp", "firewall", "internet", "proxy"].map(id => edge(`purpose-${id}`, `service:${id}`, "business_function:home", "service_business_function")),
    ...["dhcp", "firewall", "internet"].map(id => edge(`udm-${id}`, `service:${id}`, "asset:udm", "service_asset", `provider-${id}`)),
    edge("nginx", "service:proxy", "asset:nginx", "service_asset", "proxy-provider"),
    edge("proxy-dns", "service:proxy", "service:dns", "service_service"),
    edge("dns-internet", "service:dns", "service:internet", "service_service"),
    edge("internet-firewall", "service:internet", "service:firewall", "service_service"),
    edge("home-dns", "service:home", "service:dns", "service_service"),
  ],
};
