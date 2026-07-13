"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  apiRequest,
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "../../lib/api";

function validLoginResponse(result) {
  return Boolean(
    result
    && typeof result.access_token === "string"
    && result.access_token.trim()
    && result.token_type?.toLowerCase() === "bearer"
    && typeof result.user?.email === "string",
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    let active = true;
    async function checkExistingSession() {
      try {
        if (!getAccessToken()) {
          if (active) setStatus("idle");
          return;
        }
        await apiRequest("/auth/me");
        if (active) router.replace("/dashboard");
      } catch (requestError) {
        if (!active) return;
        if (requestError.status === 401) {
          try {
            clearAccessToken();
          } catch (storageError) {
            setError(storageError.message);
          }
        } else {
          setError(`Could not verify the saved session. ${requestError.message}`);
        }
        setStatus("idle");
      }
    }
    checkExistingSession();
    return () => { active = false; };
  }, [router]);

  async function submit(event) {
    event.preventDefault();
    setStatus("submitting");
    setError("");
    try {
      const result = await apiRequest("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      if (!validLoginResponse(result)) {
        throw new Error("Atlas API returned an unexpected login response without a valid bearer token.");
      }
      setAccessToken(result.access_token);
      setStatus("redirecting");
      router.replace("/dashboard");
      router.refresh();
    } catch (requestError) {
      setError(
        requestError.status === 401
          ? "The email or password is incorrect."
          : requestError.message || "Atlas could not complete the login request.",
      );
      setStatus("idle");
    }
  }

  const busy = status !== "idle";
  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-brand">
          <span className="brand-mark" aria-hidden="true">A</span>
          Atlas
        </div>
        <p className="eyebrow">Welcome back</p>
        <h1 id="login-title">Sign in to Atlas</h1>
        <p className="page-description">Use the administrator credentials configured for this deployment.</p>
        {error && <div className="error-banner" role="alert">{error}</div>}
        {status === "checking" && <div className="status-banner" role="status">Checking for an existing session…</div>}
        {status === "redirecting" && <div className="status-banner" role="status">Login successful. Opening dashboard…</div>}
        <form className="login-form" onSubmit={submit}>
          <label className="field">
            <span>Email</span>
            <input
              autoComplete="email"
              autoFocus
              disabled={busy}
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
              disabled={busy}
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </label>
          <button className="button button-primary login-submit" disabled={busy} type="submit">
            {status === "submitting" ? "Signing in…" : status === "redirecting" ? "Opening dashboard…" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
