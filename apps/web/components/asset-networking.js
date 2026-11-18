"use client";

import { useState } from "react";
import { apiRequest } from "../lib/api";
import { Button } from "./button";
import { InterfaceAttachment, InterfaceDiscoveryDetails } from "./interface-knowledge";
import styles from "./asset-networking.module.css";

const newInterface = { name: "eth0", network_id: "", ip_address: "", mac_address: "", is_primary: true, notes: "" };

function interfaceFields(item) {
  return {
    name: item.name,
    network_id: item.network_id ?? "",
    ip_address: item.ip_address ?? "",
    mac_address: item.mac_address ?? "",
    is_primary: item.is_primary,
    notes: item.notes ?? "",
  };
}

function interfacePayload(draft, original) {
  const fields = Object.entries(draft).filter(([field, value]) => !original || value !== original[field]);
  return Object.fromEntries(fields.map(([field, value]) => [field, value === "" ? null : value]));
}

function hasRequiredHostnameGap(completeness) {
  return completeness?.active_gaps?.some((gap) => {
    const details = gap.details_json;
    // The evaluator emits a top-level field for direct field rules. A value
    // constraint also has allowed_values, and an alternative rule has its own shape.
    return gap.requirement_level === "required"
      && ["open", "deferred"].includes(gap.status)
      && Boolean(gap.last_evaluated_at)
      && details?.field === "hostname"
      && details.configuration_invalid === false
      && !Object.hasOwn(details, "allowed_values");
  });
}

function InterfaceForm({ draft, networks, onChange, onSubmit, onCancel, busy, error, editing = false }) {
  const submitLabel = editing ? "Save" : "Add interface";
  function change(event) {
    const { name, type, checked, value } = event.target;
    onChange({ ...draft, [name]: type === "checkbox" ? checked : value });
  }
  return <form aria-label={editing ? "Edit interface" : "Add interface"} className={styles.form} onSubmit={onSubmit}>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <fieldset className={`form-grid ${styles.fields}`} disabled={busy}>
      <label className="field"><span>Interface name *</span><input autoFocus={editing} maxLength={100} name="name" onChange={change} required value={draft.name} /></label>
      <label className="field"><span>Assigned Atlas Network</span><select name="network_id" onChange={change} value={draft.network_id}>
        <option value="">Unassigned</option>
        {networks.map((network) => <option key={network.id} value={network.id}>{network.name}{network.vlan_id != null && ` · VLAN ${network.vlan_id}`}</option>)}
      </select></label>
      <label className="field"><span>IP address</span><input maxLength={45} name="ip_address" onChange={change} value={draft.ip_address} /></label>
      <label className="field"><span>MAC address</span><input maxLength={17} name="mac_address" onChange={change} value={draft.mac_address} /></label>
      <label className="field checkbox-field"><input checked={draft.is_primary} name="is_primary" onChange={change} type="checkbox" /><span>Primary interface</span></label>
      <label className="field field-wide"><span>Notes</span><textarea maxLength={10000} name="notes" onChange={change} value={draft.notes} /></label>
    </fieldset>
    <div className="form-actions">
      <Button disabled={busy} onClick={onCancel}>Cancel</Button>
      <Button loading={busy} type="submit" variant="primary">{submitLabel}</Button>
    </div>
  </form>;
}

