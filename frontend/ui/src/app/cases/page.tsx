/**
 * Case Management page — investigation workflow for flagged tenders.
 */

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useCases, useCaseStats } from "@/hooks/useTenders";
import { downloadCasesCsv, getWorkload } from "@/lib/api";
import { AuthGuard } from "@/components/AuthGuard";
import { useAuth } from "@/lib/auth";
import {
  Loader2,
  FolderOpen,
  Search,
  CheckCircle2,
  Clock,
  ArrowUpRight,
  XCircle,
  Users,
  Download,
} from "lucide-react";
import type {
  CaseWithTender,
  CaseStatus,
  RiskCategory,
  WorkloadItem,
} from "@/lib/types";

const STATUS_CONFIG: Record<
  CaseStatus,
  { label: string; dot: string; icon: React.ReactNode }
> = {
  OPEN: {
    label: "Open",
    dot: "bg-[#35638c]",
    icon: <FolderOpen size={12} />,
  },
  INVESTIGATING: {
    label: "Investigating",
    dot: "bg-[#b78b43]",
    icon: <Search size={12} />,
  },
  ESCALATED: {
    label: "Escalated",
    dot: "bg-[#c4412f]",
    icon: <ArrowUpRight size={12} />,
  },
  RESOLVED: {
    label: "Resolved",
    dot: "bg-[#1f6f5c]",
    icon: <CheckCircle2 size={12} />,
  },
  DISMISSED: {
    label: "Dismissed",
    dot: "bg-[#8a8580]",
    icon: <XCircle size={12} />,
  },
};

const PRIORITY_COLOR: Record<RiskCategory, string> = {
  HIGH: "text-[#c4412f]",
  MEDIUM: "text-[#b78b43]",
  LOW: "text-[#1f6f5c]",
};

const PRIORITY_ACCENT: Record<RiskCategory, string> = {
  HIGH: "from-[#c4412f] via-[#c4412f]/60 to-transparent",
  MEDIUM: "from-[#b78b43] via-[#b78b43]/60 to-transparent",
  LOW: "from-[#1f6f5c] via-[#1f6f5c]/60 to-transparent",
};

