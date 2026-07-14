"use client";

import Link from "next/link";
import { authenticatedHome, useAuth } from "./auth-context";

export function AccessDenied({ description = "Your Atlas role does not include access to this page." }) {
  const { user } = useAuth();
  return (
    <section className="error-panel" role="alert">
      <strong>Access unavailable</strong>
      <p>{description}</p>
      <Link className="button button-secondary" href={authenticatedHome(user)}>Return to Atlas</Link>
    </section>
  );
}
