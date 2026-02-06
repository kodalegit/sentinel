/**
 * Shadow Graph Explorer - cluster-first UX.
 * Shows detected communities in a sidebar, clicking one loads its subgraph.
 */

"use client";

import { useState, useEffect } from "react";
import { useFullGraph } from "@/hooks/useTenders";
import { ShadowGraph } from "@/components/ShadowGraph";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Shield,
  ArrowLeft,
  Loader2,
  Network,
  AlertTriangle,
  Users,
  Phone,
  MapPin,
  UserCheck,
  Eye,
  LayoutGrid,
} from "lucide-react";
import Link from "next/link";
import type { NodeType, CommunityCluster, GraphData } from "@/lib/types";
import { getCommunities, getCommunityGraph } from "@/lib/api";

export default function GraphExplorer() {
  const { graph: fullGraph, loading: graphLoading, error } = useFullGraph();
  const [clusters, setClusters] = useState<CommunityCluster[]>([]);
  const [clustersLoading, setClustersLoading] = useState(true);
  const [selectedCluster, setSelectedCluster] = useState<CommunityCluster | null>(null);
  const [clusterGraph, setClusterGraph] = useState<GraphData | null>(null);
  const [clusterGraphLoading, setClusterGraphLoading] = useState(false);
  const [viewMode, setViewMode] = useState<"full" | "cluster">("full");

  // Load communities on mount
  useEffect(() => {
    getCommunities()
      .then((data) => setClusters(data.clusters))
      .catch(() => {})
      .finally(() => setClustersLoading(false));
  }, []);

  // Load cluster subgraph when selected
  const handleClusterClick = async (cluster: CommunityCluster) => {
    setSelectedCluster(cluster);
    setViewMode("cluster");
    setClusterGraphLoading(true);
    try {
      const data = await getCommunityGraph(cluster.id);
      setClusterGraph(data);
    } catch {
      setClusterGraph(null);
    } finally {
      setClusterGraphLoading(false);
    }
  };

  const handleShowFullGraph = () => {
    setViewMode("full");
    setSelectedCluster(null);
    setClusterGraph(null);
  };

  const activeGraph = viewMode === "cluster" && clusterGraph ? clusterGraph : fullGraph;
  const isLoading = viewMode === "cluster" ? clusterGraphLoading : graphLoading;

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="bg-card border-b">
        <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Link href="/">
                <Button variant="ghost" size="sm">
                  <ArrowLeft size={18} />
                  Dashboard
                </Button>
              </Link>

              <Separator orientation="vertical" className="h-8" />

              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-linear-to-br from-blue-600 to-indigo-700 flex items-center justify-center">
                  <Shield className="text-white" size={22} />
                </div>
                <div>
                  <h1 className="text-xl font-bold">Shadow Graph Explorer</h1>
                  <p className="text-xs text-muted-foreground">
                    {viewMode === "cluster" && selectedCluster
                      ? `Viewing: ${selectedCluster.company_names[0]} cluster`
                      : "Full procurement network"}
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {activeGraph && (
                <span className="text-sm text-muted-foreground">
                  <span className="font-medium">{activeGraph.nodes.length}</span> nodes
                  {" \u2022 "}
                  <span className="font-medium">{activeGraph.edges.length}</span> edges
                </span>
              )}
              {viewMode === "cluster" && (
                <Button variant="outline" size="sm" onClick={handleShowFullGraph}>
                  <LayoutGrid size={16} />
                  Full Graph
                </Button>
              )}
            </div>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Cluster sidebar */}
        <aside className="w-80 border-r bg-card flex flex-col">
          <div className="p-4 border-b">
            <h2 className="font-semibold flex items-center gap-2">
              <Users size={18} className="text-primary" />
              Detected Communities
            </h2>
            <p className="text-xs text-muted-foreground mt-1">
              Click a cluster to explore its subgraph
            </p>
          </div>

          <ScrollArea className="flex-1">
            <div className="p-3 space-y-2">
              {clustersLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-primary" />
                </div>
              ) : clusters.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
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
                <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
                <p className="text-muted-foreground">Loading graph...</p>
              </div>
            </div>
          ) : error ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <AlertTriangle className="w-12 h-12 text-destructive mx-auto mb-4" />
                <p>Failed to load graph data</p>
                <p className="text-sm text-muted-foreground">{error.message}</p>
              </div>
            </div>
          ) : activeGraph ? (
            <div className="h-[calc(100vh-64px)]">
              <ShadowGraph
                data={activeGraph}
                focusNodeId={selectedCluster?.company_ids[0]}
              />
            </div>
          ) : null}

          {/* Cluster detail overlay */}
          {selectedCluster && viewMode === "cluster" && (
            <div className="absolute bottom-4 right-4 w-80">
              <Card className="shadow-lg">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center justify-between">
                    <span>Cluster Details</span>
                    <Badge
                      variant={selectedCluster.suspicion_score >= 60 ? "destructive" : "secondary"}
                    >
                      Suspicion: {selectedCluster.suspicion_score}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-sm space-y-3">
                  <div>
                    <span className="text-muted-foreground">Companies:</span>
                    <ul className="mt-1 space-y-0.5">
                      {selectedCluster.company_names.map((name, i) => (
                        <li key={i} className="flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                          {name}
                        </li>
                      ))}
                    </ul>
                  </div>

                  {selectedCluster.shared_attributes.phones.length > 0 && (
                    <div className="flex items-start gap-2 text-amber-700 bg-amber-50 rounded-md p-2">
                      <Phone size={14} className="mt-0.5 shrink-0" />
                      <span>Shared phone numbers detected</span>
                    </div>
                  )}
                  {selectedCluster.shared_attributes.directors.length > 0 && (
                    <div className="flex items-start gap-2 text-red-700 bg-red-50 rounded-md p-2">
                      <UserCheck size={14} className="mt-0.5 shrink-0" />
                      <span>Shared directors across companies</span>
                    </div>
                  )}
                  {selectedCluster.shared_attributes.addresses.length > 0 && (
                    <div className="flex items-start gap-2 text-purple-700 bg-purple-50 rounded-md p-2">
                      <MapPin size={14} className="mt-0.5 shrink-0" />
                      <span>Shared addresses detected</span>
                    </div>
                  )}

                  <div className="text-muted-foreground">
                    Co-bid on <span className="font-medium">{selectedCluster.co_bid_count}</span> tenders
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </main>
      </div>
    </div>
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
      ? "text-red-600"
      : cluster.suspicion_score >= 30
      ? "text-amber-600"
      : "text-emerald-600";

  return (
    <Card
      onClick={onClick}
      className={`cursor-pointer transition-all hover:shadow-sm ${
        isSelected ? "ring-2 ring-primary" : ""
      }`}
    >
      <CardContent className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="font-medium text-sm truncate">
              {cluster.company_names[0]}
              {cluster.size > 1 && (
                <span className="text-muted-foreground"> +{cluster.size - 1}</span>
              )}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {cluster.co_bid_count} co-bids
              {cluster.shared_attributes.directors.length > 0 && " \u2022 shared directors"}
            </p>
          </div>
          <div className={`text-lg font-bold ${scoreColor}`}>
            {cluster.suspicion_score}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
