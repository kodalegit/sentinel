/**
 * API client for Sentinel backend.
 */

import type {
  DashboardStats,
  TenderWithRisk,
  TenderDetail,
  GraphData,
  CommunitiesResponse,
  CaseWithTender,
  CaseStats,
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
  depth: number = 2,
): Promise<GraphData> {
  return fetchApi<GraphData>(`/api/tenders/${tenderId}/graph?depth=${depth}`);
}

export async function getFullGraph(): Promise<GraphData> {
  return fetchApi<GraphData>("/api/graph/explore");
}

export async function getCommunities(): Promise<CommunitiesResponse> {
  return fetchApi<CommunitiesResponse>("/api/graph/communities");
}

export async function getCommunityGraph(clusterId: string): Promise<GraphData> {
  return fetchApi<GraphData>(`/api/graph/communities/${clusterId}`);
}

// --- Case Management ---

export async function getCases(options?: {
  status?: string;
  priority?: string;
}): Promise<CaseWithTender[]> {
  const params = new URLSearchParams();
  if (options?.status) params.set("status", options.status);
  if (options?.priority) params.set("priority", options.priority);
  const qs = params.toString();
  return fetchApi<CaseWithTender[]>(`/api/cases${qs ? `?${qs}` : ""}`);
}

export async function getCaseStats(): Promise<CaseStats> {
  return fetchApi<CaseStats>("/api/cases/stats");
}

export async function getCaseDetail(caseId: string): Promise<CaseWithTender> {
  return fetchApi<CaseWithTender>(`/api/cases/${caseId}`);
}

export async function createCase(data: {
  tender_id: string;
  title: string;
  priority?: string;
  assigned_to?: string;
  summary?: string;
  created_by?: string;
}): Promise<CaseWithTender> {
  const response = await fetch(`${API_BASE}/api/cases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

export async function updateCase(
  caseId: string,
  data: {
    status?: string;
    priority?: string;
    assigned_to?: string;
    summary?: string;
    decision?: string;
  },
): Promise<CaseWithTender> {
  const response = await fetch(`${API_BASE}/api/cases/${caseId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

export async function addCaseNote(
  caseId: string,
  data: { content: string; author?: string; note_type?: string },
): Promise<unknown> {
  const response = await fetch(`${API_BASE}/api/cases/${caseId}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
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
      return "text-red-400";
    case "MEDIUM":
      return "text-amber-400";
    case "LOW":
      return "text-emerald-400";
  }
}

export function getRiskBgColor(category: RiskCategory): string {
  switch (category) {
    case "HIGH":
      return "bg-red-500/10";
    case "MEDIUM":
      return "bg-amber-500/10";
    case "LOW":
      return "bg-emerald-500/10";
  }
}

export function getRiskBorderColor(category: RiskCategory): string {
  switch (category) {
    case "HIGH":
      return "border-red-500/30";
    case "MEDIUM":
      return "border-amber-500/30";
    case "LOW":
      return "border-emerald-500/30";
  }
}
