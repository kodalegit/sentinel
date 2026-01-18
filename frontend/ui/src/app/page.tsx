/**
 * Sentinel Dashboard - Main page.
 */

"use client";

import { useState } from "react";
import { useDashboardStats, useTenders, useTenderDetail, useTenderGraph } from "@/hooks/useTenders";
import { formatKES } from "@/lib/api";
import type { RiskCategory } from "@/lib/types";
import { TenderCard } from "@/components/TenderCard";
import { TenderDetailModal } from "@/components/TenderDetailModal";
import { ShadowGraph } from "@/components/ShadowGraph";
import { StatCard } from "@/components/ui/StatCard";
import { Modal } from "@/components/ui/Modal";
import {
  Shield,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  FileText,
  Clock,
  TrendingUp,
  Network,
  Loader2,
} from "lucide-react";
import Link from "next/link";

type FilterTab = "ALL" | RiskCategory;

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<FilterTab>("ALL");
  const [selectedTenderId, setSelectedTenderId] = useState<string | null>(null);
  const [showGraph, setShowGraph] = useState(false);

  const { stats, loading: statsLoading } = useDashboardStats();
  const { tenders, loading: tendersLoading } = useTenders(
    activeTab === "ALL" ? undefined : activeTab
  );
  const { detail, loading: detailLoading } = useTenderDetail(selectedTenderId);
  const { graph, loading: graphLoading } = useTenderGraph(
    showGraph ? selectedTenderId : null
  );

  const tabs: { key: FilterTab; label: string; color: string }[] = [
    { key: "ALL", label: "All Tenders", color: "bg-slate-600" },
    { key: "HIGH", label: "High Risk", color: "bg-red-600" },
    { key: "MEDIUM", label: "Medium Risk", color: "bg-amber-500" },
    { key: "LOW", label: "Low Risk", color: "bg-emerald-600" },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center">
                <Shield className="text-white" size={22} />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">SENTINEL</h1>
                <p className="text-xs text-slate-500">Public Procurement Guardian</p>
              </div>
            </div>

            <Link
              href="/graph"
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition-colors"
            >
              <Network size={18} />
              Explore Shadow Graph
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {statsLoading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-28 bg-white rounded-xl border border-slate-200 animate-pulse"
              />
            ))
          ) : stats ? (
            <>
              <StatCard
                title="Total Tenders"
                value={stats.total_tenders}
                icon={<FileText />}
                subtitle={`${formatKES(stats.total_value)} total value`}
              />
              <StatCard
                title="High Risk"
                value={stats.high_risk_count}
                icon={<AlertTriangle />}
                variant="danger"
                subtitle={`${stats.flagged_today} new today`}
              />
              <StatCard
                title="Medium Risk"
                value={stats.medium_risk_count}
                icon={<AlertCircle />}
                variant="warning"
              />
              <StatCard
                title="Pending Review"
                value={stats.pending_review}
                icon={<Clock />}
                subtitle="Open & Evaluation"
              />
            </>
          ) : null}
        </div>

        {/* Filter tabs */}
        <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-2">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`
                px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all
                ${
                  activeTab === tab.key
                    ? `${tab.color} text-white shadow-lg`
                    : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
                }
              `}
            >
              {tab.label}
              {stats && (
                <span className="ml-2 opacity-75">
                  {tab.key === "ALL"
                    ? stats.total_tenders
                    : tab.key === "HIGH"
                    ? stats.high_risk_count
                    : tab.key === "MEDIUM"
                    ? stats.medium_risk_count
                    : stats.low_risk_count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tender list */}
        <div className="space-y-4">
          {tendersLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="h-40 bg-white rounded-xl border border-slate-200 animate-pulse"
              />
            ))
          ) : tenders.length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
              <CheckCircle className="mx-auto text-emerald-500 mb-4" size={48} />
              <p className="text-slate-600">
                No tenders found with this filter.
              </p>
            </div>
          ) : (
            tenders.map((tender) => (
              <TenderCard
                key={tender.tender.id}
                tender={tender}
                onClick={() => setSelectedTenderId(tender.tender.id)}
              />
            ))
          )}
        </div>
      </main>

      {/* Tender Detail Modal */}
      <TenderDetailModal
        detail={detail}
        loading={detailLoading}
        isOpen={!!selectedTenderId && !showGraph}
        onClose={() => setSelectedTenderId(null)}
        onViewGraph={() => setShowGraph(true)}
      />

      {/* Graph Modal */}
      <Modal
        isOpen={showGraph}
        onClose={() => setShowGraph(false)}
        title={`Connection Graph: ${detail?.tender.title || ""}`}
        size="xl"
      >
        <div className="h-[600px] p-4">
          {graphLoading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
            </div>
          ) : graph ? (
            <ShadowGraph data={graph} focusNodeId={selectedTenderId || undefined} />
          ) : (
            <div className="flex items-center justify-center h-full text-slate-500">
              No graph data available
            </div>
          )}
        </div>
      </Modal>

      {/* Footer */}
      <footer className="mt-16 border-t border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="text-sm text-slate-500">
              Sentinel MVP • AI Hackathon 2026
            </div>
            <div className="flex items-center gap-4 text-sm text-slate-500">
              <span className="flex items-center gap-1">
                <TrendingUp size={14} />
                Powered by AI
              </span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
