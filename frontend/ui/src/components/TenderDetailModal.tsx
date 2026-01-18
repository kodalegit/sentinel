/**
 * Tender detail modal showing full risk breakdown.
 */

"use client";

import type { TenderDetail, RiskFactor } from "@/lib/types";
import { formatKES } from "@/lib/api";
import { Modal } from "@/components/ui/Modal";
import { RiskBadge, StatusBadge } from "@/components/ui/Badge";
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
} from "lucide-react";

interface TenderDetailModalProps {
  detail: TenderDetail | null;
  loading: boolean;
  isOpen: boolean;
  onClose: () => void;
  onViewGraph: () => void;
}

export function TenderDetailModal({
  detail,
  loading,
  isOpen,
  onClose,
  onViewGraph,
}: TenderDetailModalProps) {
  if (loading) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title="Loading...">
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        </div>
      </Modal>
    );
  }

  if (!detail) return null;

  const { tender, risk, bids, winning_company } = detail;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={tender.title} size="xl">
      <div className="p-6 space-y-6">
        {/* Header with risk score */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
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
              <div className="text-sm text-slate-500">Risk Score</div>
              <RiskBadge category={risk.category} size="lg" />
            </div>
          </div>

          <button
            onClick={onViewGraph}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Network size={18} />
            Explore Connections
          </button>
        </div>

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
          <span className="text-sm text-slate-500">Status:</span>
          <StatusBadge status={tender.status} />
        </div>

        {/* Winner info */}
        {winning_company && (
          <div className="bg-slate-50 rounded-xl p-4">
            <h4 className="font-medium text-slate-700 mb-2">
              Awarded To
            </h4>
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                <Building2 className="text-blue-600" size={20} />
              </div>
              <div>
                <p className="font-semibold text-slate-900">
                  {winning_company.name}
                </p>
                <p className="text-sm text-slate-500">
                  Reg: {winning_company.registration_number}
                </p>
                <p className="text-sm text-slate-500">
                  {winning_company.address}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Risk Factors */}
        {risk.factors.length > 0 && (
          <div>
            <h4 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <ShieldAlert className="text-red-500" size={20} />
              Why This Tender Is Flagged
            </h4>
            <div className="space-y-4">
              {risk.factors.map((factor, idx) => (
                <RiskFactorCard key={idx} factor={factor} />
              ))}
            </div>
          </div>
        )}

        {/* Recommendation */}
        {risk.recommendation && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
            <h4 className="font-medium text-amber-800 mb-2 flex items-center gap-2">
              <AlertTriangle size={18} />
              Recommended Actions
            </h4>
            <p className="text-amber-900 text-sm leading-relaxed">
              {risk.recommendation.split(" • ").map((rec, idx) => (
                <span key={idx} className="block">• {rec}</span>
              ))}
            </p>
          </div>
        )}
      </div>
    </Modal>
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
      <div className="text-slate-400 mt-0.5">{icon}</div>
      <div>
        <div className="text-xs text-slate-500">{label}</div>
        <div className="text-sm font-medium text-slate-900">{children}</div>
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
    CARTEL_PATTERN: "bg-purple-100 text-purple-600 border-purple-200",
    SHELL_COMPANY: "bg-orange-100 text-orange-600 border-orange-200",
    CONFLICT_OF_INTEREST: "bg-red-100 text-red-600 border-red-200",
    PRICE_ANOMALY: "bg-amber-100 text-amber-600 border-amber-200",
    RUSHED_TIMELINE: "bg-blue-100 text-blue-600 border-blue-200",
  };

  const labels = {
    CARTEL_PATTERN: "Cartel Pattern",
    SHELL_COMPANY: "Shell Company",
    CONFLICT_OF_INTEREST: "Conflict of Interest",
    PRICE_ANOMALY: "Price Anomaly",
    RUSHED_TIMELINE: "Rushed Timeline",
  };

  return (
    <div className={`rounded-xl border p-4 ${colors[factor.type]}`}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5">{icons[factor.type]}</div>
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1">
            <span className="font-semibold">{labels[factor.type]}</span>
            <span className="text-sm font-bold">{factor.weight} points</span>
          </div>
          <p className="text-sm opacity-90 mb-2">{factor.description}</p>
          {factor.evidence.length > 0 && (
            <div className="text-xs opacity-75 space-y-0.5">
              {factor.evidence.filter(e => e).map((ev, idx) => (
                <p key={idx}>• {ev}</p>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
