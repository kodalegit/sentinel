/**
 * Shadow Graph component using React Flow.
 * Uses barycenter heuristic for edge-crossing minimization.
 */

"use client";

import { useMemo, useCallback, useState, useEffect } from "react";
import {
  ReactFlow,
  Node,
  Edge,
  type ReactFlowInstance,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Position,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphData, NodeType, RiskCategory } from "@/lib/types";
import { Building2, User, Briefcase, FileText } from "lucide-react";
import { useTheme } from "next-themes";

interface ShadowGraphProps {
  data: GraphData;
  focusNodeId?: string;
  highlightNodeIds?: string[];
  highlightEdgeIds?: string[];
  onNodeClick?: (nodeId: string, nodeType: NodeType) => void;
  minimapPosition?: "bottom-center" | "bottom-right";
}

const NODE_THEME_LIGHT = {
  COMPANY: { bg: "#e8f0ed", border: "#1f4b46", color: "#1f4b46" },
  DIRECTOR: { bg: "#f3ede3", border: "#7c5d3b", color: "#7c5d3b" },
  OFFICIAL: { bg: "#f6e7e3", border: "#c4412f", color: "#9d2f23" },
  TENDER: { bg: "#eef2f5", border: "#35638c", color: "#2f4d67" },
};

const NODE_THEME_DARK = {
  COMPANY: { bg: "#162b28", border: "#3d9e8f", color: "#8fd4c8" },
  DIRECTOR: { bg: "#2a2218", border: "#c9a35c", color: "#e0c88a" },
  OFFICIAL: { bg: "#2d1814", border: "#e06050", color: "#f0a090" },
  TENDER: { bg: "#172430", border: "#5a9ac4", color: "#a0c8e8" },
};

const NODE_META = {
  COMPANY: { icon: Building2, radius: "10px" },
  DIRECTOR: { icon: User, radius: "999px" },
  OFFICIAL: { icon: Briefcase, radius: "999px" },
  TENDER: { icon: FileText, radius: "12px" },
};

const RISK_COLORS: Record<RiskCategory, string> = {
  HIGH: "#c4412f",
  MEDIUM: "#b78b43",
  LOW: "#1f6f5c",
};

const LAYER_ORDER: NodeType[] = ["OFFICIAL", "TENDER", "COMPANY", "DIRECTOR"];
const LAYER_Y_SPACING = 260;
const X_SPACING = 360;

/**
 * Build adjacency map for barycenter computation.
 */
function buildAdjacency(graphData: GraphData) {
  const adj: Record<string, Set<string>> = {};
  for (const n of graphData.nodes) adj[n.id] = new Set();
  for (const e of graphData.edges) {
    adj[e.source]?.add(e.target);
    adj[e.target]?.add(e.source);
  }
  return adj;
}

