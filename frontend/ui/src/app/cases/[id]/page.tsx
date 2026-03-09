/**
 * Case Detail Page — full investigation view with timeline, evidence, and decision recording.
 * Redesigned for a chat-first, side-by-side industrial analyst dashboard UI.
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
  Link2,
  Gavel,
  PanelLeft,
  Settings2,
  ShieldAlert,
  Menu,
} from "lucide-react";
import type {
  CaseStatus,
  CaseEvent,
  NoteType,
  RiskCategory,
  DecisionType,
} from "@/lib/types";

const STATUS_CONFIG: Record<CaseStatus, { label: string; color: string; icon: React.ReactNode }> = {
  OPEN: { label: "OPEN", color: "bg-sky-500/10 text-sky-500 border border-sky-500/20", icon: <FolderOpen size={12} /> },
  INVESTIGATING: { label: "INVESTIGATING", color: "bg-amber-500/10 text-amber-500 border border-amber-500/20", icon: <Search size={12} /> },
  ESCALATED: { label: "ESCALATED", color: "bg-rose-500/10 text-rose-500 border border-rose-500/20", icon: <ArrowUpRight size={12} /> },
  RESOLVED: { label: "RESOLVED", color: "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20", icon: <CheckCircle2 size={12} /> },
  DISMISSED: { label: "DISMISSED", color: "bg-muted text-muted-foreground border border-border", icon: <XCircle size={12} /> },
};

const PRIORITY_COLOR: Record<RiskCategory, string> = {
  HIGH: "text-rose-500",
  MEDIUM: "text-amber-500",
  LOW: "text-emerald-500",
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
  OBSERVATION: "OBSERVATION",
  EVIDENCE: "EVIDENCE",
  DECISION: "DECISION",
  ACTION: "ACTION",
};

const DECISION_TYPE_LABELS: Record<DecisionType, string> = {
  SUBSTANTIATED: "SUBSTANTIATED",
  UNSUBSTANTIATED: "UNSUBSTANTIATED",
  REFERRED: "REFERRED",
  INCONCLUSIVE: "INCONCLUSIVE",
};

type TabId = "overview" | "evidence" | "timeline" | "notes";

function CaseDetailContent() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isSupervisorOrAdmin, user } = useAuth();
  const caseId = params.id as string;

  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [noteContent, setNoteContent] = useState("");
  const [noteType, setNoteType] = useState<NoteType>("OBSERVATION");
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

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
    setActionError(null);
    try {
      await updateCase(caseId, { status: newStatus });
      invalidateAll();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Failed to update case status.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleAssign = async (userId: string) => {
    setSubmitting(true);
    setActionError(null);
    try {
      await updateCase(caseId, {
        assigned_to_id: userId === "unassigned" ? null : userId,
      });
      invalidateAll();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Failed to update assignment.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddNote = async () => {
    if (!noteContent.trim()) return;
    setSubmitting(true);
    setActionError(null);
    try {
      await addCaseNote(caseId, { content: noteContent.trim(), note_type: noteType });
      setNoteContent("");
      invalidateAll();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Failed to add note.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRecordDecision = async () => {
    if (!finding.trim()) return;
    setSubmitting(true);
    setActionError(null);
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
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Failed to record decision.");
    } finally {
      setSubmitting(false);
    }
  };

  if (caseLoading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4 text-primary">
          <Loader2 className="w-12 h-12 animate-spin" />
          <p className="font-mono text-sm tracking-widest uppercase text-muted-foreground animate-pulse">Initializing Interface...</p>
        </div>
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4 max-w-sm text-center">
          <ShieldAlert className="w-12 h-12 text-destructive mb-2 opacity-80" />
          <h1 className="text-xl font-semibold tracking-tight">Case Not Found</h1>
          <p className="text-sm text-muted-foreground">The investigation record you are looking for has been removed or is inaccessible.</p>
          <Button variant="outline" className="mt-4" onClick={() => router.push("/cases")}>
            <ArrowLeft className="mr-2 h-4 w-4" /> Return to Database
          </Button>
        </div>
      </div>
    );
  }

  const c = caseData.case;
  const statusCfg = STATUS_CONFIG[c.status];
  const isAssignedInvestigator = user?.id === c.assigned_to_id;
  const canAddNote = isSupervisorOrAdmin || isAssignedInvestigator;
  const canTransitionCase = isSupervisorOrAdmin || isAssignedInvestigator;
  const canRecordDecision =
    isSupervisorOrAdmin &&
    (c.status === "INVESTIGATING" || c.status === "ESCALATED");
  const assignmentValue = c.assigned_to_id ?? "unassigned";

  const nextStatuses: Record<CaseStatus, CaseStatus[]> = {
    OPEN: ["INVESTIGATING", "DISMISSED"],
    INVESTIGATING: ["ESCALATED", "RESOLVED", "DISMISSED"],
    ESCALATED: ["RESOLVED", "INVESTIGATING"],
    RESOLVED: [],
    DISMISSED: ["OPEN"],
  };
  const availableNextStatuses = nextStatuses[c.status].filter(
    (status) => isSupervisorOrAdmin || status === "ESCALATED" || status === "RESOLVED",
  );

  return (
    <div className="flex flex-col h-dvh bg-background text-foreground overflow-hidden selection:bg-primary/30">
      
      {/* Top Application Bar */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border/60 bg-card/40 px-4 md:px-6 backdrop-blur-md z-30">
        <div className="flex items-center gap-4 min-w-0">
          <Button 
            variant="ghost" 
            size="icon" 
            className="h-8 w-8 text-muted-foreground hover:text-foreground shrink-0 rounded-md bg-muted/50" 
            onClick={() => router.push("/cases")}
            title="Back to Database"
          >
            <ArrowLeft size={16} />
          </Button>
          
          <div className="h-4 w-px bg-border/80 hidden sm:block"></div>

          <div className="flex items-center gap-3 overflow-hidden">
            <span className={`flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-mono tracking-widest uppercase font-semibold ${statusCfg.color} rounded`}>
              {statusCfg.icon}
              {statusCfg.label}
            </span>
            <span className={`text-[10px] font-mono font-bold tracking-widest px-2 py-1 rounded bg-muted/40 uppercase items-center flex border border-border/40 ${PRIORITY_COLOR[c.priority]}`}>
              <ShieldAlert className="w-3 h-3 mr-1.5 opacity-70" /> {c.priority} RISK
            </span>
            <h1 className="text-sm font-semibold truncate max-w-xs md:max-w-xl text-foreground/90 pl-1">{c.title}</h1>
          </div>
        </div>

        <div className="flex items-center gap-4 shrink-0">
          <div className="hidden sm:flex flex-col items-end mr-2">
            <div className="flex items-baseline gap-1.5">
              <span className={`text-xl font-bold font-mono tracking-tight leading-none ${PRIORITY_COLOR[caseData.risk_category]}`}>
                {caseData.risk_score}
              </span>
              <span className="text-[10px] font-mono tracking-widest text-muted-foreground uppercase leading-none">Score</span>
            </div>
          </div>
          <Button 
            variant="outline" 
            size="sm" 
            className="lg:hidden h-8"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            <Menu className="h-4 w-4 mr-2" />
            <span className="text-[10px] font-mono tracking-widest">CONTEXT</span>
          </Button>
        </div>
      </header>

      {/* Main Workspace */}
      <div className="flex flex-1 min-h-0 overflow-hidden relative">
        
        {/* Left Context Sidebar */}
        <div className={`
          absolute lg:relative z-20 h-full w-full sm:w-[380px] lg:w-[420px] 
          bg-card/95 lg:bg-card/30 border-r border-border/50 shadow-2xl lg:shadow-none 
          transition-transform duration-300 ease-out select-none flex flex-col shrink-0
          backdrop-blur-xl lg:backdrop-blur-none
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}>
          {/* Active Tab Content Area */}
          <ScrollArea className="flex-1 w-full" type="scroll">
            <div className="p-5 lg:p-6 space-y-8 select-text">
              
              {/* TAB CONTENT: OVERVIEW */}
              <div className={activeTab === "overview" ? "block" : "hidden"}>
                 <div className="space-y-6">
                   {/* Meta Details */}
                   <section>
                      <h3 className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-4 font-semibold">
                         <Settings2 className="w-3 h-3"/> CORE METADATA
                      </h3>
                      <div className="grid grid-cols-2 gap-y-4 gap-x-2 text-sm bg-muted/20 p-4 rounded-lg border border-border/30">
                        <div>
                          <p className="text-[10px] font-mono text-muted-foreground uppercase opacity-70 mb-1">Created By</p>
                          <p className="font-medium truncate" title={c.created_by}>{c.created_by}</p>
                        </div>
                        <div>
                          <p className="text-[10px] font-mono text-muted-foreground uppercase opacity-70 mb-1">Date Logged</p>
                          <p className="font-mono text-[13px]">{new Date(c.created_at).toLocaleDateString()}</p>
                        </div>
                        <div className="col-span-2">
                          <p className="text-[10px] font-mono text-muted-foreground uppercase opacity-70 mb-1">Subject Tender</p>
                          <p className="font-medium text-[13px] line-clamp-2 leading-relaxed opacity-90">{caseData.tender_title}</p>
                        </div>
                        <div className="col-span-2 pt-2 border-t border-border/30">
                          <p className="text-[10px] font-mono text-muted-foreground uppercase opacity-70 mb-1">Assigned Investigator</p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="font-medium truncate">{c.assigned_to || "UNASSIGNED"}</span>
                          </div>
                        </div>
                      </div>
                   </section>

                   {/* Case Summary */}
                   {c.summary && (
                     <section>
                       <h3 className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-3 font-semibold">
                         EXECUTIVE SUMMARY
                       </h3>
                       <div className="p-4 rounded-lg bg-card border border-border/60 text-[13px] leading-relaxed text-foreground/80 shadow-sm relative overflow-hidden">
                         <div className="absolute top-0 left-0 w-1 h-full bg-primary/40"></div>
                         {c.summary}
                       </div>
                     </section>
                   )}

                   {/* Actions Group (Record Decision, Transition, Assign) */}
                   <section className="space-y-4 pt-4 border-t border-border/40">
                     <h3 className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-3 font-semibold">
                       INVESTIGATION ACTIONS
                     </h3>

                     {actionError && (
                       <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-[11px] text-destructive">
                         {actionError}
                       </div>
                     )}
                     
                     {/* Assignment Action */}
                     {isSupervisorOrAdmin && (
                        <div className="space-y-2">
                          <label className="text-[10px] font-mono text-muted-foreground uppercase">Personnel Assignment</label>
                          <Select onValueChange={handleAssign} value={assignmentValue}>
                            <SelectTrigger className="w-full h-9 text-xs font-medium">
                              <SelectValue placeholder="Select investigator..." />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="unassigned" className="text-xs">
                                <span className="font-mono text-[10px] opacity-60 mr-2 w-16 inline-block">queue</span> Unassigned Queue
                              </SelectItem>
                              {assignableUsers.map((u) => (
                                <SelectItem key={u.id} value={u.id} className="text-xs">
                                  <span className="font-mono text-[10px] opacity-60 mr-2 w-16 inline-block">{u.role}</span> {u.full_name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                     )}

                     {/* Status Transitions Action */}
                     {canTransitionCase && availableNextStatuses.length > 0 && (
                        <div className="space-y-2 pt-2">
                           <label className="text-[10px] font-mono text-muted-foreground uppercase mb-1 block">Transition Case Status</label>
                           <div className="flex flex-wrap gap-2">
                             {availableNextStatuses.map((s) => (
                                 <Button
                                   key={s}
                                   variant="outline"
                                   size="sm"
                                   onClick={() => handleStatusChange(s)}
                                   disabled={submitting}
                                   className={`h-8 text-[11px] font-mono tracking-wide bg-background hover:bg-muted border-border flex-1 ${STATUS_CONFIG[s].color.split(" ")[1]}`}
                                 >
                                   {STATUS_CONFIG[s].icon}
                                   <span className="ml-2">{STATUS_CONFIG[s].label}</span>
                                 </Button>
                               ))}
                           </div>
                        </div>
                     )}

                     {/* Decision Recording */}
                     {canRecordDecision && (
                       <div className="pt-2">
                         <label className="text-[10px] font-mono text-muted-foreground uppercase mb-2 block">Formal Decision</label>
                        {c.decision_type ? (
                           <div className="p-4 rounded-lg border border-border/50 bg-secondary/20 space-y-3">
                             <div className="flex items-center gap-2">
                               <Gavel size={14} className="text-primary"/>
                               <Badge variant="outline" className="text-[10px] font-mono border-primary text-primary tracking-widest bg-primary/5 uppercase rouded-sm px-1.5 h-6">
                                 {DECISION_TYPE_LABELS[c.decision_type as DecisionType]}
                               </Badge>
                             </div>
                             <p className="text-[13px] text-foreground/90 italic border-l-2 border-primary/30 pl-3">&quot;{c.finding}&quot;</p>
                             {c.decision && <p className="text-[11px] text-muted-foreground mt-2">{c.decision}</p>}
                           </div>
                         ) : showDecisionForm ? (
                           <div className="p-4 rounded-lg border border-border/80 bg-card space-y-3 shadow-sm animate-in fade-in slide-in-from-top-2">
                             <h4 className="flex items-center gap-2 text-xs font-mono font-medium tracking-wide mb-1"><Gavel size={14}/> RECORD DECISION</h4>
                             <Select value={decisionType} onValueChange={(v) => setDecisionType(v as DecisionType)}>
                               <SelectTrigger className="h-9 text-xs">
                                 <SelectValue />
                               </SelectTrigger>
                               <SelectContent>
                                 {(Object.keys(DECISION_TYPE_LABELS) as DecisionType[]).map((dt) => (
                                   <SelectItem key={dt} value={dt} className="text-xs font-mono">{DECISION_TYPE_LABELS[dt]}</SelectItem>
                                 ))}
                               </SelectContent>
                             </Select>
                             <textarea
                               value={finding}
                               onChange={(e) => setFinding(e.target.value)}
                               placeholder="Enter formalized findings..."
                               rows={3}
                               className="w-full text-xs rounded-md border border-input bg-background px-3 py-2 resize-none placeholder:opacity-50 focus:outline-none focus:ring-1 focus:ring-primary shadow-sm"
                             />
                             <textarea
                               value={recommendation}
                               onChange={(e) => setRecommendation(e.target.value)}
                               placeholder="Actions/Recommendations (Optional)..."
                               rows={2}
                               className="w-full text-xs rounded-md border border-input bg-background px-3 py-2 resize-none placeholder:opacity-50 focus:outline-none focus:ring-1 focus:ring-primary shadow-sm"
                             />
                             <div className="flex items-center justify-end gap-2 pt-1 border-t border-border/50">
                               <Button size="sm" variant="ghost" className="h-8 text-xs px-3" onClick={() => setShowDecisionForm(false)}>
                                 Cancel
                               </Button>
                               <Button size="sm" className="h-8 text-xs px-4" onClick={handleRecordDecision} disabled={!finding.trim() || submitting}>
                                 {submitting ? <Loader2 size={12} className="animate-spin" /> : "Save to Ledger"}
                               </Button>
                             </div>
                           </div>
                         ) : (
                           <Button variant="outline" size="sm" onClick={() => setShowDecisionForm(true)} className="w-full h-10 border-dashed border-border hover:bg-muted text-xs font-medium bg-transparent">
                             <Gavel size={14} className="mr-2 mb-0.5 text-muted-foreground" />
                             INITIATE FINAL DECISION ENTRY
                           </Button>
                         )}
                       </div>
                     )}
                   </section>
                 </div>
              </div>

              {/* TAB CONTENT: EVIDENCE */}
              <div className={activeTab === "evidence" ? "block" : "hidden"}>
                <h3 className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-4 font-semibold">
                   Linked Source Data <span className="opacity-50 ml-auto">({evidence.length})</span>
                </h3>
                {evidence.length === 0 ? (
                  <div className="border border-dashed border-border/60 rounded-lg p-8 flex flex-col items-center justify-center text-center opacity-60 bg-muted/20">
                    <Link2 size={24} className="mb-3 text-muted-foreground" />
                    <p className="text-sm font-medium">No Evidentiary Links</p>
                    <p className="text-xs text-muted-foreground mt-1 max-w-[200px]">Use the AI to discover and link documents to this case.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {evidence.map((e) => (
                      <div key={e.id} className="relative group rounded-md border border-border/50 bg-card p-4 hover:border-primary/30 transition-colors shadow-sm overflow-hidden">
                        <div className="absolute top-0 left-0 w-1 h-full bg-border/50 group-hover:bg-primary/50 transition-colors"></div>
                        <div className="flex items-center justify-between pl-2 mb-2">
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 rounded text-[9px] font-mono tracking-widest font-bold uppercase bg-muted/60 text-foreground border border-border">
                              {e.evidence_type}
                            </span>
                            {e.link_metadata && typeof e.link_metadata === 'object' && 'protected' in e.link_metadata && e.link_metadata.protected ? (
                              <span className="px-2 py-0.5 rounded text-[9px] font-mono tracking-widest uppercase border border-border/60 text-muted-foreground">
                                baseline
                              </span>
                            ) : null}
                          </div>
                          <span className="text-[10px] font-mono text-muted-foreground opacity-70">
                            {new Date(e.created_at).toLocaleDateString()}
                          </span>
                        </div>
                        <p className="text-[13px] font-medium leading-snug pl-2">{e.label}</p>
                        <p className="mt-2 pl-2 text-[10px] font-mono text-muted-foreground break-all">Ref: {e.reference_id}</p>
                        {e.link_metadata && typeof e.link_metadata === 'object' && 'description' in e.link_metadata && e.evidence_type === "RISK_FACTOR" && e.link_metadata.description ? (
                          <div className="mt-3 pl-2 text-xs text-muted-foreground bg-muted/30 p-2 rounded border border-border/40">
                            {String(e.link_metadata.description)}
                          </div>
                        ) : null}
                        {e.evidence_type === "TENDER" && (
                          <div className="mt-3 pl-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-0 text-[11px]"
                              onClick={() => router.push(`/tenders/${e.reference_id}`)}
                            >
                              View tender details
                            </Button>
                          </div>
                        )}
                        {e.link_metadata && typeof e.link_metadata === 'object' && 'source_url' in e.link_metadata && typeof e.link_metadata.source_url === 'string' && e.link_metadata.source_url ? (
                          <div className="mt-2 pl-2">
                            <a
                              href={e.link_metadata.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[11px] text-primary hover:underline"
                            >
                              Open source document
                            </a>
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* TAB CONTENT: TIMELINE */}
              <div className={activeTab === "timeline" ? "block" : "hidden"}>
                 <h3 className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-6 font-semibold">
                   Immutable Audit Trail <span className="opacity-50 ml-auto">({timeline.length})</span>
                 </h3>
                 <div className="relative pl-2.5">
                   <div className="absolute left-6 top-1 bottom-1 w-px bg-border/60"></div>
                   {timeline.length === 0 ? (
                      <p className="text-xs text-muted-foreground">No events recorded yet.</p>
                   ) : (
                      <div className="space-y-6">
                        {timeline.map((event) => (
                          <div key={event.id} className="relative flex gap-4 pr-1">
                            <div className="w-8 h-8 rounded-full bg-card border border-border flex items-center justify-center shrink-0 z-10 shadow-sm text-muted-foreground mt-0.5">
                                <TimelineEventIcon type={event.event_type} />
                            </div>
                            <div className="flex-1 min-w-0 pt-1">
                              <div className="flex justify-between items-baseline mb-1">
                                <span className="text-[12px] font-medium uppercase tracking-wide font-mono">
                                  {EVENT_LABELS[event.event_type] || event.event_type}
                                </span>
                                <span className="text-[10px] font-mono text-muted-foreground opacity-80 whitespace-nowrap ml-2">
                                  {new Date(event.created_at).toLocaleString([], { hour12: false, month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' })}
                                </span>
                              </div>
                              <p className="text-xs text-muted-foreground/90 leading-relaxed max-w-[95%]">
                                <TimelineEventDescription event={event} /> 
                                <span className="block mt-1 font-mono text-[9px] uppercase tracking-widest opacity-50">Auth: {event.actor}</span>
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                   )}
                 </div>
              </div>

              {/* TAB CONTENT: NOTES */}
              <div className={activeTab === "notes" ? "block" : "hidden"}>
                 <div className="flex items-center justify-between mb-4">
                   <h3 className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-muted-foreground font-semibold">
                     Analyst Notebook <span className="opacity-50">({c.notes.length})</span>
                   </h3>
                 </div>

                 {/* New Note Input Area */}
                 <div className="mb-8 p-1 bg-muted/20 border border-border/60 rounded-lg shadow-sm">
                   <div className="flex border-b border-border/40 p-2 overflow-x-auto gap-1 hide-scrollbar">
                     {(Object.keys(NOTE_TYPE_LABELS) as NoteType[]).map((t) => (
                       <button
                         key={t}
                         onClick={() => setNoteType(t)}
                         className={`px-3 py-1 text-[10px] font-mono tracking-widest uppercase transition-all rounded whitespace-nowrap font-medium ${
                           noteType === t
                             ? "bg-foreground/10 text-foreground border-border/hover shadow-sm"
                             : "text-muted-foreground hover:bg-muted"
                         }`}
                       >
                         {NOTE_TYPE_LABELS[t]}
                       </button>
                     ))}
                   </div>
                   <div className="p-2 pb-2">
                     <textarea
                       value={noteContent}
                       onChange={(e) => setNoteContent(e.target.value)}
                       placeholder={canAddNote ? "Enter new insight, deduction, or observation..." : "Only the assigned investigator or supervisors can add notes."}
                       rows={4}
                       disabled={!canAddNote}
                       className="w-full text-xs bg-transparent p-2 resize-none focus:outline-none placeholder:text-muted-foreground/40 font-mono"
                     />
                     <div className="flex justify-between items-center px-1">
                       <span className="text-[10px] font-mono text-muted-foreground opacity-50">
                         {canAddNote ? "Markdown supported" : "Read-only until this case is assigned to you or updated by a supervisor"}
                       </span>
                       <Button size="sm" onClick={handleAddNote} disabled={!canAddNote || !noteContent.trim() || submitting} className="h-7 text-xs px-3 shadow-none gap-2">
                         {submitting ? <Loader2 size={12} className="animate-spin" /> : <><MessageSquarePlus size={12} /> Post Entry</>}
                       </Button>
                     </div>
                   </div>
                 </div>

                 {/* Notes List */}
                 {c.notes.length === 0 ? (
                  <div className="border border-dashed border-border/60 rounded-lg p-10 flex flex-col items-center justify-center text-center opacity-60 bg-muted/20">
                    <FileText size={24} className="mb-3 text-muted-foreground" />
                    <p className="text-sm font-medium">Empty Logbook</p>
                  </div>
                 ) : (
                   <div className="space-y-4">
                     {c.notes.map((note) => (
                       <div key={note.id} className="relative rounded-lg border border-border/50 bg-card p-4 shadow-sm group">
                         <div className="flex items-center justify-between mb-3 border-b border-border/40 pb-2">
                           <div className="flex items-center gap-2">
                             <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-muted/60 text-foreground font-bold tracking-widest uppercase border border-border/60">
                               {NOTE_TYPE_LABELS[note.note_type]}
                             </span>
                             <span className="text-[10px] font-mono uppercase tracking-wide opacity-80">{note.author}</span>
                           </div>
                           <span className="text-[10px] font-mono text-muted-foreground opacity-70">
                             {new Date(note.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                           </span>
                         </div>
                         <div className="text-[13px] text-foreground/90 whitespace-pre-wrap leading-relaxed font-mono">
                           {note.content}
                         </div>
                       </div>
                     ))}
                   </div>
                 )}
              </div>

            </div>
          </ScrollArea>

          {/* Bottom Tabs Switcher - Sticky */}
          <div className="grid grid-cols-4 shrink-0 border-t border-border/60 bg-muted/20 h-14">
            <TabBtn id="overview" label="Overview" icon={<PanelLeft size={16}/>} active={activeTab === 'overview'} set={setActiveTab} />
            <TabBtn id="evidence" label="Evidence" icon={<Link2 size={16}/>} count={evidence.length} active={activeTab === 'evidence'} set={setActiveTab} />
            <TabBtn id="timeline" label="Timeline" icon={<Clock size={16}/>} count={timeline.length} active={activeTab === 'timeline'} set={setActiveTab} />
            <TabBtn id="notes" label="Notes" icon={<FileText size={16}/>} count={c.notes.length} active={activeTab === 'notes'} set={setActiveTab} />
          </div>
        </div>

        {/* Desktop Sidebar Shadow Fade */}
        <div className="hidden lg:block w-px h-full bg-linear-to-r from-border/50 via-background to-transparent shadow-[4px_0_24px_-4px_rgba(0,0,0,0.3)] z-10 box-content"></div>

        {/* Main Interface: Chat Panel */}
        <div className="flex-1 flex flex-col h-full bg-background relative overflow-hidden z-10">
           {/* The Chat Application */}
           <CaseChat caseId={caseId} className="flex-1 h-full rounded-none border-0 shadow-none" />
           
           {/* Mobile Sidebar Overlay mask */}
           {sidebarOpen && (
              <div 
                 className="absolute inset-0 bg-background/80 backdrop-blur-sm z-10 lg:hidden cursor-pointer animate-in fade-in"
                 onClick={() => setSidebarOpen(false)}
              ></div>
           )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function TabBtn({ id, label, icon, active, set, count }: { id: TabId, label: string, icon: React.ReactNode, active: boolean, set: (id: TabId) => void, count?: number }) {
  return (
    <button 
      onClick={() => set(id)}
      className={`relative flex flex-col items-center justify-center gap-1 transition-all h-full
        ${active ? "text-primary bg-background shadow-[inset_0_2px_0_0_rgba(var(--primary),0.5)]" : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"}
      `}
    >
      <div className={`relative ${active ? "opacity-100" : "opacity-70"}`}>
        {icon}
        {count !== undefined && count > 0 && (
          <span className="absolute -top-1.5 -right-2.5 min-w-3.5 h-3.5 px-1 bg-primary text-primary-foreground text-[8px] font-bold rounded-full flex items-center justify-center font-mono ring-1 ring-background">
            {count > 99 ? '99+' : count}
          </span>
        )}
      </div>
      <span className="text-[9px] font-mono tracking-widest uppercase font-semibold mx-auto translate-x-px truncate w-full px-1">{label}</span>
      {active && <div className="absolute right-0 w-px h-8 bg-border/40" />}
    </button>
  );
}

function TimelineEventIcon({ type }: { type: string }) {
  switch (type) {
    case "CASE_OPENED": return <FolderOpen size={14} />;
    case "STATUS_CHANGE": return <ArrowUpRight size={14} />;
    case "ASSIGNMENT": return <User size={14} />;
    case "NOTE_ADDED": return <FileText size={14} />;
    case "PRIORITY_CHANGE": return <AlertTriangle size={14} />;
    case "DECISION_RECORDED": return <Gavel size={14} />;
    case "EVIDENCE_LINKED":
    case "EVIDENCE_UNLINKED": return <Link2 size={14} />;
    default: return <Clock size={14} />;
  }
}

function TimelineEventDescription({ event }: { event: CaseEvent }) {
  const oldAssigneeName =
    event.event_metadata && typeof event.event_metadata.old_assignee_name === "string"
      ? event.event_metadata.old_assignee_name
      : null;
  const newAssigneeName =
    event.event_metadata && typeof event.event_metadata.new_assignee_name === "string"
      ? event.event_metadata.new_assignee_name
      : null;

  switch (event.event_type) {
    case "STATUS_CHANGE": return <span className="font-mono">[{event.old_value}] → [{event.new_value}]</span>;
    case "PRIORITY_CHANGE": return <span className="font-mono">{event.old_value} → {event.new_value}</span>;
    case "ASSIGNMENT":
      return (
        <span className="font-medium text-foreground">
          {(oldAssigneeName || "Unassigned queue")} → {(newAssigneeName || "Unassigned queue")}
        </span>
      );
    case "NOTE_ADDED": return <>{event.new_value} record appended</>;
    case "EVIDENCE_LINKED": return <span className="text-primary italic truncate block max-w-full">Target: {event.new_value}</span>;
    case "EVIDENCE_UNLINKED": return <>Removed connection to: <del className="opacity-70">{event.old_value}</del></>;
    case "DECISION_RECORDED": return <span className="font-medium bg-muted px-1.5 py-0.5 rounded font-mono text-[10px] uppercase border border-border/80 text-foreground">{event.new_value}</span>;
    default: return <>{event.new_value || "Event occurred"}</>;
  }
}

export default function CaseDetailPage() {
  return (
    <AuthGuard>
      <CaseDetailContent />
    </AuthGuard>
  );
}
