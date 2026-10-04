"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "./button";
import { Section } from "./section";
import { apiRequest } from "../lib/api";
import { apiUrl } from "../lib/api-url.mjs";
import { backupValidation, restoreFileValidation } from "../lib/backup.mjs";
import styles from "./backup-restore.module.css";

function useBackupJob(restore = false) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!job || !["requested", "uploading", "preparing", "restoring"].includes(job.state)) return;
    let active = true;
    let timer;
    async function poll() {
      try {
        const next = await apiRequest(restore ? `/restore-status/${job.id}` : `/system-settings/backups/${job.id}`,
          { omitContext: true, redirectOnUnauthorized: false, cache: "no-store" });
        if (!active) return;
        setJob(next);
        setError("");
        if (next.state === "complete" && restore) window.location.replace("/login");
      } catch (failure) {
        if (active) {
          setError(failure.message || "Atlas could not check operation progress.");
          timer = setTimeout(poll, 3000);
        }
      }
    }
    timer = setTimeout(poll, 1500);
    return () => { active = false; clearTimeout(timer); };
  }, [job, restore]);
  return { job, setJob, error, setError };
}

function JobProgress({ job, error }) {
  return <>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {job && <p role={job.state === "failed" ? "alert" : "status"} aria-live="polite">{job.message}</p>}
  </>;
}

function PasswordField() {
  return <label className="field"><span>Current password</span><input name="current_password" type="password" autoComplete="current-password" required maxLength="1024" /></label>;
}

export function RestoreBackupForm({ fresh = false, onCancel }) {
  const { job, setJob, error, setError } = useBackupJob(true);
  const [busy, setBusy] = useState(false);
  const [mfaStatus, setMfaStatus] = useState(fresh ? { enabled: false } : null);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    if (fresh) return;
    let active = true;
    apiRequest("/auth/mfa/status", { omitContext: true, cache: "no-store" })
      .then(status => { if (active) setMfaStatus(status); })
      .catch(failure => { if (active) setError(failure.message || "Atlas could not check your verification requirements. Close this form and try again."); });
    return () => { active = false; };
  }, [fresh, setError]);
  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const file = values.get("archive");
    const validation = restoreFileValidation(file);
    if (validation) { setError(validation); return; }
    const payload = { passphrase: values.get("passphrase") };
    if (!fresh) Object.assign(payload, {
      current_password: values.get("current_password"), acknowledgement: values.get("acknowledgement"),
      code: values.get("code") || null, method: values.get("method") || "totp",
    });
    form.reset();
    setError(""); setBusy(true);
    try {
      const authorization = await apiRequest(fresh ? "/setup/restore/authorize" : "/system-settings/restore/authorize",
        { method: "POST", body: JSON.stringify(payload), omitContext: true, redirectOnUnauthorized: false });
      const result = await apiRequest(fresh ? `/setup/restore/${authorization.id}/upload` : `/system-settings/restore/${authorization.id}/upload`,
        { method: "PUT", body: file, headers: { "Content-Type": "application/octet-stream" }, omitContext: true, redirectOnUnauthorized: false });
      if (alive.current) setJob(result);
    } catch (failure) {
      if (alive.current) setError(failure.message || "Atlas could not start restore.");
    } finally { if (alive.current) setBusy(false); }
  }
  const running = job && ["requested", "uploading", "preparing", "restoring", "complete"].includes(job.state);
  return <div className={styles.flow}>
    <JobProgress job={job} error={error} />
    {busy && <p role="status">Uploading encrypted backup…</p>}
    {!mfaStatus && !error && <p role="status">Checking verification requirements…</p>}
    {!running && !busy && mfaStatus && <form className={styles.form} onSubmit={submit}>
      <p>{fresh ? "Restore your Atlas accounts and data, then sign in using a restored account." : "This will replace the current Atlas data with the contents of this backup."} Atlas will pause normal operations during restore.</p>
      <p className="secondary-text">The target installation keeps its deployment settings and security keys. A valid backup is required before Atlas changes its data.</p>
      <label className="field"><span>Atlas backup file</span><input aria-label="Atlas backup file" aria-describedby="restore-file-help" name="archive" type="file" accept=".atlasbackup" required /><small id="restore-file-help">Encrypted .atlasbackup file, up to 2 GiB.</small></label>
      <label className="field"><span>Backup passphrase</span><input aria-label="Backup passphrase" name="passphrase" type="password" autoComplete="off" required minLength="12" maxLength="1024" /></label>
      {!fresh && <>
        <PasswordField />
        {mfaStatus.enabled && <>
          <label className="field"><span>Verification method</span><select name="method" defaultValue="totp"><option value="totp">Authenticator code</option><option value="recovery">Recovery code</option></select></label>
          <label className="field"><span>Current authenticator or recovery code</span><input name="code" type="password" autoComplete="off" required maxLength="100" /></label>
        </>}
        <label className="field"><span>Type RESTORE to confirm replacement</span><input name="acknowledgement" autoComplete="off" pattern="RESTORE" required /></label>
      </>}
      <div className="form-actions">
        {onCancel && <Button variant="secondary" onClick={onCancel} type="button">Cancel</Button>}
        <Button variant="destructive" type="submit">{fresh ? "Restore Atlas" : "Replace Atlas data"}</Button>
      </div>
    </form>}
    {running && <p className="secondary-text">Keep this page open to follow progress. Atlas requires a new login after restore.</p>}
  </div>;
}

