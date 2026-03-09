/**
 * Shadow Graph Explorer - cluster-first UX.
 * Shows detected communities in a sidebar, clicking one loads its subgraph.
 */

"use client";

import { AuthGuard } from "@/components/AuthGuard";
import { GraphExplorerContent } from "@/components/GraphExplorerContent";

export default function GraphExplorer() {
  return (
    <AuthGuard>
      <GraphExplorerContent />
    </AuthGuard>
  );
}
