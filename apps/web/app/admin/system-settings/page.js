"use client";

import { IconButton, Button } from "../../../components/button";

import { useCallback, useEffect, useState } from "react";
import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { DataTable } from "../../../components/data-table";
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
      {editing && <section className="form-card"><div className="form-card-header"><h2>Edit {editing.key}</h2><IconButton onClick={() => setEditing(null)} type="button" label="Close form" icon="close" /></div><form onSubmit={save}><label className="field"><span>Value</span><textarea autoFocus onChange={(event) => setValue(event.target.value)} required rows="5" value={value} /><small>JSON values are accepted; other input is stored as text.</small></label><div className="form-actions"><Button variant="secondary" onClick={() => setEditing(null)} type="button">Cancel</Button><Button variant="primary" disabled={saving} type="submit">{saving ? "Saving…" : "Save setting"}</Button></div></form></section>}
      <DataTable label="System settings" rows={settings} loading={loading} error={error} onRefresh={load} empty="No administrator-managed runtime settings are configured yet." columns={[
        { key: "key", label: "Key", render: setting => <span className="mono">{setting.key}</span> },
        { key: "value", label: "Value", render: setting => <code>{inputValue(setting.value)}</code> },
        { key: "description", label: "Description" },
        { key: "updated_at", label: "Updated", render: setting => new Date(setting.updated_at).toLocaleString() },
      ]} actions={setting => <button className="text-button" onClick={() => { setEditing(setting); setValue(inputValue(setting.value)); }} type="button">Edit</button>} />
      </section>
      <section className="ops-card system-settings-section" aria-labelledby="settings-about">
        <h2 id="settings-about">About</h2>
        <p><strong>Atlas Impact</strong></p>
        <p className="secondary-text">Web package version: <strong>{packageMetadata.version}</strong></p>
      </section>
    </>
  );
}