function getNodeSubtitle(node: GraphData["nodes"][number]): string | null {
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

function formatEdgeLabel(edge: GraphData["edges"][number]): string | undefined {
  if (edge.label) {
    return edge.label;
  }
  if (!edge.suspicious) {
    return undefined;
  }
  return edge.relationship.replace(/_/g, " ").toLowerCase();
}

/**
 * Barycenter heuristic: order nodes in a layer by the average x-position
 * of their neighbours in the previously placed layer. Significantly reduces
 * edge crossings compared to arbitrary ordering.
 */
function layoutNodes(
  graphData: GraphData,
  focusNodeId?: string,
  highlightNodeIds?: string[],
  isDark = false,
): Node[] {
  const NODE_THEME = isDark ? NODE_THEME_DARK : NODE_THEME_LIGHT;
  const highlightNodeSet = highlightNodeIds ? new Set(highlightNodeIds) : null;
  const adj = buildAdjacency(graphData);
  const nodeTypeById = new Map(
    graphData.nodes.map((node) => [node.id, node.type] as const)
  );

  const nodesByType: Record<string, typeof graphData.nodes> = {};
  for (const t of LAYER_ORDER) nodesByType[t] = [];
  graphData.nodes.forEach((n) => nodesByType[n.type]?.push(n));

  const positionMap: Record<string, { x: number; y: number }> = {};
  const layerIndex = Object.fromEntries(
    LAYER_ORDER.map((type, idx) => [type, idx])
  ) as Record<NodeType, number>;

  const seedLayers = LAYER_ORDER.map((type) => {
    const layerNodes = nodesByType[type] || [];
    return [...layerNodes].sort(
      (a, b) => (adj[b.id]?.size || 0) - (adj[a.id]?.size || 0)
    );
  });

  const placeLayer = (nodes: typeof graphData.nodes, y: number) => {
    const totalWidth = nodes.length * X_SPACING;
    const startX = -totalWidth / 2 + X_SPACING / 2;
    nodes.forEach((node, idx) => {
      positionMap[node.id] = { x: startX + idx * X_SPACING, y };
    });
  };

  seedLayers.forEach((layerNodes, idx) => {
    placeLayer(layerNodes, idx * LAYER_Y_SPACING);
  });

  const sortLayerByNeighbours = (nodes: typeof graphData.nodes, targetLayer: number) => {
    return [...nodes].sort((a, b) => {
      const score = (nodeId: string) => {
        const neighbours = adj[nodeId] || new Set<string>();
        let sumX = 0;
        let count = 0;
        neighbours.forEach((nId) => {
          const type = nodeTypeById.get(nId);
          if (type && layerIndex[type] === targetLayer && positionMap[nId]) {
            sumX += positionMap[nId].x;
            count++;
          }
        });
        return count > 0 ? sumX / count : 0;
      };

      return score(a.id) - score(b.id);
    });
  };

  for (let sweep = 0; sweep < 2; sweep++) {
    LAYER_ORDER.forEach((type, idx) => {
      if (idx === 0) return;
      const layerNodes = nodesByType[type] || [];
      const ordered = sortLayerByNeighbours(layerNodes, idx - 1);
      placeLayer(ordered, idx * LAYER_Y_SPACING);
      nodesByType[type] = ordered;
    });

    [...LAYER_ORDER].reverse().forEach((type, idx) => {
      const layerIdx = LAYER_ORDER.length - 1 - idx;
      if (layerIdx === LAYER_ORDER.length - 1) return;
      const layerNodes = nodesByType[type] || [];
      const ordered = sortLayerByNeighbours(layerNodes, layerIdx + 1);
      placeLayer(ordered, layerIdx * LAYER_Y_SPACING);
      nodesByType[type] = ordered;
    });
  }

  const result: Node[] = [];
  LAYER_ORDER.forEach((type, layerIdx) => {
    const layerNodes = nodesByType[type] || [];
    const y = layerIdx * LAYER_Y_SPACING;

    layerNodes.forEach((node, idx) => {
      const current = positionMap[node.id];
      const x = current ? current.x : idx * X_SPACING;
      positionMap[node.id] = { x, y };

      const theme = NODE_THEME[node.type as keyof typeof NODE_THEME];
      const meta = NODE_META[node.type as keyof typeof NODE_META];
      const Icon = meta.icon;
      const subtitle = getNodeSubtitle(node);
      const isHighRisk = node.risk_level === "HIGH";
      const borderColor = node.risk_level
        ? RISK_COLORS[node.risk_level]
        : theme.border;
      const isFocused = focusNodeId && node.id === focusNodeId;
      const isDimmed = focusNodeId && node.id !== focusNodeId;
      const isHighlighted = !!highlightNodeSet?.has(node.id);

      result.push({
        id: node.id,
        position: { x, y },
        data: {
          label: (
            <div className="flex items-start gap-3 px-1" title={node.label}>
              <Icon size={20} strokeWidth={1.5} className="shrink-0 mt-0.5" />
              <div className="min-w-0 max-w-[260px] text-left">
                <div className="text-[13px] font-semibold wrap-break-word leading-snug">
                  {node.label}
                </div>
                {subtitle && (
                  <div className="mt-1 text-[11px] opacity-75 wrap-break-word leading-snug">
                    {subtitle}
                  </div>
                )}
              </div>
            </div>
          ),
          nodeType: node.type,
          metadata: node.metadata,
          riskLevel: node.risk_level,
        },
        style: {
          background: theme.bg,
          border: `${isHighlighted ? 2 : 1.5}px solid ${borderColor}`,
          color: theme.color,
          borderRadius: meta.radius,
          padding: "14px 22px",
          fontSize: "14px",
          boxShadow: isFocused
            ? `0 0 0 4px ${borderColor}50`
            : isHighlighted
            ? `0 0 0 4px ${borderColor}30, 0 10px 24px ${borderColor}25`
            : isHighRisk
            ? `0 0 16px ${RISK_COLORS.HIGH}35`
            : "0 4px 16px rgba(31,75,70,0.12)",
          textAlign: "center" as const,
          opacity: isDimmed ? 0.55 : 1,
        },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
      });
    });
  });

  return result;
}

function createEdges(
  graphData: GraphData,
  focusNodeId?: string,
  highlightEdgeIds?: string[],
  isDark = false,
): Edge[] {
  const normalEdge = isDark ? "#5a5550" : "#b9b2a6";
  const suspiciousEdge = isDark ? "#e06050" : "#c4412f";
  const labelFill = isDark ? "#c8c2b8" : "#6b6761";
  const labelBg = isDark ? "#111a19" : "#fffaf4";
  const highlightEdgeSet = highlightEdgeIds ? new Set(highlightEdgeIds) : null;

  return graphData.edges.map((edge) => {
    const isConnected =
      focusNodeId && (edge.source === focusNodeId || edge.target === focusNodeId);
    const baseOpacity = focusNodeId ? (isConnected ? 0.9 : 0.18) : 0.55;
    const suspicious = edge.suspicious;
    const isHighlighted = !!highlightEdgeSet?.has(edge.id);

    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: "smoothstep",
      label: formatEdgeLabel(edge),
      style: {
        stroke: suspicious ? suspiciousEdge : normalEdge,
        strokeWidth: isHighlighted ? (suspicious ? 3 : 2.5) : suspicious ? 2 : 1,
        opacity: isHighlighted ? 0.95 : suspicious ? Math.max(baseOpacity, 0.7) : baseOpacity,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: suspicious ? suspiciousEdge : normalEdge,
        width: 16,
        height: 16,
      },
      animated: isHighlighted || !!(edge.suspicious && (!focusNodeId || isConnected)),
      labelStyle: {
        fontSize: 11,
        fill: labelFill,
        fontWeight: 500,
      },
      labelBgStyle: {
        fill: labelBg,
        fillOpacity: 0.95,
      },
      labelBgPadding: [6, 4] as [number, number],
      labelBgBorderRadius: 4,
    };
  });
}

