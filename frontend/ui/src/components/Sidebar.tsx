/**
 * Slim sidebar navigation — persistent across all pages.
 */

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Shield,
  LayoutDashboard,
  Network,
  FolderOpen,
  Sun,
  Moon,
} from "lucide-react";
import { useTheme } from "next-themes";

const NAV_ITEMS = [
  { href: "/", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/graph", icon: Network, label: "Graph" },
  { href: "/cases", icon: FolderOpen, label: "Cases" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();

  return (
    <aside className="fixed left-0 top-0 z-50 flex h-screen w-[240px] flex-col border-r border-sidebar-border/80 bg-sidebar text-sidebar-foreground">
      {/* Brand */}
      <div className="px-6 pt-6">
        <Link href="/" className="flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-sidebar-primary/30 bg-sidebar-primary/10 text-sidebar-primary">
            <Shield size={20} />
          </span>
          <div>
            <p className="text-sm font-semibold tracking-wide">Sentinel</p>
            <p className="text-[11px] text-sidebar-foreground/60">
              Procurement Intelligence
            </p>
          </div>
        </Link>
      </div>

      <div className="px-4 mt-10 flex-1">
        <p className="px-2 text-[11px] uppercase tracking-[0.15em] text-sidebar-foreground/40">
          Navigation
        </p>
        <nav className="mt-3 space-y-1">
          {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
            const isActive =
              href === "/" ? pathname === "/" : pathname.startsWith(href);

            return (
              <Link
                key={href}
                href={href}
                className={`
                  group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium
                  transition-all duration-200
                  ${
                    isActive
                      ? "bg-sidebar-accent text-sidebar-foreground shadow-[inset_0_0_0_1px_rgba(183,139,67,0.35)]"
                      : "text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground"
                  }
                `}
              >
                <span
                  className={`flex h-8 w-8 items-center justify-center rounded-lg border border-transparent ${
                    isActive
                      ? "bg-sidebar-primary/20 text-sidebar-primary"
                      : "bg-transparent text-sidebar-foreground/70 group-hover:text-sidebar-foreground"
                  }`}
                >
                  <Icon size={18} strokeWidth={isActive ? 2 : 1.5} />
                </span>
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="px-6 pb-6 space-y-3">
        {/* Theme toggle */}
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground transition-all duration-200"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-lg">
            {theme === "dark" ? <Sun size={18} strokeWidth={1.5} /> : <Moon size={18} strokeWidth={1.5} />}
          </span>
          <span>{theme === "dark" ? "Light Mode" : "Dark Mode"}</span>
        </button>

        <div className="rounded-xl border border-sidebar-border/70 bg-sidebar-accent/40 px-4 py-3 text-[11px] text-sidebar-foreground/70">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            <span className="uppercase tracking-wider">Monitoring Active</span>
          </div>
          <p className="mt-1 text-sidebar-foreground/50">v2.0 Intelligence Suite</p>
        </div>
      </div>
    </aside>
  );
}
