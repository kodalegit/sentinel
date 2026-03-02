/**
 * Case Detail Page — full investigation view with timeline, evidence, and decision recording.
 */

"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getCaseDetail,
  getCaseTimeline,
  getCaseEvidence,
  updateCase,
  addCaseNote,
  selfAssignCase,
  recordDecision,
  getAssignableUsers,
} from "@/lib/api";
import { CaseChat } from "@/components/CaseChat";
import { AuthGuard } from "@/components/AuthGuard";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Loader2,
  ArrowLeft,
  Clock,
  User,
  FileText,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ArrowUpRight,
  Search,
  FolderOpen,
  MessageSquarePlus,
  Send,
  Link2,
  Gavel,
  UserPlus,
} from "lucide-react";
import type {
  CaseWithTender,
  CaseStatus,
  CaseEvent,
  CaseEvidenceLink,
  NoteType,
  RiskCategory,
  DecisionType,
} from "@/lib/types";

const STATUS_CONFIG: Record<CaseStatus, { label: string; color: string; icon: React.ReactNode }> = {
  OPEN: { label: "Open", color: "bg-[#35638c]", icon: <FolderOpen size={14} /> },
  INVESTIGATING: { label: "Investigating", color: "bg-[#b78b43]", icon: <Search size={14} /> },
  ESCALATED: { label: "Escalated", color: "bg-[#c4412f]", icon: <ArrowUpRight size={14} /> },
  RESOLVED: { label: "Resolved", color: "bg-[#1f6f5c]", icon: <CheckCircle2 size={14} /> },
  DISMISSED: { label: "Dismissed", color: "bg-[#8a8580]", icon: <XCircle size={14} /> },
};

const PRIORITY_COLOR: Record<RiskCategory, string> = {
  HIGH: "text-[#c4412f]",
  MEDIUM: "text-[#b78b43]",
  LOW: "text-[#1f6f5c]",
};

const EVENT_LABELS: Record<string, string> = {
  CASE_OPENED: "Case Opened",
  STATUS_CHANGE: "Status Changed",
  ASSIGNMENT: "Assignment Changed",
  NOTE_ADDED: "Note Added",
  PRIORITY_CHANGE: "Priority Changed",
  DECISION_RECORDED: "Decision Recorded",
  EVIDENCE_LINKED: "Evidence Linked",
  EVIDENCE_UNLINKED: "Evidence Removed",
};

const NOTE_TYPE_LABELS: Record<NoteType, string> = {
  OBSERVATION: "Observation",
  EVIDENCE: "Evidence",
  DECISION: "Decision",
  ACTION: "Action",
};

const DECISION_TYPE_LABELS: Record<DecisionType, string> = {
  SUBSTANTIATED: "Substantiated",
  UNSUBSTANTIATED: "Unsubstantiated",
  REFERRED: "Referred",
  INCONCLUSIVE: "Inconclusive",
};

