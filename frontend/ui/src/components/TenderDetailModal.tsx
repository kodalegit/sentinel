/**
 * Tender detail modal showing full risk breakdown.
 * Built on shadcn/ui Dialog, Button, Card, Separator primitives.
 */

"use client";

import type { TenderDetail, RiskFactor } from "@/lib/types";
import { formatKES } from "@/lib/api";
import { RiskBadge, StatusBadge } from "@/components/ui/RiskBadge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  AlertTriangle,
  Building2,
  Calendar,
  FileText,
  Network,
  Users,
  ShieldAlert,
  Clock,
  DollarSign,
  UserX,
  Loader2,
  FolderOpen,
} from "lucide-react";

interface TenderDetailModalProps {
  detail: TenderDetail | null;
  loading: boolean;
  isOpen: boolean;
  onClose: () => void;
  onViewGraph: () => void;
  onOpenCase?: (tenderId: string, tenderTitle: string) => void;
}

export function TenderDetailModal({
  detail,
  loading,
  isOpen,
  onClose,
  onViewGraph,
  onOpenCase,
}: TenderDetailModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] p-0">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : detail ? (
          <>
            <DialogHeader className="px-6 pt-6 pb-0">
              <DialogTitle className="text-lg leading-snug">
                {detail.tender.title}
              </DialogTitle>
            </DialogHeader>
            <ScrollArea className="max-h-[calc(90vh-80px)]">
              <TenderDetailContent
                detail={detail}
                onViewGraph={onViewGraph}
                onOpenCase={onOpenCase}
              />
            </ScrollArea>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function TenderDetailContent({
  detail,
  onViewGraph,
  onOpenCase,
}: {
  detail: TenderDetail;
  onViewGraph: () => void;
  onOpenCase?: (tenderId: string, tenderTitle: string) => void;
}) {
  const { tender, risk, bids, winning_company } = detail;

  return (
    <div className="px-6 pb-6 space-y-6">
      {/* Header with risk score */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div
            className={`
              w-16 h-16 rounded-xl flex items-center justify-center text-2xl font-bold
              ${risk.category === "HIGH" ? "bg-red-100 text-red-600" : ""}
              ${risk.category === "MEDIUM" ? "bg-amber-100 text-amber-600" : ""}
              ${risk.category === "LOW" ? "bg-emerald-100 text-emerald-600" : ""}
            `}
          >
            {risk.overall}
          </div>
          <div>
            <div className="text-sm text-muted-foreground">Risk Score</div>
            <RiskBadge category={risk.category} size="lg" />
          </div>
        </div>

        <div className="flex gap-2">
          {onOpenCase && (
            <Button
              variant="outline"
              onClick={() => onOpenCase(tender.id, tender.title)}
            >
              <FolderOpen size={18} />
              Open Case
            </Button>
          )}
          <Button onClick={onViewGraph}>
            <Network size={18} />
            Explore Connections
          </Button>
        </div>
      </div>

      <Separator />

      {/* Tender info grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <InfoItem icon={<FileText size={16} />} label="Reference">
          {tender.reference_number}
        </InfoItem>
        <InfoItem icon={<Building2 size={16} />} label="Procuring Entity">
          {tender.procuring_entity}
        </InfoItem>
        <InfoItem icon={<Calendar size={16} />} label="Deadline">
          {tender.deadline}
        </InfoItem>
        <InfoItem icon={<DollarSign size={16} />} label="Estimated Value">
          {formatKES(tender.estimated_value)}
        </InfoItem>
        {tender.awarded_amount && (
          <InfoItem icon={<DollarSign size={16} />} label="Awarded Amount">
            {formatKES(tender.awarded_amount)}
          </InfoItem>
        )}
        <InfoItem icon={<Users size={16} />} label="Bidders">
          {bids.length} companies
        </InfoItem>
      </div>

      {/* Status */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Status:</span>
        <StatusBadge status={tender.status} />
      </div>

      {/* Winner info */}
      {winning_company && (
        <Card className="bg-muted/50">
          <CardContent className="p-4">
            <h4 className="font-medium mb-2">Awarded To</h4>
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <Building2 className="text-primary" size={20} />
              </div>
              <div>
                <p className="font-semibold">{winning_company.name}</p>
                <p className="text-sm text-muted-foreground">
                  Reg: {winning_company.registration_number}
                </p>
                <p className="text-sm text-muted-foreground">
                  {winning_company.address}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Risk Factors */}
      {risk.factors.length > 0 && (
        <div>
          <h4 className="font-semibold mb-4 flex items-center gap-2">
            <ShieldAlert className="text-red-500" size={20} />
            Why This Tender Is Flagged
          </h4>
          <div className="space-y-3">
            {risk.factors.map((factor, idx) => (
              <RiskFactorCard key={idx} factor={factor} />
            ))}
          </div>
        </div>
      )}

      {/* Recommendation */}
      {risk.recommendation && (
        <Card className="border-amber-200 bg-amber-50/50">
          <CardContent className="p-4">
            <h4 className="font-medium text-amber-800 mb-2 flex items-center gap-2">
              <AlertTriangle size={18} />
              Recommended Actions
            </h4>
            <div className="text-amber-900 text-sm leading-relaxed">
              {risk.recommendation.split(" \u2022 ").map((rec, idx) => (
                <span key={idx} className="block">{"\u2022"} {rec}</span>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function InfoItem({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2">
      <div className="text-muted-foreground mt-0.5">{icon}</div>
      <div>
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-sm font-medium">{children}</div>
      </div>
    </div>
  );
}

function RiskFactorCard({ factor }: { factor: RiskFactor }) {
  const icons = {
    CARTEL_PATTERN: <Users size={20} />,
    SHELL_COMPANY: <Building2 size={20} />,
    CONFLICT_OF_INTEREST: <UserX size={20} />,
    PRICE_ANOMALY: <DollarSign size={20} />,
    RUSHED_TIMELINE: <Clock size={20} />,
  };

  const colors = {
    CARTEL_PATTERN: "bg-purple-50 text-purple-700 border-purple-200",
    SHELL_COMPANY: "bg-orange-50 text-orange-700 border-orange-200",
    CONFLICT_OF_INTEREST: "bg-red-50 text-red-700 border-red-200",
    PRICE_ANOMALY: "bg-amber-50 text-amber-700 border-amber-200",
    RUSHED_TIMELINE: "bg-blue-50 text-blue-700 border-blue-200",
  };

  const labels = {
    CARTEL_PATTERN: "Cartel Pattern",
    SHELL_COMPANY: "Shell Company",
    CONFLICT_OF_INTEREST: "Conflict of Interest",
    PRICE_ANOMALY: "Price Anomaly",
    RUSHED_TIMELINE: "Rushed Timeline",
  };

  return (
    <Card className={`${colors[factor.type]}`}>
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5">{icons[factor.type]}</div>
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1">
              <span className="font-semibold">{labels[factor.type]}</span>
              <span className="text-sm font-bold">{factor.weight} pts</span>
            </div>
            <p className="text-sm opacity-90 mb-2">{factor.description}</p>
            {factor.evidence.length > 0 && (
              <div className="text-xs opacity-75 space-y-0.5">
                {factor.evidence.filter(e => e).map((ev, idx) => (
                  <p key={idx}>{"\u2022"} {ev}</p>
                ))}
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
