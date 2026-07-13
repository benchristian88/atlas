"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "../../components/page-header";
import {
  apiRequest,
  clearAccessToken,
  getAccessToken,
} from "../../lib/api";

function validUser(value) {
  return Boolean(
    value
    && typeof value.email === "string"
    && typeof value.display_name === "string",
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadCurrentUser = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      if (!getAccessToken()) {
        router.replace("/login");
        return;
      }
      const currentUser = await apiRequest("/auth/me");
      if (!validUser(currentUser)) {
        throw new Error("Atlas API returned an unexpected user response.");
      }
      setUser(currentUser);
    } catch (requestError) {
      if (requestError.status === 401) {
        try {
          clearAccessToken();
        } catch (storageError) {
          setError(storageError.message);
          return;
        }
        router.replace("/login");
        return;
      }
      setError(requestError.message || "Atlas could not load the dashboard.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => { loadCurrentUser(); }, [loadCurrentUser]);

  function logout() {
    try {
      clearAccessToken();
      router.replace("/login");
      router.refresh();
    } catch (storageError) {
      setError(storageError.message);
    }
  }

  if (loading) {
    return <div className="status-banner" role="status">Checking your Atlas session…</div>;
  }

  return (
    <>
      <div className="page-heading-row">
        <PageHeader
          eyebrow="Dashboard"
          title="Welcome to Atlas"
          description="Your authenticated Atlas session is active."
        />
        {user && <button className="button button-secondary" onClick={logout} type="button">Log out</button>}
      </div>
      {error ? (
        <div className="error-panel" role="alert">
          <p>{error}</p>
          <button className="button button-secondary" onClick={loadCurrentUser} type="button">Try again</button>
        </div>
      ) : user ? (
        <section className="profile-card">
          <p className="eyebrow">Signed in as</p>
          <h2>{user.display_name}</h2>
          <p>{user.email}</p>
        </section>
      ) : null}
    </>
  );
}
