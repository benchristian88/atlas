"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  clearToken,
  getCurrentUser,
  getToken,
  login,
} from "../../lib/auth";

function developmentInfo(message) {
  if (process.env.NODE_ENV === "development") console.info(message);
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    async function validateExistingToken() {
      let existingToken;
      try {
        existingToken = getToken();
        if (!existingToken) return;
        await getCurrentUser();
        if (active) router.replace("/dashboard");
      } catch (requestError) {
        if (!active) return;
        try {
          // Do not let an older session check erase a token from a new login.
          if (getToken() !== existingToken) return;
          clearToken();
        } catch (storageError) {
          setError(storageError.message);
          return;
        }
        setError(
          requestError.status === 401
            ? "Your previous session expired. Sign in again."
            : `The saved session could not be verified. ${requestError.message}`,
        );
      }
    }
    validateExistingToken();
    return () => { active = false; };
  }, [router]);

  async function submit(event) {
    event.preventDefault();
    developmentInfo("login submit clicked");
    setSubmitting(true);
    setError("");
    try {
      await login(email, password);
      developmentInfo("redirecting to dashboard");
      setSubmitting(false);
      router.replace("/dashboard");
      router.refresh();
    } catch (requestError) {
      setError(
        requestError.status === 401
          ? "The email or password is incorrect."
          : requestError.message || "Atlas could not complete the login request.",
      );
    } finally {
      setSubmitting(false);
    }
  }

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
        <form className="login-form" onSubmit={submit}>
          <label className="field">
            <span>Email</span>
            <input
              autoComplete="email"
              autoFocus
              disabled={submitting}
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
              disabled={submitting}
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </label>
          <button className="button button-primary login-submit" disabled={submitting} type="submit">
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
