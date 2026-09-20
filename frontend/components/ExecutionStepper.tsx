"use client";

import React from "react";
import { CheckCircle2, XCircle, Clock, ShieldCheck, Sparkles, AlertTriangle } from "lucide-react";
import { PipelineAccumulatedState } from "../hooks/usePipelineWebSocket";
import { CounterexampleCard } from "./CounterexampleCard";
import { RepairCard } from "./RepairCard";

interface ExecutionStepperProps {
  state: PipelineAccumulatedState;
  isStreaming: boolean;
}

export function ExecutionStepper({ state, isStreaming }: ExecutionStepperProps) {
  const hasStarted = Boolean(state.prompt);

  if (!hasStarted) {
    return (
      <div className="flex h-full min-h-[300px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-800 bg-slate-900/30 p-8 text-center">
        <Sparkles className="mb-3 h-8 w-8 text-slate-600" />
        <h3 className="font-mono text-sm font-semibold text-slate-400">Pipeline Idle</h3>
        <p className="mt-1 max-w-sm text-xs text-slate-500">
          Select a capability preset or enter an instruction, then click{" "}
          <strong className="text-cyan-400">Run Neurosymbolic Pipeline</strong> to watch real-time execution.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-xl backdrop-blur-sm">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-cyan-400" />
          <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-slate-200">
            Live Execution Trace
          </h3>
        </div>
        <span className="font-mono text-xs font-bold text-emerald-400">
          {state.executionTimeMs > 0 ? `${state.executionTimeMs.toFixed(1)} ms` : "Streaming..."}
        </span>
      </div>

      <div className="flex flex-col gap-4">
        {/* Step 1: Neural Interpretation */}
        <div className="flex items-start gap-3 rounded-xl border border-slate-800 bg-slate-950/60 p-3.5">
          <div className="mt-0.5">
            {state.isSchemaValid === true ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-400" />
            ) : state.isSchemaValid === false ? (
              <XCircle className="h-5 w-5 text-rose-400" />
            ) : (
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-600 border-t-cyan-400" />
            )}
          </div>
          <div className="flex-1 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-200">1. Neural Interpretation & Validation</span>
              <span className="font-mono text-[10px] text-slate-400">Untrusted Proposer</span>
            </div>
            {Object.keys(state.entities).length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {Object.entries(state.entities).map(([k, v]) => (
                  <span
                    key={k}
                    className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[11px] text-cyan-300"
                  >
                    {k}: {v}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Step 2: Candidate Plan Generation */}
        <div className="flex items-start gap-3 rounded-xl border border-slate-800 bg-slate-950/60 p-3.5">
          <div className="mt-0.5">
            {state.candidatePlan.length > 0 ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-400" />
            ) : (
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-600 border-t-cyan-400" />
            )}
          </div>
          <div className="flex-1 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-200">2. Candidate Plan Generation (A*)</span>
              <span className="font-mono text-[10px] text-slate-400">
                {state.candidatePlan.length} Actions (Cost: {state.candidateCost})
              </span>
            </div>
            {state.candidatePlan.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {state.candidatePlan.map((act, i) => (
                  <span
                    key={i}
                    className="rounded bg-slate-800/80 px-2 py-0.5 font-mono text-[11px] text-slate-300"
                  >
                    {i + 1}. {act.name}({act.arguments.join(", ")})
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Step 3: Formal Verification Result */}
        <div className="flex items-start gap-3 rounded-xl border border-slate-800 bg-slate-950/60 p-3.5">
          <div className="mt-0.5">
            {state.initialVerificationPassed === true ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-400" />
            ) : state.initialVerificationPassed === false ? (
              <XCircle className="h-5 w-5 text-rose-400" />
            ) : (
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-600 border-t-cyan-400" />
            )}
          </div>
          <div className="flex-1 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-200">3. Formal State Transition Verification</span>
              <span
                className={`font-mono text-[10px] font-bold ${
                  state.initialVerificationPassed
                    ? "text-emerald-400"
                    : state.initialVerificationPassed === false
                    ? "text-rose-400"
                    : "text-slate-400"
                }`}
              >
                {state.initialVerificationPassed
                  ? "VERIFIED SATISFIED"
                  : state.initialVerificationPassed === false
                  ? "VIOLATION DETECTED"
                  : "Checking..."}
              </span>
            </div>
            {state.verificationFailureMessage && (
              <p className="mt-1 font-mono text-[11px] text-rose-300">
                {state.verificationFailureMessage}
              </p>
            )}
          </div>
        </div>

        {/* Step 4 & 5: Counterexample Witness & Fault Attribution (if failure occurred) */}
        {state.counterexample && (
          <CounterexampleCard witness={state.counterexample} attribution={state.attribution} />
        )}

        {/* Step 6: Symbolic Repair Card (if repair succeeded) */}
        {state.repairsApplied && state.repairsApplied.length > 0 && (
          <RepairCard repairs={state.repairsApplied} finalPlan={state.finalPlan} />
        )}

        {/* Step 7: Final Verified Plan */}
        {state.isFinalVerified && (
          <div className="flex items-center justify-between rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-4">
            <div className="flex items-center gap-3">
              <ShieldCheck className="h-6 w-6 text-emerald-400" />
              <div>
                <h4 className="font-mono text-xs font-bold uppercase tracking-wider text-emerald-300">
                  Ready for Robotic Dispatch
                </h4>
                <p className="text-[11px] text-slate-400">
                  100% mathematically verified against preconditions, mutexes, and negative invariants.
                </p>
              </div>
            </div>
            <span className="rounded-full bg-emerald-500/20 px-3 py-1 font-mono text-xs font-bold text-emerald-300">
              SAFETY GUARANTEED
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
