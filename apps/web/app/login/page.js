"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AtlasLogo } from "../../components/atlas-brand.mjs";
import { Button } from "../../components/button";
import { authenticatedHome } from "../../components/auth-context";
import { cancelLoginMfa, getCurrentUser, login, verifyLoginMfa } from "../../lib/auth";
import { getSetupStatus } from "../../lib/setup";
import { checkSession } from "../../lib/session-state.mjs";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);
  const [mfaRequired, setMfaRequired] = useState(false);
  const [code, setCode] = useState("");
  const [method, setMethod] = useState("totp");

  useEffect(() => {
    let active = true;
    async function validateExistingSession() {
      try {
        const setup = await getSetupStatus();
        if (!active) return;
        if (setup.state === "UNINITIALISED") {
          router.replace("/setup");
          return;
        }
        const session = await checkSession(getCurrentUser, () => active);
        if (!session) return;
        if (session.status === "authenticated") {
          router.replace(authenticatedHome(session.user));
        } else if (session.status === "error") {
          setError(`Atlas could not check your existing session. ${session.error}`);
        }
      } catch (requestError) {
        if (active) setError(requestError.message || "Atlas could not check initialization.");
      } finally {
        if (active) setCheckingSession(false);
      }
    }
    validateExistingSession();
    return () => { active = false; };
  }, [router]);

  async function submit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const user = mfaRequired ? await verifyLoginMfa(code, method) : await login(email, password);
      setPassword(""); setCode("");
      if (user.mfa_required) { setMfaRequired(true); setMethod("totp"); return; }
      router.replace(authenticatedHome(user));
      router.refresh();
    } catch (requestError) {
      setPassword(""); setCode("");
      if (mfaRequired && requestError.status === 401) setMfaRequired(false);
      setError(
        requestError.status === 401 && !mfaRequired
          ? "The email or password is incorrect."
          : requestError.message || "Atlas could not complete the login request.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <div className="login-panel">
        <div className="login-logo">
          <AtlasLogo className="login-logo-image" fallbackClassName="login-logo-fallback" />
        </div>
        <section className="login-card" aria-labelledby="login-title">
          <p className="eyebrow">Welcome back</p>
          <h1 id="login-title">{mfaRequired ? "Verify two-factor authentication" : "Sign in"}</h1>
          <p className="page-description">{mfaRequired ? "Enter a current authenticator code or one of your recovery codes." : "Use your database-backed Atlas Impact account."}</p>
          {error && <div className="error-banner" role="alert">{error}</div>}
          <form className="login-form" onSubmit={submit}>
            {!mfaRequired && <><label className="field">
              <span>Email</span>
              <input
                autoComplete="email"
                autoFocus
                disabled={submitting || checkingSession}
                onChange={(event) => setEmail(event.target.value)}
                required
                type="email"
                value={email}
              />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                autoComplete="current-password"
                disabled={submitting || checkingSession}
                onChange={(event) => setPassword(event.target.value)}
                required
                type="password"
                value={password}
              />
            </label></>}
            {mfaRequired && <><label className="field"><span>{method === "totp" ? "Authenticator code" : "Recovery code"}</span><input autoFocus required autoComplete="one-time-code" inputMode={method === "totp" ? "numeric" : "text"} pattern={method === "totp" ? "[0-9]{6}" : undefined} maxLength={method === "totp" ? 6 : 100} value={code} onChange={event => setCode(event.target.value)} disabled={submitting} /></label>
              <Button disabled={submitting} onClick={() => { setMethod(method === "totp" ? "recovery" : "totp"); setCode(""); setError(""); }}>{method === "totp" ? "Use a recovery code" : "Use an authenticator code"}</Button></>}
            <Button
              variant="primary" className="login-submit"
              disabled={submitting || checkingSession}
              type="submit"
            >
              {checkingSession ? "Checking session…" : submitting ? "Signing in…" : mfaRequired ? "Verify and sign in" : "Sign in"}
            </Button>
            {mfaRequired && <Button disabled={submitting} onClick={async () => { setSubmitting(true); try { await cancelLoginMfa(); setMfaRequired(false); setCode(""); setError(""); } catch (requestError) { setError(requestError.message); } finally { setSubmitting(false); } }}>Back to sign in</Button>}
          </form>
        </section>
      </div>
    </main>
  );
}
