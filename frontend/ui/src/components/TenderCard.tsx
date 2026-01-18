/**
 * Tender card component for the dashboard list.
 */

"use client";

import type { TenderWithRisk } from "@/lib/types";
import { formatKES } from "@/lib/api";
import { RiskBadge, StatusBadge } from "@/components/ui/Badge";
import { Building2, Calendar, Users } from "lucide-react";

interface TenderCardProps {
  tender: TenderWithRisk;
  onClick: () => void;
}

export function TenderCard({ tender, onClick }: TenderCardProps) {
  const { tender: t, risk, bidder_count } = tender;

  const borderColors = {
    HIGH: "border-l-red-500",
    MEDIUM: "border-l-amber-500",
    LOW: "border-l-emerald-500",
  };

  return (
    <div
      onClick={onClick}
      className={`
        bg-white rounded-xl border border-slate-200 border-l-4 p-5
        hover:shadow-lg hover:border-slate-300 transition-all duration-200
        cursor-pointer group
        ${borderColors[risk.category]}
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <StatusBadge status={t.status} />
            <span className="text-xs text-slate-400">{t.reference_number}</span>
          </div>
          <h3 className="font-semibold text-slate-900 group-hover:text-blue-600 transition-colors line-clamp-2">
            {t.title}
          </h3>
        </div>
        <RiskBadge
          category={risk.category}
          score={risk.overall}
          pulse={risk.category === "HIGH"}
        />
      </div>

      {/* Meta info */}
      <div className="mt-4 flex flex-wrap items-center gap-4 text-sm text-slate-600">
        <div className="flex items-center gap-1.5">
          <Building2 size={14} className="text-slate-400" />
          <span>{t.procuring_entity}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Calendar size={14} className="text-slate-400" />
          <span>{t.deadline}</span>
        </div>
        {bidder_count > 0 && (
          <div className="flex items-center gap-1.5">
            <Users size={14} className="text-slate-400" />
            <span>{bidder_count} bidders</span>
          </div>
        )}
      </div>

      {/* Value and top risk factor */}
      <div className="mt-4 pt-4 border-t border-slate-100 flex items-end justify-between">
        <div>
          <span className="text-xs text-slate-500">Contract Value</span>
          <p className="font-bold text-lg text-slate-900">
            {formatKES(t.awarded_amount || t.estimated_value)}
          </p>
        </div>

        {risk.factors.length > 0 && (
          <div className="text-right max-w-[60%]">
            <span className="text-xs text-slate-500">Top Risk Factor</span>
            <p className="text-sm text-slate-700 line-clamp-1">
              {risk.factors[0].description}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
