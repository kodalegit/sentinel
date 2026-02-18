/**
 * Shadow Graph Explorer - cluster-first UX.
 * Shows detected communities in a sidebar, clicking one loads its subgraph.
 */

"use client";

import { useState } from "react";
import { useFullGraph, useCommunities, useCommunityGraph } from "@/hooks/useTenders";
import { ShadowGraph } from "@/components/ShadowGraph";
import { AuthGuard } from "@/components/AuthGuard";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Loader2,
  AlertTriangle,
  Users,
  Phone,
  MapPin,
  UserCheck,
  LayoutGrid,
} from "lucide-react";
import type { CommunityCluster } from "@/lib/types";

function GraphExplorerContent() {
  const { graph: fullGraph, loading: graphLoading, error } = useFullGraph();
  const { clusters, loading: clustersLoading } = useCommunities();
  const [selectedCluster, setSelectedCluster] = useState<CommunityCluster | null>(null);
  const [viewMode, setViewMode] = useState<"full" | "cluster">("full");

  const { graph: clusterGraph, loading: clusterGraphLoading } = useCommunityGraph(
    viewMode === "cluster" && selectedCluster ? selectedCluster.id : null
  );

  const handleClusterClick = (cluster: CommunityCluster) => {
    setSelectedCluster(cluster);
    setViewMode("cluster");
  };

  const handleShowFullGraph = () => {
    setViewMode("full");
    setSelectedCluster(null);
  };

  const activeGraph = viewMode === "cluster" && clusterGraph ? clusterGraph : fullGraph;
  const isLoading = viewMode === "cluster" ? clusterGraphLoading : graphLoading;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Page header */}
      <header className="shrink-0 border-b border-border/70 bg-card/70 backdrop-blur-sm z-30">
        <div className="px-6 lg:px-10">
          <div className="flex flex-col gap-4 py-6 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.35em] text-muted-foreground">
                Network Intelligence
              </p>
              <h1 className="font-display text-2xl text-foreground">
                Shadow Graph Explorer
              </h1>
              <p className="text-xs text-muted-foreground max-w-xl">
                Visualize procurement relationships, suspicious ties, and community clusters with guided focus views.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {activeGraph && (
                <span className="text-xs text-muted-foreground tabular-nums">
                  <span className="text-foreground/70">{activeGraph.nodes.length}</span> nodes
                  <span className="mx-1.5 opacity-40">&middot;</span>
                  <span className="text-foreground/70">{activeGraph.edges.length}</span> edges
                </span>
              )}
              {viewMode === "cluster" && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleShowFullGraph}
                  className="text-xs h-8"
                >
                  <LayoutGrid size={14} />
                  Full Graph
                </Button>
              )}
            </div>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Cluster sidebar */}
        <aside className="w-80 shrink-0 border-r border-border/60 bg-card/70 flex flex-col">
          <div className="p-5 border-b border-border/60">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.25em] text-muted-foreground flex items-center gap-2">
              <Users size={14} className="text-primary" />
              Detected Communities
            </h2>
            <p className="mt-2 text-xs text-muted-foreground">
              Click a cluster to isolate its network and reduce visual noise.
            </p>
          </div>

          <ScrollArea className="flex-1">
            <div className="p-3 space-y-2">
              {clustersLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-5 h-5 animate-spin text-primary" />
                </div>
              ) : clusters.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-12">
                  No communities detected
                </p>
              ) : (
                clusters.map((cluster) => (
                  <ClusterCard
                    key={cluster.id}
                    cluster={cluster}
                    isSelected={selectedCluster?.id === cluster.id}
                    onClick={() => handleClusterClick(cluster)}
                  />
                ))
              )}
            </div>
          </ScrollArea>
        </aside>

        {/* Graph area */}
        <main className="flex-1 relative">
          {isLoading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">Loading graph...</p>
              </div>
            </div>
          ) : error ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <AlertTriangle className="w-8 h-8 text-destructive mx-auto mb-3" />
                <p className="text-sm">Failed to load graph data</p>
                <p className="text-xs text-muted-foreground mt-1">{error.message}</p>
              </div>
            </div>
          ) : activeGraph ? (
            <div className="h-full">
              <ShadowGraph
                data={activeGraph}
                focusNodeId={selectedCluster?.company_ids[0]}
              />
            </div>
          ) : null}

          {/* Cluster detail overlay */}
          {selectedCluster && viewMode === "cluster" && (
            <div className="absolute bottom-4 right-4 w-80 animate-fade-in-up">
              <div className="rounded-2xl border border-border/60 bg-card/95 backdrop-blur-sm shadow-xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                    Cluster Details
                  </span>
                  <SuspicionBadge score={selectedCluster.suspicion_score} />
                </div>

                <div className="space-y-3 text-xs">
                  <div>
                    <span className="text-muted-foreground">Companies:</span>
                    <ul className="mt-1.5 space-y-1">
                      {selectedCluster.company_names.map((name, i) => (
                        <li key={i} className="flex items-center gap-1.5">
                          <span className="w-1 h-1 rounded-full bg-primary" />
                          <span className="text-foreground/80">{name}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {selectedCluster.shared_attributes.phones.length > 0 && (
                    <div className="flex items-start gap-2 rounded-md border border-[#b78b43]/20 bg-[#b78b43]/10 p-2 text-[#b78b43]">
                      <Phone size={12} className="mt-0.5 shrink-0" />
                      <span>Shared phone numbers</span>
                    </div>
                  )}
                  {selectedCluster.shared_attributes.directors.length > 0 && (
                    <div className="flex items-start gap-2 rounded-md border border-[#c4412f]/20 bg-[#c4412f]/10 p-2 text-[#c4412f]">
                      <UserCheck size={12} className="mt-0.5 shrink-0" />
                      <span>Shared directors</span>
                    </div>
                  )}
                  {selectedCluster.shared_attributes.addresses.length > 0 && (
                    <div className="flex items-start gap-2 rounded-md border border-[#35638c]/20 bg-[#35638c]/10 p-2 text-[#35638c]">
                      <MapPin size={12} className="mt-0.5 shrink-0" />
                      <span>Shared addresses</span>
                    </div>
                  )}

                  <div className="text-muted-foreground pt-1 border-t border-border/40">
                    Co-bid on <span className="text-foreground/70 font-medium">{selectedCluster.co_bid_count}</span> tenders
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default function GraphExplorer() {
  return (
    <AuthGuard>
      <GraphExplorerContent />
    </AuthGuard>
  );
}

function SuspicionBadge({ score }: { score: number }) {
  const cfg =
    score >= 60
      ? { text: "text-[#c4412f]", bg: "bg-[#c4412f]/10", border: "border-[#c4412f]/25" }
      : score >= 30
      ? { text: "text-[#b78b43]", bg: "bg-[#b78b43]/10", border: "border-[#b78b43]/25" }
      : { text: "text-[#1f6f5c]", bg: "bg-[#1f6f5c]/10", border: "border-[#1f6f5c]/25" };

  return (
    <span className={`inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded border ${cfg.text} ${cfg.bg} ${cfg.border}`}>
      {score}
    </span>
  );
}

function ClusterCard({
  cluster,
  isSelected,
  onClick,
}: {
  cluster: CommunityCluster;
  isSelected: boolean;
  onClick: () => void;
}) {
  const scoreColor =
    cluster.suspicion_score >= 60
      ? "text-[#c4412f]"
      : cluster.suspicion_score >= 30
      ? "text-[#b78b43]"
      : "text-[#1f6f5c]";

  return (
    <div
      onClick={onClick}
      className={`
        cursor-pointer rounded-lg px-3 py-2.5 transition-all duration-150
        ${
          isSelected
            ? "bg-accent border border-primary/30"
            : "hover:bg-accent/50 border border-transparent"
        }
      `}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium truncate text-foreground/90">
            {cluster.company_names[0]}
            {cluster.size > 1 && (
              <span className="text-muted-foreground"> +{cluster.size - 1}</span>
            )}
          </p>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            {cluster.co_bid_count} co-bids
            {cluster.shared_attributes.directors.length > 0 && " \u2022 shared dirs"}
          </p>
        </div>
        <span className={`text-sm font-bold tabular-nums ${scoreColor}`}>
          {cluster.suspicion_score}
        </span>
      </div>
    </div>
  );
}