export function AssetNetworking({
  assetId, hostname, completeness, interfaces, networks, canViewNetworks,
  canCreateInterface, canEditInterface, canDeleteInterface, onChanged,
}) {
  const [addDraft, setAddDraft] = useState(newInterface);
  const [showAdd, setShowAdd] = useState(false);
  const [edit, setEdit] = useState(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [error, setError] = useState("");
  const hostnameText = (hostname?.trim() && hostname) || (hasRequiredHostnameGap(completeness) ? "Required, not recorded" : null);

  function closeForm() {
    setShowAdd(false);
    setEdit(null);
    setFormError("");
  }

  function startEdit(item) {
    const original = interfaceFields(item);
    setFormError("");
    setEdit({ id: item.id, original, draft: original });
  }

  async function refreshAfterChange(change) {
    try {
      await onChanged();
    } catch (requestError) {
      setError(`${change} Reload this page to refresh the asset. ${requestError.message}`);
    }
  }

  async function saveInterface(event) {
    event.preventDefault();
    if (busy || (edit ? !canEditInterface : !canCreateInterface)) return;
    const changes = edit ? interfacePayload(edit.draft, edit.original) : interfacePayload(addDraft);
    if (edit && !Object.keys(changes).length) {
      closeForm();
      return;
    }
    setBusy(true);
    setFormError("");
    setError("");
    try {
      // The PATCH response has no scoped assignment or discovery projection.
      await apiRequest(edit ? `/asset-interfaces/${edit.id}` : "/asset-interfaces", {
        method: edit ? "PATCH" : "POST",
        body: JSON.stringify(edit ? changes : { ...changes, asset_id: assetId }),
      });
      if (!edit) setAddDraft({ ...newInterface, is_primary: false });
      closeForm();
      await refreshAfterChange(edit ? "Interface saved." : "Interface added.");
    } catch (requestError) {
      setFormError(requestError.message || (edit ? "Atlas could not save this interface." : "Atlas could not create this interface."));
    } finally {
      setBusy(false);
    }
  }

  async function removeInterface(item) {
    if (busy || !window.confirm(`Delete interface “${item.name}”?`)) return;
    setBusy(true);
    setError("");
    try {
      await apiRequest(`/asset-interfaces/${item.id}`, { method: "DELETE" });
      if (edit?.id === item.id) closeForm();
      await refreshAfterChange("Interface deleted.");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  if (!hostnameText && !canViewNetworks) return null;
  return <section aria-labelledby="asset-networking-title" className={`form-card ${styles.card}`}>
    <h2 id="asset-networking-title">Networking</h2>
    {hostnameText && <dl className={styles.hostname}>
      <dt>Hostname</dt>
      <dd>{hostnameText}</dd>
    </dl>}
    {canViewNetworks && <>
      <header className={styles.interfacesHeader}>
        <h3>Interfaces</h3>
        {canCreateInterface && !showAdd && <Button disabled={busy || Boolean(edit)} onClick={() => setShowAdd(true)} variant="primary">Add interface</Button>}
      </header>
      {error && <div className="error-banner" role="alert">{error}</div>}
      {canCreateInterface && showAdd && <InterfaceForm busy={busy} draft={addDraft} error={formError} networks={networks} onCancel={closeForm} onChange={setAddDraft} onSubmit={saveInterface} />}
      {interfaces.length === 0 ? <p className="empty-state">No interfaces yet.</p> :
        <ul className={styles.list}>{interfaces.map((item) => {
          const editing = canEditInterface && edit?.id === item.id;
          const assigned = item.assigned_network;
          const editNetworks = assigned && !networks.some((network) => network.id === assigned.id) ? [assigned, ...networks] : networks;
          return <li className={`interface-row ${styles.row}`} key={item.id}>
            <div className={styles.rowHeader}>
              <div>
                <strong>{item.name}{item.is_primary ? " · Primary" : ""}</strong>
                <p>{item.ip_address || "IP not recorded"}{item.mac_address && <> · MAC <code>{item.mac_address}</code></>}</p>
              </div>
              {(canEditInterface || canDeleteInterface) && <div className={styles.actions}>
                {canEditInterface && <Button disabled={busy || showAdd || Boolean(edit)} onClick={() => startEdit(item)} variant="quiet">Edit</Button>}
                {canDeleteInterface && <Button className="text-danger" disabled={busy} onClick={() => removeInterface(item)} variant="quiet">Delete</Button>}
              </div>}
            </div>
            <InterfaceAttachment className={styles.attachments} item={item} />
            <InterfaceDiscoveryDetails facts={item.observed_facts} />
            {editing && <InterfaceForm busy={busy} draft={edit.draft} editing error={formError} networks={editNetworks} onCancel={closeForm} onChange={(draft) => setEdit({ ...edit, draft })} onSubmit={saveInterface} />}
          </li>;
        })}</ul>}
    </>}
  </section>;
}
