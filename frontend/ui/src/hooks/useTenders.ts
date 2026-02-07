/**
 * Custom hooks for data fetching — powered by TanStack Query.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { RiskCategory, CaseStatus } from "@/lib/types";
import {
  getDashboardStats,
  getTenders,
  getTenderDetail,
  getTenderGraph,
  getFullGraph,
  getCases,
  getCaseStats,
  getCaseDetail,
  getCommunities,
  getCommunityGraph,
} from "@/lib/api";

// --- Query key factory ---

export const queryKeys = {
  dashboard: ["dashboard-stats"] as const,
  tenders: (filter?: RiskCategory) => ["tenders", filter ?? "ALL"] as const,
  tenderDetail: (id: string) => ["tender-detail", id] as const,
  tenderGraph: (id: string) => ["tender-graph", id] as const,
  fullGraph: ["full-graph"] as const,
  cases: (status?: CaseStatus | "ALL") => ["cases", status ?? "ALL"] as const,
  caseStats: ["case-stats"] as const,
  caseDetail: (id: string) => ["case-detail", id] as const,
  communities: ["communities"] as const,
  communityGraph: (id: string) => ["community-graph", id] as const,
};

// --- Tender hooks ---

export function useDashboardStats() {
  const { data: stats = null, isLoading: loading, error } = useQuery({
    queryKey: queryKeys.dashboard,
    queryFn: getDashboardStats,
  });
  return { stats, loading, error };
}

export function useTenders(filter?: RiskCategory) {
  const { data: tenders = [], isLoading: loading, error } = useQuery({
    queryKey: queryKeys.tenders(filter),
    queryFn: () => getTenders({ riskLevel: filter, sortBy: "risk" }),
  });
  return { tenders, loading, error };
}

export function useTenderDetail(tenderId: string | null) {
  const { data: detail = null, isLoading: loading, error } = useQuery({
    queryKey: queryKeys.tenderDetail(tenderId!),
    queryFn: () => getTenderDetail(tenderId!),
    enabled: !!tenderId,
  });
  return { detail, loading, error };
}

export function useTenderGraph(tenderId: string | null) {
  const queryClient = useQueryClient();
  const { data: graph = null, isLoading: loading, error } = useQuery({
    queryKey: queryKeys.tenderGraph(tenderId!),
    queryFn: () => getTenderGraph(tenderId!),
    enabled: !!tenderId,
    staleTime: 5 * 60 * 1000,
  });

  const refetch = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.tenderGraph(tenderId!) });

  return { graph, loading, error, refetch };
}

export function useFullGraph() {
  const { data: graph = null, isLoading: loading, error } = useQuery({
    queryKey: queryKeys.fullGraph,
    queryFn: getFullGraph,
    staleTime: 5 * 60 * 1000,
  });
  return { graph, loading, error };
}

// --- Case hooks ---

export function useCases(statusFilter?: CaseStatus | "ALL") {
  const status = statusFilter === "ALL" ? undefined : statusFilter;
  const { data: cases = [], isLoading: loading, error } = useQuery({
    queryKey: queryKeys.cases(statusFilter),
    queryFn: () => getCases(status ? { status } : undefined),
  });
  return { cases, loading, error };
}

export function useCaseStats() {
  const { data: stats = null, isLoading: loading, error } = useQuery({
    queryKey: queryKeys.caseStats,
    queryFn: getCaseStats,
  });
  return { stats, loading, error };
}

export function useCaseDetail(caseId: string | null) {
  const { data: detail = null, isLoading: loading, error } = useQuery({
    queryKey: queryKeys.caseDetail(caseId!),
    queryFn: () => getCaseDetail(caseId!),
    enabled: !!caseId,
  });
  return { detail, loading, error };
}

// --- Graph community hooks ---

export function useCommunities() {
  const { data, isLoading: loading, error } = useQuery({
    queryKey: queryKeys.communities,
    queryFn: getCommunities,
    staleTime: 5 * 60 * 1000,
  });
  return { clusters: data?.clusters ?? [], loading, error };
}

export function useCommunityGraph(clusterId: string | null) {
  const { data: graph = null, isLoading: loading, error } = useQuery({
    queryKey: queryKeys.communityGraph(clusterId!),
    queryFn: () => getCommunityGraph(clusterId!),
    enabled: !!clusterId,
    staleTime: 5 * 60 * 1000,
  });
  return { graph, loading, error };
}