function CaseDetailContent() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, isSupervisorOrAdmin } = useAuth();
  const caseId = params.id as string;

  const [noteContent, setNoteContent] = useState("");
  const [noteType, setNoteType] = useState<NoteType>("OBSERVATION");
  const [submitting, setSubmitting] = useState(false);

  // Decision form state
  const [showDecisionForm, setShowDecisionForm] = useState(false);
  const [decisionType, setDecisionType] = useState<DecisionType>("SUBSTANTIATED");
  const [finding, setFinding] = useState("");
  const [recommendation, setRecommendation] = useState("");

  // Queries
  const { data: caseData, isLoading: caseLoading } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => getCaseDetail(caseId),
  });

  const { data: timeline = [] } = useQuery({
    queryKey: ["case-timeline", caseId],
    queryFn: () => getCaseTimeline(caseId),
    enabled: !!caseId,
  });

  const { data: evidence = [] } = useQuery({
    queryKey: ["case-evidence", caseId],
    queryFn: () => getCaseEvidence(caseId),
    enabled: !!caseId,
  });

  const { data: assignableUsers = [] } = useQuery({
    queryKey: ["assignable-users"],
    queryFn: getAssignableUsers,
    enabled: isSupervisorOrAdmin,
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["case", caseId] });
    queryClient.invalidateQueries({ queryKey: ["case-timeline", caseId] });
    queryClient.invalidateQueries({ queryKey: ["case-evidence", caseId] });
    queryClient.invalidateQueries({ queryKey: ["cases"] });
  };

  const handleStatusChange = async (newStatus: CaseStatus) => {
    setSubmitting(true);
    try {
      await updateCase(caseId, { status: newStatus });
      invalidateAll();
    } finally {
      setSubmitting(false);
    }
  };

  const handleAssign = async (userId: string) => {
    setSubmitting(true);
    try {
      await updateCase(caseId, { assigned_to_id: userId });
      invalidateAll();
    } finally {
      setSubmitting(false);
    }
  };

  const handleSelfAssign = async () => {
    setSubmitting(true);
    try {
      await selfAssignCase(caseId);
      invalidateAll();
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddNote = async () => {
    if (!noteContent.trim()) return;
    setSubmitting(true);
    try {
      await addCaseNote(caseId, { content: noteContent.trim(), note_type: noteType });
      setNoteContent("");
      invalidateAll();
    } finally {
      setSubmitting(false);
    }
  };

  const handleRecordDecision = async () => {
    if (!finding.trim()) return;
    setSubmitting(true);
    try {
      await recordDecision(caseId, {
        decision_type: decisionType,
        finding: finding.trim(),
        recommendation: recommendation.trim() || undefined,
        evidence_references: evidence.map((e) => e.id),
      });
      setShowDecisionForm(false);
      setFinding("");
      setRecommendation("");
      invalidateAll();
    } finally {
      setSubmitting(false);
    }
  };

  if (caseLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <p className="text-muted-foreground">Case not found</p>
        <Button variant="outline" onClick={() => router.push("/cases")}>
          Back to Cases
        </Button>
      </div>
    );
  }

  const c = caseData.case;
  const statusCfg = STATUS_CONFIG[c.status];
  const canSelfAssign = !c.assigned_to_id && c.status === "OPEN";
  const canRecordDecision = c.status === "INVESTIGATING" || c.status === "ESCALATED";

  const nextStatuses: Record<CaseStatus, CaseStatus[]> = {
    OPEN: ["INVESTIGATING", "DISMISSED"],
    INVESTIGATING: ["ESCALATED", "RESOLVED", "DISMISSED"],
    ESCALATED: ["RESOLVED", "INVESTIGATING"],
    RESOLVED: [],
    DISMISSED: ["OPEN"],
  };

  return (
    <div className="min-h-screen pb-12">
      {/* Header */}
      <header className="border-b border-border/70 bg-card/70 backdrop-blur-sm sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 lg:px-10 py-4">
          <button
            onClick={() => router.push("/cases")}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-3 transition-colors"
          >
            <ArrowLeft size={16} />
            Back to Cases
          </button>
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-2">
                <Badge className={`${statusCfg.color} text-white`}>
                  {statusCfg.icon}
                  <span className="ml-1">{statusCfg.label}</span>
                </Badge>
                <span className={`text-sm font-semibold ${PRIORITY_COLOR[c.priority]}`}>
                  {c.priority} Priority
                </span>
              </div>
              <h1 className="font-display text-2xl text-foreground truncate">{c.title}</h1>
              <p className="text-sm text-muted-foreground mt-1">{caseData.tender_title}</p>
            </div>
            <div className="text-right shrink-0">
              <p className={`font-display text-3xl ${PRIORITY_COLOR[caseData.risk_category]}`}>
                {caseData.risk_score}
              </p>
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Risk Score</p>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 lg:px-10 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Evidence Panel */}
            <section className="rounded-2xl border border-border/70 bg-card p-5">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
                <Link2 size={16} />
                Linked Evidence ({evidence.length})
              </h2>
              {evidence.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-6">No evidence linked</p>
              ) : (
                <div className="space-y-2">
                  {evidence.map((e) => (
                    <div
                      key={e.id}
                      className="rounded-lg border border-border/50 bg-muted/20 p-3 text-sm"
                    >
                      <div className="flex items-center justify-between">
                        <Badge variant="outline" className="text-xs">
                          {e.evidence_type}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {new Date(e.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <p className="mt-1 text-foreground/90">{e.label}</p>
                      {e.link_metadata && (
                        <p className="text-xs text-muted-foreground mt-1">
                          {e.evidence_type === "RISK_FACTOR" && e.link_metadata.description
                            ? String(e.link_metadata.description)
                            : null}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Timeline */}
            <section className="rounded-2xl border border-border/70 bg-card p-5">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
                <Clock size={16} />
                Activity Timeline ({timeline.length})
              </h2>
              <ScrollArea className="max-h-[400px]">
                {timeline.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-6">No activity yet</p>
                ) : (
                  <div className="space-y-3">
                    {timeline.map((event) => (
                      <TimelineEvent key={event.id} event={event} />
                    ))}
                  </div>
                )}
              </ScrollArea>
            </section>

            {/* Notes Section */}
            <section className="rounded-2xl border border-border/70 bg-card p-5">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
                <MessageSquarePlus size={16} />
                Investigation Notes ({c.notes.length})
              </h2>

              {/* Add note form */}
              <div className="space-y-2 mb-4">
                <div className="flex gap-1.5 flex-wrap">
                  {(Object.keys(NOTE_TYPE_LABELS) as NoteType[]).map((t) => (
                    <button
                      key={t}
                      onClick={() => setNoteType(t)}
                      className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
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
                    className="flex-1 text-sm rounded-xl border border-border/50 bg-secondary/50 px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <Button
                    size="sm"
                    onClick={handleAddNote}
                    disabled={!noteContent.trim() || submitting}
                    className="self-end h-8"
                  >
                    {submitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                  </Button>
                </div>
              </div>

              {/* Notes list */}
              {c.notes.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">No notes yet</p>
              ) : (
                <div className="space-y-2">
                  {c.notes.map((note) => (
                    <div
                      key={note.id}
                      className="rounded-lg border border-border/40 bg-muted/20 p-3 text-sm"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-xs">
                            {NOTE_TYPE_LABELS[note.note_type]}
                          </Badge>
                          <span className="text-xs text-muted-foreground">{note.author}</span>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {new Date(note.created_at).toLocaleString()}
                        </span>
                      </div>
                      <p className="mt-1 text-foreground/80">{note.content}</p>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* AI Assistant Chat */}
            <section className="rounded-2xl border border-border/70 bg-card overflow-hidden">
              <CaseChat caseId={caseId} />
            </section>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Case Meta */}
            <section className="rounded-2xl border border-border/70 bg-card p-5">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4">
                Case Details
              </h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Created</span>
                  <span>{new Date(c.created_at).toLocaleDateString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Created by</span>
                  <span>{c.created_by}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Assigned to</span>
                  <span>{c.assigned_to || "Unassigned"}</span>
                </div>
                {c.closed_at && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Closed</span>
                    <span>{new Date(c.closed_at).toLocaleDateString()}</span>
                  </div>
                )}
              </div>
            </section>

            {/* Assignment */}
            {(canSelfAssign || isSupervisorOrAdmin) && (
              <section className="rounded-2xl border border-border/70 bg-card p-5">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
                  <UserPlus size={16} />
                  Assignment
                </h3>
                {canSelfAssign && (
                  <Button
                    onClick={handleSelfAssign}
                    disabled={submitting}
                    className="w-full mb-3"
                    variant="outline"
                  >
                    {submitting ? <Loader2 size={14} className="animate-spin mr-2" /> : null}
                    Pick Up Case
                  </Button>
                )}
                {isSupervisorOrAdmin && (
                  <Select onValueChange={handleAssign} value={c.assigned_to_id || ""}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Assign to..." />
                    </SelectTrigger>
                    <SelectContent>
                      {assignableUsers.map((u) => (
                        <SelectItem key={u.id} value={u.id}>
                          {u.full_name} ({u.role})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </section>
            )}

            {/* Status Transitions */}
            {nextStatuses[c.status].length > 0 && (
              <section className="rounded-2xl border border-border/70 bg-card p-5">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4">
                  Transition Status
                </h3>
                <div className="flex flex-col gap-2">
                  {nextStatuses[c.status]
                    .filter((s) => s !== "DISMISSED" || isSupervisorOrAdmin)
                    .map((s) => (
                      <Button
                        key={s}
                        variant="outline"
                        size="sm"
                        onClick={() => handleStatusChange(s)}
                        disabled={submitting}
                        className="justify-start"
                      >
                        {STATUS_CONFIG[s].icon}
                        <span className="ml-2">{STATUS_CONFIG[s].label}</span>
                      </Button>
                    ))}
                </div>
              </section>
            )}

            {/* Decision Recording */}
            {canRecordDecision && (
              <section className="rounded-2xl border border-border/70 bg-card p-5">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
                  <Gavel size={16} />
                  Record Decision
                </h3>
                {c.decision_type ? (
                  <div className="space-y-2">
                    <Badge className="bg-[#1f6f5c] text-white">
                      {DECISION_TYPE_LABELS[c.decision_type as DecisionType]}
                    </Badge>
                    <p className="text-sm text-foreground/80">{c.finding}</p>
                    {c.decision && (
                      <p className="text-xs text-muted-foreground">{c.decision}</p>
                    )}
                  </div>
                ) : showDecisionForm ? (
                  <div className="space-y-3">
                    <Select
                      value={decisionType}
                      onValueChange={(v) => setDecisionType(v as DecisionType)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(Object.keys(DECISION_TYPE_LABELS) as DecisionType[]).map((dt) => (
                          <SelectItem key={dt} value={dt}>
                            {DECISION_TYPE_LABELS[dt]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <textarea
                      value={finding}
                      onChange={(e) => setFinding(e.target.value)}
                      placeholder="Finding..."
                      rows={3}
                      className="w-full text-sm rounded-lg border border-border/50 bg-secondary/50 px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                    />
                    <textarea
                      value={recommendation}
                      onChange={(e) => setRecommendation(e.target.value)}
                      placeholder="Recommendation (optional)..."
                      rows={2}
                      className="w-full text-sm rounded-lg border border-border/50 bg-secondary/50 px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={handleRecordDecision}
                        disabled={!finding.trim() || submitting}
                        className="flex-1"
                      >
                        {submitting ? <Loader2 size={14} className="animate-spin" /> : "Save"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setShowDecisionForm(false)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowDecisionForm(true)}
                    className="w-full"
                  >
                    <Gavel size={14} className="mr-2" />
                    Record Decision
                  </Button>
                )}
              </section>
            )}

            {/* Summary */}
            {c.summary && (
              <section className="rounded-2xl border border-border/70 bg-card p-5">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                  Summary
                </h3>
                <p className="text-sm text-foreground/80">{c.summary}</p>
              </section>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function TimelineEvent({ event }: { event: CaseEvent }) {
  const getEventIcon = () => {
    switch (event.event_type) {
      case "CASE_OPENED":
        return <FolderOpen size={14} />;
      case "STATUS_CHANGE":
        return <ArrowUpRight size={14} />;
      case "ASSIGNMENT":
        return <User size={14} />;
      case "NOTE_ADDED":
        return <FileText size={14} />;
      case "PRIORITY_CHANGE":
        return <AlertTriangle size={14} />;
      case "DECISION_RECORDED":
        return <Gavel size={14} />;
      case "EVIDENCE_LINKED":
      case "EVIDENCE_UNLINKED":
        return <Link2 size={14} />;
      default:
        return <Clock size={14} />;
    }
  };

  const getEventDescription = () => {
    switch (event.event_type) {
      case "STATUS_CHANGE":
        return `${event.old_value} → ${event.new_value}`;
      case "PRIORITY_CHANGE":
        return `${event.old_value} → ${event.new_value}`;
      case "ASSIGNMENT":
        return event.new_value ? "Assigned" : "Unassigned";
      case "NOTE_ADDED":
        return `${event.new_value} note`;
      case "EVIDENCE_LINKED":
        return event.new_value;
      case "EVIDENCE_UNLINKED":
        return `Removed: ${event.old_value}`;
      case "DECISION_RECORDED":
        return event.new_value;
      default:
        return event.new_value || "";
    }
  };

  return (
    <div className="flex gap-3 text-sm">
      <div className="shrink-0 w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground">
        {getEventIcon()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="font-medium text-foreground">
            {EVENT_LABELS[event.event_type] || event.event_type}
          </span>
          <span className="text-xs text-muted-foreground shrink-0">
            {new Date(event.created_at).toLocaleString()}
          </span>
        </div>
        <p className="text-muted-foreground text-xs mt-0.5">
          {getEventDescription()} • by {event.actor}
        </p>
      </div>
    </div>
  );
}

export default function CaseDetailPage() {
  return (
    <AuthGuard>
      <CaseDetailContent />
    </AuthGuard>
  );
}
