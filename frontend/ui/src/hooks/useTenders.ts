/**
 * Custom hooks for data fetching.
 */

import { useState, useEffect, useCallback } from "react";
import type {
  DashboardStats,
  TenderWithRisk,
  TenderDetail,
  GraphData,
  RiskCategory,
} from "@/lib/types";
import {
  getDashboardStats,
  getTenders,
  getTenderDetail,
  getTenderGraph,
  getFullGraph,
} from "@/lib/api";

export function useDashboardStats() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    getDashboardStats()
      .then(setStats)
      .catch(setError)
      .finally(() => setLoading(false));
  }, []);

  return { stats, loading, error };
}

export function useTenders(filter?: RiskCategory) {
  const [tenders, setTenders] = useState<TenderWithRisk[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    setLoading(true);
    getTenders({ riskLevel: filter, sortBy: "risk" })
      .then(setTenders)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [filter]);

  return { tenders, loading, error };
}

export function useTenderDetail(tenderId: string | null) {
  const [detail, setDetail] = useState<TenderDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!tenderId) {
      setDetail(null);
      return;
    }

    setLoading(true);
    getTenderDetail(tenderId)
      .then(setDetail)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [tenderId]);

  return { detail, loading, error };
}

export function useTenderGraph(tenderId: string | null) {
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchGraph = useCallback(async () => {
    if (!tenderId) {
      setGraph(null);
      return;
    }

    setLoading(true);
    try {
      const data = await getTenderGraph(tenderId);
      setGraph(data);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, [tenderId]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  return { graph, loading, error, refetch: fetchGraph };
}

export function useFullGraph() {
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    getFullGraph()
      .then(setGraph)
      .catch(setError)
      .finally(() => setLoading(false));
  }, []);

  return { graph, loading, error };
}
