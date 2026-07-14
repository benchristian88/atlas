"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { visibleAdminSections } from "../../components/admin-sections";
import { useAuth } from "../../components/auth-context";

export default function AdminLayout({ children }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const sections = visibleAdminSections(user);
  if (!sections.length) return <AccessDenied />;

  return (
    <div className="admin-layout">
      <nav className="admin-tabs" aria-label="Administration sections">
        <Link
          aria-current={pathname === "/admin" ? "page" : undefined}
          className={pathname === "/admin" ? "active" : ""}
          href="/admin"
        >
          Overview
        </Link>
        {sections.map((section) => {
          const active = pathname === section.href || pathname.startsWith(`${section.href}/`);
          return (
            <Link
              aria-current={active ? "page" : undefined}
              className={active ? "active" : ""}
              href={section.href}
              key={section.href}
            >
              {section.label}
            </Link>
          );
        })}
      </nav>
      {children}
    </div>
  );
}
