/**
 * Case Management page — investigation workflow for flagged tenders.
 */

"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useCases, useCaseStats, useCaseDetail, queryKeys } from "@/hooks/useTenders";
import { updateCase, addCaseNote } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Loader2,
  FolderOpen,
  Search,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ArrowUpRight,
  XCircle,
  MessageSquarePlus,
  Send,
} from "lucide-react";
import type {
  CaseWithTender,
  CaseStatus,
  NoteType,
  RiskCategory,
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

const NOTE_TYPE_LABELS: Record<NoteType, string> = {
  OBSERVATION: "Observation",
  EVIDENCE: "Evidence",
  DECISION: "Decision",
  ACTION: "Action",
};

export default function CasesPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<CaseStatus | "ALL">("ALL");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const { cases, loading } = useCases(statusFilter);
  const { stats } = useCaseStats();
  const { detail: selectedCase } = useCaseDetail(detailOpen ? selectedCaseId : null);

  const invalidateCases = () => {
    queryClient.invalidateQueries({ queryKey: ["cases"] });
    queryClient.invalidateQueries({ queryKey: queryKeys.caseStats });
  };

  const handleOpenDetail = (caseId: string) => {
    setSelectedCaseId(caseId);
    setDetailOpen(true);
  };

  const handleStatusChange = async (
    caseId: string,
    newStatus: CaseStatus
  ) => {
    try {
      await updateCase(caseId, { status: newStatus });
      invalidateCases();
      queryClient.invalidateQueries({ queryKey: queryKeys.caseDetail(caseId) });
    } catch {
      // silent
    }
  };

  const handleAddNote = async (
    caseId: string,
    content: string,
    noteType: NoteType
  ) => {
    try {
      await addCaseNote(caseId, { content, note_type: noteType });
      queryClient.invalidateQueries({ queryKey: queryKeys.caseDetail(caseId) });
    } catch {
      // silent
    }
  };

  const statusTabs: { key: CaseStatus | "ALL"; label: string; count?: number }[] =
    [
      { key: "ALL", label: "All", count: stats?.total },
      { key: "OPEN", label: "Open", count: stats?.open },
      { key: "INVESTIGATING", label: "Investigating", count: stats?.investigating },
      { key: "ESCALATED", label: "Escalated", count: stats?.escalated },
      { key: "RESOLVED", label: "Resolved", count: stats?.resolved },
      { key: "DISMISSED", label: "Dismissed", count: stats?.dismissed },
    ];

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
            <p className="text-xs text-muted-foreground">
              Live case activity &amp; notes
            </p>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8 space-y-6">
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
        ) : cases.length === 0 ? (
          <div className="rounded-2xl border border-border/50 bg-card p-16 text-center">
            <FolderOpen className="w-10 h-10 text-muted-foreground/50 mx-auto mb-4" />
            <p className="font-medium text-foreground/80">No cases yet</p>
            <p className="text-sm text-muted-foreground mt-1">
              Open a case from any tender&apos;s detail view to start investigating.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {cases.map((item) => (
              <CaseRow
                key={item.case.id}
                item={item}
                onClick={() => handleOpenDetail(item.case.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Case Detail Dialog */}
      <CaseDetailDialog
        open={detailOpen && !!selectedCase}
        onClose={() => {
          setDetailOpen(false);
          setSelectedCaseId(null);
        }}
        item={selectedCase}
        onStatusChange={handleStatusChange}
        onAddNote={handleAddNote}
      />
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

function CaseDetailDialog({
  open,
  onClose,
  item,
  onStatusChange,
  onAddNote,
}: {
  open: boolean;
  onClose: () => void;
  item: CaseWithTender | null;
  onStatusChange: (caseId: string, status: CaseStatus) => Promise<void>;
  onAddNote: (caseId: string, content: string, noteType: NoteType) => Promise<void>;
}) {
  const [noteContent, setNoteContent] = useState("");
  const [noteType, setNoteType] = useState<NoteType>("OBSERVATION");
  const [submitting, setSubmitting] = useState(false);

  if (!item) return null;
  const c = item.case;
  const statusCfg = STATUS_CONFIG[c.status];

  const handleSubmitNote = async () => {
    if (!noteContent.trim()) return;
    setSubmitting(true);
    await onAddNote(c.id, noteContent.trim(), noteType);
    setNoteContent("");
    setSubmitting(false);
  };

  const nextStatuses: Record<CaseStatus, CaseStatus[]> = {
    OPEN: ["INVESTIGATING", "DISMISSED"],
    INVESTIGATING: ["ESCALATED", "RESOLVED", "DISMISSED"],
    ESCALATED: ["RESOLVED", "INVESTIGATING"],
    RESOLVED: [],
    DISMISSED: ["OPEN"],
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col bg-card/95 border border-border/70">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.15em] text-muted-foreground">
              <span className={`h-1.5 w-1.5 rounded-full ${statusCfg.dot}`} />
              {statusCfg.label}
            </span>
            <span className="font-display text-lg truncate">{c.title}</span>
          </DialogTitle>
        </DialogHeader>

        <ScrollArea className="flex-1 -mx-6 px-6">
          <div className="space-y-5 pb-4">
            {/* Meta grid */}
            <div className="grid grid-cols-2 gap-3 text-sm">
              <MetaItem label="Tender" value={item.tender_title} />
              <MetaItem
                label="Risk"
                value={`${item.risk_score} (${item.risk_category})`}
                className={PRIORITY_COLOR[item.risk_category]}
              />
              <MetaItem label="Priority" value={c.priority} />
              <MetaItem label="Assigned to" value={c.assigned_to || "Unassigned"} />
              <MetaItem label="Created" value={new Date(c.created_at).toLocaleString()} />
              <MetaItem label="Created by" value={c.created_by} />
            </div>

            {c.summary && (
              <div>
                <span className="text-[11px] uppercase tracking-[0.15em] text-muted-foreground">
                  Summary
                </span>
                <p className="text-sm mt-1 text-foreground/80">{c.summary}</p>
              </div>
            )}

            {c.decision && (
              <div className="rounded-xl border border-[#1f6f5c]/20 bg-[#1f6f5c]/10 p-3">
                <p className="text-xs font-medium text-[#1f6f5c]">Decision</p>
                <p className="text-sm text-[#1f6f5c]/80 mt-1">{c.decision}</p>
              </div>
            )}

            {/* Status transitions */}
            {nextStatuses[c.status].length > 0 && (
              <div>
                <span className="text-[11px] uppercase tracking-[0.15em] text-muted-foreground">
                  Transition to
                </span>
                <div className="flex gap-2 mt-1.5">
                  {nextStatuses[c.status].map((s) => (
                    <Button
                      key={s}
                      variant="outline"
                      size="sm"
                      onClick={() => onStatusChange(c.id, s)}
                      className="text-xs h-8"
                    >
                      {STATUS_CONFIG[s].icon}
                      <span className="ml-1">{STATUS_CONFIG[s].label}</span>
                    </Button>
                  ))}
                </div>
              </div>
            )}

            <div className="border-t border-border/50" />

            {/* Notes */}
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground mb-3 flex items-center gap-2">
                <MessageSquarePlus size={14} />
                Investigation Notes ({c.notes.length})
              </h3>

              {/* Add note form */}
              <div className="space-y-2 mb-4">
                <div className="flex gap-1.5">
                  {(Object.keys(NOTE_TYPE_LABELS) as NoteType[]).map((t) => (
                    <button
                      key={t}
                      onClick={() => setNoteType(t)}
                      className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors uppercase tracking-[0.15em] font-medium ${
                        noteType === t
                          ? "bg-primary text-primary-foreground border-primary"
                          : "border-border/50 text-muted-foreground hover:bg-accent/50"
                      }`}
                    >
                      {NOTE_TYPE_LABELS[t]}
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
                  <textarea
                    value={noteContent}
                    onChange={(e) => setNoteContent(e.target.value)}
                    placeholder="Add a note..."
                    rows={2}
                    className="flex-1 text-sm rounded-xl border border-border/50 bg-secondary/50 px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-primary text-foreground placeholder:text-muted-foreground"
                  />
                  <Button
                    size="sm"
                    onClick={handleSubmitNote}
                    disabled={!noteContent.trim() || submitting}
                    className="self-end h-8"
                  >
                    {submitting ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <Send size={14} />
                    )}
                  </Button>
                </div>
              </div>

              {/* Note list */}
              {c.notes.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-6">
                  No notes yet
                </p>
              ) : (
                <div className="space-y-2">
                  {c.notes.map((note) => (
                    <div
                      key={note.id}
                      className="rounded-lg border border-border/40 bg-muted/20 p-3 text-sm"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-[11px] uppercase tracking-wider">
                            {NOTE_TYPE_LABELS[note.note_type]}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {note.author}
                          </span>
                        </div>
                        <span className="text-[11px] text-muted-foreground">
                          {new Date(note.created_at).toLocaleString()}
                        </span>
                      </div>
                      <p className="mt-1 text-foreground/80">{note.content}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}

function MetaItem({
  label,
  value,
  className = "",
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div>
      <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <p className={`text-sm font-medium mt-0.5 ${className || "text-foreground/80"}`}>
        {value}
      </p>
    </div>
  );
}
