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
  CaseEvent,
  CaseEvidenceLink,
  CaseNotification,
  WorkloadItem,
  KnowledgeDocument,
  KnowledgeChunk,
  KnowledgeStats,
  ChatThread,
  ChatMessage,
  ChatStreamEvent,
  AgentSettings,
  AgentSettingsUpdate,
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
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${newToken}`,
        },
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
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${newToken}`,
        },
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

async function deleteApi(endpoint: string): Promise<void> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });

  if (response.status === 401) {
    const newToken = await refreshTokens();
    if (newToken) {
      const retried = await fetch(`${API_BASE}${endpoint}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${newToken}` },
      });
      if (retried.ok || retried.status === 204) return;
    }
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Session expired. Please log in again.");
  }

  if (!response.ok && response.status !== 204) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `API error: ${response.status}`);
  }
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

export interface GraphStats {
  total_nodes: number;
  total_edges: number;
  node_types: Record<string, number>;
  edge_types: Record<string, number>;
  communities: number;
  is_large: boolean;
}

export async function getGraphStats(): Promise<GraphStats> {
  return fetchApi<GraphStats>("/api/graph/stats");
}

export async function getFullGraph(options?: {
  limitNodes?: number;
  limitEdges?: number;
  nodeType?: string;
}): Promise<GraphData> {
  const params = new URLSearchParams();
  if (options?.limitNodes)
    params.set("limit_nodes", String(options.limitNodes));
  if (options?.limitEdges)
    params.set("limit_edges", String(options.limitEdges));
  if (options?.nodeType) params.set("node_type", options.nodeType);
  const qs = params.toString();
  return fetchApi<GraphData>(`/api/graph/explore${qs ? `?${qs}` : ""}`);
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

// --- M3: Timeline & Evidence ---

export async function getCaseTimeline(caseId: string): Promise<CaseEvent[]> {
  return fetchApi<CaseEvent[]>(`/api/cases/${caseId}/timeline`);
}

export async function getCaseEvidence(
  caseId: string,
): Promise<CaseEvidenceLink[]> {
  return fetchApi<CaseEvidenceLink[]>(`/api/cases/${caseId}/evidence`);
}

export async function addCaseEvidence(
  caseId: string,
  data: {
    evidence_type: string;
    reference_id: string;
    label: string;
    link_metadata?: Record<string, unknown>;
  },
): Promise<CaseEvidenceLink> {
  return postApi<CaseEvidenceLink>(`/api/cases/${caseId}/evidence`, data);
}

export async function removeCaseEvidence(
  caseId: string,
  linkId: string,
): Promise<void> {
  return deleteApi(`/api/cases/${caseId}/evidence/${linkId}`);
}

// --- M3: Self-Assign & Decision ---

export async function selfAssignCase(caseId: string): Promise<CaseWithTender> {
  return postApi<CaseWithTender>(`/api/cases/${caseId}/self-assign`, {});
}

export async function recordDecision(
  caseId: string,
  data: {
    decision_type: string;
    finding: string;
    recommendation?: string;
    evidence_references?: string[];
  },
): Promise<CaseWithTender> {
  return postApi<CaseWithTender>(`/api/cases/${caseId}/decision`, data);
}

// --- M3: Workload ---

export async function getWorkload(): Promise<WorkloadItem[]> {
  return fetchApi<WorkloadItem[]>("/api/cases/workload");
}

// --- M3: Notifications ---

export async function getNotifications(
  unreadOnly = false,
): Promise<CaseNotification[]> {
  const qs = unreadOnly ? "?unread_only=true" : "";
  return fetchApi<CaseNotification[]>(`/api/notifications${qs}`);
}

export async function getNotificationCount(): Promise<{
  unread_count: number;
}> {
  return fetchApi<{ unread_count: number }>("/api/notifications/count");
}

export async function markNotificationRead(
  notificationId: string,
): Promise<void> {
  return patchApi(`/api/notifications/${notificationId}/read`, {});
}

// --- Ingestion ---

export async function syncPPIP(fiscalYear: string): Promise<IngestionResponse> {
  return postApi<IngestionResponse>("/api/ingest/ppip/sync", {
    fiscal_year: fiscalYear,
  });
}

export async function ingestEGPTenders(
  payload: unknown,
): Promise<IngestionResponse> {
  return postApi<IngestionResponse>("/api/ingest/egp/tenders", payload);
}

export async function ingestEGPContracts(
  payload: unknown,
): Promise<IngestionResponse> {
  return postApi<IngestionResponse>("/api/ingest/egp/contracts", payload);
}

export async function triggerRecompute(): Promise<{ status: string; job_id: string }> {
  return postApi<{ status: string; job_id: string }>("/api/recompute", {});
}

export async function getRecomputeStatus(jobId: string): Promise<{
  status: string;
  stats?: RecomputeResponse["stats"];
  error?: string;
}> {
  return fetchApi<{ status: string; stats?: RecomputeResponse["stats"]; error?: string }>(
    `/api/recompute/status/${jobId}`
  );
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
  data: {
    role?: string;
    is_active?: boolean;
    full_name?: string;
    email?: string;
    password?: string;
  },
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

// =============================================================================
// M5: Knowledge Base API
// =============================================================================

export async function getKnowledgeDocuments(): Promise<KnowledgeDocument[]> {
  return fetchApi<KnowledgeDocument[]>("/api/knowledge/documents");
}

export async function getKnowledgeDocument(id: string): Promise<KnowledgeDocument> {
  return fetchApi<KnowledgeDocument>(`/api/knowledge/documents/${id}`);
}

export async function uploadKnowledgeDocument(
  file: File,
  title: string,
  category: string,
  description?: string,
  sourceUrl?: string
): Promise<KnowledgeDocument> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("title", title);
  formData.append("category", category);
  if (description) formData.append("description", description);
  if (sourceUrl) formData.append("source_url", sourceUrl);

  const response = await fetch(`${API_BASE}/api/knowledge/documents`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(error.detail || "Upload failed");
  }

  return response.json();
}

export async function deleteKnowledgeDocument(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/knowledge/documents/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!response.ok) {
    throw new Error("Failed to delete document");
  }
}

