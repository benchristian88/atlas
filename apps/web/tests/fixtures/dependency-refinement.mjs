import { impactGraph } from "./dependency-impact.mjs";
const uuid = "6ad9f820-4884-47b9-b6f5-123456789012";
const node = (type, id, name) => ({ key: `${type}:${id}`, entity_type: type, entity_id: id, name, href: `/${type === "asset" ? "assets" : type === "service" ? "services" : "business-functions"}/${id}` });
const edge = (key, from, to, family, extra = {}) => ({ key, source_key: from, target_key: to, edge_family: family, label: family === "service_business_function" ? "Supports" : family === "service_service" ? "Depends on" : "Provided by", ...extra });
export const refinementGraph = {
  ...impactGraph,
  nodes: [...impactGraph.nodes, node("business_function", "continuity", "Home Continuity"), node("service", "media", "Media Library"), node("asset", "media", "Media Server")],
  edges: [
    ...impactGraph.edges.map(e => e.dependency_group_id === "files" ? { ...e, dependency_group_name: `Providers ${uuid}` } : e.dependency_group_id === "home" ? { ...e, dependency_group_name: `Dependency asset ${uuid}` } : e),
    edge("files-purpose", "service:files", "business_function:continuity", "service_business_function"),
    edge("home-purpose", "service:home", "business_function:continuity", "service_business_function"),
    edge("proxy-purpose", "service:proxy", "business_function:home", "service_business_function"),
    edge("media-purpose", "service:media", "business_function:continuity", "service_business_function"),
    edge("media-dns", "service:media", "service:dns", "service_service", { dependency_requirement: "required", failure_effect: "unknown" }),
    edge("media-provider", "service:media", "asset:media", "service_asset", { dependency_group_id: "media", dependency_group_name: "Playback", dependency_strategy: "all", dependency_requirement: "required", failure_effect: "unavailable" }),
    edge("media-storage", "service:media", "service:files", "service_service", { dependency_group_id: "media-storage", dependency_group_name: "Media storage", dependency_strategy: "all", dependency_requirement: "required", failure_effect: "degraded" }),
  ],
};
