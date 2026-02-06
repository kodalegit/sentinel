/**
 * Badge component for risk levels and statuses.
 */

import type { RiskCategory, TenderStatus } from "@/lib/types";

interface RiskBadgeProps {
  category: RiskCategory;
  score?: number;
  size?: "sm" | "md" | "lg";
  pulse?: boolean;
}

export function RiskBadge({
  category,
  score,
  size = "md",
  pulse = false,
}: RiskBadgeProps) {
  const colors = {
    HIGH: "bg-red-100 text-red-700 border-red-300",
    MEDIUM: "bg-amber-100 text-amber-700 border-amber-300",
    LOW: "bg-emerald-100 text-emerald-700 border-emerald-300",
  };

  const sizes = {
    sm: "text-xs px-2 py-0.5",
    md: "text-sm px-2.5 py-1",
    lg: "text-base px-3 py-1.5",
  };

  const icons = {
    HIGH: "🔴",
    MEDIUM: "🟡",
    LOW: "🟢",
  };

  return (
    <span
      className={`
        inline-flex items-center gap-1.5 font-medium rounded-full border
        ${colors[category]} ${sizes[size]}
        ${pulse && category === "HIGH" ? "animate-pulse" : ""}
      `}
    >
      <span>{icons[category]}</span>
      <span>{category}</span>
      {score !== undefined && (
        <span className="font-bold">{score}</span>
      )}
    </span>
  );
}

interface StatusBadgeProps {
  status: TenderStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const colors = {
    OPEN: "bg-blue-100 text-blue-700",
    EVALUATION: "bg-purple-100 text-purple-700",
    AWARDED: "bg-slate-100 text-slate-700",
    CANCELLED: "bg-gray-100 text-gray-500",
  };

  return (
    <span
      className={`
        inline-flex items-center text-xs px-2 py-0.5 font-medium rounded
        ${colors[status]}
      `}
    >
      {status}
    </span>
  );
}
