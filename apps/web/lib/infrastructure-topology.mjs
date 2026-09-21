// Presentation over authorized domain projections. No relationship semantics live here.
export const CHILD_PREVIEW_COUNT = 8;
export const CATEGORY_PREVIEW_COUNT = 6;
export const CONNECTIVITY_NODE_WIDTH = 180;
export const CONNECTIVITY_NODE_HEIGHT = 88;

// Stable interface ordering; the legacy Asset IP is deliberately excluded.
export function compactInterfaceIp(interfaces) {
  const ordered = interfaces.filter(i => i.ip_address).sort((a, b) => Number(Boolean(b.is_primary)) - Number(Boolean(a.is_primary)) || (a.name || "").localeCompare(b.name || "") || a.id.localeCompare(b.id));
  const ips = [...new Set(ordered.map(i => i.ip_address))];
  return ips.length ? `${ips[0]}${ips.length > 1 ? ` +${ips.length - 1}` : ""}` : "";
}
export const byName = (a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id);
export const byNetwork = (a, b) => (a.vlan_id ?? Infinity) - (b.vlan_id ?? Infinity) || byName(a, b);
export const matchesSearch = (asset, query) => !query || [asset.name, asset.hostname, ...(asset.interface_ips || [])].filter(Boolean).join(" ").toLowerCase().includes(query.toLowerCase());

export function topologyPresentation(data, enabled) {
  const types = Object.fromEntries(data.asset_types.map(t => [t.key, t]));
  const categories = data.categories.filter(c => enabled.has(c.id));
  const interfaceGroups = {};
  for (const item of data.asset_interfaces) (interfaceGroups[item.asset_id] ||= []).push(item);
  const assets = data.assets.filter(a => enabled.has(types[a.asset_type]?.category_id)).map(a => ({ ...a,
    interface_ips: (interfaceGroups[a.id] || []).map(i => i.ip_address).filter(Boolean),
    display_ip: compactInterfaceIp(interfaceGroups[a.id] || []),
  })).sort(byName);
  const byId = Object.fromEntries(assets.map(a => [a.id, a]));
  const links = data.platform_links.filter(l => byId[l.parent_id] && byId[l.child_id]);
  const children = Object.fromEntries(assets.map(a => [a.id, []]));
  const childIds = new Set();
  for (const link of links) {
    if (!children[link.parent_id].some(a => a.id === link.child_id)) children[link.parent_id].push(byId[link.child_id]);
    childIds.add(link.child_id);
  }
  for (const group of Object.values(children)) group.sort(byName);
  const roots = assets.filter(a => !childIds.has(a.id));
  // Retain closed cycles without pretending a member has a canonical parent.
  const visited = new Set();
  const visit = id => {
    const queue = [id];
    while (queue.length) {
      const next = queue.pop();
      if (visited.has(next)) continue;
      visited.add(next);
      queue.push(...children[next].map(a => a.id));
    }
  };
  roots.forEach(a => visit(a.id));
  const cycleRoots = new Set();
  for (const asset of assets) if (!visited.has(asset.id)) {
    roots.push(asset); cycleRoots.add(asset.id); visit(asset.id);
  }
  const interfaces = data.asset_interfaces.filter(i => byId[i.asset_id]);
  const definitions = Object.fromEntries(data.relationship_types.map(t => [t.key, t]));
  const relationships = data.relationships.filter(r => byId[r.source_asset_id] && byId[r.target_asset_id]).map(r => ({ ...r, display_label: definitions[r.relationship_type]?.source_label, directional: definitions[r.relationship_type]?.directional }));
  return { assets, byId, types, categories, children, roots, cycleRoots, interfaces, relationships, networks: [...data.networks].sort(byNetwork) };
}

export function platformMatches(asset, children, query) {
  const queue = [asset], seen = new Set();
  while (queue.length) {
    const next = queue.pop();
    if (seen.has(next.id)) continue;
    seen.add(next.id);
    if (matchesSearch(next, query)) return true;
    queue.push(...(children[next.id] || []));
  }
  return false;
}

export function connectivityLayout(graph) {
  const focus = graph.nodes.find(n => n.key === graph.focus_key);
  if (!focus) return [];
  const order = (a, b) => a.name.localeCompare(b.name) || a.key.localeCompare(b.key);
  const inner = graph.nodes.filter(n => n.distance === 1).sort(order);
  const outer = graph.nodes.filter(n => n.distance === 2).sort(order);
  const cellWidth = CONNECTIVITY_NODE_WIDTH + 24, cellHeight = CONNECTIVITY_NODE_HEIGHT + 24;
  const radius = Math.max(cellWidth, inner.length * cellHeight / (2 * Math.PI));
  const result = [{ ...focus, x: 0, y: 0 }];
  const occupied = new Set(["0/0"]);
  // Snap balanced radial targets onto card-sized cells. Dense branches can use
  // adjacent rows instead of forcing every ring to expand for one crowded arc.
  const range = graph.nodes.length + 2;
  const cells = [];
  for (let col = -range; col <= range; col++) for (let row = -range; row <= range; row++) {
    cells.push({ x: col * cellWidth, y: row * cellHeight, key: `${col}/${row}` });
  }
  const place = (node, target, outside = 0) => {
    let best, score = Infinity;
    for (const cell of cells) {
      if (occupied.has(cell.key) || Math.hypot(cell.x, cell.y) < outside) continue;
      const candidate = (cell.x - target.x) ** 2 + (cell.y - target.y) ** 2;
      if (candidate < score) { best = cell; score = candidate; }
    }
    occupied.add(best.key);
    result.push({ ...node, x: best.x, y: best.y });
  };
  inner.forEach((node, i) => {
    const angle = -Math.PI / 2 + 2 * Math.PI * i / inner.length;
    place(node, { x: radius * Math.cos(angle), y: radius * Math.sin(angle) });
  });
  const outside = Math.max(0, ...result.map(n => Math.hypot(n.x, n.y))) + CONNECTIVITY_NODE_HEIGHT / 2 + 24;
  for (const node of outer) {
    const parent = result.find(n => n.key === node.parent_key) || result[1] || result[0];
    const length = Math.hypot(parent.x, parent.y) || 1;
    place(node, { x: parent.x / length * outside, y: parent.y / length * outside }, outside);
  }
  return result;
}
