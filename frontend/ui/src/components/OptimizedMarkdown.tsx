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
  const label = `[${marker}]`;

  if (!citation) {
    return (
      <span className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-[6px] border border-border/70 bg-muted/70 px-1.5 align-baseline font-mono text-[10px] font-semibold leading-none text-amber-700 dark:text-amber-300">
        {label}
      </span>
    );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={`View citation ${marker}`}
          className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-[6px] border border-border/70 bg-muted/80 px-1.5 align-baseline font-mono text-[10px] font-semibold leading-none text-amber-700 shadow-sm transition-colors hover:bg-muted dark:text-amber-300"
        >
          {label}
        </button>
      </TooltipTrigger>
      <TooltipContent
        side="top"
        align="start"
        sideOffset={8}
        className="max-w-[18rem] rounded-xl border border-border/80 bg-popover px-3 py-2.5 text-left text-popover-foreground shadow-xl [&>svg]:hidden"
      >
        <div className="space-y-2">
          <div className="space-y-1">
            <div className="flex items-center gap-1.5">
              <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-[6px] bg-amber-500/10 px-1.5 font-mono text-[10px] font-semibold leading-none text-amber-700 dark:text-amber-300">
                {marker}
              </span>
              <p className="min-w-0 text-xs font-semibold leading-snug">{citation.title || `Source ${marker}`}</p>
            </div>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
              {citation.category || "source"}
              {citation.page ? ` · Page ${citation.page}` : ""}
            </p>
          </div>

          {citation.excerpt && (
            <p className="text-[11px] leading-relaxed text-muted-foreground">{citation.excerpt}</p>
          )}

          {citation.source_url && (
            <a
              href={citation.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex text-[11px] font-medium text-muted-foreground underline underline-offset-2 hover:text-foreground"
            >
              View source
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
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
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
