"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authenticatedHome } from "../../components/auth-context";
import { getCurrentUser, login } from "../../lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    let active = true;
    async function validateExistingSession() {
      try {
        const user = await getCurrentUser();
        if (active) {
          router.replace(authenticatedHome(user));
        }
      } catch (requestError) {
        if (!active) return;
        if (requestError.status !== 401) {
          setError(`Atlas could not check your existing session. ${requestError.message}`);
        }
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
      const user = await login(email, password);
      router.replace(authenticatedHome(user));
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
        <p className="page-description">Use your database-backed Atlas account.</p>
        {error && <div className="error-banner" role="alert">{error}</div>}
        <form className="login-form" onSubmit={submit}>
          <label className="field">
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
          </label>
          <button
            className="button button-primary login-submit"
            disabled={submitting || checkingSession}
            type="submit"
          >
            {checkingSession ? "Checking session…" : submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
