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
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
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
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CaseChatProps {
  caseId: string;
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
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs rounded bg-primary/10 text-primary cursor-help">
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
        <TooltipContent side="top" className="max-w-sm">
          <p className="font-medium text-sm">{citation.title}</p>
          <p className="text-xs text-muted-foreground mt-1">{citation.excerpt}</p>
          {citation.page && (
            <p className="text-xs text-muted-foreground mt-1">Page {citation.page}</p>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function ToolIcon({ tool }: { tool: string }) {
  switch (tool) {
    case "search_legal_knowledge":
      return <FileText className="h-3 w-3" />;
    case "search_case_evidence":
      return <Search className="h-3 w-3" />;
    case "get_risk_analysis":
      return <Brain className="h-3 w-3" />;
    default:
      return <Search className="h-3 w-3" />;
  }
}

function toolLabel(name: string) {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
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
    <Collapsible open={open} onOpenChange={setOpen} className="mb-2">
      <CollapsibleTrigger className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors w-full py-1">
        {open ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        <Wrench className="h-3 w-3" />
        <span>
          {hasRunning ? "Working" : "Used"} {completedCount}/{totalCount} tool{totalCount !== 1 ? "s" : ""}
          {step > 0 && ` · Step ${step}`}
        </span>
        {hasRunning && <Loader2 className="h-3 w-3 animate-spin ml-auto" />}
      </CollapsibleTrigger>
      <CollapsibleContent className="pl-5 space-y-1 mt-1">
        {reasoning && (
          <p className="text-xs text-muted-foreground italic">{reasoning}</p>
        )}
        {toolEvents.map((event, i) => (
          <div key={`${event.toolCallId}-${i}`} className="flex items-center gap-2 text-xs text-muted-foreground py-0.5">
            <ToolIcon tool={event.tool} />
            <span className="font-medium">{toolLabel(event.tool)}</span>
            {event.type === "start" && !toolEvents.find((te) => te.toolCallId === event.toolCallId && te.type === "end") && (
              <Loader2 className="h-3 w-3 animate-spin" />
            )}
            {event.type === "end" && (
              <>
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                {event.summary && (
                  <span className="text-muted-foreground/70 truncate max-w-[250px]">{event.summary}</span>
                )}
              </>
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
    <Collapsible open={open} onOpenChange={setOpen} className="mb-2">
      <CollapsibleTrigger className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors w-full py-1">
        {open ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        <Wrench className="h-3 w-3" />
        <span>
          Used {toolCount} tool{toolCount !== 1 ? "s" : ""}
          {reasoningEvents.length > 0 && ` · ${reasoningEvents.length} reasoning step${reasoningEvents.length !== 1 ? "s" : ""}`}
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent className="pl-5 space-y-1 mt-1">
        {events.map((event, i) => {
          if (event.type === "reasoning") {
            return (
              <p key={i} className="text-xs text-muted-foreground italic">
                {event.content}
              </p>
            );
          }
          if (event.type === "tool_start") {
            return (
              <div key={i} className="flex items-center gap-2 text-xs text-muted-foreground py-0.5">
                <ToolIcon tool={event.tool || ""} />
                <span className="font-medium">{toolLabel(event.tool || "unknown")}</span>
                <span className="text-muted-foreground/50">started</span>
              </div>
            );
          }
          if (event.type === "tool_end") {
            return (
              <div key={i} className="flex items-center gap-2 text-xs text-muted-foreground py-0.5">
                <ToolIcon tool={event.tool || ""} />
                <span className="font-medium">{toolLabel(event.tool || "unknown")}</span>
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                {event.summary && (
                  <span className="text-muted-foreground/70 truncate max-w-[250px]">{event.summary}</span>
                )}
              </div>
            );
          }
          if (event.type === "citation") {
            return (
              <div key={i} className="flex items-center gap-1 text-xs text-muted-foreground py-0.5">
                <span>[{event.marker}]</span>
                <span className="truncate max-w-[250px]">{event.title}</span>
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
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser ? "bg-primary/20 text-primary" : "bg-muted"
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 ${
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        }`}
      >
        {!isUser && message.events && message.events.length > 0 && (
          <PersistedEventsSection events={message.events} />
        )}
        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        {citationsList.length > 0 && (
          <div className="mt-2 pt-2 border-t border-current/10 flex flex-wrap gap-1">
            {citationsList.map((c: Citation) => (
              <CitationBadge key={c.marker} citation={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function CaseChat({ caseId }: CaseChatProps) {
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
  }, [messages, streamingState.content, scrollToBottom]);

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

  return (
    <div className="flex flex-col h-[500px] border rounded-xl overflow-hidden bg-background">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-muted/30">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-5 w-5 text-primary" />
          <span className="font-medium">AI Assistant</span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => runStream("", "summary")}
            disabled={isStreaming}
          >
            <Sparkles className="h-4 w-4" />
            <span className="ml-1 hidden sm:inline">Summary</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => runStream("", "next_steps")}
            disabled={isStreaming}
          >
            <ListChecks className="h-4 w-4" />
            <span className="ml-1 hidden sm:inline">Next Steps</span>
          </Button>
          <div className="relative">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowThreads(!showThreads)}
            >
              <ChevronDown className={`h-4 w-4 transition-transform ${showThreads ? "rotate-180" : ""}`} />
            </Button>
            {showThreads && (
              <div className="absolute right-0 top-full mt-1 w-64 rounded-lg border bg-popover shadow-lg z-10">
                <div className="p-2 border-b">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full justify-start"
                    onClick={handleNewThread}
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    New Conversation
                  </Button>
                </div>
                <div className="max-h-48 overflow-y-auto">
                  {threads.length === 0 ? (
                    <p className="p-3 text-sm text-muted-foreground text-center">
                      No conversations yet
                    </p>
                  ) : (
                    threads.map((thread) => (
                      <button
                        key={thread.id}
                        onClick={() => {
                          setActiveThreadId(thread.id);
                          setShowThreads(false);
                        }}
                        className={`w-full px-3 py-2 text-left text-sm hover:bg-muted transition-colors ${
                          activeThreadId === thread.id ? "bg-muted" : ""
                        }`}
                      >
                        <p className="font-medium truncate">{thread.title || "Untitled"}</p>
                        <p className="text-xs text-muted-foreground">
                          {thread.message_count} messages
                        </p>
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4">
          {messages.length === 0 && !streamingState.content && !isStreaming && (
            <div className="text-center py-8 text-muted-foreground">
              <Bot className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p className="text-sm">
                Ask me about this case, Kenyan procurement law, or request analysis.
              </p>
            </div>
          )}
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {/* Streaming assistant message */}
          {isStreaming && (
            <div className="flex gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                <Bot className="h-4 w-4" />
              </div>
              <div className="max-w-[80%] rounded-2xl px-4 py-2.5 bg-muted">
                <StreamingToolSection
                  toolEvents={streamingState.toolEvents}
                  reasoning={streamingState.reasoning}
                  step={streamingState.currentStep}
                />
                {streamingState.content ? (
                  <>
                    <p className="text-sm whitespace-pre-wrap">
                      {streamingState.content}
                      <span className="inline-block w-2 h-4 bg-primary/50 animate-pulse ml-0.5 align-text-bottom" />
                    </p>
                    {streamingState.citations.size > 0 && (
                      <div className="mt-2 pt-2 border-t border-current/10 flex flex-wrap gap-1">
                        {Array.from(streamingState.citations.values()).map((c) => (
                          <CitationBadge key={c.marker} citation={c} />
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Thinking...</span>
                  </div>
                )}
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="p-4 border-t bg-muted/30">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex gap-2"
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about this case..."
            disabled={isStreaming}
            className="flex-1"
          />
          <Button type="submit" disabled={!input.trim() || isStreaming}>
            {isStreaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </form>
      </div>
    </div>
  );
}
