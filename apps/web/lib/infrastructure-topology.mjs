// Presentation over authorized domain projections. No relationship semantics live here.
export const CHILD_PREVIEW_COUNT = 8;
export const byName = (a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id);
export const byNetwork = (a, b) => (a.vlan_id ?? Infinity) - (b.vlan_id ?? Infinity) || byName(a, b);
export const matchesSearch = (asset, query) => !query || [asset.name, asset.hostname, asset.ip_address].filter(Boolean).join(" ").toLowerCase().includes(query.toLowerCase());

export function topologyPresentation(data, enabled) {
  const types = Object.fromEntries(data.asset_types.map(t => [t.key, t]));
  const categories = data.categories.filter(c => enabled.has(c.id));
  const assets = data.assets.filter(a => enabled.has(types[a.asset_type]?.category_id)).sort(byName);
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
  const others = graph.nodes.filter(n => n.key !== focus.key).sort((a, b) => a.distance - b.distance || a.name.localeCompare(b.name) || a.key.localeCompare(b.key));
  const result = [{ ...focus, x: 550, y: 550 }];
  // Concentric, bounded rings keep the focus centred at every viewport size.
  for (let i = 0; i < others.length; i++) {
    const ring = i < 8 ? 0 : 1;
    const start = ring ? 8 : 0, count = Math.min(ring ? 16 : 8, others.length - start);
    const angle = -Math.PI / 2 + 2 * Math.PI * (i - start) / count;
    const radius = ring ? 440 : 235;
    result.push({ ...others[i], x: 550 + Math.cos(angle) * radius, y: 550 + Math.sin(angle) * radius });
  }
  return result;
}
