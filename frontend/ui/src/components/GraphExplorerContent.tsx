"use client";

import { useEffect, useMemo, useState } from "react";
import {
  useFullGraph,
  useCommunities,
  useCommunityGraph,
  useEntityNeighborhood,
  useGraphPath,
  useGraphSearch,
  useGraphStats,
} from "@/hooks/useTenders";
import { ShadowGraph } from "@/components/ShadowGraph";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Loader2,
  AlertTriangle,
  Users,
  Search,
  Target,
  X,
  Phone,
  MapPin,
  UserCheck,
  LayoutGrid,
  ShieldAlert,
} from "lucide-react";
import type {
  CommunityCluster,
  GraphData,
  GraphNode,
  GraphPathResult,
  GraphSearchResult,
} from "@/lib/types";

type ClusterInsightFocus = {
  kind: "phone" | "address" | "director";
  label: string;
  companyIds: string[];
  directorId?: string;
};

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => setDebouncedValue(value), delayMs);
    return () => window.clearTimeout(timeoutId);
  }, [delayMs, value]);

  return debouncedValue;
}

function filterGraphToSuspicious(graph: GraphData | null): GraphData | null {
  if (!graph) {
    return null;
  }

  const suspiciousEdges = graph.edges.filter((edge) => edge.suspicious);
  if (suspiciousEdges.length === 0) {
    return { nodes: [], edges: [] };
  }

  const nodeIds = new Set(suspiciousEdges.flatMap((edge) => [edge.source, edge.target]));
  return {
    nodes: graph.nodes.filter((node) => nodeIds.has(node.id)),
    edges: suspiciousEdges,
  };
}

function filterGraphToNodeNeighborhood(graph: GraphData | null, nodeId: string | null): GraphData | null {
  if (!graph || !nodeId) {
    return graph;
  }

  const relatedEdges = graph.edges.filter(
    (edge) => edge.source === nodeId || edge.target === nodeId,
  );
  const nodeIds = new Set([nodeId]);
  relatedEdges.forEach((edge) => {
    nodeIds.add(edge.source);
    nodeIds.add(edge.target);
  });

  return {
    nodes: graph.nodes.filter((node) => nodeIds.has(node.id)),
    edges: relatedEdges,
  };
}

function buildPathGraph(path: GraphPathResult | null): GraphData | null {
  if (!path) {
    return null;
  }

  return {
    nodes: path.nodes.map((node) => ({
      id: node.id,
      type: node.type,
      label: node.label,
      risk_level: node.risk_level ?? null,
      metadata: {},
    })),
    edges: path.edges.map((edge, index) => ({
      id: `${edge.source}:${edge.target}:${edge.relationship}:${index}`,
      source: edge.source,
      target: edge.target,
      relationship: edge.relationship,
      suspicious: edge.suspicious,
      label: null,
    })),
  };
}

function getNodeSubtitle(node: GraphNode): string | null {
  const metadata = node.metadata as Record<string, unknown>;
  if (node.type === "TENDER") {
    return typeof metadata.procuring_entity === "string" ? metadata.procuring_entity : null;
  }
  if (node.type === "OFFICIAL") {
    const department = typeof metadata.department === "string" ? metadata.department : null;
    const position = typeof metadata.position === "string" ? metadata.position : null;
    if (department && position) {
      return `${department} · ${position}`;
    }
    return department || position;
  }
  if (node.type === "COMPANY") {
    const address = typeof metadata.address === "string" ? metadata.address : null;
    if (address) {
      return address;
    }
    return typeof metadata.source_system === "string"
      ? metadata.source_system.toUpperCase()
      : null;
  }
  return null;
}

function formatNodeFactValue(value: unknown): string | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toLocaleString() : String(value);
  }
  return String(value);
}

function formatRelationshipLabel(value: string): string {
  return value.replace(/_/g, " ").toLowerCase();
}

function getNodeFacts(node: GraphNode): Array<{ label: string; value: string }> {
  const metadata = node.metadata as Record<string, unknown>;
  const candidates: Array<{ label: string; value: unknown }> =
    node.type === "TENDER"
      ? [
          { label: "Procuring Entity", value: metadata.procuring_entity },
          { label: "Status", value: metadata.status },
          { label: "Estimated Value", value: metadata.value },
        ]
      : node.type === "COMPANY"
      ? [
          { label: "Address", value: metadata.address },
          { label: "Phone", value: metadata.phone },
          { label: "Email", value: metadata.contact_email },
          { label: "Source", value: metadata.source_system },
        ]
      : node.type === "OFFICIAL"
      ? [
          { label: "Department", value: metadata.department },
          { label: "Position", value: metadata.position },
        ]
      : [{ label: "Entity ID", value: node.id }];

  const facts = candidates
    .map((item) => ({ label: item.label, value: formatNodeFactValue(item.value) }))
    .filter((item): item is { label: string; value: string } => Boolean(item.value));

  return facts.length > 0 ? facts : [{ label: "Entity ID", value: node.id }];
}

