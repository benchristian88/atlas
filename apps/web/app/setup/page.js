"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AtlasLogo } from "../../components/atlas-brand.mjs";
import { Button } from "../../components/button";
import { RestoreBackupForm } from "../../components/backup-restore";
import { getSetupStatus, setupRequest } from "../../lib/setup";

export default function SetupPage() {
  const router = useRouter();
  const [stage, setStage] = useState("checking");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    getSetupStatus().then((status) => {
      if (!active) return;
      if (status.state === "INITIALISED") router.replace("/login");
      else setStage(status.authorized ? "choices" : "code");
    }).catch((failure) => { if (active) { setError(failure.message); setStage("error"); } });
    return () => { active = false; };
  }, [router, retry]);

  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const payload = stage === "code" ? { code: values.get("code") } : {
      display_name: values.get("display_name"), email: values.get("email"),
      password: values.get("password"), password_confirmation: values.get("password_confirmation"),
    };
    // Clear credential inputs immediately. Keep no credential in React state
    // or browser storage; only the request owns it while in flight.
    form.reset();
    setBusy(true);
    setError("");
    try {
      await setupRequest(stage === "code" ? "verify" : "administrator", payload);
      if (stage === "code") setStage("choices");
      else { setStage("complete"); router.replace("/login"); }
    } catch (failure) {
      if (failure.status === 409) { setStage("complete"); router.replace("/login"); }
      else if (failure.status === 401 && stage !== "code") {
        setStage("code"); setError("Setup authorization expired. Enter your setup code again.");
      } else setError(failure.message || "Atlas could not complete setup.");
    } finally { setBusy(false); }
  }

  return <main className="login-page">
    <div className="login-panel">
      <div className="login-logo"><AtlasLogo className="login-logo-image" fallbackClassName="login-logo-fallback" /></div>
      <section className="login-card" aria-labelledby="setup-title">
        <p className="eyebrow">First-run setup</p>
        <h1 id="setup-title">{stage === "administrator" ? "Create your administrator" : "Welcome to Atlas"}</h1>
        {error && <div className="error-banner" role="alert">{error}</div>}
        {stage === "checking" && <p role="status">Checking Atlas initialization…</p>}
        {stage === "complete" && <p role="status">Opening sign in…</p>}
        {stage === "error" && <Button onClick={() => { setStage("checking"); setError(""); setRetry(v => v + 1); }}>Try again</Button>}
        {stage === "code" && <>
          <p className="page-description">Enter the one-time code shown in your installation terminal to secure this Atlas instance.</p>
          <form className="login-form" onSubmit={submit}>
            <label className="field"><span>Setup code</span><input name="code" type="password" autoComplete="off" autoFocus required maxLength="128" disabled={busy} spellCheck="false" autoCapitalize="characters" /></label>
            <Button variant="primary" type="submit" disabled={busy}>{busy ? "Verifying…" : "Continue"}</Button>
          </form>
          <p className="secondary-text">Lost the code? Use the local setup-code reset command on the Atlas host.</p>
        </>}
        {stage === "choices" && <div className="setup-choices">
          <p className="page-description">Choose how to initialize your Atlas installation.</p>
          <section><h2>Set up a new Atlas</h2><p>Create the first administrator and start curating your operational knowledge.</p><Button variant="primary" onClick={() => setStage("administrator")}>Set up a new Atlas</Button></section>
          <section><h2>Restore an existing Atlas backup</h2><p>Restore your encrypted Atlas backup and sign in using an existing account.</p><Button variant="secondary" onClick={() => setStage("restore")}>Restore existing Atlas backup</Button></section>
        </div>}
        {stage === "restore" && <RestoreBackupForm fresh onCancel={() => setStage("choices")} />}
        {stage === "administrator" && <>
          <p className="page-description">This account receives global Master Administrator access. Use it to manage users and instance settings.</p>
          <form className="login-form" onSubmit={submit}>
            <label className="field"><span>Name</span><input name="display_name" autoComplete="name" autoFocus required maxLength="255" disabled={busy} /></label>
            <label className="field"><span>Email</span><input name="email" type="email" autoComplete="email" required maxLength="320" disabled={busy} /></label>
            <label className="field"><span>Password</span><input aria-label="Password" aria-describedby="setup-password-help" name="password" type="password" autoComplete="new-password" required minLength="12" maxLength="1024" disabled={busy} /><small id="setup-password-help">Use at least 12 characters.</small></label>
            <label className="field"><span>Confirm password</span><input name="password_confirmation" type="password" autoComplete="new-password" required minLength="12" maxLength="1024" disabled={busy} /></label>
            <Button variant="primary" type="submit" disabled={busy}>{busy ? "Creating administrator…" : "Create administrator"}</Button>
          </form>
        </>}
      </section>
    </div>
  </main>;
}