export function ShadowGraph({
  data,
  onNodeClick,
  focusNodeId,
  highlightNodeIds,
  highlightEdgeIds,
  minimapPosition = "bottom-center",
}: ShadowGraphProps) {
  const { resolvedTheme } = useTheme();
  const [isDark, setIsDark] = useState(false);
  const [flowInstance, setFlowInstance] = useState<ReactFlowInstance<Node, Edge> | null>(null);

  useEffect(() => {
    setIsDark(resolvedTheme === "dark");
  }, [resolvedTheme]);

  const initialNodes = useMemo(
    () => layoutNodes(data, focusNodeId, highlightNodeIds, isDark),
    [data, focusNodeId, highlightNodeIds, isDark]
  );
  const initialEdges = useMemo(
    () => createEdges(data, focusNodeId, highlightEdgeIds, isDark),
    [data, focusNodeId, highlightEdgeIds, isDark]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  useEffect(() => {
    setEdges(initialEdges);
  }, [initialEdges, setEdges]);

  useEffect(() => {
    if (!flowInstance) {
      return;
    }

    if (!focusNodeId) {
      flowInstance.fitView({ padding: 0.25, duration: 300 });
      return;
    }

    const targetNode = initialNodes.find((node) => node.id === focusNodeId);
    if (!targetNode) {
      return;
    }

    flowInstance.setCenter(targetNode.position.x + 120, targetNode.position.y + 40, {
      zoom: 0.9,
      duration: 350,
    });
  }, [flowInstance, focusNodeId, initialNodes]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (onNodeClick) {
        onNodeClick(node.id, node.data.nodeType as NodeType);
      }
    },
    [onNodeClick]
  );

  const nodeTheme = isDark ? NODE_THEME_DARK : NODE_THEME_LIGHT;

  const minimapNodeColor = useCallback((node: Node) => {
    const type = node.data?.nodeType as keyof typeof NODE_THEME_LIGHT;
    if (type === "TENDER" && node.data?.riskLevel) {
      return RISK_COLORS[node.data.riskLevel as RiskCategory];
    }
    return nodeTheme[type]?.border ?? "#64748b";
  }, [nodeTheme]);

  const minimapPositionClass =
    minimapPosition === "bottom-right"
      ? "bottom-4! left-auto! right-4! translate-x-0!"
      : "bottom-4! left-1/2! right-auto! -translate-x-1/2!";

  return (
    <div className="relative flex h-full w-full min-h-0 flex-col overflow-hidden rounded-2xl border border-border/60 bg-card/80 shadow-[0_25px_60px_-45px_rgba(31,75,70,0.4)]">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onInit={setFlowInstance}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        attributionPosition="bottom-left"
        proOptions={{ hideAttribution: true }}
        className="bg-transparent"
      >
        <Background color={isDark ? "#2a3533" : "#c8bfb4"} gap={48} size={1} />
        <Controls className="bottom-auto! left-4! top-4! [&>button]:bg-card/95! [&>button]:border-border/70! [&>button]:shadow-sm! [&>button]:text-foreground! [&>button:hover]:bg-primary/10! [&>button:hover]:text-primary!" />
        <MiniMap
          position="bottom-right"
          pannable
          zoomable
          className={`${minimapPositionClass} overflow-hidden rounded-lg border border-border/60 bg-card/95 shadow-lg backdrop-blur-sm`}
          nodeColor={minimapNodeColor}
          maskColor={isDark ? "rgba(11,17,16,0.7)" : "rgba(246,243,238,0.7)"}
        />
      </ReactFlow>

      {/* Legend */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 flex flex-col gap-3 p-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="pointer-events-auto max-w-[220px] rounded-xl border border-border/60 bg-card/95 p-3.5 text-xs text-muted-foreground shadow-lg backdrop-blur-sm">
          <div className="mb-2 text-[13px] font-semibold text-foreground/80">Legend</div>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <div className="h-2.5 w-2.5 rounded-sm" style={{ background: nodeTheme.COMPANY.border }} />
              <span>Company</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-2.5 w-2.5 rounded-full" style={{ background: nodeTheme.DIRECTOR.border }} />
              <span>Director</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-2.5 w-2.5 rounded-full" style={{ background: nodeTheme.OFFICIAL.border }} />
              <span>Official</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-2.5 w-2.5 rounded" style={{ background: nodeTheme.TENDER.border }} />
              <span>Tender</span>
            </div>
            <div className="my-1.5 border-t border-border/40" />
            <div className="flex items-center gap-2">
              <div className="h-px w-5" style={{ background: isDark ? "#5a5550" : "#b9b2a6" }} />
              <span>Connection</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-[2px] w-5 rounded-full" style={{ background: isDark ? "#e06050" : "#c4412f" }} />
              <span style={{ color: isDark ? "#e06050" : "#c4412f" }}>Suspicious</span>
            </div>
          </div>
        </div>
        <div className="pointer-events-none hidden min-h-[120px] min-w-[180px] sm:block" />
      </div>
    </div>
  );
}