function toGraphSearchResult(node: GraphNode): GraphSearchResult {
  return {
    id: node.id,
    type: node.type,
    label: node.label,
    risk_level: node.risk_level,
    subtitle: getNodeSubtitle(node),
  };
}

function getClusterInsightHighlights(
  graph: GraphData | null,
  insight: ClusterInsightFocus | null,
): {
  highlightNodeIds: string[] | undefined;
  highlightEdgeIds: string[] | undefined;
} {
  if (!graph || !insight) {
    return { highlightNodeIds: undefined, highlightEdgeIds: undefined };
  }

  const companyIds = new Set(insight.companyIds);
  const highlightNodeIds = new Set(insight.companyIds);
  if (insight.kind === "director" && insight.directorId) {
    highlightNodeIds.add(insight.directorId);
  }

  const highlightEdgeIds = graph.edges
    .filter((edge) => {
      if (insight.kind === "phone") {
        return (
          edge.relationship === "SHARES_PHONE" &&
          companyIds.has(edge.source) &&
          companyIds.has(edge.target)
        );
      }
      if (insight.kind === "address") {
        return (
          edge.relationship === "SHARES_ADDRESS" &&
          companyIds.has(edge.source) &&
          companyIds.has(edge.target)
        );
      }
      return (
        edge.relationship === "DIRECTOR_OF" &&
        !!insight.directorId &&
        ((edge.source === insight.directorId && companyIds.has(edge.target)) ||
          (edge.target === insight.directorId && companyIds.has(edge.source)))
      );
    })
    .map((edge) => edge.id);

  return {
    highlightNodeIds: Array.from(highlightNodeIds),
    highlightEdgeIds,
  };
}

function getClusterInsightNodeIds(insight: ClusterInsightFocus | null): string[] {
  if (!insight) {
    return [];
  }
  return insight.directorId
    ? [insight.directorId, ...insight.companyIds]
    : insight.companyIds;
}

