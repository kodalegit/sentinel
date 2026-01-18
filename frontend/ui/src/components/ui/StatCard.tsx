/**
 * Card component for dashboard stats.
 */

import type { ReactNode } from "react";

interface StatCardProps {
  title: string;
  value: string | number;
  icon: ReactNode;
  variant?: "default" | "danger" | "warning" | "success";
  subtitle?: string;
}

export function StatCard({
  title,
  value,
  icon,
  variant = "default",
  subtitle,
}: StatCardProps) {
  const variants = {
    default: "bg-white border-slate-200",
    danger: "bg-red-50 border-red-200",
    warning: "bg-amber-50 border-amber-200",
    success: "bg-emerald-50 border-emerald-200",
  };

  const iconColors = {
    default: "text-slate-600",
    danger: "text-red-600",
    warning: "text-amber-600",
    success: "text-emerald-600",
  };

  return (
    <div
      className={`
        rounded-xl border p-5 shadow-sm
        ${variants[variant]}
      `}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500">{title}</p>
          <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
          {subtitle && (
            <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
          )}
        </div>
        <div className={`text-2xl ${iconColors[variant]}`}>{icon}</div>
      </div>
    </div>
  );
}
