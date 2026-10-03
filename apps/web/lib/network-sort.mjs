// Compare packed address groups, including compressed and IPv4-mapped IPv6.
function address(value) {
  const text = (value || "").split("/")[0].split("%")[0];
  const ipv4 = value => /^\d+\.\d+\.\d+\.\d+$/.test(value) && value.split(".").every(n => Number(n) <= 255) ? value.split(".").map(Number) : null;
  const v4 = ipv4(text);
  if (v4) return [4, ...v4];
  if (!text.includes(":")) return null;
  let normalized = text;
  if (text.includes(".")) {
    const tail = text.slice(text.lastIndexOf(":") + 1), parts = ipv4(tail);
    if (!parts) return null;
    normalized = text.slice(0, -tail.length) + ((parts[0] << 8) + parts[1]).toString(16) + ":" + ((parts[2] << 8) + parts[3]).toString(16);
  }
  const halves = normalized.split("::");
  if (halves.length > 2) return null;
  const left = halves[0] ? halves[0].split(":") : [], right = halves[1] ? halves[1].split(":") : [];
  if (![...left, ...right].every(n => /^[\da-f]{1,4}$/i.test(n))) return null;
  const missing = 8 - left.length - right.length;
  if (halves.length === 1 && missing !== 0 || halves.length === 2 && missing < 1) return null;
  return [6, ...left.map(n => parseInt(n, 16)), ...Array(missing).fill(0), ...right.map(n => parseInt(n, 16))];
}
export function compareIp(a, b) {
  const left = address(a), right = address(b);
  if (!left || !right) return left ? -1 : right ? 1 : String(a || "").localeCompare(String(b || ""));
  for (let i = 0; i < left.length; i++) if (left[i] !== right[i]) return left[i] - right[i];
  return 0;
}
export function sortNetworkMembers(members, assets, { key, direction }) {
  const value = row => key === "asset" ? assets[row.asset_id].name : key === "status" ? assets[row.asset_id].status : row[key];
  return [...members].sort((a, b) => direction * (key === "ip_address" ? compareIp(value(a), value(b)) : String(value(a) || "").localeCompare(String(value(b) || ""))) || assets[a.asset_id].name.localeCompare(assets[b.asset_id].name) || a.asset_id.localeCompare(b.asset_id) || a.id.localeCompare(b.id));
}