export function BackupRestore() {
  const [action, setAction] = useState("");
  const [busy, setBusy] = useState(false);
  const { job, setJob, error, setError } = useBackupJob();
  async function create(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const passphrase = values.get("passphrase");
    const confirmation = values.get("passphrase_confirmation");
    const validation = backupValidation(passphrase, confirmation);
    if (validation) { setError(validation); return; }
    const payload = { passphrase, passphrase_confirmation: confirmation, current_password: values.get("current_password") };
    form.reset();
    setBusy(true); setError("");
    try {
      setJob(await apiRequest("/system-settings/backups", { method: "POST", body: JSON.stringify(payload), omitContext: true }));
      setAction("");
    } catch (failure) { setError(failure.message || "Atlas could not create a backup."); }
    finally { setBusy(false); }
  }
  const preparing = job && ["requested", "preparing"].includes(job.state);
  return <Section title="Backup & Restore" id="settings-backup" className="ops-card system-settings-section">
    <div className={styles.panels}>
      <div><h3>Backup Atlas</h3><p>Create a passphrase-protected backup of Atlas application data and the cryptographic material needed to restore encrypted data.</p>
        <JobProgress job={job} error={error} />
        {job?.state === "ready" && <div className="form-actions"><Button href={apiUrl(`/system-settings/backups/${job.id}/download`, process.env.NEXT_PUBLIC_API_URL)} download prefetch={false}>Download encrypted backup</Button><small>One download; expires after 15 minutes.</small></div>}
        {action === "backup" ? <form className={styles.form} onSubmit={create}>
          <label className="field"><span>Backup passphrase</span><input aria-label="Backup passphrase" aria-describedby="backup-passphrase-help" name="passphrase" type="password" autoComplete="new-password" autoFocus required minLength="12" maxLength="1024" /><small id="backup-passphrase-help">Use at least 12 characters. A phrase of several unrelated words works well.</small></label>
          <label className="field"><span>Confirm backup passphrase</span><input name="passphrase_confirmation" type="password" autoComplete="new-password" required minLength="12" maxLength="1024" /></label>
          <p>Atlas cannot recover this backup if the passphrase is lost.</p>
          <PasswordField />
          <div className="form-actions"><Button variant="secondary" type="button" disabled={busy} onClick={() => { setAction(""); setError(""); }}>Cancel</Button><Button type="submit" loading={busy}>Create encrypted backup</Button></div>
        </form> : <Button variant="secondary" disabled={busy || preparing || action === "restore"} onClick={() => { setAction("backup"); setError(""); }}>Create backup</Button>}
      </div>
      <div><h3>Restore Atlas</h3><p>Replace this installation’s Atlas data from an encrypted backup.</p>
        {action === "restore" ? <RestoreBackupForm onCancel={() => setAction("")} />
          : <Button variant="secondary" disabled={busy || preparing || action === "backup"} onClick={() => setAction("restore")}>Restore backup</Button>}
      </div>
    </div>
  </Section>;
}