export async function getKnowledgeStats(): Promise<KnowledgeStats> {
  return fetchApi<KnowledgeStats>("/api/knowledge/stats");
}

export async function getDocumentChunks(documentId: string): Promise<KnowledgeChunk[]> {
  return fetchApi<KnowledgeChunk[]>(`/api/knowledge/documents/${documentId}/chunks`);
}

// =============================================================================
// M5: Chat API
// =============================================================================

export async function getChatThreads(caseId: string): Promise<ChatThread[]> {
  return fetchApi<ChatThread[]>(`/api/cases/${caseId}/chat/threads`);
}

export async function getThreadMessages(caseId: string, threadId: string): Promise<ChatMessage[]> {
  return fetchApi<ChatMessage[]>(`/api/cases/${caseId}/chat/threads/${threadId}/messages`);
}

export async function deleteChatThread(caseId: string, threadId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/cases/${caseId}/chat/threads/${threadId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Delete failed" }));
    throw new Error(error.detail || "Delete failed");
  }
}

export type StreamAction = "chat" | "summary" | "next_steps" | "risk_analysis";

export async function* streamChat(
  caseId: string,
  message: string,
  options?: {
    threadId?: string;
    action?: StreamAction;
  }
): AsyncGenerator<ChatStreamEvent> {
  const response = await fetch(`${API_BASE}/api/cases/${caseId}/chat/stream`, {
    method: "POST",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      thread_id: options?.threadId,
      action: options?.action || "chat",
    }),
  });

  if (!response.ok) {
    throw new Error("Chat request failed");
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const event = JSON.parse(line.slice(6)) as ChatStreamEvent;
          yield event;
        } catch {
          // Ignore parse errors
        }
      }
    }
  }
}

// =============================================================================
// M5: Agent Settings API
// =============================================================================

export async function getAgentSettings(): Promise<AgentSettings> {
  return fetchApi<AgentSettings>("/api/settings/llm");
}

export async function updateAgentSettings(settings: AgentSettingsUpdate): Promise<AgentSettings> {
  const response = await fetch(`${API_BASE}/api/settings/llm`, {
    method: "PATCH",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(settings),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Update failed" }));
    throw new Error(error.detail || "Update failed");
  }

  return response.json();
}

export async function testLLMConnection(): Promise<{
  success: boolean;
  provider: string;
  model: string;
  response?: string;
  error?: string;
}> {
  return postApi("/api/settings/llm/test", {});
}
