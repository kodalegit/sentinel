/**
 * Tender detail modal showing full risk breakdown.
 * Built on shadcn/ui Dialog, Button, Card, Separator primitives.
 */

"use client";

import type { TenderDetail, RiskFactor, RiskFactorType } from "@/lib/types";
import { formatKES } from "@/lib/api";
import { RiskBadge, StatusBadge } from "@/components/ui/RiskBadge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { VisuallyHidden } from "radix-ui";
import { Button } from "@/components/ui/button";
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
  Tag,
  Mail,
  MapPin,
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
      <DialogContent className="max-w-4xl max-h-[90vh] p-0 bg-card/95 border border-border/70">
        {loading ? (
          <>
            <VisuallyHidden.Root>
              <DialogTitle>Loading tender details</DialogTitle>
            </VisuallyHidden.Root>
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
          </>
        ) : detail ? (
          <>
            <DialogHeader className="px-6 pt-6 pb-0">
              <DialogTitle className="font-display text-xl leading-snug">
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
        ) : (
          <VisuallyHidden.Root>
            <DialogTitle>Tender details</DialogTitle>
          </VisuallyHidden.Root>
        )}
      </DialogContent>
    </Dialog>
  );
}

const RISK_SCORE_COLORS = {
  HIGH: "border-[#c4412f]/30 text-[#c4412f] bg-[#c4412f]/10",
  MEDIUM: "border-[#b78b43]/30 text-[#b78b43] bg-[#b78b43]/10",
  LOW: "border-[#1f6f5c]/30 text-[#1f6f5c] bg-[#1f6f5c]/10",
};

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
      {/* Risk score + actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div
            className={`
              w-16 h-16 rounded-2xl border-2 flex items-center justify-center
              font-display text-2xl font-bold
              ${RISK_SCORE_COLORS[risk.category]}
            `}
          >
            {risk.overall}
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
              Risk Score
            </div>
            <RiskBadge category={risk.category} size="lg" />
          </div>
        </div>

        <div className="flex gap-2">
          {onOpenCase && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onOpenCase(tender.id, tender.title)}
              className="text-xs"
            >
              <FolderOpen size={14} />
              Open Investigation Case
            </Button>
          )}
          <Button
            size="sm"
            onClick={onViewGraph}
            className="text-xs bg-primary text-primary-foreground hover:bg-primary/90"
          >
            <Network size={14} />
            Explore Connections
          </Button>
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-border/50" />

      {/* Info grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <InfoItem icon={<FileText size={14} />} label="Reference">
          <span className="font-mono text-xs">{tender.reference_number}</span>
        </InfoItem>
        <InfoItem icon={<Building2 size={14} />} label="Procuring Entity">
          {tender.procuring_entity}
        </InfoItem>
        {tender.deadline && (
          <InfoItem icon={<Calendar size={14} />} label="Deadline">
            {tender.deadline}
          </InfoItem>
        )}
        {tender.estimated_value && (
          <InfoItem icon={<DollarSign size={14} />} label="Estimated Value">
            <span className="font-display">{formatKES(tender.estimated_value)}</span>
          </InfoItem>
        )}
        {tender.awarded_amount && (
          <InfoItem icon={<DollarSign size={14} />} label="Awarded Amount">
            <span className="font-display">{formatKES(tender.awarded_amount)}</span>
          </InfoItem>
        )}
        <InfoItem icon={<Users size={14} />} label="Bidders">
          {bids.length} companies
        </InfoItem>
        {tender.procurement_method && (
          <InfoItem icon={<Tag size={14} />} label="Method">
            {tender.procurement_method}
          </InfoItem>
        )}
        {tender.pe_type && (
          <InfoItem icon={<Building2 size={14} />} label="PE Type">
            {tender.pe_type}
          </InfoItem>
        )}
        <InfoItem icon={<DollarSign size={14} />} label="Currency">
          {tender.currency}
        </InfoItem>
      </div>

      {/* Status */}
      <div className="flex items-center gap-2">
        <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
          Status:
        </span>
        <StatusBadge status={tender.status} />
      </div>

      {/* Winner */}
      {winning_company && (
        <div className="rounded-xl border border-border/50 bg-secondary/60 p-4">
          <h4 className="text-[11px] uppercase tracking-[0.15em] text-muted-foreground mb-3">
            Awarded To
          </h4>
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
              <Building2 className="text-primary" size={16} />
            </div>
            <div className="space-y-1">
              <p className="font-medium text-sm">{winning_company.name}</p>
              <p className="text-xs text-muted-foreground">
                Reg: {winning_company.registration_number}
              </p>
              {(winning_company.physical_address || winning_company.address) && (
                <p className="text-xs text-muted-foreground flex items-center gap-1">
                  <MapPin size={10} className="shrink-0" />
                  {winning_company.physical_address || winning_company.address}
                </p>
              )}
              {winning_company.contact_email && (
                <p className="text-xs text-muted-foreground flex items-center gap-1">
                  <Mail size={10} className="shrink-0" />
                  {winning_company.contact_email}
                </p>
              )}
              {winning_company.supplier_type && (
                <span className="inline-flex text-[10px] rounded-full border border-border/50 bg-secondary/80 px-2 py-0.5">
                  {winning_company.supplier_type}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Risk Factors */}
      {risk.factors.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <ShieldAlert className="text-[#c4412f]" size={16} />
            Why This Tender Is Flagged
          </h4>
          <div className="space-y-2">
            {risk.factors.map((factor, idx) => (
              <RiskFactorCard key={idx} factor={factor} />
            ))}
          </div>
        </div>
      )}

      {/* Recommendation */}
      {risk.recommendation && (
        <div className="rounded-xl border border-[#b78b43]/20 bg-[#b78b43]/10 p-4">
          <h4 className="text-sm font-medium text-[#b78b43] mb-2 flex items-center gap-2">
            <AlertTriangle size={14} />
            Recommended Actions
          </h4>
          <div className="text-[#7c5d3b] text-xs leading-relaxed space-y-1">
            {risk.recommendation.split(" • ").map((rec, idx) => (
              <p key={idx}>&bull; {rec}</p>
            ))}
          </div>
        </div>
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
    <div className="flex items-start gap-2.5">
      <div className="text-muted-foreground mt-0.5">{icon}</div>
      <div>
        <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <div className="text-sm font-medium mt-0.5">{children}</div>
      </div>
    </div>
  );
}

const FACTOR_CONFIG: Record<
  RiskFactorType,
  { icon: React.ReactNode; label: string; accent: string; border: string }
> = {
  CARTEL_PATTERN: {
    icon: <Users size={16} />,
    label: "Cartel Pattern",
    accent: "text-[#1f4b46]",
    border: "border-[#1f4b46]/20 bg-[#1f4b46]/10",
  },
  SHELL_COMPANY: {
    icon: <Building2 size={16} />,
    label: "Shell Company",
    accent: "text-[#b78b43]",
    border: "border-[#b78b43]/20 bg-[#b78b43]/10",
  },
  CONFLICT_OF_INTEREST: {
    icon: <UserX size={16} />,
    label: "Conflict of Interest",
    accent: "text-[#c4412f]",
    border: "border-[#c4412f]/20 bg-[#c4412f]/10",
  },
  PRICE_ANOMALY: {
    icon: <DollarSign size={16} />,
    label: "Price Anomaly",
    accent: "text-[#7c5d3b]",
    border: "border-[#7c5d3b]/20 bg-[#7c5d3b]/10",
  },
  RUSHED_TIMELINE: {
    icon: <Clock size={16} />,
    label: "Rushed Timeline",
    accent: "text-[#35638c]",
    border: "border-[#35638c]/20 bg-[#35638c]/10",
  },
  ML_ANOMALY: {
    icon: <ShieldAlert size={16} />,
    label: "ML Anomaly",
    accent: "text-[#6b4bbd]",
    border: "border-[#6b4bbd]/20 bg-[#6b4bbd]/10",
  },
};

function RiskFactorCard({ factor }: { factor: RiskFactor }) {
  const cfg = FACTOR_CONFIG[factor.type];

  return (
    <div className={`rounded-xl border p-4 ${cfg.border}`}>
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 ${cfg.accent}`}>{cfg.icon}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <span className={`text-sm font-semibold ${cfg.accent}`}>
              {cfg.label}
            </span>
            <span className="text-xs font-bold text-muted-foreground tabular-nums">
              {factor.weight} pts
            </span>
          </div>
          <p className="text-xs text-foreground/70 mb-2">{factor.description}</p>
          {factor.evidence.length > 0 && (
            <div className="text-[11px] text-muted-foreground space-y-0.5">
              {factor.evidence.filter(e => e).map((ev, idx) => (
                <p key={idx}>&bull; {ev}</p>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