function CasesPageContent() {
  const router = useRouter();
  const { isSupervisorOrAdmin } = useAuth();
  const [statusFilter, setStatusFilter] = useState<CaseStatus | "ALL">("ALL");
  const [assigneeFilter, setAssigneeFilter] = useState<string>("all");
  const [exportingCsv, setExportingCsv] = useState(false);

  const { cases, loading } = useCases(statusFilter);
  const { stats } = useCaseStats();

  // M3: Workload data for supervisors
  const { data: workload = [] } = useQuery<WorkloadItem[]>({
    queryKey: ["workload"],
    queryFn: getWorkload,
    enabled: isSupervisorOrAdmin,
  });

  const handleOpenDetail = (caseId: string) => {
    router.push(`/cases/${caseId}`);
  };

  // Filter cases by assignee
  const filteredCases = cases.filter((item) => {
    if (assigneeFilter === "all") return true;
    if (assigneeFilter === "unassigned") return !item.case.assigned_to_id;
    return item.case.assigned_to_id === assigneeFilter;
  });

  const statusTabs: { key: CaseStatus | "ALL"; label: string; count?: number }[] = [
    { key: "ALL", label: "All", count: stats?.total },
    { key: "OPEN", label: "Open", count: stats?.open },
    { key: "INVESTIGATING", label: "Investigating", count: stats?.investigating },
    { key: "ESCALATED", label: "Escalated", count: stats?.escalated },
    { key: "RESOLVED", label: "Resolved", count: stats?.resolved },
    { key: "DISMISSED", label: "Dismissed", count: stats?.dismissed },
  ];

  const handleExportCsv = async () => {
    setExportingCsv(true);
    try {
      await downloadCasesCsv({
        status: statusFilter === "ALL" ? undefined : statusFilter,
        assignedToId: assigneeFilter === "all" ? undefined : assigneeFilter,
      });
    } finally {
      setExportingCsv(false);
    }
  };

  return (
    <div className="min-h-screen pb-12">
      {/* Page header */}
      <header className="border-b border-border/70 bg-card/70 backdrop-blur-sm sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 lg:px-10">
          <div className="flex flex-col gap-4 py-6 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.35em] text-muted-foreground">
                Case Management
              </p>
              <h1 className="font-display text-3xl text-foreground">Investigation Cases</h1>
              <p className="mt-1 text-sm text-muted-foreground max-w-xl">
                Manage escalations, track decisions, and collaborate on procurement investigations.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <p className="text-xs text-muted-foreground">
                Click any case to view full details
              </p>
              <button
                onClick={handleExportCsv}
                disabled={exportingCsv || loading}
                className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-card px-3 py-1.5 text-[11px] font-medium uppercase tracking-[0.15em] text-muted-foreground transition-colors hover:bg-secondary/70 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60"
              >
                {exportingCsv ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
                Export CSV
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8 space-y-6">
        {/* M3: Supervisor Workload Overview */}
        {isSupervisorOrAdmin && workload.length > 0 && (
          <section className="rounded-2xl border border-border/70 bg-card p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
              <Users size={16} />
              Team Workload
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
              {workload.map((w) => (
                <button
                  key={w.user_id || "unassigned"}
                  onClick={() => setAssigneeFilter(w.user_id || "unassigned")}
                  className={`rounded-xl border p-3 text-left transition-all hover:border-primary/50 ${
                    assigneeFilter === (w.user_id || "unassigned")
                      ? "border-primary bg-primary/5"
                      : "border-border/50 bg-muted/20"
                  }`}
                >
                  <p className="text-sm font-medium truncate">{w.full_name}</p>
                  <p className="text-xs text-muted-foreground">{w.role || "Queue"}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-lg font-display">{w.total_active}</span>
                    <span className="text-xs text-muted-foreground">active</span>
                  </div>
                  <div className="flex gap-1 mt-1 text-[10px]">
                    {w.open > 0 && <span className="text-[#35638c]">{w.open} open</span>}
                    {w.investigating > 0 && <span className="text-[#b78b43]">{w.investigating} inv</span>}
                    {w.escalated > 0 && <span className="text-[#c4412f]">{w.escalated} esc</span>}
                  </div>
                </button>
              ))}
            </div>
            {assigneeFilter !== "all" && (
              <button
                onClick={() => setAssigneeFilter("all")}
                className="mt-3 text-xs text-primary hover:underline"
              >
                Clear filter
              </button>
            )}
          </section>
        )}

        {/* Status filter chips */}
        {stats && (
          <div className="flex items-center gap-2 overflow-x-auto pb-1 stagger-children">
            {statusTabs.map((tab) => {
              const isActive = statusFilter === tab.key;
              const statusCfg = tab.key !== "ALL" ? STATUS_CONFIG[tab.key] : null;

              return (
                <button
                  key={tab.key}
                  onClick={() => setStatusFilter(tab.key)}
                  className={`
                    flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium
                    whitespace-nowrap transition-all duration-200 border
                    ${
                      isActive
                        ? "bg-primary text-primary-foreground border-primary/40 shadow-sm"
                        : "border-border/60 text-muted-foreground hover:text-foreground hover:bg-secondary/70"
                    }
                  `}
                >
                  {statusCfg && (
                    <span className={`h-1.5 w-1.5 rounded-full ${statusCfg.dot}`} />
                  )}
                  {tab.label}
                  <span className="tabular-nums text-xs opacity-60">
                    {tab.count ?? 0}
                  </span>
                </button>
              );
            })}
          </div>
        )}

        {/* Case list */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-7 h-7 animate-spin text-primary" />
          </div>
        ) : filteredCases.length === 0 ? (
          <div className="rounded-2xl border border-border/50 bg-card p-16 text-center">
            <FolderOpen className="w-10 h-10 text-muted-foreground/50 mx-auto mb-4" />
            <p className="font-medium text-foreground/80">No cases found</p>
            <p className="text-sm text-muted-foreground mt-1">
              {assigneeFilter !== "all"
                ? "Try clearing the assignee filter."
                : "Supervisors and admins can open cases from tender detail view to start an investigation."}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredCases.map((item) => (
              <CaseRow
                key={item.case.id}
                item={item}
                onClick={() => handleOpenDetail(item.case.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function CaseRow({
  item,
  onClick,
}: {
  item: CaseWithTender;
  onClick: () => void;
}) {
  const c = item.case;
  const statusCfg = STATUS_CONFIG[c.status];

  return (
    <div
      onClick={onClick}
      className="group relative cursor-pointer overflow-hidden rounded-2xl border border-border/70 bg-card/95 p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-lg"
    >
      <span
        className={`absolute inset-y-0 left-0 w-1.5 bg-linear-to-b ${
          PRIORITY_ACCENT[item.risk_category]
        }`}
      />
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.15em] text-muted-foreground">
              <span className={`h-1.5 w-1.5 rounded-full ${statusCfg.dot}`} />
              {statusCfg.label}
            </span>
            <span className={`text-[11px] font-bold uppercase tracking-[0.15em] ${PRIORITY_COLOR[c.priority]}`}>
              {c.priority}
            </span>
          </div>
          <p className="font-medium text-sm text-foreground/90 truncate group-hover:text-primary transition-colors">
            {c.title}
          </p>
          <p className="text-xs text-muted-foreground truncate mt-0.5">
            {item.tender_title}
          </p>
        </div>

        <div className="text-right shrink-0">
          <p className={`font-display text-xl ${PRIORITY_COLOR[item.risk_category]}`}>
            {item.risk_score}
          </p>
          <p className="text-[11px] uppercase tracking-[0.15em] text-muted-foreground">
            risk
          </p>
        </div>
      </div>

      {c.summary && (
        <p className="text-xs text-muted-foreground mt-2 line-clamp-1">
          {c.summary}
        </p>
      )}

      <div className="flex items-center gap-4 mt-2.5 text-[11px] text-muted-foreground">
        {c.assigned_to && <span>Assigned: {c.assigned_to}</span>}
        <span className="inline-flex items-center gap-1">
          <Clock size={10} />
          {new Date(c.created_at).toLocaleDateString()}
        </span>
        {c.notes.length > 0 && (
          <span>{c.notes.length} note{c.notes.length !== 1 ? "s" : ""}</span>
        )}
      </div>
    </div>
  );
}

export default function CasesPage() {
  return (
    <AuthGuard>
      <CasesPageContent />
    </AuthGuard>
  );
}
