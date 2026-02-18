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
  IngestionResponse,
  RecomputeResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TOKEN_KEY = "sentinel_access_token";
const REFRESH_KEY = "sentinel_refresh_token";

async function refreshTokens(): Promise<string | null> {
  const refreshToken = localStorage.getItem(REFRESH_KEY);
  if (!refreshToken) return null;
  try {
    const res = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(REFRESH_KEY, data.refresh_token);
    return data.access_token;
  } catch {
    return null;
  }
}

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchApi<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: getAuthHeaders(),
  });

  if (response.status === 401) {
    // Try token refresh once
    const newToken = await refreshTokens();
    if (newToken) {
      const retried = await fetch(`${API_BASE}${endpoint}`, {
        headers: { Authorization: `Bearer ${newToken}` },
      });
      if (retried.ok) return retried.json();
    }
    // Redirect to login if refresh fails
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Session expired. Please log in again.");
  }

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

async function postApi<T>(endpoint: string, data: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(data),
  });

  if (response.status === 401) {
    const newToken = await refreshTokens();
    if (newToken) {
      const retried = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${newToken}` },
        body: JSON.stringify(data),
      });
      if (retried.ok) return retried.json();
    }
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Session expired. Please log in again.");
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `API error: ${response.status}`);
  }
  return response.json();
}

async function patchApi<T>(endpoint: string, data: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(data),
  });

  if (response.status === 401) {
    const newToken = await refreshTokens();
    if (newToken) {
      const retried = await fetch(`${API_BASE}${endpoint}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${newToken}` },
        body: JSON.stringify(data),
      });
      if (retried.ok) return retried.json();
    }
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Session expired. Please log in again.");
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `API error: ${response.status}`);
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
  assigned_to_id?: string;
  summary?: string;
}): Promise<CaseWithTender> {
  return postApi<CaseWithTender>("/api/cases", data);
}

export async function updateCase(
  caseId: string,
  data: {
    status?: string;
    priority?: string;
    assigned_to_id?: string;
    summary?: string;
    decision?: string;
  },
): Promise<CaseWithTender> {
  return patchApi<CaseWithTender>(`/api/cases/${caseId}`, data);
}

export async function addCaseNote(
  caseId: string,
  data: { content: string; note_type?: string },
): Promise<unknown> {
  return postApi<unknown>(`/api/cases/${caseId}/notes`, data);
}

// --- Ingestion ---

export async function syncPPIP(fiscalYear: string): Promise<IngestionResponse> {
  return postApi<IngestionResponse>("/api/ingest/ppip/sync", { fiscal_year: fiscalYear });
}

export async function ingestEGPTenders(payload: unknown): Promise<IngestionResponse> {
  return postApi<IngestionResponse>("/api/ingest/egp/tenders", payload);
}

export async function ingestEGPContracts(payload: unknown): Promise<IngestionResponse> {
  return postApi<IngestionResponse>("/api/ingest/egp/contracts", payload);
}

export async function triggerRecompute(): Promise<RecomputeResponse> {
  return postApi<RecomputeResponse>("/api/recompute", {});
}

// --- User Management ---

export interface ApiUser {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export async function getUsers(): Promise<ApiUser[]> {
  return fetchApi<ApiUser[]>("/api/users");
}

export async function createUser(data: {
  username: string;
  email: string;
  password: string;
  full_name: string;
  role: string;
}): Promise<ApiUser> {
  return postApi<ApiUser>("/api/users", data);
}

export async function updateUser(
  userId: string,
  data: { role?: string; is_active?: boolean; full_name?: string; email?: string; password?: string },
): Promise<ApiUser> {
  return patchApi<ApiUser>(`/api/users/${userId}`, data);
}

export async function getAssignableUsers(): Promise<ApiUser[]> {
  return fetchApi<ApiUser[]>("/api/users/assignable/list");
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
