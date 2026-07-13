"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "../../components/page-header";
import {
  apiRequest,
  clearAccessToken,
  getAccessToken,
} from "../../lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }

    let active = true;
    apiRequest("/auth/me")
      .then((currentUser) => {
        if (active) setUser(currentUser);
      })
      .catch((requestError) => {
        if (!active) return;
        clearAccessToken();
        if (requestError.message === "Sign in to Atlas before managing records.") {
          router.replace("/login");
        } else {
          setError(requestError.message);
        }
      });
    return () => { active = false; };
  }, [router]);

  async function logout() {
    try {
      await apiRequest("/auth/logout", { method: "POST" });
    } finally {
      clearAccessToken();
      router.replace("/login");
    }
  }

  if (!user && !error) {
    return <p className="secondary-text">Loading dashboard…</p>;
  }

  return (
    <>
      <div className="page-heading-row">
        <PageHeader
          eyebrow="Dashboard"
          title="Welcome to Atlas"
          description="Your authenticated Atlas session is active."
        />
        <button className="button button-secondary" onClick={logout} type="button">Log out</button>
      </div>
      {error ? (
        <div className="error-banner" role="alert">{error}</div>
      ) : (
        <section className="profile-card">
          <p className="eyebrow">Signed in as</p>
          <h2>{user.display_name}</h2>
          <p>{user.email}</p>
        </section>
      )}
    </>
  );
}
