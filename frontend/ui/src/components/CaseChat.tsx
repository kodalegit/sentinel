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
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
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
  Wrench,
  Terminal,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CaseChatProps {
  caseId: string;
  className?: string;
}

interface ToolEvent {
  type: "start" | "end";
  tool: string;
  toolCallId: string;
  input?: Record<string, unknown>;
  summary?: string;
}

interface StreamingState {
  content: string;
  reasoning: string;
  currentStep: number;
  toolEvents: ToolEvent[];
  citations: Map<number, Citation>;
  isComplete: boolean;
}

const initialStreamingState: StreamingState = {
  content: "",
  reasoning: "",
  currentStep: 0,
  toolEvents: [],
  citations: new Map(),
  isComplete: false,
};

// ---------------------------------------------------------------------------
// Small components
// ---------------------------------------------------------------------------

function CitationBadge({ citation }: { citation: Citation }) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs font-mono rounded bg-primary/10 text-primary cursor-help">
            [{citation.marker}]
            {citation.source_url && (
              <a
                href={citation.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-sm border-border bg-popover/95 backdrop-blur-sm shadow-xl">
          <p className="font-semibold text-xs tracking-wide uppercase text-muted-foreground">{citation.category || "SOURCE"}</p>
          <p className="font-medium text-sm mt-1">{citation.title}</p>
          <p className="text-xs text-muted-foreground mt-2 border-l-2 border-primary pl-2 italic">{citation.excerpt}</p>
          {citation.page && (
            <p className="text-xs font-mono text-muted-foreground mt-2">Page {citation.page}</p>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function ToolIcon({ tool }: { tool: string }) {
  switch (tool) {
    case "search_legal_knowledge":
      return <FileText className="h-3 w-3 text-emerald-500" />;
    case "search_case_evidence":
      return <Search className="h-3 w-3 text-amber-500" />;
    case "get_risk_analysis":
      return <Brain className="h-3 w-3 text-purple-500" />;
    default:
      return <Terminal className="h-3 w-3 text-sky-500" />;
  }
}

function toolLabel(name: string) {
  return name.replace(/_/g, " ").toUpperCase();
}

// ---------------------------------------------------------------------------
// Collapsible events section (used for real-time streaming tool calls)
// ---------------------------------------------------------------------------

function StreamingToolSection({
  toolEvents,
  reasoning,
  step,
}: {
  toolEvents: ToolEvent[];
  reasoning: string;
  step: number;
}) {
  const [open, setOpen] = useState(true);
  if (toolEvents.length === 0 && !reasoning) return null;

  const completedCount = toolEvents.filter((e) => e.type === "end").length;
  const totalCount = new Set(toolEvents.map((e) => e.toolCallId)).size;
  const hasRunning = toolEvents.some((e) => e.type === "start" && !toolEvents.find((te) => te.toolCallId === e.toolCallId && te.type === "end"));

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="mb-4 bg-muted/40 border border-border/50 rounded-md overflow-hidden">
      <CollapsibleTrigger className="flex items-center gap-2 text-xs font-mono text-muted-foreground hover:bg-muted/80 transition-colors w-full px-3 py-2 border-b border-border/20">
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <Wrench className="h-3 w-3" />
        <span className="flex-1 text-left">
          {hasRunning ? "EXECUTING TOOLS" : "TOOLS EXECUTED"} : {completedCount}/{totalCount}
          {step > 0 && ` [STEP ${step}]`}
        </span>
        {hasRunning && <Loader2 className="h-3 w-3 animate-spin" />}
      </CollapsibleTrigger>
      
      <CollapsibleContent className="p-3 space-y-3">
        {reasoning && (
          <div className="text-xs text-muted-foreground italic border-l-2 border-primary/40 pl-3 py-1">
            &quot;{reasoning}&quot;
          </div>
        )}
        
        {toolEvents.map((event, i) => (
          <div key={`${event.toolCallId}-${i}`} className="text-xs group">
            <div className="flex items-center gap-2 mb-1.5 font-mono text-muted-foreground">
              <ToolIcon tool={event.tool} />
              <span className="font-semibold text-foreground/80">{toolLabel(event.tool)}</span>
              {event.type === "start" && !toolEvents.find((te) => te.toolCallId === event.toolCallId && te.type === "end") && (
                <span className="flex gap-1 items-center bg-primary/10 text-primary px-1.5 py-0.5 rounded text-[10px]">
                  <Loader2 className="h-2.5 w-2.5 animate-spin" /> RUNNING
                </span>
              )}
              {event.type === "end" && (
                <span className="flex gap-1 items-center text-green-600 bg-green-500/10 px-1.5 py-0.5 rounded text-[10px]">
                  <CheckCircle2 className="h-2.5 w-2.5" /> OK
                </span>
              )}
            </div>
            
            {event.type === "end" && event.summary && (
              <div className="pl-5">
                <div className="font-mono text-[11px] bg-background/50 border border-border/50 rounded p-2 text-muted-foreground whitespace-pre-wrap max-w-full overflow-x-auto">
                  {event.summary}
                </div>
              </div>
            )}
          </div>
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}

// ---------------------------------------------------------------------------
// Persisted events section (collapsed when loading existing chat)
// ---------------------------------------------------------------------------

function PersistedEventsSection({ events }: { events: ChatStreamEvent[] }) {
  const [open, setOpen] = useState(false);
  if (!events || events.length === 0) return null;

  const toolCount = events.filter((e) => e.type === "tool_end").length;
  const reasoningEvents = events.filter((e) => e.type === "reasoning");

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="mb-4 bg-muted/20 border border-border/30 rounded-md overflow-hidden">
      <CollapsibleTrigger className="flex items-center gap-2 text-xs font-mono text-muted-foreground hover:bg-muted/60 transition-colors w-full px-3 py-2">
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <Wrench className="h-3 w-3" />
        <span className="flex-1 text-left">
          TOOL CHAIN : {toolCount} OP{toolCount !== 1 ? "s" : ""}
          {reasoningEvents.length > 0 && ` | ${reasoningEvents.length} STATE${reasoningEvents.length !== 1 ? "s" : ""}`}
        </span>
      </CollapsibleTrigger>
      
      <CollapsibleContent className="p-3 bg-muted/30 border-t border-border/20 space-y-3">
        {events.map((event, i) => {
          if (event.type === "reasoning") {
            return (
              <div key={i} className="text-xs text-muted-foreground/80 italic border-l-2 border-primary/30 pl-3">
                {event.content}
              </div>
            );
          }
          if (event.type === "tool_end") {
            return (
              <div key={i} className="text-xs group">
                <div className="flex items-center gap-2 font-mono text-muted-foreground mb-1">
                  <ToolIcon tool={event.tool || ""} />
                  <span className="font-semibold text-foreground/80">{toolLabel(event.tool || "unknown")}</span>
                  <span className="text-green-600 bg-green-500/10 px-1 py-0.5 rounded text-[10px] flex items-center gap-1">
                    <CheckCircle2 className="h-2 w-2" /> OK
                  </span>
                </div>
                {event.summary && (
                  <div className="pl-5">
                    <div className="font-mono text-[11px] bg-background/60 border border-border/40 rounded p-2.5 text-muted-foreground whitespace-pre-wrap max-w-full overflow-x-auto shadow-sm">
                      {event.summary}
                    </div>
                  </div>
                )}
              </div>
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
          {/* Tool Events */}
          {!isUser && message.events && message.events.length > 0 && (
            <PersistedEventsSection events={message.events} />
          )}
          
          {/* Text Content */}
          <div className={`whitespace-pre-wrap ${isUser ? "text-background/90" : "text-foreground/90"}`}>
            {message.content}
          </div>
          
          {/* Citations */}
          {citationsList.length > 0 && (
            <div className={`mt-4 pt-3 border-t flex flex-wrap gap-1.5 ${isUser ? "border-background/20" : "border-border/60"}`}>
              {citationsList.map((c: Citation) => (
                <CitationBadge key={c.marker} citation={c} />
              ))}
            </div>
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
  }, [messages, streamingState.content, streamingState.toolEvents, scrollToBottom]);

  const handleStreamEvent = useCallback((event: ChatStreamEvent) => {
    setStreamingState((prev) => {
      const next = { ...prev };

      switch (event.type) {
        case "token":
          next.content += event.delta || "";
          finalContentRef.current += event.delta || "";
          break;

        case "reasoning":
          next.reasoning = event.content || "";
          next.currentStep = event.step || 0;
          break;

        case "tool_start":
          next.toolEvents = [
            ...prev.toolEvents,
            {
              type: "start",
              tool: event.tool || "unknown",
              toolCallId: event.tool_call_id || "",
              input: event.input,
            },
          ];
          break;

        case "tool_end":
          next.toolEvents = prev.toolEvents.map((te) =>
            te.toolCallId === event.tool_call_id
              ? { ...te, type: "end" as const, summary: event.summary }
              : te
          );
          break;

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
      }
    },
    [caseId, activeThreadId, queryClient, refetchMessages, handleStreamEvent]
  );

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;
    const userMessage = input.trim();
    setInput("");
    await runStream(userMessage, "chat");
  };

  const handleNewThread = () => {
    setActiveThreadId(null);
    setShowThreads(false);
  };

  const activeThreadTitle = threads.find((t) => t.id === activeThreadId)?.title || "Current Session";

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

          {/* Streaming Response Bubble */}
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
                  <StreamingToolSection
                    toolEvents={streamingState.toolEvents}
                    reasoning={streamingState.reasoning}
                    step={streamingState.currentStep}
                  />
                  
                  {streamingState.content ? (
                    <div className="whitespace-pre-wrap text-foreground/90">
                      {streamingState.content}
                      <span className="inline-block w-2 h-4 bg-primary/70 animate-pulse ml-[2px] align-middle rounded-sm" />
                    </div>
                  ) : (
                    <div className="flex items-center gap-3 text-sm text-muted-foreground font-mono">
                      <span className="relative flex h-3 w-3">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-3 w-3 bg-primary"></span>
                      </span>
                      Computing response...
                    </div>
                  )}
                  
                  {streamingState.citations.size > 0 && (
                    <div className="mt-4 pt-3 border-t border-border/60 flex flex-wrap gap-1.5">
                      {Array.from(streamingState.citations.values()).map((c) => (
                        <CitationBadge key={c.marker} citation={c} />
                      ))}
                    </div>
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
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Message Sentinel (Press Enter to send)..."
              disabled={isStreaming}
              rows={1}
              className="flex-1 max-h-32 min-h-[44px] py-3 text-sm resize-none bg-transparent focus:outline-none placeholder:text-muted-foreground/50 disabled:opacity-50"
              style={{ overflowY: 'auto' }}
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
