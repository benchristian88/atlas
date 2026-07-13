"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "../../components/page-header";
import { useAuth } from "../../components/auth-context";
import { logout } from "../../lib/auth";

export default function DashboardPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [error, setError] = useState("");

  function signOut() {
    try {
      logout();
      router.replace("/login");
      router.refresh();
    } catch (storageError) {
      setError(storageError.message);
    }
  }

  return (
    <>
      <div className="page-heading-row">
        <PageHeader
          eyebrow="Dashboard"
          title="Welcome to Atlas"
          description="Your authenticated Atlas session is active."
        />
        <button className="button button-secondary" onClick={signOut} type="button">Log out</button>
      </div>
      {error && <div className="error-banner" role="alert">{error}</div>}
      <section className="profile-card">
        <p className="eyebrow">Signed in as</p>
        <h2>{user.display_name}</h2>
        <p>{user.email}</p>
      </section>
    </>
  );
}
