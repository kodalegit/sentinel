"use client";

import { memo, useMemo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

interface OptimizedMarkdownProps {
  content: string;
}

const markdownComponents: Components = {
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
  a: (props) => (
    <a
      className="text-primary underline underline-offset-2 hover:text-primary/80 transition-colors"
      target="_blank"
      rel="noopener noreferrer"
      {...props}
    />
  ),
  strong: (props) => <strong className="font-semibold" {...props} />,
};

function parseMarkdownIntoBlocks(markdown: string): string[] {
  return markdown
    .split(/\n\n+/)
    .map((block) => block.trim())
    .filter(Boolean);
}

const MemoizedMarkdownBlock = memo(
  ({ content }: { content: string }) => {
    return (
      <div className="prose prose-slate dark:prose-invert max-w-none text-sm leading-relaxed">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={markdownComponents}
        >
          {content}
        </ReactMarkdown>
      </div>
    );
  },
  (previous, next) => previous.content === next.content,
);

MemoizedMarkdownBlock.displayName = "MemoizedMarkdownBlock";

export function OptimizedMarkdown({ content }: OptimizedMarkdownProps) {
  const blocks = useMemo(() => parseMarkdownIntoBlocks(content), [content]);

  if (!content.trim()) {
    return null;
  }

  return (
    <div className="text-foreground/90">
      {blocks.map((block, index) => (
        <MemoizedMarkdownBlock key={`md-block-${index}`} content={block} />
      ))}
    </div>
  );
}
