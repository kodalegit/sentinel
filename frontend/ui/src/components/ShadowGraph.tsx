/**
 * Shadow Graph component using React Flow.
 */

"use client";

import { useMemo, useCallback } from "react";
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

interface ShadowGraphProps {
  data: GraphData;
  focusNodeId?: string;
  onNodeClick?: (nodeId: string, nodeType: NodeType) => void;
}

// Custom node styles
const nodeStyles = {
  COMPANY: {
    background: "linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)",
    border: "2px solid #1e40af",
    color: "#ffffff",
    icon: Building2,
  },
  DIRECTOR: {
    background: "linear-gradient(135deg, #64748b 0%, #475569 100%)",
    border: "2px solid #334155",
    color: "#ffffff",
    icon: User,
  },
  OFFICIAL: {
    background: "linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)",
    border: "2px solid #991b1b",
    color: "#ffffff",
    icon: Briefcase,
  },
  TENDER: {
    background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
    border: "2px solid #047857",
    color: "#ffffff",
    icon: FileText,
  },
};

const riskColors: Record<RiskCategory, string> = {
  HIGH: "#ef4444",
  MEDIUM: "#f59e0b",
  LOW: "#10b981",
};

function layoutNodes(graphData: GraphData): Node[] {
  // Group nodes by type for layered layout
  const nodesByType: Record<string, typeof graphData.nodes> = {
    OFFICIAL: [],
    TENDER: [],
    COMPANY: [],
    DIRECTOR: [],
  };

  graphData.nodes.forEach((node) => {
    nodesByType[node.type]?.push(node);
  });

  const nodes: Node[] = [];
  let yOffset = 0;

  // Layout each type in rows
  const typeOrder = ["OFFICIAL", "TENDER", "COMPANY", "DIRECTOR"];

  typeOrder.forEach((type) => {
    const typeNodes = nodesByType[type] || [];
    const xSpacing = 250;
    const startX = -(typeNodes.length * xSpacing) / 2 + xSpacing / 2;

    typeNodes.forEach((node, idx) => {
      const style = nodeStyles[node.type as keyof typeof nodeStyles];
      const Icon = style.icon;

      // Determine if this is a high-risk tender
      const isHighRisk = node.risk_level === "HIGH";
      const borderColor = node.risk_level
        ? riskColors[node.risk_level]
        : style.border.split(" ")[2];

      nodes.push({
        id: node.id,
        position: { x: startX + idx * xSpacing, y: yOffset },
        data: {
          label: (
            <div className="flex items-center gap-2 px-2">
              <Icon size={16} />
              <span className="text-xs font-medium truncate max-w-[120px]">
                {node.label}
              </span>
            </div>
          ),
          nodeType: node.type,
          metadata: node.metadata,
          riskLevel: node.risk_level,
        },
        style: {
          background: style.background,
          border: `2px solid ${borderColor}`,
          color: style.color,
          borderRadius: node.type === "TENDER" ? "12px" : node.type === "DIRECTOR" || node.type === "OFFICIAL" ? "50%" : "8px",
          padding: "8px 12px",
          fontSize: "12px",
          boxShadow: isHighRisk
            ? `0 0 20px ${riskColors.HIGH}40`
            : "0 4px 12px rgba(0,0,0,0.15)",
          minWidth: node.type === "DIRECTOR" || node.type === "OFFICIAL" ? "100px" : "auto",
          textAlign: "center" as const,
        },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
      });
    });

    yOffset += 150;
  });

  return nodes;
}

function createEdges(graphData: GraphData): Edge[] {
  return graphData.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.label || undefined,
    style: {
      stroke: edge.suspicious ? "#ef4444" : "#94a3b8",
      strokeWidth: edge.suspicious ? 2 : 1,
      strokeDasharray: edge.suspicious ? "5,5" : undefined,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: edge.suspicious ? "#ef4444" : "#94a3b8",
    },
    animated: edge.suspicious,
    labelStyle: {
      fontSize: 10,
      fill: "#64748b",
    },
    labelBgStyle: {
      fill: "#ffffff",
    },
  }));
}

export function ShadowGraph({ data, focusNodeId, onNodeClick }: ShadowGraphProps) {
  const initialNodes = useMemo(() => layoutNodes(data), [data]);
  const initialEdges = useMemo(() => createEdges(data), [data]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (onNodeClick) {
        onNodeClick(node.id, node.data.nodeType as NodeType);
      }
    },
    [onNodeClick]
  );

  const minimapNodeColor = useCallback((node: Node) => {
    const type = node.data?.nodeType as keyof typeof nodeStyles;
    if (type === "TENDER" && node.data?.riskLevel) {
      return riskColors[node.data.riskLevel as RiskCategory];
    }
    return type === "COMPANY"
      ? "#3b82f6"
      : type === "DIRECTOR"
      ? "#64748b"
      : type === "OFFICIAL"
      ? "#dc2626"
      : "#10b981";
  }, []);

  return (
    <div className="w-full h-full bg-slate-50 rounded-xl overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        attributionPosition="bottom-left"
      >
        <Background color="#cbd5e1" gap={20} size={1} />
        <Controls className="bg-white rounded-lg shadow-lg" />
        <MiniMap
          nodeColor={minimapNodeColor}
          className="bg-white rounded-lg shadow-lg"
          maskColor="rgba(0,0,0,0.1)"
        />
      </ReactFlow>

      {/* Legend */}
      <div className="absolute bottom-4 right-4 bg-white rounded-lg shadow-lg p-3 text-xs">
        <div className="font-semibold mb-2 text-slate-700">Legend</div>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-blue-500" />
            <span>Company</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-slate-500" />
            <span>Director</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <span>Official</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-lg bg-emerald-500" />
            <span>Tender</span>
          </div>
          <hr className="my-2" />
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 bg-slate-400" />
            <span>Connection</span>
          </div>
          <div className="flex items-center gap-2">
            <div
              className="w-6 h-0.5 bg-red-500"
              style={{ backgroundImage: "repeating-linear-gradient(90deg, #ef4444, #ef4444 3px, transparent 3px, transparent 6px)" }}
            />
            <span className="text-red-600">Suspicious</span>
          </div>
        </div>
      </div>
    </div>
  );
}
