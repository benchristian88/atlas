export function initialsForName(value) {
  const normalized = String(value || "").trim();
  if (!normalized) return "?";
  const name = normalized.includes("@") ? normalized.split("@")[0] : normalized;
  const words = name.split(/\s+/).map((word) => word.match(/[\p{L}\p{N}]/u)?.[0]).filter(Boolean);
  if (words.length >= 2) return `${words[0]}${words.at(-1)}`.toLocaleUpperCase();
  const characters = [...name].filter((character) => /[\p{L}\p{N}]/u.test(character));
  return characters.slice(0, 2).join("").toLocaleUpperCase() || "?";
}

export function primaryRoleLabel(user) {
  const directRoles = Array.isArray(user?.roles)
    ? user.roles.map((role) => typeof role === "string" ? role : role?.name).filter(Boolean)
    : [];
  const assignedRoles = Array.isArray(user?.assignments)
    ? user.assignments.map((assignment) => assignment?.role_name).filter(Boolean)
    : [];
  const roles = [...new Set([...directRoles, ...assignedRoles])];
  if (roles.length) return roles[0];
  const permissions = Array.isArray(user?.permissions) ? user.permissions : [];
  return permissions.some((permission) => permission.endsWith(".manage")) ? "Administrator" : "Atlas user";
}

export function validAvatarUrl(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  const candidate = value.trim();
  if (candidate.startsWith("/")) return candidate;
  try {
    const url = new URL(candidate);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}
