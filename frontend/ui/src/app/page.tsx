/**
 * Sentinel Dashboard - Main page.
 */

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useDashboardStats, useTenders } from "@/hooks/useTenders";
import { formatKES } from "@/lib/api";
import type { RiskCategory } from "@/lib/types";
import { TenderCard } from "@/components/TenderCard";
import { StatCard } from "@/components/ui/StatCard";
import {
  AlertTriangle,
  AlertCircle,
  FileText,
  Clock,
  CheckCircle,
} from "lucide-react";

type FilterTab = "ALL" | RiskCategory;

const FILTER_TABS: { key: FilterTab; label: string; dot?: string }[] = [
  { key: "ALL", label: "All Tenders" },
  { key: "HIGH", label: "High Risk", dot: "bg-[#c4412f]" },
  { key: "MEDIUM", label: "Medium Risk", dot: "bg-[#b78b43]" },
  { key: "LOW", label: "Low Risk", dot: "bg-[#1f6f5c]" },
];

export default function Dashboard() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<FilterTab>("ALL");

  const { stats, loading: statsLoading } = useDashboardStats();
  const { tenders, loading: tendersLoading } = useTenders(
    activeTab === "ALL" ? undefined : activeTab
  );

  return (
    <div className="min-h-screen pb-12">
      {/* Page header */}
      <header className="border-b border-border/70 bg-card/70 backdrop-blur-sm sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 lg:px-10">
          <div className="flex flex-col gap-4 py-6 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.35em] text-muted-foreground">
                Sentinel Intelligence
              </p>
              <h1 className="font-display text-3xl text-foreground">
                Oversight Dashboard
              </h1>
              <p className="mt-1 text-sm text-muted-foreground max-w-xl">
                Monitor procurement risk signals, clustering anomalies, and investigation readiness across the agency portfolio.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-secondary/70 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                Live Monitoring
              </span>
              <span className="text-xs text-muted-foreground">Updated every hour</span>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8">
        {/* Stats row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-10 stagger-children">
          {statsLoading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-[120px] rounded-2xl border border-border/40 bg-card animate-pulse"
              />
            ))
          ) : stats ? (
            <>
              <StatCard
                title="Total Tenders"
                value={stats.total_tenders}
                icon={<FileText size={18} />}
                subtitle={`${formatKES(stats.total_value)} total value`}
              />
              <StatCard
                title="High Risk"
                value={stats.high_risk_count}
                icon={<AlertTriangle size={18} />}
                variant="danger"
                subtitle={`${stats.flagged_today} new today`}
              />
              <StatCard
                title="Medium Risk"
                value={stats.medium_risk_count}
                icon={<AlertCircle size={18} />}
                variant="warning"
              />
              <StatCard
                title="Pending Review"
                value={stats.pending_review}
                icon={<Clock size={18} />}
                subtitle="Open & Evaluation"
              />
            </>
          ) : null}
        </div>

        {/* Filter tabs */}
        <div className="flex items-center gap-2 mb-8 overflow-x-auto pb-1">
          {FILTER_TABS.map((tab) => {
            const isActive = activeTab === tab.key;
            const count =
              tab.key === "ALL"
                ? stats?.total_tenders
                : tab.key === "HIGH"
                ? stats?.high_risk_count
                : tab.key === "MEDIUM"
                ? stats?.medium_risk_count
                : stats?.low_risk_count;

            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
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
                {tab.dot && (
                  <span className={`h-1.5 w-1.5 rounded-full ${tab.dot}`} />
                )}
                {tab.label}
                {count !== undefined && (
                  <span className="tabular-nums text-xs opacity-70">
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Tender list */}
        <div className="flex items-end justify-between gap-4 mb-4">
          <div>
            <h2 className="text-lg font-semibold text-foreground">Risk-flagged tenders</h2>
            <p className="text-xs text-muted-foreground">
              Prioritized by anomaly signals, bid behavior, and entity relationships.
            </p>
          </div>
          <span className="text-xs text-muted-foreground">
            {tendersLoading ? "Loading" : `${tenders.length} results`}
          </span>
        </div>
        <div className="space-y-3">
          {tendersLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="h-[168px] rounded-2xl border border-border/40 bg-card animate-pulse"
              />
            ))
          ) : tenders.length === 0 ? (
            <div className="rounded-2xl border border-border/40 bg-card p-16 text-center">
              <CheckCircle className="mx-auto text-emerald-500/60 mb-4" size={40} />
              <p className="text-muted-foreground">
                No tenders found with this filter.
              </p>
            </div>
          ) : (
            tenders.map((tender) => (
              <TenderCard
                key={tender.tender.id}
                tender={tender}
                onClick={() => router.push(`/tenders/${tender.tender.id}`)}
              />
            ))
          )}
        </div>
      </div>

    </div>
  );
}
