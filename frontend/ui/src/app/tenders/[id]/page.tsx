/**
 * Tender detail page — full investigation view.
 * Two-column layout: risk analysis (left) + metadata sidebar (right).
 */

"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTenderDetail, useTenderGraph } from "@/hooks/useTenders";
import { formatKES, createCase, getTenderCases } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Case, RiskFactor, RiskFactorType, RiskCategory } from "@/lib/types";
import { RiskBadge, StatusBadge } from "@/components/ui/RiskBadge";
import { ShadowGraph } from "@/components/ShadowGraph";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ArrowLeft,
  AlertTriangle,
  Building2,
  Calendar,
  ScanSearch,
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

const RISK_SCORE_COLORS: Record<RiskCategory, string> = {
  HIGH: "border-[#c4412f]/30 text-[#c4412f] bg-[#c4412f]/10",
  MEDIUM: "border-[#b78b43]/30 text-[#b78b43] bg-[#b78b43]/10",
  LOW: "border-[#1f6f5c]/30 text-[#1f6f5c] bg-[#1f6f5c]/10",
};

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

export default function TenderDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();
  const { detail, loading } = useTenderDetail(id);
  const { isSupervisorOrAdmin } = useAuth();
  const [showGraph, setShowGraph] = useState(false);
  const [caseActionError, setCaseActionError] = useState<string | null>(null);
  const { graph, loading: graphLoading } = useTenderGraph(showGraph ? id : null);
  const { data: tenderCases = [] } = useQuery<Case[]>({
    queryKey: ["tender-cases", id],
    queryFn: () => getTenderCases(id),
    enabled: !!id,
  });

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-muted-foreground">Tender not found</p>
          <Button variant="outline" size="sm" className="mt-4" onClick={() => router.push("/")}>
            <ArrowLeft size={14} />
            Back to Dashboard
          </Button>
        </div>
      </div>
    );
  }

  const { tender, risk, bids, winning_company } = detail;
  const activeCase = tenderCases.find((item) =>
    ["OPEN", "INVESTIGATING", "ESCALATED"].includes(item.status),
  );

  const handleOpenCase = async () => {
    if (activeCase) {
      router.push(`/cases/${activeCase.id}`);
      return;
    }

    try {
      setCaseActionError(null);
      const created = await createCase({
        tender_id: tender.id,
        title: `Investigation: ${tender.title}`,
      });
      await queryClient.invalidateQueries({ queryKey: ["cases"] });
      await queryClient.invalidateQueries({ queryKey: ["tender-cases", id] });
      router.push(`/cases/${created.case.id}`);
    } catch (error) {
      setCaseActionError(
        error instanceof Error ? error.message : "Failed to open investigation case.",
      );
    }
  };

  return (
    <div className="min-h-screen pb-12">
      {/* Sticky header */}
      <header className="border-b border-border/70 bg-card/70 backdrop-blur-sm sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 lg:px-10">
          <div className="flex items-center justify-between gap-4 py-4">
            <div className="flex items-center gap-4 min-w-0">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => router.push("/")}
                className="shrink-0 text-muted-foreground hover:text-foreground"
              >
                <ArrowLeft size={16} />
                <span className="hidden sm:inline">Dashboard</span>
              </Button>
              <div className="h-5 w-px bg-border/60 shrink-0" />
              <div className="min-w-0">
                <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                  Tender Investigation
                </p>
                <h1 className="font-display text-lg leading-snug truncate">
                  {tender.title}
                </h1>
              </div>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              <RiskBadge
                category={risk.category}
                score={risk.overall}
                pulse={risk.category === "HIGH"}
              />
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8">
        {/* Two-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main column — Risk Analysis */}
          <div className="lg:col-span-2 space-y-6">
            {/* Risk score hero */}
            <div className="rounded-2xl border border-border/70 bg-card/90 p-6">
              <div className="flex items-center gap-5">
                <div
                  className={`
                    w-20 h-20 rounded-2xl border-2 flex items-center justify-center
                    font-display text-3xl font-bold
                    ${RISK_SCORE_COLORS[risk.category]}
                  `}
                >
                  {risk.overall}
                </div>
                <div>
                  <div className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
                    Overall Risk Score
                  </div>
                  <RiskBadge category={risk.category} size="lg" />
                  <p className="text-xs text-muted-foreground mt-2 max-w-md">
                    Combined score from rule-based analysis (60%) and machine learning anomaly detection (40%).
                  </p>
                </div>
              </div>
            </div>

            {/* Risk Factors */}
            {risk.factors.length > 0 && (
              <div>
                <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
                  <ShieldAlert className="text-[#c4412f]" size={16} />
                  Why This Tender Is Flagged
                </h2>
                <div className="space-y-3">
                  {risk.factors.map((factor, idx) => (
                    <RiskFactorCard key={idx} factor={factor} />
                  ))}
                </div>
              </div>
            )}

            {/* Recommendation */}
            {risk.recommendation && (
              <div className="rounded-2xl border border-[#b78b43]/20 bg-[#b78b43]/10 p-5">
                <h3 className="text-sm font-medium text-[#b78b43] mb-3 flex items-center gap-2">
                  <AlertTriangle size={14} />
                  Recommended Actions
                </h3>
                <div className="text-[#7c5d3b] dark:text-[#e0c88a] text-sm leading-relaxed space-y-1.5">
                  {risk.recommendation.split(" • ").map((rec, idx) => (
                    <p key={idx} className="flex items-start gap-2">
                      <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#b78b43]/50 shrink-0" />
                      {rec}
                    </p>
                  ))}
                </div>
              </div>
            )}

            {/* Bidders */}
            {bids.length > 0 && (
              <div>
                <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
                  <Users size={16} className="text-primary" />
                  Submitted Bids ({bids.length})
                </h2>
                <div className="rounded-2xl border border-border/70 bg-card/90 overflow-hidden divide-y divide-border/40">
                  {bids.map((bid) => (
                    <div key={bid.id} className="px-5 py-3 flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-foreground/90">
                          {bid.company_id.slice(0, 8)}...
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Submitted {bid.submission_date}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-display font-medium">{formatKES(bid.amount)}</p>
                        {bid.technical_score !== null && (
                          <p className="text-xs text-muted-foreground">
                            Score: {bid.technical_score}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Sidebar — Metadata & Actions */}
          <div className="space-y-5">
            {/* Actions */}
            <div className="rounded-2xl border border-border/70 bg-card/90 p-5 space-y-3">
              <h3 className="text-[11px] uppercase tracking-[0.15em] text-muted-foreground font-semibold">
                Actions
              </h3>
              {caseActionError && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-[11px] text-destructive">
                  {caseActionError}
                </div>
              )}
              <Button
                size="sm"
                onClick={() => setShowGraph(true)}
                className="w-full text-xs bg-primary text-primary-foreground hover:bg-primary/90"
              >
                <Network size={14} />
                Explore Connections
              </Button>
              {activeCase ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => router.push(`/cases/${activeCase.id}`)}
                  className="w-full text-xs"
                >
                  <FolderOpen size={14} />
                  View Active Case
                </Button>
              ) : isSupervisorOrAdmin ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleOpenCase}
                  className="w-full text-xs"
                >
                  <FolderOpen size={14} />
                  Open Investigation Case
                </Button>
              ) : (
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Supervisors and admins open and assign cases for tender reviews.
                </p>
              )}
            </div>

            {/* Tender metadata */}
            <div className="rounded-2xl border border-border/70 bg-card/90 p-5 space-y-4">
              <h3 className="text-[11px] uppercase tracking-[0.15em] text-muted-foreground font-semibold">
                Tender Details
              </h3>
              <MetaItem icon={<FileText size={14} />} label="Reference">
                <span className="font-mono text-xs">{tender.reference_number}</span>
              </MetaItem>
              <MetaItem icon={<Building2 size={14} />} label="Procuring Entity">
                {tender.procuring_entity}
              </MetaItem>
              {tender.deadline && (
                <MetaItem icon={<Calendar size={14} />} label="Deadline">
                  {tender.deadline}
                </MetaItem>
              )}
              {tender.estimated_value && (
                <MetaItem icon={<DollarSign size={14} />} label="Estimated Value">
                  <span className="font-display">{formatKES(tender.estimated_value)}</span>
                </MetaItem>
              )}
              {tender.awarded_amount && (
                <MetaItem icon={<DollarSign size={14} />} label="Awarded Amount">
                  <span className="font-display">{formatKES(tender.awarded_amount)}</span>
                </MetaItem>
              )}
              <MetaItem icon={<Users size={14} />} label="Bidders">
                {bids.length} companies
              </MetaItem>
              {tender.procurement_method && (
                <MetaItem icon={<Tag size={14} />} label="Procurement Method">
                  {tender.procurement_method}
                </MetaItem>
              )}
              {tender.procurement_category && (
                <MetaItem icon={<Tag size={14} />} label="Category">
                  {tender.procurement_category}
                </MetaItem>
              )}
              {tender.pe_type && (
                <MetaItem icon={<Building2 size={14} />} label="PE Type">
                  {tender.pe_type}
                </MetaItem>
              )}
              <MetaItem icon={<DollarSign size={14} />} label="Currency">
                {tender.currency}
              </MetaItem>
              <div className="pt-2 border-t border-border/40">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">Status:</span>
                  <StatusBadge status={tender.status} />
                </div>
                {tender.source_system && tender.source_system !== "synthetic" && (
                  <span className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/5 px-2 py-0.5 text-[10px] text-primary">
                    Source: {tender.source_system.toUpperCase()}
                  </span>
                )}
              </div>
            </div>

            {/* Winning company */}
            {winning_company && (
              <div className="rounded-2xl border border-border/70 bg-card/90 p-5">
                <h3 className="text-[11px] uppercase tracking-[0.15em] text-muted-foreground font-semibold mb-3">
                  Awarded To
                </h3>
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 shrink-0">
                    <Building2 className="text-primary" size={16} />
                  </div>
                  <div className="space-y-1">
                    <p className="font-medium text-sm">{winning_company.name}</p>
                    <p className="text-xs text-muted-foreground">
                      Reg: {winning_company.registration_number}
                    </p>
                    {winning_company.physical_address && (
                      <p className="text-xs text-muted-foreground flex items-center gap-1">
                        <MapPin size={10} className="shrink-0" />
                        {winning_company.physical_address}
                      </p>
                    )}
                    {!winning_company.physical_address && winning_company.address && (
                      <p className="text-xs text-muted-foreground flex items-center gap-1">
                        <MapPin size={10} className="shrink-0" />
                        {winning_company.address}
                      </p>
                    )}
                    {winning_company.contact_email && (
                      <p className="text-xs text-muted-foreground flex items-center gap-1">
                        <Mail size={10} className="shrink-0" />
                        {winning_company.contact_email}
                      </p>
                    )}
                    {winning_company.supplier_type && (
                      <span className="inline-flex text-[10px] rounded-full border border-border/50 bg-secondary/50 px-2 py-0.5">
                        {winning_company.supplier_type}
                      </span>
                    )}
                    {winning_company.data_quality_flags && (
                      <div className="mt-2 pt-2 border-t border-border/30">
                        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Data Quality</span>
                        <div className="flex items-center gap-2 mt-1">
                          <QualityBar score={winning_company.data_quality_flags.quality_score as number | undefined} />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Graph Modal */}
      <Dialog open={showGraph} onOpenChange={(open) => !open && setShowGraph(false)}>
        <DialogContent className="flex max-h-[92vh] max-w-[96vw] flex-col overflow-hidden border border-border/70 bg-card/95 p-0 shadow-2xl sm:max-w-[92vw] xl:max-w-[1200px]">
          <DialogHeader className="shrink-0 border-b border-border/60 px-4 py-4 sm:px-6 sm:py-5">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 space-y-2">
                <DialogTitle className="font-display text-lg leading-tight sm:text-xl">
                  Connection Graph: {tender.title}
                </DialogTitle>
                <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                  <span className="inline-flex items-center gap-1 rounded-full border border-border/60 bg-muted/30 px-2 py-1">
                    <ScanSearch size={12} />
                    Explore linked entities, officials, and suspicious paths
                  </span>
                  <span className="inline-flex items-center rounded-full border border-border/60 bg-muted/30 px-2 py-1">
                    Drag nodes, zoom, or use the minimap to reframe the graph
                  </span>
                </div>
              </div>
            </div>
          </DialogHeader>
          <div className="min-h-0 flex-1 p-3 sm:p-4">
            {graphLoading ? (
              <div className="flex h-[72vh] items-center justify-center rounded-2xl border border-border/60 bg-muted/20">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
              </div>
            ) : graph ? (
              <div className="h-[72vh] min-h-[420px] rounded-2xl border border-border/50 bg-linear-to-b from-background via-background to-muted/10 p-2 sm:p-3">
                <ShadowGraph data={graph} focusNodeId={id} minimapPosition="bottom-right" />
              </div>
            ) : (
              <div className="flex h-[72vh] items-center justify-center rounded-2xl border border-dashed border-border/60 bg-muted/10 text-muted-foreground">
                No graph data available
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function MetaItem({
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
        <div className="text-[11px] uppercase tracking-[0.15em] text-muted-foreground">
          {label}
        </div>
        <div className="text-sm font-medium mt-0.5">{children}</div>
      </div>
    </div>
  );
}

function RiskFactorCard({ factor }: { factor: RiskFactor }) {
  const cfg = FACTOR_CONFIG[factor.type] ?? {
    icon: <AlertTriangle size={16} />,
    label: factor.type,
    accent: "text-muted-foreground",
    border: "border-border/60 bg-card",
  };

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

function QualityBar({ score }: { score?: number }) {
  const s = score ?? 0;
  const color =
    s >= 70 ? "bg-emerald-500" : s >= 40 ? "bg-[#b78b43]" : "bg-[#c4412f]";

  return (
    <div className="flex items-center gap-2 w-full">
      <div className="flex-1 h-1.5 rounded-full bg-secondary/80 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${s}%` }} />
      </div>
      <span className="text-[10px] font-bold tabular-nums text-muted-foreground">{s}%</span>
    </div>
  );
}
