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
  onNodeClick?: (nodeId: string, nodeType: NodeType) => void;
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

/**
 * Barycenter heuristic: order nodes in a layer by the average x-position
 * of their neighbours in the previously placed layer. Significantly reduces
 * edge crossings compared to arbitrary ordering.
 */
function layoutNodes(graphData: GraphData, focusNodeId?: string, isDark = false): Node[] {
  const NODE_THEME = isDark ? NODE_THEME_DARK : NODE_THEME_LIGHT;
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
      const isHighRisk = node.risk_level === "HIGH";
      const borderColor = node.risk_level
        ? RISK_COLORS[node.risk_level]
        : theme.border;
      const isFocused = focusNodeId && node.id === focusNodeId;
      const isDimmed = focusNodeId && node.id !== focusNodeId;

      result.push({
        id: node.id,
        position: { x, y },
        data: {
          label: (
            <div className="flex items-center gap-3 px-1">
              <Icon size={20} strokeWidth={1.5} className="shrink-0" />
              <span className="text-[14px] font-semibold truncate max-w-[240px] leading-snug">
                {node.label}
              </span>
            </div>
          ),
          nodeType: node.type,
          metadata: node.metadata,
          riskLevel: node.risk_level,
        },
        style: {
          background: theme.bg,
          border: `1.5px solid ${borderColor}`,
          color: theme.color,
          borderRadius: meta.radius,
          padding: "14px 22px",
          fontSize: "14px",
          boxShadow: isFocused
            ? `0 0 0 4px ${borderColor}50`
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

function createEdges(graphData: GraphData, focusNodeId?: string, isDark = false): Edge[] {
  const normalEdge = isDark ? "#5a5550" : "#b9b2a6";
  const suspiciousEdge = isDark ? "#e06050" : "#c4412f";
  const labelFill = isDark ? "#c8c2b8" : "#6b6761";
  const labelBg = isDark ? "#111a19" : "#fffaf4";

  return graphData.edges.map((edge) => {
    const isConnected =
      focusNodeId && (edge.source === focusNodeId || edge.target === focusNodeId);
    const baseOpacity = focusNodeId ? (isConnected ? 0.9 : 0.18) : 0.55;
    const suspicious = edge.suspicious;

    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: "smoothstep",
      label: edge.suspicious ? (edge.label || undefined) : undefined,
      style: {
        stroke: suspicious ? suspiciousEdge : normalEdge,
        strokeWidth: suspicious ? 2 : 1,
        opacity: suspicious ? Math.max(baseOpacity, 0.7) : baseOpacity,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: suspicious ? suspiciousEdge : normalEdge,
        width: 16,
        height: 16,
      },
      animated: !!(edge.suspicious && (!focusNodeId || isConnected)),
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

export function ShadowGraph({ data, onNodeClick, focusNodeId }: ShadowGraphProps) {
  const { resolvedTheme } = useTheme();
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    setIsDark(resolvedTheme === "dark");
  }, [resolvedTheme]);

  const initialNodes = useMemo(() => layoutNodes(data, focusNodeId, isDark), [data, focusNodeId, isDark]);
  const initialEdges = useMemo(() => createEdges(data, focusNodeId, isDark), [data, focusNodeId, isDark]);

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

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

  return (
    <div className="w-full h-full rounded-2xl border border-border/60 overflow-hidden bg-card/80 shadow-[0_25px_60px_-45px_rgba(31,75,70,0.4)]">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        attributionPosition="bottom-left"
        proOptions={{ hideAttribution: true }}
      >
        <Background color={isDark ? "#2a3533" : "#c8bfb4"} gap={48} size={1} />
        <Controls />
        <MiniMap
          nodeColor={minimapNodeColor}
          maskColor={isDark ? "rgba(11,17,16,0.7)" : "rgba(246,243,238,0.7)"}
        />
      </ReactFlow>

      {/* Legend */}
      <div className="absolute bottom-4 left-20 rounded-xl border border-border/60 bg-card/95 backdrop-blur-sm p-3.5 text-xs text-muted-foreground shadow-lg z-10">
        <div className="font-semibold mb-2 text-foreground/80 text-[13px]">Legend</div>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-sm" style={{ background: nodeTheme.COMPANY.border }} />
            <span>Company</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: nodeTheme.DIRECTOR.border }} />
            <span>Director</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: nodeTheme.OFFICIAL.border }} />
            <span>Official</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded" style={{ background: nodeTheme.TENDER.border }} />
            <span>Tender</span>
          </div>
          <div className="my-1.5 border-t border-border/40" />
          <div className="flex items-center gap-2">
            <div className="w-5 h-px" style={{ background: isDark ? "#5a5550" : "#b9b2a6" }} />
            <span>Connection</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-5 h-[2px] rounded-full" style={{ background: isDark ? "#e06050" : "#c4412f" }} />
            <span style={{ color: isDark ? "#e06050" : "#c4412f" }}>Suspicious</span>
          </div>
        </div>
      </div>
    </div>
  );
}
