"use client";

import { useState, useEffect, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  deleteChatThread,
  getChatThreads,
  getThreadMessages,
  streamChat,
  type StreamAction,
} from "@/lib/api";
import type { Citation, ChatStreamEvent } from "@/lib/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ToolRecord {
  tool: string;
  toolCallId: string;
  status: "running" | "complete";
  input?: Record<string, unknown>;
  summary?: string;
}

export type StreamItem =
  | { kind: "reasoning"; text: string }
  | { kind: "tool"; record: ToolRecord };

export interface StreamingState {
  content: string;
  items: StreamItem[];
  citations: Map<number, Citation>;
  isComplete: boolean;
}

function createInitialStreamingState(): StreamingState {
  return {
    content: "",
    items: [],
    citations: new Map(),
    isComplete: false,
  };
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useStreamChat(caseId: string) {
  const queryClient = useQueryClient();
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [streamingState, setStreamingState] = useState<StreamingState>(
    createInitialStreamingState,
  );
  const [isStreaming, setIsStreaming] = useState(false);
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);
  const [dynamicTitle, setDynamicTitle] = useState<string | null>(null);

  // -----------------------------------------------------------------------
  // Server state queries
  // -----------------------------------------------------------------------
  const { data: threads = [], isFetched: threadsLoaded } = useQuery({
    queryKey: ["chat-threads", caseId],
    queryFn: () => getChatThreads(caseId),
  });

  const { data: messages = [], refetch: refetchMessages } = useQuery({
    queryKey: ["chat-messages", caseId, activeThreadId],
    queryFn: () =>
      activeThreadId ? getThreadMessages(caseId, activeThreadId) : Promise.resolve([]),
    enabled: !!activeThreadId,
  });

  // -----------------------------------------------------------------------
  // Stream event handler — builds interleaved items array
  // -----------------------------------------------------------------------
  const handleStreamEvent = useCallback((event: ChatStreamEvent) => {
    switch (event.type) {
      case "token":
        setStreamingState((prev) => ({
          ...prev,
          content: prev.content + (event.delta || ""),
        }));
        break;

      case "reasoning": {
        const text = event.content || "";
        if (text) {
          setStreamingState((prev) => ({
            ...prev,
            items: [...prev.items, { kind: "reasoning", text }],
          }));
        }
        break;
      }

      case "tool_start": {
        const record: ToolRecord = {
          tool: event.tool || "unknown",
          toolCallId: event.tool_call_id || "",
          status: "running",
          input: event.input,
        };
        setStreamingState((prev) => ({
          ...prev,
          items: [...prev.items, { kind: "tool", record }],
        }));
        break;
      }

      case "tool_end": {
        setStreamingState((prev) => ({
          ...prev,
          items: prev.items.map((item) => {
            if (item.kind === "tool" && item.record.toolCallId === event.tool_call_id) {
              return {
                ...item,
                record: {
                  ...item.record,
                  status: "complete" as const,
                  summary: event.summary,
                },
              };
            }
            return item;
          }),
        }));
        break;
      }

      case "citation":
        if (event.marker !== undefined) {
          setStreamingState((prev) => {
            const newCitations = new Map(prev.citations);
            newCitations.set(event.marker!, {
              marker: event.marker!,
              doc_id: event.doc_id || "",
              title: event.title || "",
              source_url: event.source_url || null,
              category: event.category || "",
              excerpt: event.excerpt || "",
              page: event.page || null,
              chunk_id: event.chunk_id || "",
            });
            return { ...prev, citations: newCitations };
          });
        }
        break;

      case "title":
        if (event.title) {
          setDynamicTitle(event.title);
        }
        break;

      case "done":
        setStreamingState((prev) => {
          const newCitations = new Map(prev.citations);
          if (event.citations) {
            for (const c of event.citations) {
              newCitations.set(c.marker, c);
            }
          }
          return { ...prev, isComplete: true, citations: newCitations };
        });
        break;

      case "error":
        console.error("Stream error:", event.message);
        break;
    }
  }, []);

  // -----------------------------------------------------------------------
  // Run a stream
  // -----------------------------------------------------------------------
  const runStream = useCallback(
    async (message: string, action: StreamAction) => {
      setIsStreaming(true);
      setStreamingState(createInitialStreamingState());
      if (!activeThreadId) {
        setDynamicTitle(null);
      }

      if (message) {
        setPendingUserMessage(message);
      }

      try {
        for await (const event of streamChat(caseId, message, {
          threadId: activeThreadId || undefined,
          action,
        })) {
          handleStreamEvent(event);

          if (event.type === "done") {
            if (event.thread_id && !activeThreadId) {
              setActiveThreadId(event.thread_id);
            } else if (activeThreadId) {
              await refetchMessages();
            }
            queryClient.invalidateQueries({ queryKey: ["chat-threads", caseId] });
          }
        }
      } catch (error) {
        console.error("Stream error:", error);
      } finally {
        setIsStreaming(false);
      }
    },
    [caseId, activeThreadId, queryClient, refetchMessages, handleStreamEvent],
  );

  useEffect(() => {
    if (!pendingUserMessage) {
      return;
    }

    const latestUserMessage = [...messages]
      .reverse()
      .find((message) => message.role === "user");

    if (latestUserMessage?.content === pendingUserMessage) {
      setPendingUserMessage(null);
    }
  }, [messages, pendingUserMessage]);

  useEffect(() => {
    if (!streamingState.isComplete || !streamingState.content) {
      return;
    }

    const latestAssistantMessage = [...messages]
      .reverse()
      .find((message) => message.role === "assistant");

    if (latestAssistantMessage?.content === streamingState.content) {
      setStreamingState(createInitialStreamingState());
    }
  }, [messages, streamingState.content, streamingState.isComplete]);

  // -----------------------------------------------------------------------
  // Derived state
  // -----------------------------------------------------------------------
  const hasRunningTools = streamingState.items.some(
    (item) => item.kind === "tool" && item.record.status === "running",
  );
  const hasAnyItems = streamingState.items.length > 0;
  const showWaitingIndicator = isStreaming && !streamingState.content && !hasAnyItems;
  const showProcessingIndicator =
    isStreaming && !streamingState.content && hasAnyItems && !hasRunningTools;

  const activeThreadTitle =
    dynamicTitle ||
    threads.find((t) => t.id === activeThreadId)?.title ||
    "Current Session";

  const selectThread = useCallback((threadId: string | null) => {
    setDynamicTitle(null);
    setActiveThreadId(threadId);
    setStreamingState(createInitialStreamingState());
    setPendingUserMessage(null);
  }, []);

  const handleNewThread = useCallback(() => {
    setActiveThreadId(null);
    setDynamicTitle(null);
    setStreamingState(createInitialStreamingState());
    setPendingUserMessage(null);
  }, []);

  const deleteThread = useCallback(
    async (threadId: string) => {
      await deleteChatThread(caseId, threadId);

      if (activeThreadId === threadId) {
        setActiveThreadId(null);
        setDynamicTitle(null);
        setStreamingState(createInitialStreamingState());
        setPendingUserMessage(null);
      }

      await queryClient.invalidateQueries({ queryKey: ["chat-threads", caseId] });
      await queryClient.invalidateQueries({ queryKey: ["chat-messages", caseId, threadId] });
    },
    [activeThreadId, caseId, queryClient],
  );

  return {
    // State
    threads,
    threadsLoaded,
    messages,
    activeThreadId,
    activeThreadTitle,
    streamingState,
    isStreaming,
    pendingUserMessage,
    dynamicTitle,
    // Derived
    hasRunningTools,
    hasAnyItems,
    showWaitingIndicator,
    showProcessingIndicator,
    // Actions
    selectThread,
    deleteThread,
    runStream,
    handleNewThread,
  };
}
