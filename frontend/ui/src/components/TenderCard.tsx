/**
 * Tender card component for the dashboard list.
 * Built on shadcn/ui Card primitive.
 */

"use client";

import type { TenderWithRisk } from "@/lib/types";
import { formatKES } from "@/lib/api";
import { RiskBadge, StatusBadge } from "@/components/ui/RiskBadge";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
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
    <Card
      onClick={onClick}
      className={`
        border-l-4 cursor-pointer group
        hover:shadow-md transition-all duration-200
        ${borderColors[risk.category]}
      `}
    >
      <CardContent className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <StatusBadge status={t.status} />
              <span className="text-xs text-muted-foreground">{t.reference_number}</span>
            </div>
            <h3 className="font-semibold group-hover:text-primary transition-colors line-clamp-2">
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
        <div className="mt-4 flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <Building2 size={14} />
            <span>{t.procuring_entity}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Calendar size={14} />
            <span>{t.deadline}</span>
          </div>
          {bidder_count > 0 && (
            <div className="flex items-center gap-1.5">
              <Users size={14} />
              <span>{bidder_count} bidders</span>
            </div>
          )}
        </div>

        <Separator className="my-4" />

        {/* Value and top risk factor */}
        <div className="flex items-end justify-between">
          <div>
            <span className="text-xs text-muted-foreground">Contract Value</span>
            <p className="font-bold text-lg">
              {formatKES(t.awarded_amount || t.estimated_value)}
            </p>
          </div>

          {risk.factors.length > 0 && (
            <div className="text-right max-w-[60%]">
              <span className="text-xs text-muted-foreground">Top Risk Factor</span>
              <p className="text-sm line-clamp-1">
                {risk.factors[0].description}
              </p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
