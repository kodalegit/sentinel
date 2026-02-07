/**
 * Card component for dashboard stats.
 * Built on shadcn/ui Card primitive.
 */

import type { ReactNode } from "react";

interface StatCardProps {
  title: string;
  value: string | number;
  icon: ReactNode;
  variant?: "default" | "danger" | "warning" | "success";
  subtitle?: string;
}

const VARIANT_CONFIG = {
  default: {
    border: "border-border/70",
    iconBg: "bg-secondary",
    iconColor: "text-muted-foreground",
    bar: "bg-gradient-to-r from-foreground/20 via-foreground/5 to-transparent",
    glow: "shadow-[0_18px_40px_-32px_rgba(31,75,70,0.45)]",
  },
  danger: {
    border: "border-red-500/25",
    iconBg: "bg-red-500/10",
    iconColor: "text-red-600",
    bar: "bg-gradient-to-r from-red-500/70 via-red-500/20 to-transparent",
    glow: "shadow-[0_20px_36px_-30px_rgba(196,65,47,0.55)]",
  },
  warning: {
    border: "border-amber-500/25",
    iconBg: "bg-amber-500/10",
    iconColor: "text-amber-600",
    bar: "bg-gradient-to-r from-amber-500/70 via-amber-500/25 to-transparent",
    glow: "shadow-[0_18px_36px_-30px_rgba(183,139,67,0.5)]",
  },
  success: {
    border: "border-emerald-500/25",
    iconBg: "bg-emerald-500/10",
    iconColor: "text-emerald-600",
    bar: "bg-gradient-to-r from-emerald-500/70 via-emerald-500/20 to-transparent",
    glow: "shadow-[0_18px_36px_-30px_rgba(31,111,92,0.45)]",
  },
};

export function StatCard({
  title,
  value,
  icon,
  variant = "default",
  subtitle,
}: StatCardProps) {
  const cfg = VARIANT_CONFIG[variant];

  return (
    <div
      className={`
        relative overflow-hidden rounded-2xl border bg-card/90 p-5
        transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg
        ${cfg.border} ${cfg.glow}
      `}
    >
      <span className={`absolute inset-x-0 top-0 h-1 ${cfg.bar}`} />
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-muted-foreground">
            {title}
          </p>
          <p className="mt-3 font-display text-3xl tracking-tight text-foreground">
            {value}
          </p>
        </div>
        <div
          className={`flex h-11 w-11 items-center justify-center rounded-2xl border border-border/60 ${cfg.iconBg}`}
        >
          <span className={cfg.iconColor}>{icon}</span>
        </div>
      </div>
      {subtitle && (
        <p className="mt-3 text-xs text-muted-foreground">{subtitle}</p>
      )}
    </div>
  );
}
