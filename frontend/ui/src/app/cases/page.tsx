/**
 * Case Management page — investigation workflow for flagged tenders.
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Shield,
  ArrowLeft,
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
  CaseStats,
  NoteType,
  RiskCategory,
} from "@/lib/types";
import {
  getCases,
  getCaseStats,
  getCaseDetail,
  updateCase,
  addCaseNote,
} from "@/lib/api";

const STATUS_CONFIG: Record<
  CaseStatus,
  { label: string; color: string; icon: React.ReactNode }
> = {
  OPEN: {
    label: "Open",
    color: "bg-blue-100 text-blue-800",
    icon: <FolderOpen size={14} />,
  },
  INVESTIGATING: {
    label: "Investigating",
    color: "bg-amber-100 text-amber-800",
    icon: <Search size={14} />,
  },
  ESCALATED: {
    label: "Escalated",
    color: "bg-red-100 text-red-800",
    icon: <ArrowUpRight size={14} />,
  },
  RESOLVED: {
    label: "Resolved",
    color: "bg-emerald-100 text-emerald-800",
    icon: <CheckCircle2 size={14} />,
  },
  DISMISSED: {
    label: "Dismissed",
    color: "bg-slate-100 text-slate-600",
    icon: <XCircle size={14} />,
  },
};

const PRIORITY_COLOR: Record<RiskCategory, string> = {
  HIGH: "text-red-600",
  MEDIUM: "text-amber-600",
  LOW: "text-emerald-600",
};

const NOTE_TYPE_LABELS: Record<NoteType, string> = {
  OBSERVATION: "Observation",
  EVIDENCE: "Evidence",
  DECISION: "Decision",
  ACTION: "Action",
};

export default function CasesPage() {
  const [cases, setCases] = useState<CaseWithTender[]>([]);
  const [stats, setStats] = useState<CaseStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<CaseStatus | "ALL">("ALL");
  const [selectedCase, setSelectedCase] = useState<CaseWithTender | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const loadCases = useCallback(async () => {
    setLoading(true);
    try {
      const opts =
        statusFilter !== "ALL" ? { status: statusFilter } : undefined;
      const [casesData, statsData] = await Promise.all([
        getCases(opts),
        getCaseStats(),
      ]);
      setCases(casesData);
      setStats(statsData);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadCases();
  }, [loadCases]);

  const handleOpenDetail = async (caseId: string) => {
    try {
      const detail = await getCaseDetail(caseId);
      setSelectedCase(detail);
      setDetailOpen(true);
    } catch {
      // silent
    }
  };

  const handleStatusChange = async (
    caseId: string,
    newStatus: CaseStatus
  ) => {
    try {
      await updateCase(caseId, { status: newStatus });
      await loadCases();
      if (selectedCase?.case.id === caseId) {
        const updated = await getCaseDetail(caseId);
        setSelectedCase(updated);
      }
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
      const updated = await getCaseDetail(caseId);
      setSelectedCase(updated);
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
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card border-b sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Link href="/">
                <Button variant="ghost" size="sm">
                  <ArrowLeft size={18} />
                  Dashboard
                </Button>
              </Link>
              <Separator orientation="vertical" className="h-8" />
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-linear-to-br from-blue-600 to-indigo-700 flex items-center justify-center">
                  <Shield className="text-white" size={22} />
                </div>
                <div>
                  <h1 className="text-xl font-bold">Case Management</h1>
                  <p className="text-xs text-muted-foreground">
                    Investigation workflow
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Stats row */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {statusTabs.map((tab) => (
              <Card
                key={tab.key}
                onClick={() => setStatusFilter(tab.key)}
                className={`cursor-pointer transition-all hover:shadow-sm ${
                  statusFilter === tab.key ? "ring-2 ring-primary" : ""
                }`}
              >
                <CardContent className="p-3 text-center">
                  <p className="text-2xl font-bold">{tab.count ?? 0}</p>
                  <p className="text-xs text-muted-foreground">{tab.label}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Case list */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : cases.length === 0 ? (
          <Card>
            <CardContent className="py-16 text-center">
              <FolderOpen className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-lg font-medium">No cases yet</p>
              <p className="text-sm text-muted-foreground mt-1">
                Open a case from any tender&apos;s detail view to start investigating.
              </p>
            </CardContent>
          </Card>
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
      </main>

      {/* Case Detail Dialog */}
      {selectedCase && (
        <CaseDetailDialog
          open={detailOpen}
          onClose={() => setDetailOpen(false)}
          item={selectedCase}
          onStatusChange={handleStatusChange}
          onAddNote={handleAddNote}
        />
      )}
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
    <Card
      onClick={onClick}
      className="cursor-pointer transition-all hover:shadow-sm"
    >
      <CardContent className="p-4">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${statusCfg.color}`}
              >
                {statusCfg.icon}
                {statusCfg.label}
              </span>
              <Badge
                variant={
                  c.priority === "HIGH"
                    ? "destructive"
                    : c.priority === "MEDIUM"
                    ? "secondary"
                    : "outline"
                }
                className="text-xs"
              >
                {c.priority}
              </Badge>
            </div>
            <p className="font-medium truncate">{c.title}</p>
            <p className="text-sm text-muted-foreground truncate">
              {item.tender_title}
            </p>
          </div>

          <div className="text-right shrink-0">
            <p className={`text-lg font-bold ${PRIORITY_COLOR[item.risk_category]}`}>
              {item.risk_score}
            </p>
            <p className="text-xs text-muted-foreground">risk score</p>
          </div>
        </div>

        {c.summary && (
          <p className="text-sm text-muted-foreground mt-2 line-clamp-1">
            {c.summary}
          </p>
        )}

        <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
          {c.assigned_to && <span>Assigned: {c.assigned_to}</span>}
          <span>
            <Clock size={12} className="inline mr-1" />
            {new Date(c.created_at).toLocaleDateString()}
          </span>
          {c.notes.length > 0 && (
            <span>{c.notes.length} note{c.notes.length !== 1 ? "s" : ""}</span>
          )}
        </div>
      </CardContent>
    </Card>
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
  item: CaseWithTender;
  onStatusChange: (caseId: string, status: CaseStatus) => Promise<void>;
  onAddNote: (caseId: string, content: string, noteType: NoteType) => Promise<void>;
}) {
  const c = item.case;
  const statusCfg = STATUS_CONFIG[c.status];
  const [noteContent, setNoteContent] = useState("");
  const [noteType, setNoteType] = useState<NoteType>("OBSERVATION");
  const [submitting, setSubmitting] = useState(false);

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
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${statusCfg.color}`}
            >
              {statusCfg.icon}
              {statusCfg.label}
            </span>
            <span className="truncate">{c.title}</span>
          </DialogTitle>
        </DialogHeader>

        <ScrollArea className="flex-1 -mx-6 px-6">
          <div className="space-y-5 pb-4">
            {/* Meta */}
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-muted-foreground">Tender:</span>
                <p className="font-medium">{item.tender_title}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Risk:</span>
                <p className={`font-bold ${PRIORITY_COLOR[item.risk_category]}`}>
                  {item.risk_score} ({item.risk_category})
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">Priority:</span>
                <p className="font-medium">{c.priority}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Assigned to:</span>
                <p className="font-medium">{c.assigned_to || "Unassigned"}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Created:</span>
                <p>{new Date(c.created_at).toLocaleString()}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Created by:</span>
                <p>{c.created_by}</p>
              </div>
            </div>

            {c.summary && (
              <div>
                <span className="text-sm text-muted-foreground">Summary</span>
                <p className="text-sm mt-1">{c.summary}</p>
              </div>
            )}

            {c.decision && (
              <Card className="border-emerald-200 bg-emerald-50">
                <CardContent className="p-3">
                  <p className="text-sm font-medium text-emerald-800">Decision</p>
                  <p className="text-sm text-emerald-700 mt-1">{c.decision}</p>
                </CardContent>
              </Card>
            )}

            {/* Status transitions */}
            {nextStatuses[c.status].length > 0 && (
              <div>
                <span className="text-sm text-muted-foreground">
                  Transition to:
                </span>
                <div className="flex gap-2 mt-1">
                  {nextStatuses[c.status].map((s) => (
                    <Button
                      key={s}
                      variant="outline"
                      size="sm"
                      onClick={() => onStatusChange(c.id, s)}
                      className="text-xs"
                    >
                      {STATUS_CONFIG[s].icon}
                      <span className="ml-1">{STATUS_CONFIG[s].label}</span>
                    </Button>
                  ))}
                </div>
              </div>
            )}

            <Separator />

            {/* Notes */}
            <div>
              <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
                <MessageSquarePlus size={16} />
                Investigation Notes ({c.notes.length})
              </h3>

              {/* Add note form */}
              <div className="space-y-2 mb-4">
                <div className="flex gap-2">
                  {(
                    Object.keys(NOTE_TYPE_LABELS) as NoteType[]
                  ).map((t) => (
                    <button
                      key={t}
                      onClick={() => setNoteType(t)}
                      className={`text-xs px-2 py-1 rounded-md border transition-colors ${
                        noteType === t
                          ? "bg-primary text-primary-foreground border-primary"
                          : "border-border hover:bg-muted"
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
                    className="flex-1 text-sm rounded-md border border-border bg-background px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                  <Button
                    size="sm"
                    onClick={handleSubmitNote}
                    disabled={!noteContent.trim() || submitting}
                    className="self-end"
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
                <p className="text-sm text-muted-foreground text-center py-4">
                  No notes yet
                </p>
              ) : (
                <div className="space-y-2">
                  {c.notes.map((note) => (
                    <div
                      key={note.id}
                      className="border rounded-md p-3 text-sm"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-xs">
                            {NOTE_TYPE_LABELS[note.note_type]}
                          </Badge>
                          <span className="text-muted-foreground">
                            {note.author}
                          </span>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {new Date(note.created_at).toLocaleString()}
                        </span>
                      </div>
                      <p className="mt-1">{note.content}</p>
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
