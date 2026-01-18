/**
 * API client for Sentinel backend.
 */

import type {
  DashboardStats,
  TenderWithRisk,
  TenderDetail,
  GraphData,
  CartelsResponse,
  RiskCategory,
  TenderStatus,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchApi<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`);
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function getDashboardStats(): Promise<DashboardStats> {
  return fetchApi<DashboardStats>("/api/stats");
}

export async function getTenders(options?: {
  riskLevel?: RiskCategory;
  status?: TenderStatus;
  sortBy?: "risk" | "value" | "date";
  limit?: number;
}): Promise<TenderWithRisk[]> {
  const params = new URLSearchParams();
  if (options?.riskLevel) params.set("risk_level", options.riskLevel);
  if (options?.status) params.set("status", options.status);
  if (options?.sortBy) params.set("sort_by", options.sortBy);
  if (options?.limit) params.set("limit", options.limit.toString());

  const queryString = params.toString();
  const endpoint = `/api/tenders${queryString ? `?${queryString}` : ""}`;
  return fetchApi<TenderWithRisk[]>(endpoint);
}

export async function getTenderDetail(tenderId: string): Promise<TenderDetail> {
  return fetchApi<TenderDetail>(`/api/tenders/${tenderId}`);
}

export async function getTenderGraph(
  tenderId: string,
  depth: number = 2
): Promise<GraphData> {
  return fetchApi<GraphData>(`/api/tenders/${tenderId}/graph?depth=${depth}`);
}

export async function getFullGraph(): Promise<GraphData> {
  return fetchApi<GraphData>("/api/graph/explore");
}

export async function getCartels(): Promise<CartelsResponse> {
  return fetchApi<CartelsResponse>("/api/graph/cartels");
}

// Utility functions
export function formatKES(amount: number): string {
  if (amount >= 1_000_000_000) {
    return `KES ${(amount / 1_000_000_000).toFixed(1)}B`;
  }
  if (amount >= 1_000_000) {
    return `KES ${(amount / 1_000_000).toFixed(1)}M`;
  }
  if (amount >= 1_000) {
    return `KES ${(amount / 1_000).toFixed(0)}K`;
  }
  return `KES ${amount.toFixed(0)}`;
}

export function getRiskColor(category: RiskCategory): string {
  switch (category) {
    case "HIGH":
      return "text-red-600";
    case "MEDIUM":
      return "text-amber-500";
    case "LOW":
      return "text-emerald-600";
  }
}

export function getRiskBgColor(category: RiskCategory): string {
  switch (category) {
    case "HIGH":
      return "bg-red-100";
    case "MEDIUM":
      return "bg-amber-100";
    case "LOW":
      return "bg-emerald-100";
  }
}

export function getRiskBorderColor(category: RiskCategory): string {
  switch (category) {
    case "HIGH":
      return "border-red-500";
    case "MEDIUM":
      return "border-amber-500";
    case "LOW":
      return "border-emerald-500";
  }
}
