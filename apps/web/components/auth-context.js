"use client";

import { createContext, useContext } from "react";

export const AuthContext = createContext(null);

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside a protected Atlas route");
  return value;
}

export function userHasPermission(user, permission) {
  return Array.isArray(user?.permissions) && user.permissions.includes(permission);
}

export function userHasAnyPermission(user, permissions) {
  return permissions.some((permission) => userHasPermission(user, permission));
}

function assignmentHasPermission(assignment, permission) {
  return Array.isArray(assignment?.permissions)
    && assignment.permissions.includes(permission);
}

export function userHasGlobalPermission(user, permission) {
  return Array.isArray(user?.assignments) && user.assignments.some(
    (assignment) => assignment.scope_type === "global"
      && assignmentHasPermission(assignment, permission),
  );
}

export function userHasPermissionInContext(
  user,
  permission,
  customerId = null,
  siteId = null,
) {
  if (!Array.isArray(user?.assignments)) return false;
  return user.assignments.some((assignment) => {
    if (!assignmentHasPermission(assignment, permission)) return false;
    if (!customerId) return true;
    if (assignment.scope_type === "global") return true;
    if (String(assignment.customer_id || "") !== String(customerId)) return false;
    if (assignment.scope_type === "customer") return true;
    return !siteId || String(assignment.site_id || "") === String(siteId);
  });
}

export function userHasPermissionForObject(
  user,
  permission,
  customerId,
  siteId = null,
) {
  if (!customerId || !Array.isArray(user?.assignments)) return false;
  return user.assignments.some((assignment) => {
    if (!assignmentHasPermission(assignment, permission)) return false;
    if (assignment.scope_type === "global") return true;
    if (String(assignment.customer_id || "") !== String(customerId)) return false;
    if (assignment.scope_type === "customer") return true;
    return Boolean(siteId)
      && String(assignment.site_id || "") === String(siteId);
  });
}

const WORKSPACE_VIEW_PERMISSIONS = [
  "customers.view",
  "sites.view",
  "assets.view",
  "relationships.view",
  "networks.view",
];

export function authenticatedHome(user) {
  if (user?.force_password_change) return "/profile?password=required";
  if (userHasAnyPermission(user, WORKSPACE_VIEW_PERMISSIONS)) return "/dashboard";
  if (userHasPermission(user, "integrations.view")) return "/integrations";
  if (Array.isArray(user?.permissions) && user.permissions.length) return "/admin";
  return "/profile";
}
