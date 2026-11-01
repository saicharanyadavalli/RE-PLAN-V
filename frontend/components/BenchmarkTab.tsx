"use client";

import React, { useState, useEffect } from "react";
import { Play, BarChart3, ShieldCheck, CheckCircle2, AlertTriangle, RefreshCw, Info } from "lucide-react";
import { getApiBaseUrl } from "../utils/api";

const MATRIX_CLASSES = [
  { key: "PLANNING_ERROR", label: "PLANNING" },
  { key: "PERCEPTION_ERROR", label: "PERCEPTION" },
  { key: "FORMALIZATION_ERROR", label: "FORMAL" },
  { key: "ENVIRONMENT_CHANGE", label: "ENV_DELTA" },
  { key: "UNKNOWN_AMBIGUOUS", label: "UNKNOWN" },
];

export type BenchmarkLifecycleStatus = "NOT_RUN" | "LOADING" | "LOADED" | "STALE" | "FAILED";

export function BenchmarkTab() {
  const [instances, setInstances] = useState(5);
  const [seed, setSeed] = useState(42);
  const [lastRunParams, setLastRunParams] = useState<{ instances: number; seed: number } | null>(null);
  const [status, setStatus] = useState<BenchmarkLifecycleStatus>("NOT_RUN");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [results, setResults] = useState<any>(null);
  const [attributionData, setAttributionData] = useState<any>(null);

  const fetchAttribution = async () => {
    try {
      const resp = await fetch(`${getApiBaseUrl()}/api/benchmark/attribution`);
      if (resp.ok) {
        const data = await resp.json();
        setAttributionData(data);
      }
    } catch (e) {
      console.warn("Could not load attribution matrix:", e);
    }
  };

  useEffect(() => {
    fetchAttribution();
  }, []);

  // Track parameter drift to mark results as STALE
  useEffect(() => {
    if (status === "LOADED" && lastRunParams) {
      if (lastRunParams.instances !== instances || lastRunParams.seed !== seed) {
        setStatus("STALE");
      }
    } else if (status === "STALE" && lastRunParams) {
      if (lastRunParams.instances === instances && lastRunParams.seed === seed) {
        setStatus("LOADED");
      }
    }
  }, [instances, seed, lastRunParams, status]);

  const runBenchmark = async () => {
    setStatus("LOADING");
    setErrorMessage(null);
    try {
      const resp = await fetch(`${getApiBaseUrl()}/api/benchmark/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ num_instances: instances, seed: seed }),
      });
      if (!resp.ok) {
        const errBody = await resp.text();
        throw new Error(`API returned HTTP ${resp.status}: ${errBody}`);
      }
      const data = await resp.json();
      setResults(data);
      setLastRunParams({ instances, seed });
      setStatus("LOADED");
      await fetchAttribution();
    } catch (e: any) {
      console.error("Benchmark error:", e);
      setErrorMessage(e.message || "Failed to communicate with benchmark backend.");
      setStatus("FAILED");
    }
  };

  const isRunning = status === "LOADING";

  return (
    <div className="flex flex-col gap-6">
      {/* Overview Card */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-cyan-400" />
              <h2 className="font-mono text-sm font-bold uppercase tracking-wider text-slate-200">
                Comparative Empirical Research Benchmark
              </h2>
            </div>
            <p className="mt-1 text-xs text-slate-400">
              Evaluating the Central Hypothesis:{" "}
              <span className="italic text-cyan-300">
                "Can counterexample-guided fault attribution and automatic repair improve recovery from
                initially invalid plans compared with generic plan regeneration?"
              </span>
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs">
              <label className="text-slate-400">Instances:</label>
              <input
                type="number"
                min={2}
                max={20}
                value={instances}
                onChange={(e) => setInstances(Number(e.target.value))}
                className="w-14 rounded-lg border border-slate-700 bg-slate-950 p-1.5 font-mono text-xs text-center text-slate-200"
              />
            </div>
            <div className="flex items-center gap-2 text-xs">
              <label className="text-slate-400">Seed:</label>
              <input
                type="number"
                value={seed}
                onChange={(e) => setSeed(Number(e.target.value))}
                className="w-14 rounded-lg border border-slate-700 bg-slate-950 p-1.5 font-mono text-xs text-center text-slate-200"
              />
            </div>
            <button
              onClick={runBenchmark}
              disabled={isRunning}
              className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-2 text-xs font-bold uppercase tracking-wider text-white shadow-lg transition hover:from-cyan-400 hover:to-blue-500 disabled:opacity-50"
            >
              {isRunning ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5 fill-current" />
                  Run Live Experiment
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Status Banners */}
      {status === "FAILED" && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-950/20 p-4 text-xs text-rose-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0" />
            <span>Benchmark execution failed: <strong>{errorMessage}</strong></span>
          </div>
          <button
            onClick={runBenchmark}
            className="rounded-lg bg-rose-600/30 px-3 py-1 text-xs font-semibold hover:bg-rose-600/50"
          >
            Retry
          </button>
        </div>
      )}

      {status === "STALE" && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-950/20 p-3 text-xs text-amber-300 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
          <span>
            Configuration modified since last execution (Seed/Instances changed). The results below reflect the previous run (Seed {lastRunParams?.seed}, {lastRunParams?.instances} instances). Re-run to refresh.
          </span>
        </div>
      )}

      {status === "NOT_RUN" && (
        <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-900/30 p-8 text-center">
          <Info className="h-8 w-8 text-slate-500 mx-auto mb-2" />
          <h3 className="font-mono text-sm font-semibold text-slate-300">Benchmark Not Yet Executed</h3>
          <p className="mt-1 text-xs text-slate-500 max-w-md mx-auto">
            Click <strong>Run Live Experiment</strong> above to execute the 5-way comparative evaluation across B0, B1, B2, B3, and RE-PLAN-V.
          </p>
        </div>
      )}

      {/* Results Table */}
      {results && results.summary && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl">
          {/* Provenance Header */}
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
            <div>
              <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-slate-300">
                Controlled Pilot Benchmark ({lastRunParams?.instances ?? instances} Instances, Seed {lastRunParams?.seed ?? seed})
              </h3>
              <p className="mt-0.5 text-[11px] text-slate-500 font-mono">
                Provenance: {results.provenance?.dataset || "Controlled synthetic blocks_world pilot instances"} | Timestamp: {results.provenance?.timestamp || new Date().toISOString()}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-cyan-500/10 px-2.5 py-0.5 font-mono text-[10px] font-bold text-cyan-400 border border-cyan-500/20">
                STATUS: {status}
              </span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="pb-3 font-semibold">Baseline / System</th>
                  <th className="pb-3 font-semibold">Valid Plan Rate</th>
                  <th className="pb-3 font-semibold">Goal Success</th>
                  <th className="pb-3 font-semibold">Fault Recovery Rate</th>
                  <th className="pb-3 font-semibold">Avg Planning Time</th>
                  <th className="pb-3 font-semibold">Avg Pure Repair Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {Object.entries(results.summary).map(([name, data]: [string, any]) => (
                  <tr
                    key={name}
                    className={
                      name === "OURS_CounterexampleRepair"
                        ? "bg-cyan-500/10 text-cyan-300 font-bold"
                        : "text-slate-300"
                    }
                  >
                    <td className="py-3 font-sans font-medium">{name}</td>
                    <td className="py-3">{(data.valid_plan_rate * 100).toFixed(1)}%</td>
                    <td className="py-3">{(data.goal_success_rate * 100).toFixed(1)}%</td>
                    <td className="py-3 text-emerald-400 font-bold">
                      {typeof data.repair_success_rate === "number"
                        ? `${(data.repair_success_rate * 100).toFixed(1)}%`
                        : "N/A"}
                    </td>
                    <td className="py-3">{data.avg_planning_time_ms.toFixed(2)} ms</td>
                    <td className="py-3 text-cyan-300">
                      {typeof data.avg_repair_time_ms === "number"
                        ? `${data.avg_repair_time_ms.toFixed(2)} ms`
                        : "N/A"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Research Finding Highlight */}
          <div className="mt-6 rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-4">
            <div className="flex items-center gap-2 text-emerald-400">
              <CheckCircle2 className="h-5 w-5" />
              <span className="font-mono text-xs font-bold uppercase tracking-wider">
                Hypothesis Empirically Evaluated
              </span>
            </div>
            {(() => {
              const oursRate = results.summary["OURS_CounterexampleRepair"]?.repair_success_rate;
              const b3Rate = results.summary["B3_GenericRegeneration"]?.repair_success_rate;
              const hasAdvantage = typeof oursRate === "number" && typeof b3Rate === "number";
              const advDiff = hasAdvantage ? (oursRate - b3Rate) * 100 : null;
              return (
                <p className="mt-1 text-xs text-slate-300">
                  Generic regeneration (Baseline B3: active candidate sequence re-sampling) achieves recovery of{" "}
                  <strong className="text-amber-300">
                    {typeof b3Rate === "number" ? `${(b3Rate * 100).toFixed(1)}%` : "N/A"}
                  </strong>
                  , whereas RE-PLAN-V's counterexample-guided pruning achieves{" "}
                  <strong className="text-emerald-400">
                    {typeof oursRate === "number" ? `${(oursRate * 100).toFixed(1)}%` : "N/A"}
                  </strong>
                  {advDiff !== null && (
                    <>
                      {" "}with a measured recovery advantage of{" "}
                      <strong className="text-cyan-300">
                        {advDiff > 0 ? "+" : ""}{advDiff.toFixed(1)}%
                      </strong>
                    </>
                  )}
                  .
                </p>
              );
            })()}
          </div>

          {/* 5-Class Fault Attribution Confusion Matrix */}
          <div className="mt-6 border-t border-slate-800 pt-6">
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-mono text-xs font-semibold uppercase tracking-wider text-slate-300">
                5-Class Fault Attribution Confusion Matrix (Controlled Fault Injection)
              </h4>
              {attributionData && (
                <span className="font-mono text-[11px] text-slate-400">
                  Macro Accuracy: <strong className="text-emerald-400">{(attributionData.accuracy * 100).toFixed(1)}%</strong> | Macro F1: <strong className="text-emerald-400">{attributionData.macro_f1.toFixed(2)}</strong> ({attributionData.total_evaluated} Ground Truth Trials)
                </span>
              )}
            </div>

            {attributionData && attributionData.confusion_matrix ? (
              <div className="grid grid-cols-6 gap-1 text-center font-mono text-[10px]">
                <div className="p-2 text-slate-500 font-bold">GT \ Pred</div>
                {MATRIX_CLASSES.map((col) => (
                  <div key={col.key} className="p-2 bg-slate-800/40 text-slate-300 font-bold">
                    {col.label}
                  </div>
                ))}

                {MATRIX_CLASSES.map((row) => (
                  <React.Fragment key={row.key}>
                    <div className="p-2 bg-slate-800/40 text-left font-bold text-slate-300">
                      {row.label}
                    </div>
                    {MATRIX_CLASSES.map((col) => {
                      const count = attributionData.confusion_matrix?.[row.key]?.[col.key] ?? 0;
                      const isDiagonal = row.key === col.key;
                      const isCorrect = isDiagonal && count > 0;
                      const isError = !isDiagonal && count > 0;
                      return (
                        <div
                          key={col.key}
                          className={`p-2 rounded font-bold ${
                            isCorrect
                              ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                              : isError
                              ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                              : "text-slate-600"
                          }`}
                        >
                          {count}
                        </div>
                      );
                    })}
                  </React.Fragment>
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-800 p-4 text-center text-xs text-slate-500">
                Loading attribution experimental results...
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
