"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/customers", label: "Customers" },
  { href: "/sites", label: "Sites" },
  { href: "/assets", label: "Assets" },
  { href: "/topology", label: "Topology" },
  { href: "/integrations", label: "Integrations" },
  { href: "/discovery-runs", label: "Discovery runs" },
];

export function Navigation() {
  const pathname = usePathname();

  return (
    <nav className="nav-list" aria-label="Primary navigation">
      {items.map((item) => {
        const active = pathname.startsWith(item.href);
        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={`nav-link${active ? " active" : ""}`}
            href={item.href}
            key={item.href}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
