"use client";

import { useCallback, useEffect, useState } from "react";
import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { PageHeader } from "../../../components/page-header";
import packageMetadata from "../../../package.json";
import { apiRequest } from "../../../lib/api";

function inputValue(value) {
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function parsedValue(value) {
  try { return JSON.parse(value); } catch { return value; }
}

export default function SystemSettingsAdminPage() {
  const { hasGlobalPermission } = useAuth();
  const [settings, setSettings] = useState([]);
  const [editing, setEditing] = useState(null);
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const canManage = hasGlobalPermission("system_settings.manage");

  const load = useCallback(async () => {
    if (!canManage) return;
    setLoading(true);
    try { setSettings((await apiRequest("/system-settings")).filter((setting) => !setting.sensitive)); }
    catch (requestError) { setError(requestError.message || "Atlas could not load system settings."); }
    finally { setLoading(false); }
  }, [canManage]);

  useEffect(() => { load(); }, [load]);
  if (!canManage) return <AccessDenied />;

  async function save(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await apiRequest(`/system-settings/${encodeURIComponent(editing.key)}`, {
        method: "PATCH",
        body: JSON.stringify({ value: parsedValue(value) }),
      });
      setSuccess(`${editing.key} updated.`);
      setEditing(null);
      setValue("");
      await load();
    } catch (requestError) {
      setError(requestError.message || "Atlas could not update this setting.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader eyebrow="System" title="System Settings" description="Instance administration and information about Atlas Impact." />
      {error && <div className="error-banner" role="alert">{error}</div>}
      {success && <div className="success-banner" role="status">{success}</div>}
      <section className="ops-card system-settings-section" aria-labelledby="settings-general"><h2 id="settings-general">General</h2><p className="secondary-text">Supported non-secret runtime settings. Deployment credentials and security keys remain managed by your deployment.</p>
      {editing && <section className="form-card"><div className="form-card-header"><h2>Edit {editing.key}</h2><button className="icon-button" aria-label="Close form" onClick={() => setEditing(null)} type="button">×</button></div><form onSubmit={save}><label className="field"><span>Value</span><textarea autoFocus onChange={(event) => setValue(event.target.value)} required rows="5" value={value} /><small>JSON values are accepted; other input is stored as text.</small></label><div className="form-actions"><button className="button button-secondary" onClick={() => setEditing(null)} type="button">Cancel</button><button className="button button-primary" disabled={saving} type="submit">{saving ? "Saving…" : "Save setting"}</button></div></form></section>}
      <section className="table-card" aria-label="System settings"><div className="table-meta"><span>{loading ? "Loading…" : `${settings.length} settings`}</span><button className="text-button" disabled={loading} onClick={load} type="button">Refresh</button></div><div className="table-scroll"><table><thead><tr><th>Key</th><th>Value</th><th>Description</th><th>Updated</th><th>Actions</th></tr></thead><tbody>
        {!loading && settings.length === 0 && <tr><td className="empty-state" colSpan="5">No administrator-managed runtime settings are configured yet.</td></tr>}
        {settings.map((setting) => <tr key={setting.id}><td className="mono">{setting.key}</td><td><code>{inputValue(setting.value)}</code></td><td className="secondary-text">{setting.description || "—"}</td><td className="secondary-text">{new Date(setting.updated_at).toLocaleString()}</td><td><button className="text-button" onClick={() => { setEditing(setting); setValue(inputValue(setting.value)); }} type="button">Edit</button></td></tr>)}
      </tbody></table></div></section>
      </section>
      <section className="ops-card system-settings-section" aria-labelledby="settings-backup">
        <h2 id="settings-backup">Backup &amp; Restore</h2>
        <p>Planned for Homelab Ready hardening.</p>
        <p className="secondary-text">Backup creation, export and safe restore with compatibility validation will be added here.</p>
      </section>
      <section className="ops-card system-settings-section" aria-labelledby="settings-updates">
        <h2 id="settings-updates">Updates</h2>
        <p>Version and update checking are planned for Homelab Ready hardening.</p>
        <p className="secondary-text">Upgrade guidance and release information will be available here. Automatic updates are not available.</p>
      </section>
      <section className="ops-card system-settings-section" aria-labelledby="settings-about">
        <h2 id="settings-about">About</h2>
        <p><strong>Atlas Impact</strong></p>
        <p className="secondary-text">Web package version: <strong>{packageMetadata.version}</strong></p>
        <p className="secondary-text">Installed release and build details will be refined during Homelab Ready hardening.</p>
      </section>
    </>
  );
}
