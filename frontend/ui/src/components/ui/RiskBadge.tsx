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

const RISK_CONFIG = {
  HIGH: {
    dot: "bg-[#c4412f]",
    text: "text-[#c4412f]",
    bg: "bg-[#c4412f]/10",
    border: "border-[#c4412f]/20",
  },
  MEDIUM: {
    dot: "bg-[#b78b43]",
    text: "text-[#b78b43]",
    bg: "bg-[#b78b43]/10",
    border: "border-[#b78b43]/20",
  },
  LOW: {
    dot: "bg-[#1f6f5c]",
    text: "text-[#1f6f5c]",
    bg: "bg-[#1f6f5c]/10",
    border: "border-[#1f6f5c]/20",
  },
};

export function RiskBadge({
  category,
  score,
  size = "md",
  pulse = false,
}: RiskBadgeProps) {
  const cfg = RISK_CONFIG[category];

  const sizes = {
    sm: "text-[11px] px-2 py-0.5 gap-1.5",
    md: "text-[11px] px-3 py-1 gap-1.5",
    lg: "text-sm px-3.5 py-1.5 gap-2",
  };

  return (
    <span
      className={`
        inline-flex items-center font-medium rounded-full border
        ${cfg.bg} ${cfg.border} ${cfg.text} ${sizes[size]}
        ${pulse && category === "HIGH" ? "animate-pulse-glow" : ""}
      `}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
      <span className="uppercase tracking-wider">{category}</span>
      {score !== undefined && (
        <span className="font-bold tabular-nums">{score}</span>
      )}
    </span>
  );
}

interface StatusBadgeProps {
  status: TenderStatus;
}

const STATUS_CONFIG = {
  OPEN: {
    text: "text-[#35638c]",
    bg: "bg-[#35638c]/10",
    border: "border-[#35638c]/20",
  },
  EVALUATION: {
    text: "text-[#7c5d3b]",
    bg: "bg-[#7c5d3b]/10",
    border: "border-[#7c5d3b]/20",
  },
  AWARDED: {
    text: "text-[#1f4b46]",
    bg: "bg-[#1f4b46]/10",
    border: "border-[#1f4b46]/20",
  },
  CANCELLED: {
    text: "text-[#8a8580]",
    bg: "bg-[#8a8580]/10",
    border: "border-[#8a8580]/20",
  },
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const cfg = STATUS_CONFIG[status];

  return (
    <span
      className={`
        inline-flex items-center text-[11px] px-2.5 py-0.5 font-medium
        uppercase tracking-[0.15em] rounded-full border
        ${cfg.text} ${cfg.bg} ${cfg.border}
      `}
    >
      {status}
    </span>
  );
}
