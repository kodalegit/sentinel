"use client";

import { useState, useRef, useEffect, useCallback, memo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { ChatMessage, Citation, ChatStreamEvent } from "@/lib/types";
import { useStreamChat, type ToolRecord } from "@/hooks/useStreamChat";
import { useChatScroll } from "@/hooks/useChatScroll";
import { OptimizedMarkdown } from "@/components/OptimizedMarkdown";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  MessageSquare,
  Send,
  Loader2,
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
  Trash2,
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

// Helper to extract query from tool input
function getToolQuery(input?: Record<string, unknown>): string | null {
  if (!input) return null;
  if (typeof input.query === "string") return input.query;
  for (const val of Object.values(input)) {
    if (typeof val === "string" && val.length > 0 && val.length < 200) return val;
  }
  return null;
}

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

  const sortedCitations = [...citations].sort((a, b) => a.marker - b.marker);

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
          {sortedCitations.map((c) => (
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

const ToolCard = memo(function ToolCard({ record }: { record: ToolRecord }) {
  const [expanded, setExpanded] = useState(false);
  const isRunning = record.status === "running";
  const query = getToolQuery(record.input);

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
          {/* Show query input for the tool call */}
          {query && (
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
});

// ---------------------------------------------------------------------------
// Persisted events section (collapsed when loading existing chat)
// ---------------------------------------------------------------------------

function PersistedEventsSection({ events }: { events: ChatStreamEvent[] }) {
  const [open, setOpen] = useState(false);
  if (!events || events.length === 0) return null;

  // Build a map of tool_start inputs keyed by tool_call_id
  const toolInputMap = new Map<string, Record<string, unknown>>();
  for (const e of events) {
    if (e.type === "tool_start" && e.tool_call_id && e.input) {
      toolInputMap.set(e.tool_call_id, e.input);
    }
  };

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
        {events.map((event, i) => {
          if (event.type === "reasoning" && event.content) {
            return (
              <p key={i} className="text-xs text-muted-foreground/70 italic pl-5 py-0.5">
                {event.content}
              </p>
            );
          }
          if (event.type === "tool_end") {
            const input = event.tool_call_id
              ? toolInputMap.get(event.tool_call_id)
              : undefined;
            return (
              <ToolCard
                key={i}
                record={{
                  tool: event.tool || "unknown",
                  toolCallId: event.tool_call_id || String(i),
                  status: "complete",
                  summary: event.summary,
                  input,
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
// Message bubble (memoized)
// ---------------------------------------------------------------------------

function UserMessageBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end w-full">
      <div className="max-w-[75%] rounded-3xl bg-muted px-4 py-3 text-[14px] leading-relaxed text-foreground shadow-sm">
        <div className="whitespace-pre-wrap">{content}</div>
      </div>
    </div>
  );
}

const MessageBubble = memo(function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const citationsList = message.citations || [];

  if (isUser) {
    return <UserMessageBubble content={message.content} />;
  }

  return (
    <div className="w-full px-1 sm:px-2">
      <div className="max-w-3xl space-y-3 text-[15px] leading-7 text-foreground/90">
        {message.events && message.events.length > 0 && (
          <PersistedEventsSection events={message.events} />
        )}

        <OptimizedMarkdown content={message.content} citations={citationsList} />

        {citationsList.length > 0 && <SourcesButton citations={citationsList} />}
      </div>
    </div>
  );
});

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function CaseChat({ caseId, className = "" }: CaseChatProps) {
  const [input, setInput] = useState("");
  const [showThreads, setShowThreads] = useState(false);
  const [threadToDelete, setThreadToDelete] = useState<string | null>(null);
  const [deletingThreadId, setDeletingThreadId] = useState<string | null>(null);
  const composerTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const syncingFromUrlRef = useRef(false);
  const lastSeenUrlThreadIdRef = useRef<string | null | undefined>(undefined);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const threadIdFromUrl = searchParams.get("thread");

  const {
    threads,
    threadsLoaded,
    messages,
    activeThreadId,
    activeThreadTitle,
    streamingState,
    isStreaming,
    pendingUserMessage,
    dynamicTitle,
    showWaitingIndicator,
    showProcessingIndicator,
    selectThread,
    deleteThread,
    runStream,
  } = useStreamChat(caseId);

  const {
    containerRef,
    userAnchorRef,
    showScrollToBottom,
    scrollToBottom,
    onScroll,
    markShouldAnchor,
    markInitialScroll,
    messagesBeforeCanvas,
    messagesInsideCanvas,
    usePersistedAnchor,
  } = useChatScroll({
    messages,
    pendingUserMessage,
    streamingState,
    isStreaming,
    activeThreadId,
  });

  const updateThreadUrl = useCallback(
    (threadId: string | null, mode: "push" | "replace" = "push") => {
      const params = new URLSearchParams(searchParams.toString());
      if (threadId) {
        params.set("thread", threadId);
      } else {
        params.delete("thread");
      }
      const nextUrl = params.size > 0 ? `${pathname}?${params.toString()}` : pathname;
      if (mode === "replace") {
        router.replace(nextUrl, { scroll: false });
        return;
      }
      router.push(nextUrl, { scroll: false });
    },
    [pathname, router, searchParams],
  );


  useEffect(() => {
    if (!threadsLoaded) {
      return;
    }

    const normalizedThreadId = threadIdFromUrl || null;
    const isFirstUrlSync = lastSeenUrlThreadIdRef.current === undefined;
    const urlChanged = lastSeenUrlThreadIdRef.current !== normalizedThreadId;

    if (!isFirstUrlSync && !urlChanged) {
      return;
    }

    lastSeenUrlThreadIdRef.current = normalizedThreadId;

    if (
      normalizedThreadId &&
      !threads.some((thread) => thread.id === normalizedThreadId)
    ) {
      updateThreadUrl(null, "replace");
      return;
    }

    if (activeThreadId === normalizedThreadId) {
      return;
    }
    syncingFromUrlRef.current = true;
    markInitialScroll(normalizedThreadId);
    selectThread(normalizedThreadId);
  }, [
    threadsLoaded,
    threadIdFromUrl,
    threads,
    activeThreadId,
    markInitialScroll,
    selectThread,
    updateThreadUrl,
  ]);

  useEffect(() => {
    if (!threadsLoaded) {
      return;
    }

    if (syncingFromUrlRef.current) {
      syncingFromUrlRef.current = false;
      return;
    }

    const normalizedThreadId = threadIdFromUrl || null;
    if (activeThreadId === normalizedThreadId) {
      return;
    }
    updateThreadUrl(activeThreadId, "replace");
  }, [threadsLoaded, activeThreadId, threadIdFromUrl, updateThreadUrl]);

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;
    const userMessage = input.trim();
    setInput("");
    markShouldAnchor();
    await runStream(userMessage, "chat");
  };

  useEffect(() => {
    const textarea = composerTextareaRef.current;
    if (!textarea) return;

    textarea.style.height = "0px";
    const nextHeight = Math.min(textarea.scrollHeight, 160);
    textarea.style.height = `${Math.max(nextHeight, 44)}px`;
    textarea.style.overflowY = textarea.scrollHeight > 160 ? "auto" : "hidden";
  }, [input]);

  const handleSuggestedQuery = useCallback(
    (message: string) => {
      markShouldAnchor();
      runStream(message, "chat");
    },
    [markShouldAnchor, runStream],
  );

  const handleNewThread = useCallback(() => {
    updateThreadUrl(null, "push");
    setShowThreads(false);
  }, [updateThreadUrl]);

  const handleDeleteThread = useCallback(
    async (threadId: string) => {
      try {
        setDeletingThreadId(threadId);
        await deleteThread(threadId);
      } catch (error) {
        console.error("Failed to delete chat thread:", error);
      } finally {
        setDeletingThreadId(null);
        setThreadToDelete(null);
      }
    },
    [deleteThread],
  );

  return (
    <div className={`flex flex-col min-h-0 bg-background relative overflow-hidden ${className}`}>
      {/* Header Bar */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border/60 bg-card/60 shrink-0 backdrop-blur-md z-10">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex items-center justify-center p-1.5 bg-primary/10 text-primary rounded-md shrink-0">
            <Brain className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70">Sentinel Analyst</span>
              <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse shrink-0"></span>
            </div>
            <h2
              key={activeThreadTitle}
              className={`text-sm font-semibold tracking-tight truncate ${
                dynamicTitle ? "animate-in fade-in duration-500" : ""
              }`}
            >
              {activeThreadId ? activeThreadTitle : "New session"}
            </h2>
          </div>
        </div>

        <div className="flex items-center gap-2 text-muted-foreground">
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-xs font-medium"
            onClick={handleNewThread}
            disabled={isStreaming}
          >
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            New chat
          </Button>

          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 hover:bg-muted"
            onClick={() => {
              markShouldAnchor();
              runStream("Generate a case summary", "summary");
            }}
            disabled={isStreaming}
            title="Generate Case Summary"
          >
            <Sparkles className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 hover:bg-muted"
            onClick={() => {
              markShouldAnchor();
              runStream("Suggest next steps", "next_steps");
            }}
            disabled={isStreaming}
            title="Suggest Next Steps"
          >
            <ListChecks className="h-4 w-4" />
          </Button>

          <div className="h-4 w-px bg-border/80 mx-1"></div>

          <Popover open={showThreads} onOpenChange={setShowThreads}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-8 font-mono text-xs"
              >
                History <ChevronDown className={`ml-1 h-3 w-3 transition-transform ${showThreads ? "rotate-180" : ""}`} />
              </Button>
            </PopoverTrigger>
            <PopoverContent
              align="end"
              sideOffset={8}
              className="w-72 p-0 overflow-hidden border-border bg-card shadow-2xl"
            >
              <div className="max-h-[320px] overflow-y-auto">
                {threads.length === 0 ? (
                  <div className="p-6 text-sm text-muted-foreground text-center flex flex-col items-center gap-2">
                    <MessageSquare className="h-8 w-8 opacity-20" />
                    No past threads
                  </div>
                ) : (
                  <div className="p-1">
                    {threads.map((thread) => (
                      <div
                        key={thread.id}
                        className={`flex items-start gap-1 rounded-md border transition-colors ${
                          activeThreadId === thread.id
                            ? "bg-primary/10 text-primary border-primary/20"
                            : "border-transparent hover:bg-muted/60"
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() => {
                            updateThreadUrl(thread.id, "push");
                            setShowThreads(false);
                          }}
                          disabled={isStreaming}
                          className="min-w-0 flex-1 px-3 py-2.5 text-left text-sm"
                        >
                          <p className="font-medium truncate text-[13px]">{thread.title || "Untitled"}</p>
                          <div className="flex justify-between items-center mt-1 gap-2">
                            <span className="text-[10px] font-mono text-muted-foreground uppercase">{thread.message_count} msgs</span>
                            <span className="text-[10px] text-muted-foreground">
                              {thread.created_at
                                ? new Date(thread.created_at).toLocaleDateString()
                                : ""}
                            </span>
                          </div>
                        </button>

                        <button
                          type="button"
                          onClick={() => setThreadToDelete(thread.id)}
                          disabled={deletingThreadId === thread.id || isStreaming}
                          className="mr-1 mt-1 shrink-0 rounded-md p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors disabled:opacity-50 disabled:pointer-events-none"
                          aria-label={`Delete ${thread.title || "chat thread"}`}
                          title="Delete thread"
                        >
                          {deletingThreadId === thread.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </PopoverContent>
          </Popover>
        </div>
      </div>

      {showScrollToBottom && (
        <div className="absolute bottom-32 left-1/2 z-20 -translate-x-1/2 sm:bottom-36">
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-9 rounded-full border-border/70 bg-background/95 px-3 shadow-lg backdrop-blur"
            onClick={() => scrollToBottom("smooth")}
          >
            <ChevronDown className="mr-1.5 h-4 w-4" />
            <span className="text-xs">Scroll to bottom</span>
          </Button>
        </div>
      )}

      {/* Messages Area */}
      <div
        ref={containerRef}
        onScroll={onScroll}
        className="flex-1 min-h-0 overflow-y-auto w-full"
      >
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
                <Button variant="outline" className="text-xs h-9 justify-start" onClick={() => handleSuggestedQuery("Summarize the main risk factors in this case")}>
                  <Sparkles className="mr-2 h-3.5 w-3.5 text-primary" /> Summarize risk factors
                </Button>
                <Button variant="outline" className="text-xs h-9 justify-start" onClick={() => handleSuggestedQuery("Find legal grounds to dismiss this case")}>
                  <FileText className="mr-2 h-3.5 w-3.5 text-emerald-500" /> Find legal precedents
                </Button>
                <Button variant="outline" className="text-xs h-9 justify-start" onClick={() => handleSuggestedQuery("List the submitted evidence")}>
                  <Search className="mr-2 h-3.5 w-3.5 text-amber-500" /> Review evidence
                </Button>
              </div>
            </div>
          )}

          {messagesBeforeCanvas.map((msg, index) => {
            const isAnchoredPersistedUser =
              usePersistedAnchor && index === messagesBeforeCanvas.length - 1;

            return (
              <div key={msg.id}>
                {isAnchoredPersistedUser && <div ref={userAnchorRef} aria-hidden="true" className="h-0" />}
                <MessageBubble message={msg} />
              </div>
            );
          })}

          {(pendingUserMessage || isStreaming || streamingState.content) && (
            <div className="min-h-[45vh] sm:min-h-[50vh]">
              {pendingUserMessage && (
                <div>
                  <div ref={userAnchorRef} aria-hidden="true" className="h-0" />
                  <UserMessageBubble content={pendingUserMessage} />
                </div>
              )}

              {messagesInsideCanvas.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}

              {(isStreaming || streamingState.content) && (
                <div className="w-full px-1 sm:px-2 animate-in fade-in duration-300">
                  <div className="max-w-3xl space-y-3 text-[15px] leading-7 text-foreground/90">
                    {showWaitingIndicator && (
                      <div className="flex items-center gap-3 text-sm text-muted-foreground">
                        <span className="relative flex h-3 w-3">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-3 w-3 bg-primary"></span>
                        </span>
                        Thinking...
                      </div>
                    )}

                    {streamingState.items.map((item, i) => {
                      if (item.kind === "reasoning") {
                        return (
                          <p key={i} className="text-xs text-muted-foreground/80 italic leading-relaxed">
                            {item.text}
                          </p>
                        );
                      }
                      return <ToolCard key={item.record.toolCallId} record={item.record} />;
                    })}

                    {showProcessingIndicator && (
                      <div className="flex items-center gap-2.5 pt-1 text-xs text-muted-foreground/85">
                        <div className="flex items-center gap-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-primary/80 animate-bounce [animation-delay:-0.2s]"></span>
                          <span className="h-1.5 w-1.5 rounded-full bg-primary/70 animate-bounce [animation-delay:-0.1s]"></span>
                          <span className="h-1.5 w-1.5 rounded-full bg-primary/60 animate-bounce"></span>
                        </div>
                        <span>Preparing final answer</span>
                      </div>
                    )}

                    {streamingState.content && (
                      <div className="mt-1">
                        <OptimizedMarkdown
                          content={streamingState.content}
                          citations={streamingState.citations}
                        />
                        {!streamingState.isComplete && (
                          <span className="inline-block w-2 h-4 bg-primary/70 animate-pulse ml-[2px] align-middle rounded-sm" />
                        )}
                      </div>
                    )}

                    {streamingState.isComplete && streamingState.citations.size > 0 && (
                      <SourcesButton citations={Array.from(streamingState.citations.values())} />
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
          <div className="h-1" />
        </div>
      </div>

      {/* Input Area */}
      <div className="shrink-0 border-t border-border/40 bg-background px-3 pb-3 pt-2 sm:p-4">
        <div className="mx-auto max-w-4xl">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="relative flex items-end gap-2 rounded-2xl border border-border bg-card px-3 py-2 shadow-lg shadow-black/5 transition-all ring-offset-background focus-within:border-transparent focus-within:ring-2 focus-within:ring-ring"
          >
            <textarea
              ref={composerTextareaRef}
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
              className="flex-1 min-h-[44px] max-h-40 bg-transparent py-2.5 text-sm leading-6 resize-none focus:outline-none placeholder:text-muted-foreground/50 disabled:opacity-50"
              style={{ overflowY: "hidden" }}
            />
            <div className="flex shrink-0 items-center justify-center self-end pb-0.5">
              <Button
                type="submit"
                size="icon"
                disabled={!input.trim() || isStreaming}
                className="h-10 w-10 rounded-xl shadow-sm"
              >
                {isStreaming ? (
                  <Loader2 className="h-4 w-4 animate-spin text-primary-foreground" />
                ) : (
                  <Send className="h-4 w-4 text-primary-foreground" />
                )}
              </Button>
            </div>
          </form>
          <div className="mt-2 flex items-center justify-between gap-3 px-1">
            <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground/60">
              Responses may be synthesized from multiple sources.
            </span>
            <span className="shrink-0 text-[10px] text-muted-foreground/60">
              Enter to send • Shift+Enter for newline
            </span>
          </div>
        </div>
      </div>

      <AlertDialog
        open={!!threadToDelete}
        onOpenChange={(open) => {
          if (!open && !deletingThreadId) setThreadToDelete(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete thread?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the thread and all its messages. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={!!deletingThreadId}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (threadToDelete) void handleDeleteThread(threadToDelete);
              }}
              disabled={!!deletingThreadId}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deletingThreadId ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Deleting…</>
              ) : (
                "Delete"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
