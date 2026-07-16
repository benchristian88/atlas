"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";
import { getCurrentUser } from "../../lib/auth";
import {
  accentThemeStyle,
  ATLAS_DEFAULT_ACCENT,
} from "../../lib/accent-theme.mjs";
import {
  accentPreferenceFromSelection,
  accentPreferenceFromText,
  appearanceProfilePayload,
} from "../../lib/accent-preference.mjs";

const ACCENT_PRESETS = [
  { name: "Atlas default", value: null },
  { name: "Blue", value: "#2563EB" },
  { name: "Teal", value: "#0F766E" },
  { name: "Green", value: "#15803D" },
  { name: "Purple", value: "#7C3AED" },
  { name: "Burgundy", value: "#9F1239" },
  { name: "Charcoal", value: "#374151" },
];

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
  const [accentInput, setAccentInput] = useState(user.accent_colour || ATLAS_DEFAULT_ACCENT);
  const [accentPreference, setAccentPreference] = useState(user.accent_colour || null);
  const [appearanceStatus, setAppearanceStatus] = useState({ saving: false, error: "", success: "" });
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

  function selectAccent(value) {
    const next = accentPreferenceFromSelection(value);
    setAppearanceStatus({ saving: false, error: next.error, success: "" });
    setAccentPreference(next.preference);
    setAccentInput(next.input);
  }

  function changeAccentText(value) {
    const next = accentPreferenceFromText(value, accentPreference);
    setAccentInput(next.input);
    setAccentPreference(next.preference);
    setAppearanceStatus({ saving: false, error: next.error, success: "" });
  }

  async function persistAppearance(state, successMessage) {
    let payload;
    try {
      payload = appearanceProfilePayload(user.display_name, state);
    } catch (validationError) {
      setAppearanceStatus({ saving: false, error: validationError.message, success: "" });
      return;
    }
    setAppearanceStatus({ saving: true, error: "", success: "" });
    try {
      const response = await apiRequest("/auth/profile", {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      const updatedUser = responseUser(response);
      if (!updatedUser) throw new Error("Atlas returned an unexpected profile response.");
      updateUser((current) => ({ ...current, ...updatedUser }));
      setAccentPreference(updatedUser?.accent_colour || null);
      setAccentInput(updatedUser?.accent_colour || ATLAS_DEFAULT_ACCENT);
      setAppearanceStatus({ saving: false, error: "", success: successMessage });
    } catch (requestError) {
      setAppearanceStatus({
        saving: false,
        error: requestError.message || "Atlas could not update your appearance.",
        success: "",
      });
    }
  }

  function saveAppearance(event) {
    event.preventDefault();
    persistAppearance(
      { input: accentInput, preference: accentPreference },
      "Appearance updated.",
    );
  }

  function resetAppearance() {
    persistAppearance(
      { input: ATLAS_DEFAULT_ACCENT, preference: null },
      "Appearance reset to the Atlas default.",
    );
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

        <section className="form-card appearance-card" aria-labelledby="appearance-title">
          <div className="form-card-header">
            <div>
              <p className="eyebrow">Appearance</p>
              <h2 id="appearance-title">Theme colour</h2>
            </div>
          </div>
          {appearanceStatus.error && <div className="error-banner" id="accent-error" role="alert">{appearanceStatus.error}</div>}
          {appearanceStatus.success && <div className="success-banner" role="status">{appearanceStatus.success}</div>}
          <form className="resource-form" onSubmit={saveAppearance}>
            <div className="appearance-controls">
              <label className="field colour-picker-field">
                <span>Accent colour</span>
                <input
                  aria-describedby={appearanceStatus.error ? "accent-error accent-help" : "accent-help"}
                  disabled={appearanceStatus.saving}
                  onChange={(event) => selectAccent(event.target.value)}
                  type="color"
                  value={accentPreference || ATLAS_DEFAULT_ACCENT}
                />
              </label>
              <label className="field">
                <span>Hex colour</span>
                <input
                  aria-describedby={appearanceStatus.error ? "accent-error accent-help" : "accent-help"}
                  aria-invalid={Boolean(appearanceStatus.error)}
                  autoComplete="off"
                  disabled={appearanceStatus.saving}
                  maxLength={7}
                  onChange={(event) => changeAccentText(event.target.value)}
                  spellCheck="false"
                  value={accentInput}
                />
                <small id="accent-help">Use a six-digit hexadecimal colour. Text contrast is selected automatically.</small>
              </label>
            </div>
            <fieldset className="accent-presets">
              <legend>Colour presets</legend>
              <div className="accent-preset-grid">
                {ACCENT_PRESETS.map((preset) => {
                  const selected = preset.value === null
                    ? accentPreference === null
                    : accentPreference === preset.value;
                  return (
                    <button
                      aria-label={`Use ${preset.name} accent colour`}
                      aria-pressed={selected}
                      className={`accent-preset${selected ? " selected" : ""}`}
                      disabled={appearanceStatus.saving}
                      key={preset.name}
                      onClick={() => selectAccent(preset.value)}
                      style={{ "--preset-colour": preset.value || ATLAS_DEFAULT_ACCENT }}
                      type="button"
                    >
                      <span aria-hidden="true" className="accent-swatch" />
                      <span>{preset.name}</span>
                      <span aria-hidden="true" className="preset-check">{selected ? "✓" : ""}</span>
                    </button>
                  );
                })}
              </div>
            </fieldset>
            <div className="accent-preview" style={accentThemeStyle(accentPreference)}>
              <div>
                <p className="eyebrow">Live preview</p>
                <strong>Atlas interface accent</strong>
                <span>Navigation, links, focus rings, and primary actions use this colour family.</span>
              </div>
              <button className="button button-primary" type="button">Primary action</button>
            </div>
            <div className="form-actions">
              <button className="button button-secondary" disabled={appearanceStatus.saving} onClick={resetAppearance} type="button">Reset to Atlas default</button>
              <button className="button button-primary" disabled={appearanceStatus.saving} type="submit">
                {appearanceStatus.saving ? "Saving…" : "Save appearance"}
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
