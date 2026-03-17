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
  Menu,
  X,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { VisuallyHidden } from "radix-ui";
import { useAuth } from "@/lib/auth";
import { getNotificationCount } from "@/lib/api";
import { NotificationsPanel } from "@/components/NotificationsPanel";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/graph", icon: Network, label: "Graph" },
  { href: "/cases", icon: FolderOpen, label: "Cases" },
  { href: "/sources", icon: Database, label: "Data Sources" },
];

const ADMIN_ITEMS = [
  { href: "/admin/users", icon: Users, label: "User Management" },
  { href: "/admin/knowledge", icon: BookOpen, label: "Knowledge Base" },
  { href: "/admin/settings", icon: Settings, label: "Agent Settings" },
];

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  supervisor: "Supervisor",
  auditor: "Auditor",
};

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  // Initialize as true to avoid hydration mismatch; next-themes handles SSR safely
  const isDarkTheme = theme === "dark";
  const isAdmin = user?.role === "admin";
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);


  // M3: Notification queries
  const { data: notificationCount } = useQuery({
    queryKey: ["notification-count"],
    queryFn: getNotificationCount,
    enabled: !!user,
    refetchInterval: 30000, // Poll every 30 seconds
  });

  const handleLogout = () => {
    setUserMenuOpen(false);
    setMobileNavOpen(false);
    logout();
    router.push("/login");
  };

  const notificationBadge = notificationCount?.unread_count ?? 0;

  const renderNavLink = (
    href: string,
    label: string,
    Icon: typeof LayoutDashboard,
    onNavigate?: () => void,
  ) => {
    const isActive =
      href === "/" ? pathname === "/" : pathname.startsWith(href);

    return (
      <Link
        key={href}
        href={href}
        onClick={onNavigate}
        className={cn(
          "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200",
          isActive
            ? "bg-sidebar-accent text-sidebar-foreground shadow-[inset_0_0_0_1px_rgba(183,139,67,0.35)]"
            : "text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground",
        )}
      >
        <span
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-lg border border-transparent",
            isActive
              ? "bg-sidebar-primary/20 text-sidebar-primary"
              : "bg-transparent text-sidebar-foreground/70 group-hover:text-sidebar-foreground",
          )}
        >
          <Icon size={18} strokeWidth={isActive ? 2 : 1.5} />
        </span>
        <span>{label}</span>
      </Link>
    );
  };

  return (
    <>
      <div className="fixed inset-x-0 top-0 z-40 flex h-16 items-center justify-between border-b border-border/70 bg-background/90 px-4 backdrop-blur lg:hidden">
        <div className="flex items-center gap-3">
          <Dialog open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
            <DialogTrigger asChild>
              <Button type="button" variant="outline" size="icon">
                <Menu className="h-5 w-5" />
              </Button>
            </DialogTrigger>
            <DialogContent
              className="left-0 top-0 h-screen w-[88vw] max-w-[320px] translate-x-0 translate-y-0 gap-0 rounded-none border-r border-border/80 p-0"
              showCloseButton={false}
            >
              <VisuallyHidden.Root>
                <DialogTitle>Mobile navigation menu</DialogTitle>
                <DialogDescription>
                  Navigate between Sentinel pages and access account actions.
                </DialogDescription>
              </VisuallyHidden.Root>
              <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
                {/* Brand */}
                <div className="border-b border-sidebar-border/70 px-5 py-5">
                  <div className="flex items-center justify-between gap-4">
                    <Link
                      href="/"
                      onClick={() => setMobileNavOpen(false)}
                      className="flex items-center gap-3"
                    >
                      <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-sidebar-primary/30 bg-sidebar-primary/10 text-sidebar-primary">
                        <Shield size={20} />
                      </span>
                      <div>
                        <p className="text-sm font-semibold tracking-wide">
                          Sentinel
                        </p>
                        <p className="text-[11px] text-sidebar-foreground/60">
                          Procurement Intelligence
                        </p>
                      </div>
                    </Link>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground"
                      onClick={() => setMobileNavOpen(false)}
                    >
                      <X className="h-5 w-5" />
                    </Button>
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto px-4 py-6">
                  <p className="px-2 text-[11px] uppercase tracking-[0.15em] text-sidebar-foreground/40">
                    Navigation
                  </p>
                  <nav className="mt-3 space-y-1">
                    {NAV_ITEMS.map(({ href, icon: Icon, label }) =>
                      renderNavLink(href, label, Icon, () =>
                        setMobileNavOpen(false),
                      ),
                    )}
                  </nav>

                  {isAdmin && (
                    <div className="mt-8 space-y-3">
                      {/* Admin links */}
                      <p className="px-2 text-[11px] uppercase tracking-[0.15em] text-sidebar-foreground/40">
                        Administration
                      </p>
                      <div className="space-y-1">
                        {ADMIN_ITEMS.map(({ href, icon: Icon, label }) =>
                          renderNavLink(href, label, Icon, () =>
                            setMobileNavOpen(false),
                          ),
                        )}
                      </div>
                    </div>
                  )}
                </div>

                <div className="space-y-2 border-t border-sidebar-border/70 px-4 py-4">
                  {/* Theme toggle */}
                  <button
                    onClick={() =>
                      setTheme(theme === "dark" ? "light" : "dark")
                    }
                    className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-sidebar-foreground/70 transition-all duration-200 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground"
                  >
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg">
                      {isDarkTheme ? (
                        <Sun size={18} strokeWidth={1.5} />
                      ) : (
                        <Moon size={18} strokeWidth={1.5} />
                      )}
                    </span>
                    <span>{isDarkTheme ? "Light Mode" : "Dark Mode"}</span>
                  </button>

                  {/* User info + logout */}
                  {user ? (
                    <div className="rounded-2xl border border-sidebar-border/70 bg-sidebar-accent/40 px-4 py-4">
                      <div className="flex items-center gap-3">
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sidebar-primary/20 text-sidebar-primary text-xs font-semibold uppercase">
                          {user.full_name.charAt(0)}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-sidebar-foreground">
                            {user.full_name}
                          </p>
                          <p className="text-[11px] text-sidebar-foreground/50">
                            {ROLE_LABELS[user.role] ?? user.role}
                          </p>
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        className="mt-4 w-full justify-start border-sidebar-border/70 bg-transparent text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground"
                        onClick={handleLogout}
                      >
                        <LogOut className="h-4 w-4" />
                        Sign out
                      </Button>
                    </div>
                  ) : (
                    <div className="rounded-xl border border-sidebar-border/70 bg-sidebar-accent/40 px-4 py-3 text-[11px] text-sidebar-foreground/70">
                      <div className="flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full bg-emerald-400" />
                        <span className="uppercase tracking-wider">
                          Monitoring Active
                        </span>
                      </div>
                      <p className="mt-1 text-sidebar-foreground/50">
                        v2.0 Intelligence Suite
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </DialogContent>
          </Dialog>

          <Link href="/" className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-primary">
              <Shield size={18} />
            </span>
            <div>
              <p className="text-sm font-semibold tracking-wide text-foreground">
                Sentinel
              </p>
              <p className="text-[11px] text-muted-foreground">
                Procurement Intelligence
              </p>
            </div>
          </Link>
        </div>

        {user && (
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="relative"
            onClick={() => setNotificationsOpen(true)}
          >
            <Bell className="h-5 w-5" />
            {notificationBadge > 0 && (
              <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#c4412f] px-1 text-[10px] font-bold text-white">
                {notificationBadge > 9 ? "9+" : notificationBadge}
              </span>
            )}
          </Button>
        )}
      </div>

      <aside className="fixed left-0 top-0 z-30 hidden h-screen w-[240px] flex-col border-r border-sidebar-border/80 bg-sidebar text-sidebar-foreground lg:flex">
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

        <div className="mt-10 flex-1 px-4">
          <p className="px-2 text-[11px] uppercase tracking-[0.15em] text-sidebar-foreground/40">
            Navigation
          </p>
          <nav className="mt-3 space-y-1">
            {NAV_ITEMS.map(({ href, icon: Icon, label }) =>
              renderNavLink(href, label, Icon),
            )}
          </nav>
        </div>

        <div className="space-y-2 px-4 pb-6">
          {/* M3: Notifications bell */}
          {user && (
            <button
              onClick={() => setNotificationsOpen(true)}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-sidebar-foreground/70 transition-all duration-200 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground"
            >
              <span className="relative flex h-8 w-8 items-center justify-center rounded-lg">
                <Bell size={18} strokeWidth={1.5} />
                {notificationBadge > 0 && (
                  <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#c4412f] px-1 text-[10px] font-bold text-white">
                    {notificationBadge > 9 ? "9+" : notificationBadge}
                  </span>
                )}
              </span>
              <span>Notifications</span>
            </button>
          )}

          {/* Admin links */}
          {isAdmin &&
            ADMIN_ITEMS.map(({ href, icon: Icon, label }) =>
              renderNavLink(href, label, Icon),
            )}

          {/* Theme toggle */}
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-sidebar-foreground/70 transition-all duration-200 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-lg">
              {isDarkTheme ? (
                <Sun size={18} strokeWidth={1.5} />
              ) : (
                <Moon size={18} strokeWidth={1.5} />
              )}
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
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-sidebar-foreground">
                    {user.full_name}
                  </p>
                  <p className="text-[11px] text-sidebar-foreground/50">
                    {ROLE_LABELS[user.role] ?? user.role}
                  </p>
                </div>
                <ChevronDown
                  size={14}
                  className={`text-sidebar-foreground/40 transition-transform ${userMenuOpen ? "rotate-180" : ""}`}
                />
              </button>

              {userMenuOpen && (
                <div className="absolute bottom-full left-0 right-0 mb-1 overflow-hidden rounded-xl border border-sidebar-border/70 bg-sidebar shadow-lg">
                  <button
                    onClick={handleLogout}
                    className="flex w-full items-center gap-3 px-4 py-3 text-sm text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent/70 hover:text-sidebar-foreground"
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
                <span className="uppercase tracking-wider">
                  Monitoring Active
                </span>
              </div>
              <p className="mt-1 text-sidebar-foreground/50">
                v2.0 Intelligence Suite
              </p>
            </div>
          )}
        </div>
      </aside>

      <NotificationsPanel
        open={notificationsOpen}
        onOpenChange={setNotificationsOpen}
      />
    </>
  );
}
