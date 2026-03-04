"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getChatThreads,
  getThreadMessages,
  streamChat,
  type StreamAction,
} from "@/lib/api";
import type { ChatMessage, Citation, ChatStreamEvent } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  MessageSquare,
  Send,
  Loader2,
  Bot,
  User,
  Sparkles,
  ListChecks,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Plus,
  Search,
  FileText,
  Brain,
  CheckCircle2,
  Terminal,
  BookOpen,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CaseChatProps {
  caseId: string;
  className?: string;
}

// A merged tool record: one entry per toolCallId, transitions from running→complete
interface ToolRecord {
  tool: string;
  toolCallId: string;
  status: "running" | "complete";
  input?: Record<string, unknown>;
  summary?: string;
}

// Interleaved stream items for Claude-style inline display
type StreamItem =
  | { kind: "reasoning"; text: string }
  | { kind: "tool"; record: ToolRecord };

interface StreamingState {
  content: string;
  items: StreamItem[];
  citations: Map<number, Citation>;
  isComplete: boolean;
}

const initialStreamingState: StreamingState = {
  content: "",
  items: [],
  citations: new Map(),
  isComplete: false,
};

// Helper to extract query from tool input
function getToolQuery(tool: string, input?: Record<string, unknown>): string | null {
  if (!input) return null;
  // Most tools have a 'query' param
  if (typeof input.query === "string") return input.query;
  // Fallback to first string value
  for (const val of Object.values(input)) {
    if (typeof val === "string" && val.length > 0 && val.length < 200) return val;
  }
  return null;
}

// Truncate summary for collapsed view
function truncateSummary(text: string, maxLen = 120): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).trimEnd() + "…";
}

// ---------------------------------------------------------------------------
// Small components
// ---------------------------------------------------------------------------

function ToolIcon({ tool }: { tool: string }) {
  switch (tool) {
    case "search_legal_knowledge":
      return <FileText className="h-3.5 w-3.5 text-emerald-500" />;
    case "search_case_evidence":
      return <Search className="h-3.5 w-3.5 text-amber-500" />;
    case "get_risk_analysis":
      return <Brain className="h-3.5 w-3.5 text-purple-500" />;
    default:
      return <Terminal className="h-3.5 w-3.5 text-sky-500" />;
  }
}

function toolDisplayName(name: string) {
  const map: Record<string, string> = {
    search_legal_knowledge: "Searching legal knowledge",
    search_case_evidence: "Searching case evidence",
    get_risk_analysis: "Analyzing risk factors",
    search_graph_connections: "Searching graph connections",
  };
  return map[name] || name.replace(/_/g, " ");
}

// ---------------------------------------------------------------------------
// Sources popover — shown at the end of a message with citations
// ---------------------------------------------------------------------------

