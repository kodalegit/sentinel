/**
 * Data Sources page — trigger PPIP sync and e-GP ingestion,
 * then recompute analysis so the dashboard reflects new data.
 */

"use client";

import { useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  syncPPIP,
  ingestEGPTenders,
  ingestEGPContracts,
  triggerRecompute,
  getRecomputeStatus,
} from "@/lib/api";
import type { RecomputeResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Database,
  RefreshCw,
  Globe,
  FileJson,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  BarChart3,
  Upload,
} from "lucide-react";

interface LogEntry {
  id: number;
  timestamp: string;
  level: "info" | "success" | "error";
  message: string;
}

let logCounter = 0;

export default function DataSourcesPage() {
  const queryClient = useQueryClient();
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [recomputing, setRecomputing] = useState(false);
  const [egpTenderJson, setEgpTenderJson] = useState("");
  const [egpContractJson, setEgpContractJson] = useState("");
  const [ingestingTenders, setIngestingTenders] = useState(false);
  const [ingestingContracts, setIngestingContracts] = useState(false);
  const [lastStats, setLastStats] = useState<RecomputeResponse["stats"] | null>(null);
  const [fiscalYear, setFiscalYear] = useState("2025-2026");

  const addLog = useCallback((level: LogEntry["level"], message: string) => {
    const entry: LogEntry = {
      id: ++logCounter,
      timestamp: new Date().toLocaleTimeString(),
      level,
      message,
    };
    setLogs((prev) => [entry, ...prev].slice(0, 100));
  }, []);

  const invalidateAll = useCallback(() => {
    queryClient.invalidateQueries();
  }, [queryClient]);

  const handlePPIPSync = async () => {
    setSyncing(true);
    addLog("info", `Starting PPIP OCDS sync for FY ${fiscalYear}...`);
    try {
      const result = await syncPPIP(fiscalYear);
      addLog("success", `PPIP sync complete: ${result.message}`);
      if (result.counts) {
        const parts = Object.entries(result.counts)
          .map(([k, v]) => `${k}: ${v}`)
          .join(", ");
        addLog("info", `Counts — ${parts}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      addLog("error", `PPIP sync failed: ${msg}`);
    } finally {
      setSyncing(false);
    }
  };

  const handleEGPTenders = async () => {
    if (!egpTenderJson.trim()) return;
    setIngestingTenders(true);
    addLog("info", "Ingesting e-GP tenders...");
    try {
      const payload = JSON.parse(egpTenderJson);
      const result = await ingestEGPTenders(payload);
      addLog("success", `e-GP tenders: ${result.message}`);
      setEgpTenderJson("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Invalid JSON";
      addLog("error", `e-GP tender ingestion failed: ${msg}`);
    } finally {
      setIngestingTenders(false);
    }
  };

  const handleEGPContracts = async () => {
    if (!egpContractJson.trim()) return;
    setIngestingContracts(true);
    addLog("info", "Ingesting e-GP contracts...");
    try {
      const payload = JSON.parse(egpContractJson);
      const result = await ingestEGPContracts(payload);
      addLog("success", `e-GP contracts: ${result.message}`);
      setEgpContractJson("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Invalid JSON";
      addLog("error", `e-GP contract ingestion failed: ${msg}`);
    } finally {
      setIngestingContracts(false);
    }
  };

  const handleRecompute = async () => {
    setRecomputing(true);
    addLog("info", "Starting recomputation (this may take a moment)...");
    try {
      // Trigger the recompute job
      const { job_id } = await triggerRecompute();
      addLog("info", `Job ${job_id.slice(0, 8)}... queued, waiting for completion...`);

      // Poll for job completion (max 60 attempts, 2 second delay = ~2 minutes)
      let attempts = 0;
      const maxAttempts = 60;
      const pollDelay = 2000;

      while (attempts < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, pollDelay));
        const status = await getRecomputeStatus(job_id);
        attempts++;

        if (status.status === "done" && status.stats) {
          setLastStats(status.stats);
          addLog(
            "success",
            `Recomputation complete — ${status.stats.tenders} tenders, ${status.stats.nodes} nodes, ${status.stats.edges} edges, ${status.stats.communities} communities`
          );
          invalidateAll();
          return;
        }

        if (status.status === "failed") {
          throw new Error(status.error || "Recomputation failed");
        }

        // Still running, continue polling
        if (attempts % 5 === 0) {
          addLog("info", `Still processing... (${attempts * 2}s elapsed)`);
        }
      }

      throw new Error("Recomputation timed out after 2 minutes");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      addLog("error", `Recomputation failed: ${msg}`);
    } finally {
      setRecomputing(false);
    }
  };

  return (
    <div className="min-h-screen pb-12">
      {/* Page header */}
      <header className="border-b border-border/70 bg-card/70 backdrop-blur-sm sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 lg:px-10">
          <div className="flex flex-col gap-4 py-6 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.35em] text-muted-foreground">
                Data Pipeline
              </p>
              <h1 className="font-display text-3xl text-foreground">
                Data Sources
              </h1>
              <p className="mt-1 text-sm text-muted-foreground max-w-xl">
                Ingest procurement data from PPIP and e-GP, then recompute
                analysis to update the dashboard.
              </p>
            </div>
            <Button
              size="sm"
              onClick={handleRecompute}
              disabled={recomputing}
              className="text-xs bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {recomputing ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <RefreshCw size={14} />
              )}
              {recomputing ? "Recomputing..." : "Recompute Analysis"}
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8">
        {/* Stats bar */}
        {lastStats && (
          <div className="mb-8 rounded-2xl border border-primary/20 bg-primary/5 p-4">
            <div className="flex items-center gap-3 mb-3">
              <BarChart3 size={16} className="text-primary" />
              <span className="text-xs font-semibold uppercase tracking-[0.15em] text-primary">
                Latest Recomputation
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
              {Object.entries(lastStats).map(([key, value]) => (
                <div key={key}>
                  <p className="text-lg font-display font-bold text-foreground">
                    {value}
                  </p>
                  <p className="text-[11px] text-muted-foreground capitalize">
                    {key.replace(/_/g, " ")}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left column — Source cards */}
          <div className="lg:col-span-2 space-y-6">
            {/* PPIP OCDS Sync */}
            <div className="rounded-2xl border border-border/70 bg-card/90 p-6">
              <div className="flex items-start gap-4 mb-5">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#1f4b46]/10 border border-[#1f4b46]/20 shrink-0">
                  <Globe size={18} className="text-[#1f4b46]" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-foreground">
                    PPIP OCDS — tenders.go.ke
                  </h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Fetch and normalize OCDS 1.1 releases from the Public
                    Procurement Information Portal for a given fiscal year.
                  </p>
                </div>
              </div>

              <div className="flex items-end gap-3">
                <div className="flex-1 max-w-[200px]">
                  <label className="text-[11px] uppercase tracking-wider text-muted-foreground block mb-1.5">
                    Fiscal Year
                  </label>
                  <input
                    type="text"
                    value={fiscalYear}
                    onChange={(e) => setFiscalYear(e.target.value)}
                    placeholder="2025-2026"
                    className="w-full rounded-lg border border-border/70 bg-secondary/50 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary/40"
                  />
                </div>
                <Button
                  size="sm"
                  onClick={handlePPIPSync}
                  disabled={syncing}
                  className="text-xs"
                >
                  {syncing ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Database size={14} />
                  )}
                  {syncing ? "Syncing..." : "Sync PPIP"}
                </Button>
              </div>
            </div>

            {/* e-GP Tenders */}
            <div className="rounded-2xl border border-border/70 bg-card/90 p-6">
              <div className="flex items-start gap-4 mb-5">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#35638c]/10 border border-[#35638c]/20 shrink-0">
                  <FileJson size={18} className="text-[#35638c]" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-foreground">
                    e-GP Tenders
                  </h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Paste a JSON payload from the e-GP tender listing API.
                    Expects <code className="text-[10px] bg-secondary/80 px-1 rounded">{"{ tenderDetails: [...] }"}</code>
                  </p>
                </div>
              </div>

              <textarea
                value={egpTenderJson}
                onChange={(e) => setEgpTenderJson(e.target.value)}
                placeholder='{"tenderDetails": [...]}'
                rows={4}
                className="w-full rounded-lg border border-border/70 bg-secondary/50 px-3 py-2 text-xs font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary/40 resize-y"
              />
              <div className="flex justify-end mt-3">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleEGPTenders}
                  disabled={ingestingTenders || !egpTenderJson.trim()}
                  className="text-xs"
                >
                  {ingestingTenders ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Upload size={14} />
                  )}
                  {ingestingTenders ? "Ingesting..." : "Ingest Tenders"}
                </Button>
              </div>
            </div>

            {/* e-GP Contracts */}
            <div className="rounded-2xl border border-border/70 bg-card/90 p-6">
              <div className="flex items-start gap-4 mb-5">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#b78b43]/10 border border-[#b78b43]/20 shrink-0">
                  <FileJson size={18} className="text-[#b78b43]" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-foreground">
                    e-GP Contracts
                  </h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Paste a JSON payload from the e-GP contract detail API.
                    Expects <code className="text-[10px] bg-secondary/80 px-1 rounded">{"{ contracts: [...] }"}</code> with supplier + director + ownership info.
                  </p>
                </div>
              </div>

              <textarea
                value={egpContractJson}
                onChange={(e) => setEgpContractJson(e.target.value)}
                placeholder='{"contracts": [...]}'
                rows={4}
                className="w-full rounded-lg border border-border/70 bg-secondary/50 px-3 py-2 text-xs font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary/40 resize-y"
              />
              <div className="flex justify-end mt-3">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleEGPContracts}
                  disabled={ingestingContracts || !egpContractJson.trim()}
                  className="text-xs"
                >
                  {ingestingContracts ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Upload size={14} />
                  )}
                  {ingestingContracts ? "Ingesting..." : "Ingest Contracts"}
                </Button>
              </div>
            </div>
          </div>

          {/* Right column — Activity log */}
          <div className="space-y-5">
            <div className="rounded-2xl border border-border/70 bg-card/90 p-5">
              <h3 className="text-[11px] uppercase tracking-[0.15em] text-muted-foreground font-semibold mb-4">
                Activity Log
              </h3>
              {logs.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-8">
                  No activity yet. Trigger a sync or ingestion to begin.
                </p>
              ) : (
                <ScrollArea className="max-h-[500px]">
                  <div className="space-y-2">
                    {logs.map((log) => (
                      <div
                        key={log.id}
                        className="flex items-start gap-2 text-xs"
                      >
                        {log.level === "success" ? (
                          <CheckCircle2
                            size={12}
                            className="text-emerald-500 mt-0.5 shrink-0"
                          />
                        ) : log.level === "error" ? (
                          <AlertTriangle
                            size={12}
                            className="text-[#c4412f] mt-0.5 shrink-0"
                          />
                        ) : (
                          <RefreshCw
                            size={12}
                            className="text-muted-foreground mt-0.5 shrink-0"
                          />
                        )}
                        <div className="min-w-0">
                          <span className="text-muted-foreground/60 tabular-nums">
                            {log.timestamp}
                          </span>{" "}
                          <span
                            className={
                              log.level === "error"
                                ? "text-[#c4412f]"
                                : log.level === "success"
                                ? "text-emerald-500"
                                : "text-foreground/80"
                            }
                          >
                            {log.message}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </div>

            {/* Workflow hint */}
            <div className="rounded-2xl border border-border/50 bg-secondary/40 p-5">
              <h3 className="text-[11px] uppercase tracking-[0.15em] text-muted-foreground font-semibold mb-3">
                Workflow
              </h3>
              <ol className="text-xs text-muted-foreground space-y-2">
                <li className="flex items-start gap-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full border border-border/60 text-[10px] font-bold shrink-0">
                    1
                  </span>
                  <span>
                    <strong className="text-foreground/80">Ingest data</strong>{" "}
                    — sync from PPIP or paste e-GP payloads
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full border border-border/60 text-[10px] font-bold shrink-0">
                    2
                  </span>
                  <span>
                    <strong className="text-foreground/80">Recompute</strong>{" "}
                    — rebuild graph, detect communities, score risk
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full border border-border/60 text-[10px] font-bold shrink-0">
                    3
                  </span>
                  <span>
                    <strong className="text-foreground/80">Review</strong>{" "}
                    — dashboard and graph update automatically
                  </span>
                </li>
              </ol>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
