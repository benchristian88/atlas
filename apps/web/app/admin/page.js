"use client";

import Link from "next/link";
import { visibleAdminSections } from "../../components/admin-sections";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";

export default function AdministrationPage() {
  const { user } = useAuth();
  const sections = visibleAdminSections(user);
  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="Atlas administration"
        description="Manage identities, customer structure, reference data, and platform governance from one place."
      />
      <div className="admin-card-grid">
        {sections.map((section) => (
          <Link className="admin-card" href={section.href} key={section.href}>
            <strong>{section.label}</strong>
            <span>{section.description}</span>
            <span className="card-link">Open section <span aria-hidden="true">→</span></span>
          </Link>
        ))}
      </div>
    </>
  );
}
