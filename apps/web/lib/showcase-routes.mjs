// Resolve presentation endpoints separately from canonical relationship IDs.
// The shared router and its obstacle/search strategy are unchanged.
function fail(route, role, key, reason) {
  const detail = { relationshipKey: route.key, relationshipKeys: route.relationshipKeys || [route.key],
    sourceAssetKey: route.source_key, targetAssetKey: route.target_key,
    renderedEndpoint: key, role, reason, groupKey: route.group_key || null, fallback: route.fallback_routing || null };
  const error = new Error(`Showcase route ${route.key}: ${role} endpoint ${key || "missing"} ${reason}`);
  error.presentationDiagnostic = detail;
  throw error;
}

function renderedRectangles(items, geometry) {
  const nodes = new Map(geometry.map(n => [n.key, n])), rectangles = new Map();
  for (const item of items) {
    rectangles.set(item.key, { kind: item.kind === "asset" ? "asset" : "category", x: item.x, y: item.y, width: item.cardWidth, height: item.cardHeight });
    if (item.kind !== "category") continue;
    for (const member of item.preview) {
      const node = nodes.get(member.key);
      if (node) rectangles.set(member.key, { kind: "asset", x: node.x - node.geometry_width / 2,
        y: node.y - node.geometry_height / 2, width: node.geometry_width, height: node.geometry_height });
    }
  }
  return rectangles;
}

function boundaryPort(route, role, key, point, rectangle) {
  if (!rectangle) fail(route, role, key, "does not resolve to a visible tile or group");
  if (!Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite)) fail(route, role, key, "has no finite attachment point");
  const { x, y, width, height } = rectangle, [px, py] = point;
  let anchor;
  if (px >= x && px <= x + width && py <= y) anchor = [px, y];
  else if (px >= x && px <= x + width && py >= y + height) anchor = [px, y + height];
  else if (py >= y && py <= y + height && px <= x) anchor = [x, py];
  else if (py >= y && py <= y + height && px >= x + width) anchor = [x + width, py];
  if (!anchor || Math.abs(anchor[0] - px) + Math.abs(anchor[1] - py) > 8.001) fail(route, role, key, `has a stale attachment at ${point.join(",")}`);
  return { key, kind: rectangle.kind, point: anchor };
}

// Remove collinear out-and-back tails: they draw a spur with no endpoint even
// though the complete polyline eventually returns to its real endpoint.
export function simplifyShowcaseRoute(points) {
  const result = [];
  for (const point of points) {
    if (result.length && point[0] === result.at(-1)[0] && point[1] === result.at(-1)[1]) continue;
    result.push([...point]);
    while (result.length >= 3) {
      const [a, b, c] = result.slice(-3);
      if (!(a[0] === b[0] && b[0] === c[0]) && !(a[1] === b[1] && b[1] === c[1])) break;
      result.splice(result.length - 2, 1);
    }
  }
  return result;
}

export function showcasePresentationRoutes(edges, routed, items, geometry, allEdges = edges) {
  const groups = new Map(items.filter(n => n.kind === "category").map(n => [n.key, n]));
  const rectangles = renderedRectangles(items, geometry);
  const routes = [];
  for (const edge of edges) {
    const route = routed[edge.key];
    if (!route) fail(edge, "source", edge.source_key, "has no routed geometry");
    if (route.render === false) continue; // Existing shared parent/group deduplication.
    const group = route.group_key ? groups.get(route.group_key) : null;
    if (route.group_key && !group) fail(edge, "group", route.group_key, "is missing");
    const sourceKey = group && edge.source_key !== group.parent ? group.key : edge.source_key;
    const targetKey = group && edge.target_key !== group.parent ? group.key : edge.target_key;
    if (group && (edge.source_key !== group.parent && edge.target_key !== group.parent ||
      !group.members.some(n => n.key === (edge.source_key === group.parent ? edge.target_key : edge.source_key)))) {
      fail(edge, "group", group.key, "does not represent this relationship");
    }
    const relationshipKeys = group ? allEdges.filter(e => e.platform_parent_key === group.parent &&
      group.members.some(n => n.key === (e.source_key === group.parent ? e.target_key : e.source_key))).map(e => e.key) : [edge.key];
    const original = { ...edge, ...route, relationshipKeys };
    const sourceEndpoint = boundaryPort(original, "source", sourceKey, route.points[0], rectangles.get(sourceKey));
    const targetEndpoint = boundaryPort(original, "target", targetKey, route.points.at(-1), rectangles.get(targetKey));
    // Connect the router's existing 8px clearance ports to visible tile borders.
    // No interior route segment, obstacle, ownership or domain endpoint changes.
    const points = simplifyShowcaseRoute([sourceEndpoint.point, ...route.points, targetEndpoint.point]);
    routes.push({ ...original, routerPoints: route.points, sourceEndpoint, targetEndpoint, points,
      path: points.map(([x, y], i) => `${i ? "L" : "M"}${x},${y}`).join(" ") });
  }
  assertShowcaseRouteEndpoints({ items, geometry, routes });
  return routes;
}

export function assertShowcaseRouteEndpoints(layout) {
  const rectangles = renderedRectangles(layout.items, layout.geometry);
  for (const route of layout.routes) for (const role of ["source", "target"]) {
    const endpoint = route[`${role}Endpoint`], point = role === "source" ? route.points[0] : route.points.at(-1);
    const resolved = boundaryPort(route, role, endpoint?.key, point, rectangles.get(endpoint?.key));
    if (resolved.kind !== endpoint.kind || resolved.point[0] !== point[0] || resolved.point[1] !== point[1] ||
      endpoint.point[0] !== point[0] || endpoint.point[1] !== point[1]) fail(route, role, endpoint.key, "does not terminate on its rendered boundary");
  }
  return true;
}
