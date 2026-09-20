"use client";

import React from "react";
import { AlertOctagon, Flame } from "lucide-react";
import { CounterexampleWitness, FaultAttribution } from "../types/pipeline";

interface CounterexampleCardProps {
  witness: CounterexampleWitness;
  attribution?: FaultAttribution;
}

export function CounterexampleCard({ witness, attribution }: CounterexampleCardProps) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-rose-500/30 bg-rose-950/20 p-4 shadow-xl">
      <div className="flex items-center justify-between border-b border-rose-500/20 pb-2">
        <div className="flex items-center gap-2 text-rose-400">
          <AlertOctagon className="h-4 w-4" />
          <h4 className="font-mono text-xs font-bold uppercase tracking-wider">
            Minimal Counterexample Witness
          </h4>
        </div>
        <span className="rounded bg-rose-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-rose-300">
          STEP {witness.step_index} FAILED
        </span>
      </div>

      <div className="flex flex-col gap-1.5 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-slate-400">Failed Action:</span>
          <code className="rounded bg-rose-900/40 px-2 py-0.5 font-mono text-rose-200">
            {witness.failed_action.name}({witness.failed_action.arguments.join(", ")})
          </code>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-400">Violated Precondition:</span>
          <code className="rounded bg-rose-900/60 px-2 py-0.5 font-mono font-semibold text-rose-300">
            {witness.violated_condition}
          </code>
        </div>
        <p className="mt-1 text-[11px] leading-relaxed text-slate-300">
          {witness.explanation}
        </p>
      </div>

      {attribution && (
        <div className="mt-2 rounded-xl border border-rose-500/20 bg-slate-950/60 p-3">
          <div className="mb-1 flex items-center justify-between">
            <span className="font-mono text-[10px] uppercase text-slate-400">
              Fault Attribution Engine (5-Class)
            </span>
            <span className="font-mono text-xs font-bold text-rose-400">
              {attribution.fault_class}
            </span>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-slate-300">
            <span>Culprit Stage:</span>
            <span className="font-mono text-cyan-300">{attribution.affected_stage}</span>
            <span>• Confidence:</span>
            <span className="font-mono font-bold text-emerald-400">
              {(attribution.confidence * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
