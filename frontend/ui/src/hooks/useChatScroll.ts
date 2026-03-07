"use client";

import { useRef, useState, useCallback, useLayoutEffect, useEffect } from "react";
import type { ChatMessage } from "@/lib/types";
import type { StreamingState } from "@/hooks/useStreamChat";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UseChatScrollOptions {
  messages: ChatMessage[];
  pendingUserMessage: string | null;
  streamingState: StreamingState;
  isStreaming: boolean;
  activeThreadId: string | null;
}

interface UseChatScrollReturn {
  containerRef: React.RefObject<HTMLDivElement | null>;
  userAnchorRef: React.RefObject<HTMLDivElement | null>;
  showScrollToBottom: boolean;
  scrollToBottom: (behavior?: ScrollBehavior) => void;
  onScroll: () => void;
  markShouldAnchor: () => void;
  markInitialScroll: (threadId: string | null) => void;
  /** Messages rendered before the response canvas (up to and including the anchored user message). */
  messagesBeforeCanvas: ChatMessage[];
  /** Messages rendered inside the response canvas (after the anchored user message). */
  messagesInsideCanvas: ChatMessage[];
  /** Whether the pending optimistic user message should be used as the anchor target. */
  usePendingAnchor: boolean;
  /** Whether a persisted user message should be used as the anchor target. */
  usePersistedAnchor: boolean;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useChatScroll({
  messages,
  pendingUserMessage,
  streamingState,
  isStreaming,
  activeThreadId,
}: UseChatScrollOptions): UseChatScrollReturn {
  const containerRef = useRef<HTMLDivElement>(null);
  const userAnchorRef = useRef<HTMLDivElement>(null);
  const pendingInitialScrollThreadIdRef = useRef<string | null>(null);
  const shouldAnchorRef = useRef(false);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);

  // -------------------------------------------------------------------------
  // Visibility check
  // -------------------------------------------------------------------------

  const updateVisibility = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    const hasOverflow = container.scrollHeight - container.clientHeight > 24;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;

    setShowScrollToBottom(hasOverflow && distanceFromBottom > 48);
  }, []);

  // -------------------------------------------------------------------------
  // Scroll actions
  // -------------------------------------------------------------------------

  const scrollToBottom = useCallback(
    (behavior: ScrollBehavior = "smooth") => {
      const container = containerRef.current;
      if (!container) return;

      container.scrollTo({ top: container.scrollHeight, behavior });
      requestAnimationFrame(updateVisibility);
    },
    [updateVisibility],
  );

  const scrollAnchorToTop = useCallback(
    (behavior: ScrollBehavior = "smooth") => {
      const container = containerRef.current;
      const anchor = userAnchorRef.current;
      if (!container || !anchor) return;

      const containerRect = container.getBoundingClientRect();
      const anchorRect = anchor.getBoundingClientRect();
      const nextScrollTop =
        container.scrollTop + (anchorRect.top - containerRect.top);

      container.scrollTo({ top: Math.max(nextScrollTop, 0), behavior });
      requestAnimationFrame(updateVisibility);
    },
    [updateVisibility],
  );

  // -------------------------------------------------------------------------
  // Public helpers
  // -------------------------------------------------------------------------

  const markShouldAnchor = useCallback(() => {
    shouldAnchorRef.current = true;
  }, []);

  const markInitialScroll = useCallback((threadId: string | null) => {
    pendingInitialScrollThreadIdRef.current = threadId;
  }, []);

  // -------------------------------------------------------------------------
  // Derived message splits
  // -------------------------------------------------------------------------

  const lastPersistedUserIndex = (() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i]?.role === "user") return i;
    }
    return -1;
  })();

  const usePersistedAnchor =
    !pendingUserMessage &&
    (isStreaming || !!streamingState.content) &&
    lastPersistedUserIndex >= 0;

  const usePendingAnchor = !!pendingUserMessage;

  const messagesBeforeCanvas = usePersistedAnchor
    ? messages.slice(0, lastPersistedUserIndex + 1)
    : messages;

  const messagesInsideCanvas = usePersistedAnchor
    ? messages.slice(lastPersistedUserIndex + 1)
    : [];

  // -------------------------------------------------------------------------
  // Effects
  // -------------------------------------------------------------------------

  // Initial thread load → jump to bottom instantly
  useLayoutEffect(() => {
    if (
      !activeThreadId ||
      pendingInitialScrollThreadIdRef.current !== activeThreadId ||
      messages.length === 0
    ) {
      return;
    }

    scrollToBottom("auto");
    pendingInitialScrollThreadIdRef.current = null;
  }, [activeThreadId, messages, scrollToBottom]);

  // Anchor new user message to the top of the viewport
  useLayoutEffect(() => {
    if (!shouldAnchorRef.current) return;
    if (!pendingUserMessage && !usePersistedAnchor) return;

    scrollAnchorToTop("smooth");
    shouldAnchorRef.current = false;
  }, [pendingUserMessage, usePersistedAnchor, scrollAnchorToTop]);

  // Keep scroll button visibility in sync with content changes
  useEffect(() => {
    updateVisibility();
  }, [messages, pendingUserMessage, streamingState.content, streamingState.items, updateVisibility]);

  return {
    containerRef,
    userAnchorRef,
    showScrollToBottom,
    scrollToBottom,
    onScroll: updateVisibility,
    markShouldAnchor,
    markInitialScroll,
    messagesBeforeCanvas,
    messagesInsideCanvas,
    usePendingAnchor,
    usePersistedAnchor,
  };
}
