"use client";

import { Button } from "./button";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiRequest } from "../lib/api";

export function EntityDeleteAction({ kind, item, onDeleted }) {
  const router = useRouter();
  const dialog = useRef(null);
  const [eligibility, setEligibility] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [open, setOpen] = useState(false);
  const label = kind === "service" ? "Service" : "Business Function";
  const collection = kind === "service" ? "/services" : "/business-functions";
  const path = `${collection}/${item.id}`;
  useEffect(() => {
    let current = true;
    setEligibility(null); setError("");
    apiRequest(`${path}/deletion-eligibility`).then((value) => {
      if (current) setEligibility(value);
    }).catch((failure) => { if (current) setError(failure.message); });
    return () => { current = false; };
  }, [path, item]);

  async function remove() {
    setSaving(true); setError("");
    try {
      await apiRequest(path, { method: "DELETE" });
      dialog.current.close();
      if (onDeleted) onDeleted();
      else { router.replace(collection); router.refresh(); }
    } catch (failure) {
      setError(failure.message);
      // Eligibility is advisory; the server rechecks on every delete attempt.
      try { setEligibility(await apiRequest(`${path}/deletion-eligibility`)); } catch { setEligibility(null); }
    } finally { setSaving(false); }
  }

  return <div className="entity-delete-action">
    <Button variant="destructive" type="button" disabled={!eligibility?.eligible || saving}
      aria-describedby={`delete-reason-${item.id}`} onClick={() => { setOpen(true); dialog.current.showModal(); }}>Delete {label}</Button>
    <p className="secondary-text" id={`delete-reason-${item.id}`}>
      {eligibility?.reason || (eligibility?.eligible ? "Delete mistakes. Archive history." : "Checking deletion eligibility…")}
    </p>
    {error && !open && <p className="error-banner" role="alert">{error}</p>}
    <dialog onClose={() => setOpen(false)} ref={dialog} className="dialog-card entity-delete-dialog" aria-labelledby={`delete-title-${item.id}`}
      aria-describedby={`delete-description-${item.id}`} onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const buttons = [...event.currentTarget.querySelectorAll("button:not([disabled])")];
        const first = buttons[0]; const last = buttons[buttons.length - 1];
        if (!first) { event.preventDefault(); return; }
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }} onCancel={(event) => { if (saving) event.preventDefault(); }}>
      <h2 id={`delete-title-${item.id}`}>Delete {label}?</h2>
      <p id={`delete-description-${item.id}`}><strong>{item.name}</strong> will be permanently removed from the operational model. This action is intended for records created by mistake and cannot be undone. Audit history is retained.</p>
      {error && <p className="error-banner" role="alert">{error}</p>}
      <div className="form-actions">
        <Button autoFocus variant="secondary" disabled={saving} type="button" onClick={() => dialog.current.close()}>Cancel</Button>
        <Button variant="destructive" disabled={saving || !eligibility?.eligible} type="button" onClick={remove}>{saving ? "Deleting…" : `Delete ${label}`}</Button>
      </div>
    </dialog>
  </div>;
}
