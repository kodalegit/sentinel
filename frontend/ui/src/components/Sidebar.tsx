/**
 * Slim sidebar navigation — persistent across all pages.
 */

"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Shield,
  LayoutDashboard,
  Network,
  FolderOpen,
  Database,
  Sun,
  Moon,
  LogOut,
  Users,
  ChevronDown,
  Bell,
  BookOpen,
  Settings,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { getNotificationCount, getNotifications, markNotificationRead } from "@/lib/api";
import type { CaseNotification } from "@/lib/types";

const NAV_ITEMS = [
  { href: "/", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/graph", icon: Network, label: "Graph" },
  { href: "/cases", icon: FolderOpen, label: "Cases" },
  { href: "/sources", icon: Database, label: "Data Sources" },
];

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  supervisor: "Supervisor",
  auditor: "Auditor",
};

export function Sidebar() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const { user, logout, isAdmin } = useAuth();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDarkTheme = mounted && theme === "dark";

  // M3: Notification queries
  const { data: notificationCount } = useQuery({
    queryKey: ["notification-count"],
    queryFn: getNotificationCount,
    enabled: !!user,
    refetchInterval: 30000, // Poll every 30 seconds
  });

  const { data: notifications = [], refetch: refetchNotifications } = useQuery<CaseNotification[]>({
    queryKey: ["notifications"],
    queryFn: () => getNotifications(false),
    enabled: !!user && notificationsOpen,
  });

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const handleNotificationClick = async (notification: CaseNotification) => {
    if (!notification.is_read) {
      await markNotificationRead(notification.id);
      refetchNotifications();
    }
    setNotificationsOpen(false);
    router.push(`/cases/${notification.case_id}`);
  };

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

      <div className="px-4 pb-6 space-y-2">
        {/* M3: Notifications bell */}
        {user && (
          <div className="relative">
            <button
              onClick={() => setNotificationsOpen((v) => !v)}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground transition-all duration-200"
            >
              <span className="relative flex h-8 w-8 items-center justify-center rounded-lg">
                <Bell size={18} strokeWidth={1.5} />
                {notificationCount && notificationCount.unread_count > 0 && (
                  <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-[#c4412f] text-[10px] font-bold text-white">
                    {notificationCount.unread_count > 9 ? "9+" : notificationCount.unread_count}
                  </span>
                )}
              </span>
              <span>Notifications</span>
            </button>

            {notificationsOpen && (
              <div className="absolute bottom-full left-0 right-0 mb-1 max-h-80 overflow-y-auto rounded-xl border border-sidebar-border/70 bg-sidebar shadow-lg">
                {notifications.length === 0 ? (
                  <div className="px-4 py-6 text-center text-xs text-sidebar-foreground/50">
                    No notifications
                  </div>
                ) : (
                  <div className="py-1">
                    {notifications.slice(0, 10).map((n) => (
                      <button
                        key={n.id}
                        onClick={() => handleNotificationClick(n)}
                        className={`w-full px-4 py-3 text-left hover:bg-sidebar-accent/70 transition-colors ${
                          n.is_read ? "opacity-60" : ""
                        }`}
                      >
                        <p className="text-xs text-sidebar-foreground line-clamp-2">{n.message}</p>
                        <p className="text-[10px] text-sidebar-foreground/50 mt-1">
                          {new Date(n.created_at).toLocaleString()}
                        </p>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Admin links */}
        {isAdmin && (
          <>
            <Link
              href="/admin/users"
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200 ${
                pathname.startsWith("/admin/users")
                  ? "bg-sidebar-accent text-sidebar-foreground"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground"
              }`}
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg">
                <Users size={18} strokeWidth={1.5} />
              </span>
              <span>User Management</span>
            </Link>
            <Link
              href="/admin/knowledge"
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200 ${
                pathname.startsWith("/admin/knowledge")
                  ? "bg-sidebar-accent text-sidebar-foreground"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground"
              }`}
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg">
                <BookOpen size={18} strokeWidth={1.5} />
              </span>
              <span>Knowledge Base</span>
            </Link>
            <Link
              href="/admin/settings"
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200 ${
                pathname.startsWith("/admin/settings")
                  ? "bg-sidebar-accent text-sidebar-foreground"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground"
              }`}
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg">
                <Settings size={18} strokeWidth={1.5} />
              </span>
              <span>Agent Settings</span>
            </Link>
          </>
        )}

        {/* Theme toggle */}
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground transition-all duration-200"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-lg">
            {isDarkTheme ? <Sun size={18} strokeWidth={1.5} /> : <Moon size={18} strokeWidth={1.5} />}
          </span>
          <span>{isDarkTheme ? "Light Mode" : "Dark Mode"}</span>
        </button>

        {/* User info + logout */}
        {user ? (
          <div className="relative">
            <button
              onClick={() => setUserMenuOpen((v) => !v)}
              className="flex w-full items-center gap-3 rounded-xl border border-sidebar-border/70 bg-sidebar-accent/40 px-3 py-2.5 text-left transition-all hover:bg-sidebar-accent/70"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sidebar-primary/20 text-sidebar-primary text-xs font-semibold uppercase">
                {user.full_name.charAt(0)}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-sidebar-foreground truncate">{user.full_name}</p>
                <p className="text-[11px] text-sidebar-foreground/50">{ROLE_LABELS[user.role] ?? user.role}</p>
              </div>
              <ChevronDown size={14} className={`text-sidebar-foreground/40 transition-transform ${userMenuOpen ? "rotate-180" : ""}`} />
            </button>

            {userMenuOpen && (
              <div className="absolute bottom-full left-0 right-0 mb-1 rounded-xl border border-sidebar-border/70 bg-sidebar shadow-lg overflow-hidden">
                <button
                  onClick={handleLogout}
                  className="flex w-full items-center gap-3 px-4 py-3 text-sm text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground transition-colors"
                >
                  <LogOut size={15} />
                  <span>Sign out</span>
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-xl border border-sidebar-border/70 bg-sidebar-accent/40 px-4 py-3 text-[11px] text-sidebar-foreground/70">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <span className="uppercase tracking-wider">Monitoring Active</span>
            </div>
            <p className="mt-1 text-sidebar-foreground/50">v2.0 Intelligence Suite</p>
          </div>
        )}
      </div>
    </aside>
  );
}
