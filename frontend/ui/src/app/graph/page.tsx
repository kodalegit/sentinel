/**
 * Full Shadow Graph Explorer page.
 */

"use client";

import { useState } from "react";
import { useFullGraph } from "@/hooks/useTenders";
import { ShadowGraph } from "@/components/ShadowGraph";
import { Shield, ArrowLeft, Loader2, Network, AlertTriangle } from "lucide-react";
import Link from "next/link";
import type { NodeType } from "@/lib/types";

export default function GraphExplorer() {
  const { graph, loading, error } = useFullGraph();
  const [selectedNode, setSelectedNode] = useState<{
    id: string;
    type: NodeType;
  } | null>(null);

  const handleNodeClick = (nodeId: string, nodeType: NodeType) => {
    setSelectedNode({ id: nodeId, type: nodeType });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Link
                href="/"
                className="flex items-center gap-2 text-slate-600 hover:text-slate-900 transition-colors"
              >
                <ArrowLeft size={20} />
                <span className="text-sm font-medium">Back to Dashboard</span>
              </Link>

              <div className="h-8 w-px bg-slate-200" />

              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center">
                  <Shield className="text-white" size={22} />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-slate-900">
                    Shadow Graph Explorer
                  </h1>
                  <p className="text-xs text-slate-500">
                    Visualize hidden procurement networks
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {graph && (
                <div className="text-sm text-slate-500">
                  <span className="font-medium text-slate-700">
                    {graph.nodes.length}
                  </span>{" "}
                  nodes •{" "}
                  <span className="font-medium text-slate-700">
                    {graph.edges.length}
                  </span>{" "}
                  connections
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 relative">
        {loading ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <Loader2 className="w-12 h-12 animate-spin text-blue-600 mx-auto mb-4" />
              <p className="text-slate-600">Loading graph data...</p>
            </div>
          </div>
        ) : error ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
              <p className="text-slate-600">Failed to load graph data</p>
              <p className="text-sm text-slate-500">{error.message}</p>
            </div>
          </div>
        ) : graph ? (
          <div className="h-[calc(100vh-64px)]">
            <ShadowGraph
              data={graph}
              onNodeClick={handleNodeClick}
            />
          </div>
        ) : null}

        {/* Info panel */}
        <div className="absolute top-4 left-4 bg-white rounded-xl shadow-lg p-4 max-w-xs">
          <div className="flex items-center gap-2 mb-3">
            <Network className="text-blue-600" size={20} />
            <h3 className="font-semibold text-slate-900">About This Graph</h3>
          </div>
          <p className="text-sm text-slate-600 mb-3">
            The Shadow Graph reveals hidden connections in public procurement.
            Look for:
          </p>
          <ul className="text-sm text-slate-600 space-y-1">
            <li className="flex items-start gap-2">
              <span className="text-red-500">•</span>
              <span>
                <strong>Red dashed lines</strong> - Suspicious relationships
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-purple-500">•</span>
              <span>
                <strong>Tight clusters</strong> - Potential cartels
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-amber-500">•</span>
              <span>
                <strong>Glowing nodes</strong> - High-risk tenders
              </span>
            </li>
          </ul>
        </div>

        {/* Selected node info */}
        {selectedNode && (
          <div className="absolute bottom-4 left-4 bg-white rounded-xl shadow-lg p-4 max-w-sm">
            <h4 className="font-semibold text-slate-900 mb-2">
              Selected: {selectedNode.type}
            </h4>
            <p className="text-sm text-slate-600">ID: {selectedNode.id}</p>
            <button
              onClick={() => setSelectedNode(null)}
              className="mt-2 text-sm text-blue-600 hover:text-blue-700"
            >
              Clear selection
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
