"use client";

import React from "react";
import { Wrench, CheckCircle2 } from "lucide-react";
import { RepairConstraint, GroundActionSchema } from "../types/pipeline";

interface RepairCardProps {
  repairs: RepairConstraint[];
  finalPlan: GroundActionSchema[];
}

export function RepairCard({ repairs, finalPlan }: RepairCardProps) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-cyan-500/30 bg-cyan-950/20 p-4 shadow-xl">
      <div className="flex items-center justify-between border-b border-cyan-500/20 pb-2">
        <div className="flex items-center gap-2 text-cyan-400">
          <Wrench className="h-4 w-4" />
          <h4 className="font-mono text-xs font-bold uppercase tracking-wider">
            Automated Symbolic Repair & Replanning
          </h4>
        </div>
        <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-300">
          REPAIR CONVERGED (100% SUCCESS)
        </span>
      </div>

      <div className="flex flex-col gap-2 text-xs">
        <span className="font-medium text-slate-300">Pruning Constraints Injected:</span>
        <div className="flex flex-col gap-1.5">
          {repairs.map((r, i) => (
            <div
              key={i}
              className="rounded-lg border border-cyan-500/20 bg-slate-950/60 p-2 font-mono text-[11px] text-cyan-200"
            >
              <span className="font-bold text-amber-400">[{r.repair_type || r.type || "CONSTRAINT"}]</span> {r.description}
            </div>
          ))}
        </div>

        <div className="mt-2 flex items-center gap-2 text-xs font-semibold text-emerald-400">
          <CheckCircle2 className="h-4 w-4" />
          <span>Synthesized Verified Alternate Trajectory:</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {finalPlan.map((act, i) => (
            <span
              key={i}
              className="flex items-center gap-1 rounded-lg border border-emerald-500/30 bg-emerald-950/30 px-2.5 py-1 font-mono text-xs font-medium text-emerald-300"
            >
              <span className="text-[10px] text-slate-500">{i + 1}.</span>
              {act.name}({(act.arguments || []).join(", ")})
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
