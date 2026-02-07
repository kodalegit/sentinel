/**
 * Tender card component for the dashboard list.
 * Built on shadcn/ui Card primitive.
 */

"use client";

import type { TenderWithRisk } from "@/lib/types";
import { formatKES } from "@/lib/api";
import { RiskBadge, StatusBadge } from "@/components/ui/RiskBadge";
import { Building2, Calendar, Users, ChevronRight } from "lucide-react";

interface TenderCardProps {
  tender: TenderWithRisk;
  onClick: () => void;
}

const RISK_ACCENT = {
  HIGH: "from-[#c4412f] via-[#c4412f]/70 to-transparent",
  MEDIUM: "from-[#b78b43] via-[#b78b43]/70 to-transparent",
  LOW: "from-[#1f6f5c] via-[#1f6f5c]/70 to-transparent",
};

export function TenderCard({ tender, onClick }: TenderCardProps) {
  const { tender: t, risk, bidder_count } = tender;

  return (
    <div
      onClick={onClick}
      className={`
        group relative cursor-pointer overflow-hidden rounded-2xl border border-border/70
        bg-card/95 p-6 transition-all duration-200
        shadow-[0_18px_40px_-36px_rgba(31,75,70,0.3)]
        hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-[0_22px_50px_-36px_rgba(31,75,70,0.4)]
      `}
    >
      <span
        className={`absolute inset-y-0 left-0 w-1.5 bg-linear-to-b ${
          RISK_ACCENT[risk.category]
        }`}
      />
      {/* Top row: status + ref + risk badge */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <StatusBadge status={t.status} />
            <span className="text-[11px] text-muted-foreground font-mono">
              {t.reference_number}
            </span>
          </div>
          <h3 className="font-semibold leading-snug text-foreground/90 group-hover:text-primary transition-colors line-clamp-2">
            {t.title}
          </h3>
        </div>
        <RiskBadge
          category={risk.category}
          score={risk.overall}
          pulse={risk.category === "HIGH"}
        />
      </div>

      {/* Meta row */}
      <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <Building2 size={12} />
          {t.procuring_entity}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Calendar size={12} />
          {t.deadline}
        </span>
        {bidder_count > 0 && (
          <span className="inline-flex items-center gap-1.5">
            <Users size={12} />
            {bidder_count} bidders
          </span>
        )}
      </div>

      {/* Bottom row: value + top factor + arrow */}
      <div className="mt-5 flex items-end justify-between border-t border-border/40 pt-4">
        <div>
          <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
            Contract Value
          </span>
          <p className="font-display text-lg text-foreground/90">
            {formatKES(t.awarded_amount || t.estimated_value)}
          </p>
        </div>

        {risk.factors.length > 0 && (
          <div className="text-right max-w-[55%]">
            <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Top Risk
            </span>
            <p className="text-xs text-foreground/70 line-clamp-1">
              {risk.factors[0].description}
            </p>
          </div>
        )}

        <ChevronRight
          size={16}
          className="text-muted-foreground/40 group-hover:text-primary transition-colors shrink-0 ml-2"
        />
      </div>
    </div>
  );
}