function SourcesButton({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button className="inline-flex items-center gap-1.5 mt-4 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground bg-muted/50 hover:bg-muted border border-border/60 rounded-lg transition-colors">
          <BookOpen className="h-3.5 w-3.5" />
          Sources
          <span className="ml-0.5 text-[10px] font-mono opacity-70">({citations.length})</span>
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        side="top"
        className="w-80 max-h-72 overflow-y-auto p-0 border-border bg-popover shadow-xl"
      >
        <div className="px-3 py-2 border-b border-border/60 bg-muted/30">
          <p className="text-[10px] font-mono font-semibold uppercase tracking-widest text-muted-foreground">
            Referenced Sources
          </p>
        </div>
        <div className="divide-y divide-border/40">
          {citations.map((c) => (
            <div key={c.marker} className="px-3 py-2.5 hover:bg-muted/30 transition-colors">
              <div className="flex items-start gap-2">
                <span className="shrink-0 flex items-center justify-center h-5 w-5 rounded bg-primary/10 text-primary text-[10px] font-mono font-bold mt-0.5">
                  {c.marker}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <p className="text-xs font-medium truncate">{c.title}</p>
                    {c.source_url && (
                      <a
                        href={c.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="shrink-0 text-muted-foreground hover:text-primary"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                  <p className="text-[10px] font-mono uppercase text-muted-foreground/70 tracking-wide mt-0.5">
                    {c.category || "source"}
                    {c.page ? ` · p.${c.page}` : ""}
                  </p>
                  {c.excerpt && (
                    <p className="text-[11px] text-muted-foreground mt-1 line-clamp-2 leading-relaxed">
                      {c.excerpt}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

// ---------------------------------------------------------------------------
// Inline tool card (Claude-style) — used during streaming
// ---------------------------------------------------------------------------

function ToolCard({ record }: { record: ToolRecord }) {
  const [expanded, setExpanded] = useState(false);
  const isRunning = record.status === "running";
  const query = getToolQuery(record.tool, record.input);

  return (
    <div className="my-2 rounded-lg border border-border/50 bg-muted/20 overflow-hidden transition-all">
      <button
        onClick={() => !isRunning && record.summary && setExpanded(!expanded)}
        disabled={isRunning || !record.summary}
        className="flex items-start gap-2 w-full px-3 py-2 text-xs text-muted-foreground hover:bg-muted/40 transition-colors text-left"
      >
        <div className="shrink-0 mt-0.5">
          <ToolIcon tool={record.tool} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-foreground/80">
              {toolDisplayName(record.tool)}
            </span>
            {isRunning ? (
              <Loader2 className="h-3 w-3 animate-spin text-primary" />
            ) : (
              <CheckCircle2 className="h-3 w-3 text-emerald-500 shrink-0" />
            )}
          </div>
          {/* Show query while running */}
          {query && isRunning && (
            <p className="text-[11px] text-muted-foreground/70 mt-1 truncate">
              &quot;{query}&quot;
            </p>
          )}
          {/* Show truncated result when complete (collapsed) */}
          {!isRunning && record.summary && !expanded && (
            <p className="text-[11px] text-muted-foreground/60 mt-1 line-clamp-1">
              {truncateSummary(record.summary)}
            </p>
          )}
        </div>
        {!isRunning && record.summary && (
          <ChevronDown className={`h-3 w-3 shrink-0 mt-0.5 transition-transform ${expanded ? "rotate-180" : ""}`} />
        )}
      </button>
      {expanded && record.summary && (
        <div className="px-3 pb-2.5 pt-0">
          <div className="font-mono text-[11px] bg-background/60 border border-border/40 rounded p-2 text-muted-foreground whitespace-pre-wrap max-w-full overflow-x-auto leading-relaxed">
            {record.summary}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Persisted events section (collapsed when loading existing chat)
// ---------------------------------------------------------------------------

function PersistedEventsSection({ events }: { events: ChatStreamEvent[] }) {
  const [open, setOpen] = useState(false);
  if (!events || events.length === 0) return null;

  // Deduplicate: only show tool_end events (which have summaries)
  const toolEndEvents = events.filter((e) => e.type === "tool_end");
  const reasoningEvents = events.filter((e) => e.type === "reasoning");
  const totalOps = toolEndEvents.length;

  if (totalOps === 0 && reasoningEvents.length === 0) return null;

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="my-2">
      <CollapsibleTrigger className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors w-full py-1">
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <span className="font-medium">
          Analyzed {totalOps} source{totalOps !== 1 ? "s" : ""}
        </span>
      </CollapsibleTrigger>

      <CollapsibleContent className="mt-1 space-y-1">
        {/* Interleave reasoning and tools in order */}
        {events.map((event, i) => {
          if (event.type === "reasoning" && event.content) {
            return (
              <p key={i} className="text-xs text-muted-foreground/70 italic pl-5 py-0.5">
                {event.content}
              </p>
            );
          }
          if (event.type === "tool_end") {
            return (
              <ToolCard
                key={i}
                record={{
                  tool: event.tool || "unknown",
                  toolCallId: event.tool_call_id || String(i),
                  status: "complete",
                  summary: event.summary,
                }}
              />
            );
          }
          return null;
        })}
      </CollapsibleContent>
    </Collapsible>
  );
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const citationsList = message.citations || [];

  return (
    <div className={`flex gap-4 w-full ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md border shadow-sm ${
          isUser
            ? "bg-foreground text-background border-foreground"
            : "bg-primary/10 text-primary border-primary/20"
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Content */}
      <div className={`flex flex-col max-w-[85%] ${isUser ? "items-end" : "items-start"}`}>
        <span className="text-[10px] font-mono font-medium text-muted-foreground mb-1.5 tracking-wider uppercase">
          {isUser ? "Investigator" : "Sentinel AI"}
        </span>

        <div
          className={`px-5 py-3.5 shadow-sm text-[14px] leading-relaxed ${
            isUser
              ? "bg-foreground text-background rounded-l-2xl rounded-tr-2xl"
              : "bg-card border border-border/80 rounded-r-2xl rounded-tl-2xl shadow-sm"
          }`}
        >
          {/* Persisted tool events — collapsed */}
          {!isUser && message.events && message.events.length > 0 && (
            <PersistedEventsSection events={message.events} />
          )}

          {/* Text Content */}
          <div className={`whitespace-pre-wrap ${isUser ? "text-background/90" : "text-foreground/90"}`}>
            {message.content}
          </div>

          {/* Sources button (replaces inline citation badges) */}
          {!isUser && citationsList.length > 0 && (
            <SourcesButton citations={citationsList} />
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function CaseChat({ caseId, className = "" }: CaseChatProps) {
  const queryClient = useQueryClient();
  const [input, setInput] = useState("");
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [streamingState, setStreamingState] = useState<StreamingState>(initialStreamingState);
  const [isStreaming, setIsStreaming] = useState(false);
  const [showThreads, setShowThreads] = useState(false);
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const finalContentRef = useRef("");

  const { data: threads = [] } = useQuery({
    queryKey: ["chat-threads", caseId],
    queryFn: () => getChatThreads(caseId),
  });

  const { data: messages = [], refetch: refetchMessages } = useQuery({
    queryKey: ["chat-messages", caseId, activeThreadId],
    queryFn: () =>
      activeThreadId ? getThreadMessages(caseId, activeThreadId) : Promise.resolve([]),
    enabled: !!activeThreadId,
  });

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingState.content, streamingState.items, scrollToBottom]);

  // -----------------------------------------------------------------------
  // Stream event handler — builds interleaved items array
  // -----------------------------------------------------------------------
  const handleStreamEvent = useCallback((event: ChatStreamEvent) => {
    setStreamingState((prev) => {
      const next = { ...prev };

      switch (event.type) {
        case "token":
          next.content += event.delta || "";
          finalContentRef.current += event.delta || "";
          break;

        case "reasoning": {
          // Append reasoning as an interleaved item
          const text = event.content || "";
          if (text) {
            next.items = [...prev.items, { kind: "reasoning", text }];
          }
          break;
        }

        case "tool_start": {
          // Add a new tool record in "running" state
          const record: ToolRecord = {
            tool: event.tool || "unknown",
            toolCallId: event.tool_call_id || "",
            status: "running",
            input: event.input,
          };
          next.items = [...prev.items, { kind: "tool", record }];
          break;
        }

        case "tool_end": {
          // Update the existing tool record to "complete"
          next.items = prev.items.map((item) => {
            if (item.kind === "tool" && item.record.toolCallId === event.tool_call_id) {
              return {
                ...item,
                record: { ...item.record, status: "complete" as const, summary: event.summary },
              };
            }
            return item;
          });
          break;
        }

        case "citation":
          if (event.marker !== undefined) {
            const newCitations = new Map(prev.citations);
            newCitations.set(event.marker, {
              marker: event.marker,
              doc_id: event.doc_id || "",
              title: event.title || "",
              source_url: event.source_url || null,
              category: event.category || "",
              excerpt: event.excerpt || "",
              page: event.page || null,
              chunk_id: event.chunk_id || "",
            });
            next.citations = newCitations;
          }
          break;

        case "done":
          next.isComplete = true;
          if (event.citations) {
            const newCitations = new Map(prev.citations);
            for (const c of event.citations) {
              newCitations.set(c.marker, c);
            }
            next.citations = newCitations;
          }
          break;

        case "error":
          console.error("Stream error:", event.message);
          break;
      }

      return next;
    });
  }, []);

  const runStream = useCallback(
    async (message: string, action: StreamAction) => {
      setIsStreaming(true);
      setStreamingState(initialStreamingState);
      finalContentRef.current = "";

      try {
        for await (const event of streamChat(caseId, message, {
          threadId: activeThreadId || undefined,
          action,
        })) {
          handleStreamEvent(event);

          if (event.type === "done") {
            if (event.thread_id && !activeThreadId) {
              setActiveThreadId(event.thread_id);
            }
            queryClient.invalidateQueries({ queryKey: ["chat-threads", caseId] });
            refetchMessages();
          }
        }
      } catch (error) {
        console.error("Stream error:", error);
      } finally {
        setIsStreaming(false);
        setStreamingState(initialStreamingState);
        setPendingUserMessage(null);
      }
    },
    [caseId, activeThreadId, queryClient, refetchMessages, handleStreamEvent]
  );

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;
    const userMessage = input.trim();
    setInput("");
    setPendingUserMessage(userMessage);
    await runStream(userMessage, "chat");
  };

  const handleNewThread = () => {
    setActiveThreadId(null);
    setShowThreads(false);
  };

  const activeThreadTitle = threads.find((t) => t.id === activeThreadId)?.title || "Current Session";

  // Check if there are any tool items currently running
  const hasRunningTools = streamingState.items.some(
    (item) => item.kind === "tool" && item.record.status === "running"
  );
  const hasAnyItems = streamingState.items.length > 0;
  // Show waiting indicator: streaming but no content and no items yet, OR all tools done but no content yet
  const showWaitingIndicator = isStreaming && !streamingState.content && !hasAnyItems;
  // Show "processing" indicator after tools complete but before answer starts
  const showProcessingIndicator = isStreaming && !streamingState.content && hasAnyItems && !hasRunningTools;

  return (
    <div className={`flex flex-col min-h-0 bg-background relative overflow-hidden ${className}`}>
      {/* Header Bar */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border/60 bg-card/60 shrink-0 backdrop-blur-md z-10">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center p-1.5 bg-primary/10 text-primary rounded-md">
            <Brain className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold tracking-tight">Sentinel Analyst</h2>
            <div className="flex items-center gap-1.5 text-[10px] uppercase font-mono tracking-widest text-muted-foreground mt-0.5">
              <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              ACTIVE : {activeThreadId ? activeThreadTitle : "NEW SESSION"}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 text-muted-foreground">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 hover:bg-muted"
            onClick={() => runStream("", "summary")}
            disabled={isStreaming}
            title="Generate Case Summary"
          >
            <Sparkles className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 hover:bg-muted"
            onClick={() => runStream("", "next_steps")}
            disabled={isStreaming}
            title="Suggest Next Steps"
          >
            <ListChecks className="h-4 w-4" />
          </Button>

          <div className="h-4 w-px bg-border/80 mx-1"></div>

          <div className="relative">
            <Button
              variant="outline"
              size="sm"
              className="h-8 font-mono text-xs"
              onClick={() => setShowThreads(!showThreads)}
            >
              History <ChevronDown className={`ml-1 h-3 w-3 transition-transform ${showThreads ? "rotate-180" : ""}`} />
            </Button>

            {showThreads && (
              <div className="absolute right-0 top-full mt-2 w-72 rounded-xl border border-border shadow-2xl bg-card z-50 overflow-hidden">
                <div className="p-2 border-b bg-muted/30">
                  <Button
                    variant="default"
                    size="sm"
                    className="w-full justify-start text-xs font-semibold h-8"
                    onClick={handleNewThread}
                  >
                    <Plus className="h-3 w-3 mr-2" />
                    New Investigation Thread
                  </Button>
                </div>
                <div className="max-h-[300px] overflow-y-auto">
                  {threads.length === 0 ? (
                    <div className="p-6 text-sm text-muted-foreground text-center flex flex-col items-center gap-2">
                      <MessageSquare className="h-8 w-8 opacity-20" />
                      No past threads
                    </div>
                  ) : (
                    <div className="p-1">
                      {threads.map((thread) => (
                        <button
                          key={thread.id}
                          onClick={() => {
                            setActiveThreadId(thread.id);
                            setShowThreads(false);
                          }}
                          className={`w-full px-3 py-2.5 text-left text-sm rounded-md transition-colors ${
                            activeThreadId === thread.id
                              ? "bg-primary/10 text-primary border border-primary/20"
                              : "hover:bg-muted/60 border border-transparent"
                          }`}
                        >
                          <p className="font-medium truncate text-[13px]">{thread.title || "Untitled"}</p>
                          <div className="flex justify-between items-center mt-1">
                            <span className="text-[10px] font-mono text-muted-foreground uppercase">{thread.message_count} msgs</span>
                            <span className="text-[10px] text-muted-foreground">{new Date(thread.created_at || Date.now()).toLocaleDateString()}</span>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 min-h-0 overflow-y-auto w-full">
        <div className="max-w-4xl mx-auto w-full p-4 sm:p-6 md:p-8 space-y-8 pb-4">
          {messages.length === 0 && !streamingState.content && !isStreaming && (
            <div className="flex flex-col items-center justify-center pt-20 pb-10 text-center opacity-80 zoom-in-95 animate-in duration-500 fade-in">
              <div className="h-20 w-20 rounded-2xl bg-primary/10 flex items-center justify-center mb-6 shadow-sm border border-primary/20">
                <Brain className="h-10 w-10 text-primary" />
              </div>
              <h3 className="text-lg font-semibold tracking-tight mb-2">Sentinel AI Ready</h3>
              <p className="text-sm text-muted-foreground max-w-[350px]">
                I can analyze evidence, verify legal compliance, extract insights, and formulate investigation next steps.
              </p>
              <div className="mt-8 grid grid-cols-1 gap-2 w-full max-w-sm">
                <Button variant="outline" className="text-xs h-9 justify-start" onClick={() => runStream("Summarize the main risk factors in this case", "chat")}>
                  <Sparkles className="mr-2 h-3.5 w-3.5 text-primary" /> Summarize risk factors
                </Button>
                <Button variant="outline" className="text-xs h-9 justify-start" onClick={() => runStream("Find legal grounds to dismiss this case", "chat")}>
                  <FileText className="mr-2 h-3.5 w-3.5 text-emerald-500" /> Find legal precedents
                </Button>
                <Button variant="outline" className="text-xs h-9 justify-start" onClick={() => runStream("List the submitted evidence", "chat")}>
                  <Search className="mr-2 h-3.5 w-3.5 text-amber-500" /> Review evidence
                </Button>
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {/* Optimistic user message — shown immediately while streaming */}
          {pendingUserMessage && (
            <div className="flex gap-4 w-full flex-row-reverse">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border shadow-sm bg-foreground text-background border-foreground">
                <User className="h-4 w-4" />
              </div>
              <div className="flex flex-col max-w-[85%] items-end">
                <span className="text-[10px] font-mono font-medium text-muted-foreground mb-1.5 tracking-wider uppercase">
                  Investigator
                </span>
                <div className="px-5 py-3.5 shadow-sm text-[14px] leading-relaxed bg-foreground text-background rounded-l-2xl rounded-tr-2xl">
                  <div className="whitespace-pre-wrap text-background/90">
                    {pendingUserMessage}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Streaming Response — Claude-style interleaved layout */}
          {isStreaming && (
            <div className="flex gap-4 w-full">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-primary/20 bg-primary/10 text-primary shadow-sm">
                <Bot className="h-4 w-4" />
              </div>
              <div className="flex flex-col max-w-[85%] items-start w-full">
                <span className="text-[10px] font-mono font-medium text-muted-foreground mb-1.5 tracking-wider uppercase">
                  Sentinel AI
                </span>

                <div className="w-full px-5 py-3.5 text-[14px] leading-relaxed bg-card border border-border/80 rounded-r-2xl rounded-tl-2xl shadow-sm">
                  {/* Waiting indicator — before any events arrive */}
                  {showWaitingIndicator && (
                    <div className="flex items-center gap-3 text-sm text-muted-foreground">
                      <span className="relative flex h-3 w-3">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-3 w-3 bg-primary"></span>
                      </span>
                      Thinking...
                    </div>
                  )}

                  {/* Interleaved reasoning + tool cards */}
                  {streamingState.items.map((item, i) => {
                    if (item.kind === "reasoning") {
                      return (
                        <p key={i} className="text-xs text-muted-foreground/80 italic my-2 leading-relaxed">
                          {item.text}
                        </p>
                      );
                    }
                    return <ToolCard key={item.record.toolCallId} record={item.record} />;
                  })}

                  {/* Processing indicator — after tools complete but before answer */}
                  {showProcessingIndicator && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mt-3 pt-2 border-t border-border/30">
                      <Loader2 className="h-3 w-3 animate-spin text-primary" />
                      <span>Generating response...</span>
                    </div>
                  )}

                  {/* Streamed answer text */}
                  {streamingState.content && (
                    <div className="whitespace-pre-wrap text-foreground/90 mt-1">
                      {streamingState.content}
                      <span className="inline-block w-2 h-4 bg-primary/70 animate-pulse ml-[2px] align-middle rounded-sm" />
                    </div>
                  )}

                  {/* Sources button — only after streaming is complete */}
                  {streamingState.isComplete && streamingState.citations.size > 0 && (
                    <SourcesButton citations={Array.from(streamingState.citations.values())} />
                  )}
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} className="h-1" />
        </div>
      </div>

      {/* Input Area */}
      <div className="shrink-0 p-4 border-t border-border/40 bg-background">
        <div className="max-w-4xl mx-auto">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="relative flex items-end gap-2 bg-card rounded-xl border border-border pb-1 pl-4 pr-2 pt-1 shadow-lg shadow-black/5 ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:border-transparent transition-all"
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Message Sentinel (Press Enter to send)..."
              disabled={isStreaming}
              rows={1}
              className="flex-1 max-h-32 min-h-[44px] py-3 text-sm resize-none bg-transparent focus:outline-none placeholder:text-muted-foreground/50 disabled:opacity-50"
              style={{ overflowY: "auto" }}
            />
            <div className="flex shrink-0 items-center justify-center p-1">
              <Button
                type="submit"
                size="icon"
                disabled={!input.trim() || isStreaming}
                className="h-9 w-9 rounded-lg"
              >
                {isStreaming ? (
                  <Loader2 className="h-4 w-4 animate-spin text-primary-foreground" />
                ) : (
                  <Send className="h-4 w-4 text-primary-foreground" />
                )}
              </Button>
            </div>
          </form>
          <div className="text-center mt-2 pb-1">
            <span className="text-[10px] font-mono text-muted-foreground/60 uppercase tracking-widest">Responses may be synthesized from multiple sources.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
