"use client";

import { memo, useMemo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Citation } from "@/lib/types";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface OptimizedMarkdownProps {
  content: string;
  citations?: Citation[] | Map<number, Citation>;
}

const CITATION_LINK_PREFIX = "citation://";

function citationUrlTransform(url: string): string {
  if (url.startsWith(CITATION_LINK_PREFIX)) {
    return url;
  }
  // Inline the safe-protocol check from react-markdown's defaultUrlTransform
  const colon = url.indexOf(":");
  const questionMark = url.indexOf("?");
  const numberSign = url.indexOf("#");
  const slash = url.indexOf("/");
  if (
    colon === -1 ||
    (slash !== -1 && colon > slash) ||
    (questionMark !== -1 && colon > questionMark) ||
    (numberSign !== -1 && colon > numberSign) ||
    /^(https?|ircs?|mailto|xmpp)$/i.test(url.slice(0, colon))
  ) {
    return url;
  }
  return "";
}

function normalizeCitations(
  citations?: Citation[] | Map<number, Citation>,
): Map<number, Citation> {
  if (!citations) {
    return new Map();
  }
  if (citations instanceof Map) {
    return citations;
  }
  return new Map(citations.map((citation) => [citation.marker, citation]));
}

function linkifyCitationMarkers(markdown: string): string {
  return markdown.replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, (match, rawMarkers) => {
    const markers = rawMarkers
      .split(",")
      .map((value: string) => Number(value.trim()))
      .filter((value: number) => Number.isInteger(value) && value > 0);

    if (markers.length === 0) {
      return match;
    }

    return markers
      .map((marker: number) => `[${marker}](${CITATION_LINK_PREFIX}${marker})`)
      .join("");
  });
}

function InlineCitation({ marker, citation }: { marker: number; citation?: Citation }) {
  if (!citation) {
    return (
      <span className="mx-0.5 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-[4px] border border-border/70 bg-muted/70 px-1 align-baseline font-sans text-[10px] font-medium leading-none text-muted-foreground">
        {marker}
      </span>
    );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={`View citation ${marker}`}
          className="mx-0.5 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-[4px] bg-primary/10 px-1 align-baseline font-sans text-[10px] font-medium leading-none text-primary shadow-sm transition-colors hover:bg-primary/20 dark:bg-primary/20 dark:hover:bg-primary/30"
        >
          {marker}
        </button>
      </TooltipTrigger>
      <TooltipContent
        side="top"
        align="center"
        sideOffset={6}
        className="max-w-[16rem] rounded-lg border border-border/80 bg-popover/95 px-3.5 py-3 text-left text-popover-foreground shadow-xl backdrop-blur-md"
      >
        <div className="space-y-2.5">
          <p className="text-xs font-semibold leading-snug text-foreground">
            {citation.title || `Source ${marker}`}
          </p>
          
          <div className="space-y-1.5">
            <div>
              <span className="inline-flex items-center rounded-md bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                {citation.category || "Source"}
              </span>
            </div>
            
            {citation.page && (
              <p className="text-[11px] text-muted-foreground">
                Page {citation.page}
              </p>
            )}
          </div>

          {citation.source_url && (
            <a
              href={citation.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              View source
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                <polyline points="15 3 21 3 21 9"></polyline>
                <line x1="10" y1="14" x2="21" y2="3"></line>
              </svg>
            </a>
          )}
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

function createMarkdownComponents(citations: Map<number, Citation>): Components {
  return {
    p: (props) => <p className="mb-3 leading-relaxed" {...props} />,
    ul: (props) => <ul className="mb-3 list-disc space-y-1 pl-6" {...props} />,
    ol: (props) => <ol className="mb-3 list-decimal space-y-1 pl-6" {...props} />,
    li: (props) => <li className="ml-2 leading-relaxed" {...props} />,
    h1: (props) => <h1 className="mb-4 mt-6 text-xl font-bold" {...props} />,
    h2: (props) => <h2 className="mb-3 mt-5 text-lg font-bold" {...props} />,
    h3: (props) => <h3 className="mb-3 mt-4 text-base font-semibold" {...props} />,
    table: (props) => (
      <div className="my-4 overflow-x-auto">
        <table className="w-full border-collapse text-sm" {...props} />
      </div>
    ),
    th: (props) => (
      <th
        className="border border-border/60 bg-muted/40 px-4 py-2 text-left text-xs font-medium"
        {...props}
      />
    ),
    td: (props) => (
      <td className="border border-border/60 px-4 py-2 text-xs" {...props} />
    ),
    hr: (props) => <hr className="my-6 border-border/60" {...props} />,
    blockquote: (props) => (
      <blockquote
        className="my-4 border-l-4 border-border/60 pl-4 italic text-muted-foreground"
        {...props}
      />
    ),
    code: ({ className, children, ...props }) => {
      if (!className) {
        return (
          <code
            className="rounded bg-muted/60 px-1.5 py-0.5 text-xs font-mono"
            {...props}
          >
            {children}
          </code>
        );
      }

      return (
        <code
          className="block rounded-md bg-muted/40 border border-border/40 p-3 text-xs font-mono overflow-x-auto whitespace-pre-wrap"
          {...props}
        >
          {children}
        </code>
      );
    },
    a: ({ href, children, ...props }) => {
      if (href?.startsWith(CITATION_LINK_PREFIX)) {
        const marker = Number(href.slice(CITATION_LINK_PREFIX.length));
        return <InlineCitation marker={marker} citation={citations.get(marker)} />;
      }

      return (
        <a
          className="text-primary underline underline-offset-2 hover:text-primary/80 transition-colors"
          target="_blank"
          rel="noopener noreferrer"
          href={href}
          {...props}
        >
          {children}
        </a>
      );
    },
    strong: (props) => <strong className="font-semibold" {...props} />,
  };
}

function parseMarkdownIntoBlocks(markdown: string): string[] {
  return markdown
    .split(/\n\n+/)
    .map((block) => block.trim())
    .filter(Boolean);
}

const MemoizedMarkdownBlock = memo(
  ({ content, citations }: { content: string; citations: Map<number, Citation> }) => {
    const markdownComponents = useMemo(
      () => createMarkdownComponents(citations),
      [citations],
    );

    return (
      <div className="prose prose-slate dark:prose-invert max-w-none text-sm leading-relaxed">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents} urlTransform={citationUrlTransform}>
          {content}
        </ReactMarkdown>
      </div>
    );
  },
  (previous, next) => previous.content === next.content && previous.citations === next.citations,
);

MemoizedMarkdownBlock.displayName = "MemoizedMarkdownBlock";

export function OptimizedMarkdown({ content, citations }: OptimizedMarkdownProps) {
  const citationMap = useMemo(() => normalizeCitations(citations), [citations]);
  const contentWithCitationLinks = useMemo(() => linkifyCitationMarkers(content), [content]);
  const blocks = useMemo(
    () => parseMarkdownIntoBlocks(contentWithCitationLinks),
    [contentWithCitationLinks],
  );

  if (!content.trim()) {
    return null;
  }

  return (
    <TooltipProvider>
      <div className="text-foreground/90">
        {blocks.map((block, index) => (
          <MemoizedMarkdownBlock
            key={`md-block-${index}`}
            content={block}
            citations={citationMap}
          />
        ))}
      </div>
    </TooltipProvider>
  );
}
