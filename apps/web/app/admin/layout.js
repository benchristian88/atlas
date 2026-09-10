"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { useWorkspaceContext } from "../../components/workspace-context";
import { SYSTEM_GROUPS, systemSectionForPath, visibleSystemSections } from "../../lib/system-navigation.mjs";

export default function AdminLayout({ children }) {
  const pathname = usePathname();
  const auth = useAuth();
  const { customerId, siteId } = useWorkspaceContext();
  const sections = visibleSystemSections({ ...auth, customerId, siteId });
  const current = systemSectionForPath(pathname);
  if (!sections.length || (current && !sections.some((section) => section.href === current.href))) return <AccessDenied />;
  const group = SYSTEM_GROUPS.find((item) => item.id === current?.group);
  const grouped = ["organisation", "reference-data"].includes(group?.id);
  return <div className="admin-layout">
    {grouped && <>
      <nav className="admin-tabs" aria-label={`${group.label} sections`}>
        {sections.filter((section) => section.group === group.id).map((section) => (
          <Link aria-current={section.href === current.href ? "page" : undefined}
            className={section.href === current.href ? "active" : ""}
            href={section.href} key={section.href}>{section.label}</Link>
        ))}
      </nav>
    </>}
    {children}
  </div>;
}
