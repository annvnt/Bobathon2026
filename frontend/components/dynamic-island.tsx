"use client";

import clsx from "clsx";
import { BarChart3, Bell, LayoutDashboard, Package, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/products", label: "Products", icon: Package },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

/**
 * Floating "dynamic island" navigation. Collapsed it shows icons with only the
 * active section labelled; hovering the island morphs it open to reveal every
 * label with a smooth width animation.
 */
export function DynamicIsland() {
  const pathname = usePathname();
  return (
      <nav className="group flex items-center gap-1 rounded-full border border-border bg-elevated/80 p-1.5 shadow-lg shadow-black/20 backdrop-blur-xl">
        <Link
          href="/dashboard"
          className="ml-1 mr-0.5 flex items-center gap-2"
          aria-label="EcoComply"
        >
          <span className="h-6 w-6 rounded-full bg-accent" />
        </Link>

        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center rounded-full px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-accent text-accent-fg"
                  : "text-muted hover:bg-surface hover:text-fg",
              )}
            >
              <Icon size={17} className="shrink-0" />
              <span
                className={clsx(
                  "overflow-hidden whitespace-nowrap font-medium transition-all duration-300 ease-out",
                  active
                    ? "ml-2 max-w-[120px] opacity-100"
                    : "ml-0 max-w-0 opacity-0 group-hover:ml-2 group-hover:max-w-[120px] group-hover:opacity-100",
                )}
              >
                {label}
              </span>
            </Link>
          );
        })}
      </nav>
  );
}
