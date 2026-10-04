"use client";

import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { Button } from "./button";
import { apiRequest } from "../lib/api";
import styles from "./mfa-security.module.css";

function AuthenticatorQr({ uri }) {
  const canvas = useRef(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const target = canvas.current;
    setFailed(false);
    QRCode.toCanvas(target, uri, { width: 240, margin: 4, errorCorrectionLevel: "M" })
      .catch(() => setFailed(true));
    return () => { target?.getContext("2d")?.clearRect(0, 0, target.width, target.height); };
  }, [uri]);
  return failed ? <p role="alert">QR code could not be rendered. Use the manual setup key below.</p>
    : <canvas ref={canvas} className={styles.qr} role="img" aria-label="Authenticator setup QR code. The same key is provided below." />;
}

export function MfaSecurity({ passwordChangeRequired = false }) {
  const [status, setStatus] = useState(null);
  const [action, setAction] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [method, setMethod] = useState("totp");
  const [pending, setPending] = useState(null);
  const [recoveryCodes, setRecoveryCodes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const operation = useRef(0);

  async function refreshStatus() {
    setStatus(await apiRequest("/auth/mfa/status", { omitContext: true }));
  }
  useEffect(() => {
    let active = true;
    apiRequest("/auth/mfa/status", { omitContext: true }).then(value => { if (active) setStatus(value); })
      .catch(() => { if (active) setError("Atlas could not load two-factor authentication status."); });
    return () => { active = false; operation.current += 1; };
  }, []);

  useEffect(() => {
    if (!pending) return;
    const timer = setTimeout(() => {
      setPending(null);
      setCode("");
      setAction("");
      setError("Enrollment has expired. Start again.");
    }, Math.max(0, new Date(pending.expires_at).getTime() - Date.now()));
    return () => clearTimeout(timer);
  }, [pending]);

  function start(nextAction) {
    setPassword(""); setCode(""); setMethod("totp"); setError(""); setNotice("");
    setRecoveryCodes(null); setPending(null); setAction(nextAction);
  }

  async function cancel() {
    setBusy(true); setError("");
    try {
      if (pending) await apiRequest("/auth/mfa/enrollment", { method: "DELETE", omitContext: true });
      setPending(null); setAction(""); setPassword(""); setCode(""); setRecoveryCodes(null);
    } catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  }

  async function submit(event) {
    event.preventDefault();
    const generation = ++operation.current;
    setBusy(true); setError(""); setNotice("");
    const payload = { current_password: password, code: code || null, method };
    setPassword(""); setCode("");
    try {
      if (pending) {
        const result = await apiRequest("/auth/mfa/enrollment/confirm", {
          method: "POST", body: JSON.stringify({ enrollment_id: pending.enrollment_id, code }), omitContext: true,
        });
        if (generation !== operation.current) return;
        setPending(null); setAction(""); setRecoveryCodes(result.recovery_codes);
        setNotice("Two-factor authentication is enabled.");
        await refreshStatus();
      } else if (action === "enroll" || action === "replace") {
        const result = await apiRequest("/auth/mfa/enrollment", { method: "POST", body: JSON.stringify(payload), omitContext: true });
        if (generation !== operation.current) return;
        setPending(result);
      } else if (action === "regenerate") {
        const result = await apiRequest("/auth/mfa/recovery-codes", { method: "POST", body: JSON.stringify(payload), omitContext: true });
        if (generation !== operation.current) return;
        setRecoveryCodes(result.recovery_codes); setAction("");
        setNotice("New recovery codes created. All old codes are invalid.");
        await refreshStatus();
      } else if (action === "disable") {
        await apiRequest("/auth/mfa/disable", { method: "POST", body: JSON.stringify(payload), omitContext: true });
        if (generation !== operation.current) return;
        setAction(""); setNotice("Two-factor authentication is disabled.");
        await refreshStatus();
      }
    } catch (requestError) {
      if (generation === operation.current) {
        setError(requestError.message || "Atlas could not complete two-factor verification.");
        if (requestError.status === 409) { setPending(null); setAction(""); }
      }
    } finally { if (generation === operation.current) setBusy(false); }
  }

  async function copyCodes() {
    try { await navigator.clipboard.writeText(recoveryCodes.join("\n")); setNotice("Recovery codes copied."); }
    catch { setError("Copy is unavailable in this browser. Select and copy the codes below, or print them."); }
  }

  const requiresFactor = status?.enabled && !pending;
  return <section className="form-card" aria-labelledby="mfa-title">
    <div className="form-card-header"><div><p className="eyebrow">Security</p><h2 id="mfa-title">Two-factor authentication</h2></div></div>
    <p>{status ? status.enabled ? "Enabled" : "Not enabled" : "Loading…"}</p>
    {status?.enabled && <p className="secondary-text">Recovery codes remaining: {status.recovery_codes_remaining} of {status.recovery_codes_total}</p>}
    {error && <div className="error-banner" role="alert">{error}</div>}
    {notice && <div className="success-banner" role="status">{notice}</div>}
    {passwordChangeRequired && <p>Change your temporary password before managing two-factor authentication.</p>}
    {recoveryCodes ? <div className={styles.recovery}>
      <h3>Recovery codes</h3>
      <p>Save these codes somewhere safe. Each code can be used once. Atlas cannot show these codes again.</p>
      <ul className={styles.codes} aria-label="Recovery codes">{recoveryCodes.map(item => <li key={item}><code>{item}</code></li>)}</ul>
      <div className={`form-actions ${styles.actions}`}><Button onClick={copyCodes}>Copy all</Button><Button onClick={() => window.print()}>Print</Button><Button variant="primary" onClick={() => { setRecoveryCodes(null); setNotice(""); }}>I have saved my recovery codes</Button></div>
    </div> : action ? <form className="resource-form" onSubmit={submit}>
      <h3>{action === "replace" ? "Replace authenticator" : action === "disable" ? "Disable two-factor authentication" : action === "regenerate" ? "Generate new recovery codes" : "Enable two-factor authentication"}</h3>
      {pending ? <>
        <p>1. Scan this QR code with your authenticator app, or enter the setup key manually.</p>
        <AuthenticatorQr uri={pending.otpauth_uri} />
        <label className="field"><span>Manual setup key</span><input className={styles.manualKey} readOnly value={pending.manual_key} autoComplete="off" spellCheck={false} /></label>
        <p>2. Enter the current 6-digit code. Setup expires in ten minutes.</p>
      </> : <>
        <p>{action === "replace" ? "Your current authenticator keeps working until the new one is confirmed." : action === "disable" ? "You will sign in using only your password after disabling two-factor authentication." : "Re-enter your current password to continue."}</p>
        <label className="field"><span>Current password</span><input required type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} disabled={busy} maxLength={1024} /></label>
      </>}
      {(pending || requiresFactor) && <label className="field"><span>{method === "recovery" && !pending ? "Recovery code" : "Authenticator code"}</span>
        <input aria-label={method === "recovery" && !pending ? "Recovery code" : "Authenticator code"} aria-describedby={pending || method === "totp" ? "mfa-code-help" : undefined} required autoComplete="one-time-code" inputMode={method === "totp" || pending ? "numeric" : "text"} pattern={method === "totp" || pending ? "[0-9]{6}" : undefined} maxLength={method === "totp" || pending ? 6 : 100} value={code} disabled={busy} onChange={event => setCode(event.target.value)} />
        {(pending || method === "totp") && <small id="mfa-code-help">Use a new code if you have just used the current one.</small>}
      </label>}
      {requiresFactor && action !== "regenerate" && <Button onClick={() => { setMethod(method === "totp" ? "recovery" : "totp"); setCode(""); }} disabled={busy}>{method === "totp" ? "Use a recovery code" : "Use an authenticator code"}</Button>}
      <div className={`form-actions ${styles.actions}`}><Button onClick={cancel} disabled={busy}>Cancel</Button><Button variant={action === "disable" ? "danger" : "primary"} type="submit" disabled={busy}>{busy ? "Verifying…" : pending ? "Confirm authenticator" : action === "disable" ? "Disable two-factor authentication" : "Continue"}</Button></div>
    </form> : status && <div className={`form-actions ${styles.actions}`}>
      {status.enabled ? <><Button disabled={passwordChangeRequired} onClick={() => start("replace")}>Replace authenticator</Button><Button disabled={passwordChangeRequired} onClick={() => start("regenerate")}>Generate new recovery codes</Button><Button variant="danger" disabled={passwordChangeRequired} onClick={() => start("disable")}>Disable two-factor authentication</Button></>
        : <Button variant="primary" disabled={passwordChangeRequired} onClick={() => start("enroll")}>Enable two-factor authentication</Button>}
    </div>}
  </section>;
}
