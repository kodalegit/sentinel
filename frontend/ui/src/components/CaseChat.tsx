"use client";

import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getChatThreads,
  getThreadMessages,
  streamChat,
  generateCaseSummary,
  suggestNextSteps,
} from "@/lib/api";
import type { ChatThread, ChatMessage, Citation, ChatStreamEvent } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
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
  Plus,
} from "lucide-react";

interface CaseChatProps {
  caseId: string;
}

function CitationBadge({ citation }: { citation: Citation }) {
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs rounded bg-primary/10 text-primary cursor-help"
      title={`${citation.title}\n${citation.excerpt}`}
    >
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
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

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
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted"
        }`}
      >
        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 pt-2 border-t border-current/10 flex flex-wrap gap-1">
            {message.citations.map((c) => (
              <CitationBadge key={c.marker} citation={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function CaseChat({ caseId }: CaseChatProps) {
  const queryClient = useQueryClient();
  const [input, setInput] = useState("");
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [showThreads, setShowThreads] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

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

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent]);

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;

    const userMessage = input.trim();
    setInput("");
    setIsStreaming(true);
    setStreamingContent("");

    try {
      for await (const event of streamChat(caseId, userMessage, activeThreadId || undefined)) {
        if (event.type === "token" && event.content) {
          setStreamingContent((prev) => prev + event.content);
        } else if (event.type === "done") {
          if (event.thread_id && !activeThreadId) {
            setActiveThreadId(event.thread_id);
          }
          queryClient.invalidateQueries({ queryKey: ["chat-threads", caseId] });
          refetchMessages();
          setStreamingContent("");
        } else if (event.type === "error") {
          console.error("Chat error:", event.error);
        }
      }
    } catch (error) {
      console.error("Stream error:", error);
    } finally {
      setIsStreaming(false);
    }
  };

  const summaryMutation = useMutation({
    mutationFn: () => generateCaseSummary(caseId),
  });

  const nextStepsMutation = useMutation({
    mutationFn: () => suggestNextSteps(caseId),
  });

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
            onClick={() => summaryMutation.mutate()}
            disabled={summaryMutation.isPending}
          >
            {summaryMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            <span className="ml-1 hidden sm:inline">Summary</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => nextStepsMutation.mutate()}
            disabled={nextStepsMutation.isPending}
          >
            {nextStepsMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ListChecks className="h-4 w-4" />
            )}
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

      {/* Summary/Next Steps Results */}
      {summaryMutation.isSuccess && (
        <div className="p-4 border-b bg-primary/5">
          <h4 className="font-medium text-sm mb-2 flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            Case Summary
          </h4>
          <p className="text-sm whitespace-pre-wrap">{summaryMutation.data.summary}</p>
          {summaryMutation.data.citations.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {summaryMutation.data.citations.map((c) => (
                <CitationBadge key={c.marker} citation={c} />
              ))}
            </div>
          )}
        </div>
      )}

      {nextStepsMutation.isSuccess && (
        <div className="p-4 border-b bg-primary/5">
          <h4 className="font-medium text-sm mb-2 flex items-center gap-2">
            <ListChecks className="h-4 w-4" />
            Suggested Next Steps
          </h4>
          <ol className="text-sm space-y-1 list-decimal list-inside">
            {nextStepsMutation.data.suggestions.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </div>
      )}

      {/* Messages */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4">
          {messages.length === 0 && !streamingContent && (
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
          {streamingContent && (
            <div className="flex gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                <Bot className="h-4 w-4" />
              </div>
              <div className="max-w-[80%] rounded-2xl px-4 py-2.5 bg-muted">
                <p className="text-sm whitespace-pre-wrap">{streamingContent}</p>
                <span className="inline-block w-2 h-4 bg-primary/50 animate-pulse ml-0.5" />
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