export function GraphExplorerContent() {
  const { stats, loading: statsLoading } = useGraphStats();
  const isLargeGraph = stats?.is_large ?? false;
  const [viewMode, setViewMode] = useState<"full" | "cluster" | "entity" | "path">("full");
  const [selectedCluster, setSelectedCluster] = useState<CommunityCluster | null>(null);
  const [selectedClusterInsight, setSelectedClusterInsight] =
    useState<ClusterInsightFocus | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<GraphSearchResult | null>(null);
  const [pathTargetEntity, setPathTargetEntity] = useState<GraphSearchResult | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [isSelectedNodeCardDismissed, setIsSelectedNodeCardDismissed] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [pathQuery, setPathQuery] = useState("");
  const [suspiciousOnly, setSuspiciousOnly] = useState(false);
  const [selectedNeighborhoodOnly, setSelectedNeighborhoodOnly] = useState(false);
  const [forceLoadFull, setForceLoadFull] = useState(false);
  const debouncedSearchQuery = useDebouncedValue(searchQuery, 250);
  const debouncedPathQuery = useDebouncedValue(pathQuery, 250);
  const shouldLoadFullGraph = !isLargeGraph || forceLoadFull;

  const { graph: fullGraph, loading: graphLoading, error } = useFullGraph(
    shouldLoadFullGraph ? { limitNodes: 500, limitEdges: 2000 } : null,
  );
  const { clusters, loading: clustersLoading } = useCommunities();
  const { graph: clusterGraph, loading: clusterGraphLoading } = useCommunityGraph(
    viewMode === "cluster" && selectedCluster ? selectedCluster.id : null,
  );
  const {
    graph: entityGraph,
    loading: entityGraphLoading,
    error: entityGraphError,
  } = useEntityNeighborhood(
    viewMode === "entity" && selectedEntity ? selectedEntity.id : null,
  );
  const { results: searchResults, loading: searchLoading } = useGraphSearch(debouncedSearchQuery);
  const { results: pathResults, loading: pathSearchLoading } = useGraphSearch(debouncedPathQuery);
  const { path, loading: pathLoading, error: pathError } = useGraphPath(
    selectedEntity?.id ?? null,
    pathTargetEntity?.id ?? null,
  );
  const pathGraph = useMemo(() => buildPathGraph(path), [path]);
  const clusterNodeLabels = useMemo(
    () => new Map((clusterGraph?.nodes ?? []).map((node) => [node.id, node.label] as const)),
    [clusterGraph],
  );
  const clusterHighlights = useMemo(
    () => getClusterInsightHighlights(clusterGraph, selectedClusterInsight),
    [clusterGraph, selectedClusterInsight],
  );

  const resolveClusterNodeLabel = (nodeId: string) => clusterNodeLabels.get(nodeId) ?? nodeId;

  const handleClusterClick = (cluster: CommunityCluster) => {
    setSelectedCluster(cluster);
    setSelectedClusterInsight(null);
    setSelectedEntity(null);
    setPathTargetEntity(null);
    setSelectedNodeId(null);
    setIsSelectedNodeCardDismissed(false);
    setPathQuery("");
    setSelectedNeighborhoodOnly(false);
    setViewMode("cluster");
  };

  const handleEntitySelect = (result: GraphSearchResult) => {
    setSelectedEntity(result);
    setSelectedCluster(null);
    setSelectedClusterInsight(null);
    setPathTargetEntity(null);
    setSelectedNodeId(result.id);
    setIsSelectedNodeCardDismissed(false);
    setPathQuery("");
    setSelectedNeighborhoodOnly(false);
    setViewMode("entity");
    setSearchQuery(result.label);
  };

  const handleClusterInsightSelect = (insight: ClusterInsightFocus) => {
    setSelectedClusterInsight(insight);
    setSelectedNodeId(null);
    setIsSelectedNodeCardDismissed(false);
    setSuspiciousOnly(false);
    setSelectedNeighborhoodOnly(false);
  };

  const handlePathTargetSelect = (result: GraphSearchResult) => {
    if (!selectedEntity || result.id === selectedEntity.id) {
      return;
    }
    setPathTargetEntity(result);
    setSelectedNodeId(null);
    setIsSelectedNodeCardDismissed(false);
    setPathQuery(result.label);
    setSuspiciousOnly(false);
    setSelectedNeighborhoodOnly(false);
    setViewMode("path");
  };

  const handleShowFullGraph = () => {
    if (isLargeGraph && !forceLoadFull) {
      setForceLoadFull(true);
    }
    setViewMode("full");
    setSelectedCluster(null);
    setSelectedClusterInsight(null);
    setSelectedEntity(null);
    setPathTargetEntity(null);
    setSelectedNodeId(null);
    setIsSelectedNodeCardDismissed(false);
    setPathQuery("");
  };

  const clearPathFocus = () => {
    setPathTargetEntity(null);
    setSelectedNodeId(selectedEntity?.id ?? null);
    setIsSelectedNodeCardDismissed(false);
    setPathQuery("");
    setSelectedNeighborhoodOnly(false);
    setViewMode(selectedEntity ? "entity" : selectedCluster ? "cluster" : "full");
  };

  const clearEntityFocus = () => {
    setSelectedEntity(null);
    setSelectedClusterInsight(null);
    setPathTargetEntity(null);
    setSelectedNodeId(null);
    setIsSelectedNodeCardDismissed(false);
    setSearchQuery("");
    setPathQuery("");
    setSelectedNeighborhoodOnly(false);
    setViewMode(selectedCluster ? "cluster" : "full");
  };

  const activeGraph =
    viewMode === "path" && pathGraph
      ? pathGraph
      : viewMode === "entity" && entityGraph
      ? entityGraph
      : viewMode === "cluster" && clusterGraph
      ? clusterGraph
      : fullGraph;
  const activeError = viewMode === "path" ? pathError : viewMode === "entity" ? entityGraphError : error;
  const isLoading =
    viewMode === "path"
      ? pathLoading
      : viewMode === "entity"
      ? entityGraphLoading
      : viewMode === "cluster"
      ? clusterGraphLoading
      : graphLoading || statsLoading;
  const showStatsView = isLargeGraph && !forceLoadFull && viewMode === "full";
  const selectedGraphTargetId =
    selectedNodeId ??
    (viewMode === "path"
      ? pathTargetEntity?.id ?? selectedEntity?.id ?? null
      : selectedEntity?.id ?? null);
  const displayGraph = useMemo(
    () => {
      const suspiciousFiltered =
        suspiciousOnly && viewMode !== "path" ? filterGraphToSuspicious(activeGraph) : activeGraph;
      return selectedNeighborhoodOnly && viewMode !== "path"
        ? filterGraphToNodeNeighborhood(suspiciousFiltered, selectedGraphTargetId)
        : suspiciousFiltered;
    },
    [activeGraph, selectedGraphTargetId, selectedNeighborhoodOnly, suspiciousOnly, viewMode],
  );
  const selectedNode = useMemo(() => {
    const targetId = selectedGraphTargetId;
    if (!targetId || !activeGraph) {
      return null;
    }
    return activeGraph.nodes.find((node) => node.id === targetId) ?? null;
  }, [activeGraph, selectedGraphTargetId]);
  const showSearchResults =
    searchQuery.trim().length >= 2 &&
    !(selectedEntity && searchQuery.trim() === selectedEntity.label);
  const visiblePathResults = useMemo(
    () => pathResults.filter((result) => result.id !== selectedEntity?.id),
    [pathResults, selectedEntity],
  );
  const showPathSearchResults =
    !!selectedEntity &&
    pathQuery.trim().length >= 2 &&
    !(pathTargetEntity && pathQuery.trim() === pathTargetEntity.label);

  const handleOpenSelectedNodeNeighborhood = () => {
    if (!selectedNode) {
      return;
    }
    const result = toGraphSearchResult(selectedNode);
    setSelectedEntity(result);
    setSelectedCluster(null);
    setSelectedClusterInsight(null);
    setPathTargetEntity(null);
    setSelectedNodeId(result.id);
    setIsSelectedNodeCardDismissed(false);
    setPathQuery("");
    setSelectedNeighborhoodOnly(false);
    setViewMode("entity");
    setSearchQuery(result.label);
  };

  const handleInvestigationNodeSelect = (nodeId: string) => {
    setSelectedNodeId(nodeId);
    setIsSelectedNodeCardDismissed(false);
    setSelectedNeighborhoodOnly(false);
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden">
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
                Search entities, isolate suspicious ties, and inspect focused neighborhoods instead of deciphering the whole network at once.
              </p>
              <p className="mt-2 max-w-2xl text-xs text-muted-foreground">
                Suspicion scores combine co-bidding, suspicious links, and confirmed shared attributes so investigators can see why a cluster is ranked before opening a case.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {stats && (
                <span className="text-xs text-muted-foreground tabular-nums">
                  <span className="text-foreground/70">{stats.total_nodes.toLocaleString()}</span> nodes
                  <span className="mx-1.5 opacity-40">&middot;</span>
                  <span className="text-foreground/70">{stats.total_edges.toLocaleString()}</span> edges
                  {stats.is_large && (
                    <span className="ml-2 text-amber-500">(large graph)</span>
                  )}
                </span>
              )}
              {selectedEntity && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={clearEntityFocus}
                  className="text-xs h-8"
                >
                  <X size={14} />
                  Clear Focus
                </Button>
              )}
              {(viewMode === "cluster" || viewMode === "entity" || viewMode === "path" || showStatsView) && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleShowFullGraph}
                  className="text-xs h-8"
                >
                  <LayoutGrid size={14} />
                  {isLargeGraph ? "Load Sample" : "Full Graph"}
                </Button>
              )}
            </div>
          </div>
        </div>
      </header>

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <aside className="w-80 shrink-0 min-h-0 border-r border-border/60 bg-card/70 flex flex-col">
          <div className="p-5 border-b border-border/60">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.25em] text-muted-foreground flex items-center gap-2">
              <Users size={14} className="text-primary" />
              Detected Communities
            </h2>
            <p className="mt-2 text-xs text-muted-foreground">
              Start with a community or search for a specific entity to load a focused neighborhood.
            </p>
            <div className="mt-4 relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Find company, tender, official..."
                className="pl-9 pr-9 bg-background/70"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          </div>

          <ScrollArea className="flex-1 h-full">
            <div className="p-3 space-y-2">
              {selectedEntity && (
                <div className="rounded-xl border border-primary/20 bg-primary/5 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-[11px] uppercase tracking-[0.2em] text-primary/80">
                        Focused Entity
                      </div>
                      <p className="mt-1 text-sm font-medium text-foreground wrap-break-word">
                        {selectedEntity.label}
                      </p>
                      {selectedEntity.subtitle && (
                        <p className="mt-1 text-xs text-muted-foreground wrap-break-word">
                          {selectedEntity.subtitle}
                        </p>
                      )}
                    </div>
                    <Button variant="ghost" size="sm" onClick={clearEntityFocus} className="h-8 px-2">
                      <X size={14} />
                    </Button>
                  </div>
                  <div className="mt-3 border-t border-primary/15 pt-3">
                    <div className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                      Trace shortest path
                    </div>
                    <div className="mt-2 relative">
                      <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        value={pathQuery}
                        onChange={(event) => setPathQuery(event.target.value)}
                        placeholder="Find a second entity..."
                        className="pl-9 pr-9 bg-background/70"
                      />
                      {pathQuery && (
                        <button
                          type="button"
                          onClick={() => setPathQuery("")}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        >
                          <X size={14} />
                        </button>
                      )}
                    </div>
                    {pathTargetEntity && (
                      <div className="mt-2 rounded-lg border border-border/50 bg-background/60 p-3">
                        <div className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                          {viewMode === "path" && path
                            ? `${path.length} ${path.length === 1 ? "hop" : "hops"}`
                            : "Path target"}
                        </div>
                        <p className="mt-1 text-sm font-medium text-foreground wrap-break-word">
                          {pathTargetEntity.label}
                        </p>
                        {pathTargetEntity.subtitle && (
                          <p className="mt-1 text-xs text-muted-foreground wrap-break-word">
                            {pathTargetEntity.subtitle}
                          </p>
                        )}
                        <div className="mt-3 flex flex-wrap gap-2">
                          {viewMode === "path" && (
                            <Button variant="outline" size="sm" onClick={clearPathFocus} className="h-8 text-xs">
                              Back to neighborhood
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={clearPathFocus}
                            className="h-8 px-2 text-xs"
                          >
                            <X size={14} />
                            Clear path
                          </Button>
                        </div>
                        {viewMode === "path" && path && path.nodes.length > 0 && (
                          <div className="mt-3 rounded-lg border border-border/50 bg-background/50 p-3">
                            <div className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                              Why these entities connect
                            </div>
                            <div className="mt-2 space-y-2">
                              {path.nodes.map((node, index) => {
                                const edge = path.edges[index];
                                const isActive = selectedGraphTargetId === node.id;
                                return (
                                  <button
                                    key={node.id}
                                    type="button"
                                    onClick={() => handleInvestigationNodeSelect(node.id)}
                                    className={`w-full rounded-md border px-3 py-2 text-left transition-colors ${
                                      isActive
                                        ? "border-primary/40 bg-primary/10"
                                        : "border-border/40 bg-background/40 hover:bg-accent/50"
                                    }`}
                                  >
                                    <div className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                                      {node.type}
                                    </div>
                                    <p className="mt-1 text-xs font-medium text-foreground wrap-break-word">
                                      {node.label}
                                    </p>
                                    {edge && (
                                      <p className="mt-1 text-[11px] text-muted-foreground wrap-break-word">
                                        via {formatRelationshipLabel(edge.relationship)}
                                        {edge.suspicious ? " · suspicious link" : ""}
                                      </p>
                                    )}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
              {showPathSearchResults && (
                <div className="rounded-xl border border-border/60 bg-background/70 p-2">
                  <div className="px-2 py-1 text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                    Path Targets
                  </div>
                  {pathSearchLoading ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="w-4 h-4 animate-spin text-primary" />
                    </div>
                  ) : visiblePathResults.length === 0 ? (
                    <p className="px-2 py-4 text-xs text-muted-foreground">
                      No connected target candidates found.
                    </p>
                  ) : (
                    <div className="space-y-1">
                      {visiblePathResults.map((result) => (
                        <button
                          key={result.id}
                          type="button"
                          onClick={() => handlePathTargetSelect(result)}
                          className="w-full rounded-lg px-2 py-2 text-left hover:bg-accent/60 transition-colors"
                        >
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="inline-flex rounded border border-border/60 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                                {result.type}
                              </span>
                              {result.risk_level && (
                                <span className="inline-flex rounded border border-[#c4412f]/25 bg-[#c4412f]/10 px-1.5 py-0.5 text-[10px] text-[#c4412f]">
                                  {result.risk_level}
                                </span>
                              )}
                            </div>
                            <p className="mt-1 text-sm text-foreground wrap-break-word">{result.label}</p>
                            {result.subtitle && (
                              <p className="text-[11px] text-muted-foreground wrap-break-word mt-0.5">
                                {result.subtitle}
                              </p>
                            )}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {showSearchResults && (
                <div className="rounded-xl border border-border/60 bg-background/70 p-2">
                  <div className="px-2 py-1 text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                    Search Results
                  </div>
                  {searchLoading ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="w-4 h-4 animate-spin text-primary" />
                    </div>
                  ) : searchResults.length === 0 ? (
                    <p className="px-2 py-4 text-xs text-muted-foreground">
                      No matching entities found.
                    </p>
                  ) : (
                    <div className="space-y-1">
                      {searchResults.map((result) => (
                        <button
                          key={result.id}
                          type="button"
                          onClick={() => handleEntitySelect(result)}
                          className="w-full rounded-lg px-2 py-2 text-left hover:bg-accent/60 transition-colors"
                        >
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="inline-flex rounded border border-border/60 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                                {result.type}
                              </span>
                              {result.risk_level && (
                                <span className="inline-flex rounded border border-[#c4412f]/25 bg-[#c4412f]/10 px-1.5 py-0.5 text-[10px] text-[#c4412f]">
                                  {result.risk_level}
                                </span>
                              )}
                            </div>
                            <p className="mt-1 text-sm text-foreground wrap-break-word">{result.label}</p>
                            {result.subtitle && (
                              <p className="text-[11px] text-muted-foreground wrap-break-word mt-0.5">
                                {result.subtitle}
                              </p>
                            )}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
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

        <main className="flex-1 min-h-0 overflow-hidden relative">
          {!showStatsView && activeGraph && viewMode !== "path" && (
            <div className="absolute left-4 top-4 z-20 flex flex-wrap gap-2">
              <Button
                variant={suspiciousOnly ? "default" : "outline"}
                size="sm"
                onClick={() => setSuspiciousOnly((current) => !current)}
                className={`h-8 text-xs backdrop-blur-sm shadow-lg ${
                  suspiciousOnly
                    ? "bg-primary text-primary-foreground hover:bg-primary/90"
                    : "bg-card/95 text-foreground hover:bg-accent"
                }`}
              >
                <ShieldAlert size={14} />
                Suspicious only
              </Button>
              {selectedGraphTargetId && (
                <Button
                  variant={selectedNeighborhoodOnly ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSelectedNeighborhoodOnly((current) => !current)}
                  className={`h-8 text-xs backdrop-blur-sm shadow-lg ${
                    selectedNeighborhoodOnly
                      ? "bg-primary text-primary-foreground hover:bg-primary/90"
                      : "bg-card/95 text-foreground hover:bg-accent"
                  }`}
                >
                  <Target size={14} />
                  Selected neighborhood
                </Button>
              )}
            </div>
          )}
          {viewMode === "path" && selectedEntity && pathTargetEntity && path && (
            <div className="absolute left-4 top-4 z-20 max-w-sm">
              <div className="rounded-xl border border-primary/20 bg-card/95 p-3 shadow-lg backdrop-blur-sm">
                <div className="text-[11px] uppercase tracking-[0.2em] text-primary/80">
                  Shortest path
                </div>
                <p className="mt-1 text-sm font-medium text-foreground wrap-break-word">
                  {selectedEntity.label} to {pathTargetEntity.label}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {path.length} {path.length === 1 ? "hop" : "hops"}
                  {path.edges.some((edge) => edge.suspicious) ? " · includes suspicious links" : " · no suspicious links on this path"}
                </p>
                <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                  Use this view to explain why two entities matter together before escalating: every hop is a concrete relationship, not a model guess.
                </p>
              </div>
            </div>
          )}
          {isLoading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">Loading graph...</p>
              </div>
            </div>
          ) : activeError ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <AlertTriangle className="w-8 h-8 text-destructive mx-auto mb-3" />
                <p className="text-sm">Failed to load graph data</p>
                <p className="text-xs text-muted-foreground mt-1">{activeError.message}</p>
              </div>
            </div>
          ) : showStatsView ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center max-w-md p-8">
                <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">Large Graph Detected</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  This graph has {stats?.total_nodes.toLocaleString()} nodes and {stats?.total_edges.toLocaleString()} edges.
                  Loading the full graph may be slow.
                </p>
                <p className="text-sm text-muted-foreground mb-6">
                  We recommend exploring individual <strong>communities</strong> from the sidebar,
                  or click below to load a sample of high-risk tenders.
                </p>
                <div className="flex gap-3 justify-center">
                  <Button onClick={handleShowFullGraph} variant="outline">
                    Load Sample (500 nodes)
                  </Button>
                  <Button
                    onClick={() => {
                      if (clusters.length > 0) {
                        handleClusterClick(clusters[0]);
                      }
                    }}
                    disabled={clusters.length === 0}
                  >
                    View Top Community
                  </Button>
                </div>
              </div>
            </div>
          ) : displayGraph && displayGraph.nodes.length > 0 ? (
            <div className="h-full">
              <ShadowGraph
                data={displayGraph}
                focusNodeId={viewMode === "path" ? selectedNodeId ?? undefined : selectedNodeId ?? selectedEntity?.id}
                highlightNodeIds={
                  viewMode === "path" && selectedEntity && pathTargetEntity
                    ? [selectedEntity.id, pathTargetEntity.id]
                    : viewMode === "cluster"
                    ? clusterHighlights.highlightNodeIds
                    : undefined
                }
                highlightEdgeIds={
                  viewMode === "path"
                    ? displayGraph.edges.map((edge) => edge.id)
                    : viewMode === "cluster"
                    ? clusterHighlights.highlightEdgeIds
                    : undefined
                }
                onNodeClick={(nodeId) => setSelectedNodeId(nodeId)}
              />
            </div>
          ) : activeGraph ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center max-w-sm p-8">
                <AlertTriangle className="w-10 h-10 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">No suspicious ties in this focused view</h3>
                <p className="text-sm text-muted-foreground mb-5">
                  Turn off suspicious-only mode to inspect the full neighborhood again.
                </p>
                <Button variant="outline" onClick={() => setSuspiciousOnly(false)}>
                  Show Full Neighborhood
                </Button>
              </div>
            </div>
          ) : null}

          {selectedNode && !isSelectedNodeCardDismissed && (
            <div className="absolute top-20 right-4 w-80 animate-fade-in-up z-20">
              <div className="rounded-2xl border border-border/60 bg-card/95 backdrop-blur-sm shadow-xl p-5">
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="min-w-0">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                      {selectedNode.type}
                    </div>
                    <p className="mt-2 text-sm font-semibold text-foreground wrap-break-word">
                      {selectedNode.label}
                    </p>
                    {getNodeSubtitle(selectedNode) && (
                      <p className="mt-1 text-xs text-muted-foreground wrap-break-word">
                        {getNodeSubtitle(selectedNode)}
                      </p>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setSelectedNodeId(null);
                      setIsSelectedNodeCardDismissed(true);
                      setSelectedNeighborhoodOnly(false);
                    }}
                    className="h-8 px-2"
                  >
                    <X size={14} />
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2 mb-4">
                  <span className="inline-flex items-center rounded border border-border/60 px-2 py-1 text-[11px] text-muted-foreground">
                    {selectedNode.type}
                  </span>
                  {selectedNode.risk_level && (
                    <span className="inline-flex items-center rounded border border-[#c4412f]/25 bg-[#c4412f]/10 px-2 py-1 text-[11px] text-[#c4412f]">
                      {selectedNode.risk_level} risk
                    </span>
                  )}
                </div>
                {(viewMode !== "entity" || selectedEntity?.id !== selectedNode.id) && (
                  <div className="mb-4">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleOpenSelectedNodeNeighborhood}
                      className="h-8 cursor-pointer border-border/70 bg-background/80 text-foreground shadow-sm hover:border-primary/40 hover:bg-primary/10 hover:text-primary dark:bg-card/80"
                    >
                      <Target size={14} />
                      Open neighborhood
                    </Button>
                  </div>
                )}
                <div className="space-y-2 text-xs">
                  {getNodeFacts(selectedNode).map((fact) => (
                    <div key={fact.label} className="flex flex-col gap-1 rounded-lg border border-border/40 bg-background/40 px-3 py-2">
                      <span className="text-[11px] uppercase tracking-[0.15em] text-muted-foreground">
                        {fact.label}
                      </span>
                      <span className="text-foreground wrap-break-word">{fact.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {selectedCluster && viewMode === "cluster" && (
            <div className="absolute bottom-4 right-4 w-80 max-h-[calc(100%-6rem)] animate-fade-in-up overflow-y-auto">
              <div className="rounded-2xl border border-border/60 bg-card/95 backdrop-blur-sm shadow-xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                    Cluster Details
                  </span>
                  <SuspicionBadge score={selectedCluster.suspicion_score} />
                </div>
                <p className="mb-3 text-[11px] leading-relaxed text-muted-foreground">
                  Suspicion score reflects cluster size, repeated co-bidding, suspicious graph links, and shared phones, addresses, or directors that survive Sentinel&apos;s noise filters.
                </p>

                <div className="space-y-3 text-xs">
                  <div>
                    <span className="text-muted-foreground">Companies:</span>
                    <ul className="mt-1.5 space-y-1">
                      {selectedCluster.company_names.map((name, index) => (
                        <li key={index} className="flex items-center gap-1.5">
                          <span className="w-1 h-1 rounded-full bg-primary" />
                          <span className="text-foreground/80">{name}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {selectedClusterInsight && (
                    <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-[11px] uppercase tracking-[0.2em] text-primary/80">
                            Active clue
                          </div>
                          <p className="mt-1 text-sm font-medium text-foreground wrap-break-word">
                            {selectedClusterInsight.label}
                          </p>
                          <p className="mt-1 text-[11px] text-muted-foreground">
                            Highlighting {selectedClusterInsight.companyIds.length} related companies
                            {selectedClusterInsight.directorId ? " and the linked director" : ""}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedClusterInsight(null)}
                          className="h-8 border border-primary/20 bg-background/60 px-2 text-foreground/80 shadow-sm hover:border-primary/40 hover:bg-primary/10 hover:text-primary dark:bg-card/70"
                        >
                          <X size={14} />
                        </Button>
                      </div>
                      {getClusterInsightNodeIds(selectedClusterInsight).length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {getClusterInsightNodeIds(selectedClusterInsight).map((nodeId) => {
                            const isActive = selectedGraphTargetId === nodeId;
                            return (
                              <button
                                key={nodeId}
                                type="button"
                                onClick={() => handleInvestigationNodeSelect(nodeId)}
                                className={`rounded-full border px-2.5 py-1 text-[11px] transition-colors ${
                                  isActive
                                    ? "border-primary/40 bg-primary/10 text-primary"
                                    : "border-border/60 bg-background/80 text-foreground/80 hover:border-primary/30 hover:bg-primary/10 hover:text-primary dark:bg-card/70"
                                }`}
                              >
                                {resolveClusterNodeLabel(nodeId)}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}

                  {selectedCluster.shared_attributes.phones.length > 0 && (
                    <div className="space-y-1.5">
                      <div className="text-[11px] uppercase tracking-[0.2em] text-[#b78b43]">
                        Shared phones
                      </div>
                      {selectedCluster.shared_attributes.phones.map((item) => {
                        const isActive =
                          selectedClusterInsight?.kind === "phone" &&
                          selectedClusterInsight.label === item.phone;
                        return (
                          <button
                            key={item.phone}
                            type="button"
                            onClick={() =>
                              handleClusterInsightSelect({
                                kind: "phone",
                                label: item.phone,
                                companyIds: item.companies,
                              })
                            }
                            className={`w-full flex items-start gap-2 rounded-md border p-2 text-left transition-colors ${
                              isActive
                                ? "border-[#b78b43]/40 bg-[#b78b43]/15 text-[#b78b43]"
                                : "border-[#b78b43]/20 bg-[#b78b43]/10 text-[#b78b43] hover:bg-[#b78b43]/15"
                            }`}
                          >
                            <Phone size={12} className="mt-0.5 shrink-0" />
                            <div className="min-w-0">
                              <p className="text-foreground wrap-break-word">{item.phone}</p>
                              <p className="mt-0.5 text-[11px] text-muted-foreground">
                                {item.companies.length} related companies
                              </p>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                  {selectedCluster.shared_attributes.directors.length > 0 && (
                    <div className="space-y-1.5">
                      <div className="text-[11px] uppercase tracking-[0.2em] text-[#c4412f]">
                        Shared directors
                      </div>
                      {selectedCluster.shared_attributes.directors.map((item) => {
                        const directorLabel = resolveClusterNodeLabel(item.director_id);
                        const isActive =
                          selectedClusterInsight?.kind === "director" &&
                          selectedClusterInsight.directorId === item.director_id;
                        return (
                          <button
                            key={item.director_id}
                            type="button"
                            onClick={() =>
                              handleClusterInsightSelect({
                                kind: "director",
                                label: directorLabel,
                                companyIds: item.companies,
                                directorId: item.director_id,
                              })
                            }
                            className={`w-full flex items-start gap-2 rounded-md border p-2 text-left transition-colors ${
                              isActive
                                ? "border-[#c4412f]/40 bg-[#c4412f]/15 text-[#c4412f]"
                                : "border-[#c4412f]/20 bg-[#c4412f]/10 text-[#c4412f] hover:bg-[#c4412f]/15"
                            }`}
                          >
                            <UserCheck size={12} className="mt-0.5 shrink-0" />
                            <div className="min-w-0">
                              <p className="text-foreground wrap-break-word">{directorLabel}</p>
                              <p className="mt-0.5 text-[11px] text-muted-foreground">
                                {item.companies.length} linked companies
                              </p>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                  {selectedCluster.shared_attributes.addresses.length > 0 && (
                    <div className="space-y-1.5">
                      <div className="text-[11px] uppercase tracking-[0.2em] text-[#35638c]">
                        Shared addresses
                      </div>
                      {selectedCluster.shared_attributes.addresses.map((item) => {
                        const isActive =
                          selectedClusterInsight?.kind === "address" &&
                          selectedClusterInsight.label === item.address;
                        return (
                          <button
                            key={item.address}
                            type="button"
                            onClick={() =>
                              handleClusterInsightSelect({
                                kind: "address",
                                label: item.address,
                                companyIds: item.companies,
                              })
                            }
                            className={`w-full flex items-start gap-2 rounded-md border p-2 text-left transition-colors ${
                              isActive
                                ? "border-[#35638c]/40 bg-[#35638c]/15 text-[#35638c]"
                                : "border-[#35638c]/20 bg-[#35638c]/10 text-[#35638c] hover:bg-[#35638c]/15"
                            }`}
                          >
                            <MapPin size={12} className="mt-0.5 shrink-0" />
                            <div className="min-w-0">
                              <p className="text-foreground wrap-break-word">{item.address}</p>
                              <p className="mt-0.5 text-[11px] text-muted-foreground">
                                {item.companies.length} related companies
                              </p>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}

                  <div className="text-muted-foreground pt-1 border-t border-border/40">
                    Co-bid on <span className="text-foreground/70 font-medium">{selectedCluster.co_bid_count}</span> tenders
                  </div>
                  <div className="rounded-lg border border-border/40 bg-background/40 px-3 py-2 text-[11px] leading-relaxed text-muted-foreground">
                    Why this matters: clusters with repeated bidding overlap and verified relationship signals are stronger candidates for investigator review than one-off shared records.
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
            {cluster.shared_attributes.directors.length > 0 && " • shared dirs"}
          </p>
        </div>
        <span className={`text-sm font-bold tabular-nums ${scoreColor}`}>
          {cluster.suspicion_score}
        </span>
      </div>
    </div>
  );
}
