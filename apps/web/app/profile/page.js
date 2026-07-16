"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";
import { getCurrentUser } from "../../lib/auth";

function responseUser(response) {
  const user = response?.user || response;
  return user && typeof user.email === "string" ? user : null;
}

function formatScope(assignment, customersById, sitesById) {
  const scopeType = String(assignment.scope_type || "").toLowerCase();
  if (scopeType === "global") return "All customers and sites";
  if (scopeType === "site") {
    const site = sitesById.get(String(assignment.site_id));
    const customer = customersById.get(String(assignment.customer_id));
    if (site && customer) return `${customer.name} / ${site.name}`;
    return site?.name || "Assigned site";
  }
  if (scopeType === "customer") {
    return customersById.get(String(assignment.customer_id))?.name || "Assigned customer";
  }
  return "Assigned scope";
}

export default function ProfilePage() {
  const router = useRouter();
  const { user, updateUser } = useAuth();
  const { customers, sites } = useWorkspaceContext();
  const [displayName, setDisplayName] = useState(user.display_name || "");
  const [profileStatus, setProfileStatus] = useState({ saving: false, error: "", success: "" });
  const [passwords, setPasswords] = useState({
    current_password: "",
    new_password: "",
    new_password_confirmation: "",
  });
  const [passwordStatus, setPasswordStatus] = useState({ saving: false, error: "", success: "" });

  const customersById = useMemo(
    () => new Map(customers.map((customer) => [String(customer.id), customer])),
    [customers],
  );
  const sitesById = useMemo(
    () => new Map(sites.map((site) => [String(site.id), site])),
    [sites],
  );
  const roleNames = Array.isArray(user.roles)
    ? user.roles
    : [...new Set((user.assignments || []).map((assignment) => assignment.role_name).filter(Boolean))];

  async function saveProfile(event) {
    event.preventDefault();
    setProfileStatus({ saving: true, error: "", success: "" });
    try {
      const response = await apiRequest("/auth/profile", {
        method: "PATCH",
        body: JSON.stringify({ display_name: displayName.trim() }),
      });
      const updatedUser = responseUser(response);
      if (updatedUser) updateUser((current) => ({ ...current, ...updatedUser }));
      setProfileStatus({ saving: false, error: "", success: "Profile updated." });
    } catch (requestError) {
      setProfileStatus({
        saving: false,
        error: requestError.message || "Atlas could not update your profile.",
        success: "",
      });
    }
  }

  async function changePassword(event) {
    event.preventDefault();
    if (passwords.new_password !== passwords.new_password_confirmation) {
      setPasswordStatus({ saving: false, error: "The new passwords do not match.", success: "" });
      return;
    }
    if (passwords.new_password.length < 12) {
      setPasswordStatus({
        saving: false,
        error: "Your new password must be at least 12 characters.",
        success: "",
      });
      return;
    }

    setPasswordStatus({ saving: true, error: "", success: "" });
    try {
      const response = await apiRequest("/auth/change-password", {
        method: "POST",
        body: JSON.stringify(passwords),
        redirectOnUnauthorized: false,
      });
      let updatedUser = responseUser(response);
      if (!updatedUser) {
        try {
          updatedUser = await getCurrentUser();
        } catch (sessionError) {
          if (sessionError.status === 401) {
            router.replace("/login");
            return;
          }
          throw sessionError;
        }
      }
      updateUser((current) => ({ ...current, ...updatedUser, force_password_change: false }));
      setPasswords({ current_password: "", new_password: "", new_password_confirmation: "" });
      setPasswordStatus({ saving: false, error: "", success: "Password changed." });
    } catch (requestError) {
      setPasswordStatus({
        saving: false,
        error: requestError.message || "Atlas could not change your password.",
        success: "",
      });
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Account"
        title="Profile"
        description="Manage your Atlas identity and review the access assigned to you."
      />

      {user.force_password_change && (
        <div className="warning-banner" role="alert">
          Change your temporary password before continuing to the rest of Atlas.
        </div>
      )}

      <div className="profile-layout">
        <section className="form-card" aria-labelledby="profile-details-title">
          <div className="form-card-header">
            <div>
              <p className="eyebrow">Identity</p>
              <h2 id="profile-details-title">Profile details</h2>
            </div>
          </div>
          {profileStatus.error && <div className="error-banner" role="alert">{profileStatus.error}</div>}
          {profileStatus.success && <div className="success-banner" role="status">{profileStatus.success}</div>}
          <form className="resource-form" onSubmit={saveProfile}>
            <div className="form-grid profile-form-grid">
              <label className="field">
                <span>Email</span>
                <input disabled readOnly type="email" value={user.email} />
                <small>Your login email can only be changed by an administrator.</small>
              </label>
              <label className="field">
                <span>Display name *</span>
                <input
                  autoComplete="name"
                  disabled={profileStatus.saving}
                  maxLength={255}
                  onChange={(event) => setDisplayName(event.target.value)}
                  required
                  value={displayName}
                />
              </label>
            </div>
            <div className="form-actions">
              <button className="button button-primary" disabled={profileStatus.saving} type="submit">
                {profileStatus.saving ? "Saving…" : "Save profile"}
              </button>
            </div>
          </form>
        </section>

        <section className="form-card" aria-labelledby="password-title">
          <div className="form-card-header">
            <div>
              <p className="eyebrow">Security</p>
              <h2 id="password-title">Change password</h2>
            </div>
          </div>
          {passwordStatus.error && <div className="error-banner" role="alert">{passwordStatus.error}</div>}
          {passwordStatus.success && <div className="success-banner" role="status">{passwordStatus.success}</div>}
          <form className="resource-form" onSubmit={changePassword}>
            <div className="password-fields">
              <label className="field">
                <span>Current password</span>
                <input
                  autoComplete="current-password"
                  disabled={passwordStatus.saving}
                  onChange={(event) => setPasswords({ ...passwords, current_password: event.target.value })}
                  required
                  type="password"
                  value={passwords.current_password}
                />
              </label>
              <label className="field">
                <span>New password</span>
                <input
                  autoComplete="new-password"
                  disabled={passwordStatus.saving}
                  minLength={12}
                  onChange={(event) => setPasswords({ ...passwords, new_password: event.target.value })}
                  required
                  type="password"
                  value={passwords.new_password}
                />
                <small>Use at least 12 characters.</small>
              </label>
              <label className="field">
                <span>Confirm new password</span>
                <input
                  autoComplete="new-password"
                  disabled={passwordStatus.saving}
                  minLength={12}
                  onChange={(event) => setPasswords({
                    ...passwords,
                    new_password_confirmation: event.target.value,
                  })}
                  required
                  type="password"
                  value={passwords.new_password_confirmation}
                />
              </label>
            </div>
            <div className="form-actions">
              <button className="button button-primary" disabled={passwordStatus.saving} type="submit">
                {passwordStatus.saving ? "Changing…" : "Change password"}
              </button>
            </div>
          </form>
        </section>

        <section className="profile-access-card" aria-labelledby="access-title">
          <p className="eyebrow">Authorisation</p>
          <h2 id="access-title">Roles and access</h2>
          <div className="profile-role-list" aria-label="Assigned roles">
            {roleNames.length ? roleNames.map((role) => <span key={role}>{role}</span>) : <span>No roles assigned</span>}
          </div>
          <div className="assignment-list">
            {(user.assignments || []).length ? user.assignments.map((assignment) => (
              <div className="assignment-row" key={assignment.id}>
                <strong>{assignment.role_name || "Assigned role"}</strong>
                <span>{formatScope(assignment, customersById, sitesById)}</span>
              </div>
            )) : (
              <p className="secondary-text">No customer or site access is assigned.</p>
            )}
          </div>
        </section>
      </div>
    </>
  );
}
