"use client";

import React, { useState } from "react";
import { Database, CheckCircle2, ShieldAlert, Target, Box, ArrowRight, Layers, Cpu } from "lucide-react";
import { FactSchema, GroundActionSchema } from "../types/pipeline";

interface SymbolicStateInspectorProps {
  domainId: string;
  entities: Record<string, string>;
  initialFacts: FactSchema[] | any[];
  goalFacts?: FactSchema[] | any[];
  negativeConstraints?: FactSchema[] | any[];
  finalPlan?: GroundActionSchema[];
  isStreaming?: boolean;
}

const DOMAIN_TITLES: Record<string, { title: string; subtitle: string; color: string }> = {
  grid_world: {
    title: "Grid World Navigation",
    subtitle: "Cell topology, waypoint connectivity & item transport state",
    color: "from-blue-500/20 to-cyan-500/10 border-blue-500/30",
  },
  warehouse: {
    title: "Warehouse AGV Logistics",
    subtitle: "Bay occupancy, SKU inventory allocation & carrier dispatch",
    color: "from-amber-500/20 to-orange-500/10 border-amber-500/30",
  },
  household: {
    title: "Household Service Robotics",
    subtitle: "Room spatial topology, surface containers & manipulator gripper",
    color: "from-emerald-500/20 to-teal-500/10 border-emerald-500/30",
  },
  household_robotics: {
    title: "Household Service Robotics",
    subtitle: "Room spatial topology, surface containers & manipulator gripper",
    color: "from-emerald-500/20 to-teal-500/10 border-emerald-500/30",
  },
  scheduling: {
    title: "Job Shop Scheduling & Resource Allocation",
    subtitle: "Machine slots, worker availability & precedence DAG constraints",
    color: "from-purple-500/20 to-pink-500/10 border-purple-500/30",
  },
  software_workflow: {
    title: "CI/CD Software Release Pipeline",
    subtitle: "Commit artifacts, test pass gates & target deployment health",
    color: "from-indigo-500/20 to-cyan-500/10 border-indigo-500/30",
  },
};

function formatFact(f: any): string {
  if (typeof f === "string") return f;
  if (!f) return "";
  const pred = f.predicate || "fact";
  const args = Array.isArray(f.arguments) ? f.arguments.join(", ") : "";
  return `${pred}(${args})`;
}

export function SymbolicStateInspector({
  domainId,
  entities = {},
  initialFacts = [],
  goalFacts = [],
  negativeConstraints = [],
  finalPlan = [],
  isStreaming = false,
}: SymbolicStateInspectorProps) {
  const meta = DOMAIN_TITLES[domainId] || {
    title: `Symbolic Domain State: ${domainId}`,
    subtitle: "Authoritative First-Order STRIPS state model and predicates",
    color: "from-cyan-500/20 to-blue-500/10 border-cyan-500/30",
  };

  const entityEntries = Object.entries(entities);

  return (
    <div className={`rounded-2xl border bg-slate-900/70 p-5 shadow-xl backdrop-blur-md ${meta.color} flex flex-col gap-4`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-2.5">
          <Database className="h-5 w-5 text-cyan-400" />
          <div>
            <h3 className="font-mono text-sm font-bold text-slate-100">{meta.title}</h3>
            <p className="text-[11px] text-slate-400">{meta.subtitle}</p>
          </div>
        </div>
        <span className="rounded-md border border-cyan-500/40 bg-cyan-950/60 px-2.5 py-0.5 font-mono text-[10px] font-semibold uppercase text-cyan-300">
          Domain: {domainId}
        </span>
      </div>

      {/* Entity Registry */}
      <div>
        <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-slate-300">
          <Box className="h-3.5 w-3.5 text-cyan-400" />
          <span>Active Problem Entities ({entityEntries.length})</span>
        </div>
        {entityEntries.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-800 p-3 text-center text-xs text-slate-500">
            No entities registered yet. Enter an instruction above to formalize.
          </div>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {entityEntries.map(([name, type]) => (
              <span
                key={name}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-950/80 px-2 py-1 font-mono text-[11px] text-slate-200"
              >
                <span className="font-semibold text-cyan-300">{name}</span>
                <span className="text-slate-500">:</span>
                <span className="text-[10px] text-slate-400">{type}</span>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Initial State Facts */}
      <div>
        <div className="mb-2 flex items-center justify-between text-xs font-semibold text-slate-300">
          <div className="flex items-center gap-1.5">
            <Layers className="h-3.5 w-3.5 text-blue-400" />
            <span>Initial State Conditions ({initialFacts.length})</span>
          </div>
          <span className="font-mono text-[10px] text-slate-500">S₀ Ground Truth</span>
        </div>
        {initialFacts.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-800 p-3 text-center text-xs text-slate-500">
            Initial facts will appear once instruction is formalized.
          </div>
        ) : (
          <div className="max-h-36 overflow-y-auto rounded-xl border border-slate-800/80 bg-slate-950/70 p-2.5 font-mono text-xs text-slate-300 flex flex-wrap gap-1.5">
            {initialFacts.map((f, idx) => (
              <span
                key={idx}
                className="rounded-md border border-slate-800 bg-slate-900 px-2 py-0.5 text-[11px] text-slate-300"
              >
                {formatFact(f)}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Goal Conditions & Safety Invariants */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* Goals */}
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/10 p-3">
          <div className="mb-1.5 flex items-center gap-1.5 font-mono text-[11px] font-bold uppercase text-emerald-400">
            <Target className="h-3.5 w-3.5" />
            <span>Goal Target ({goalFacts.length})</span>
          </div>
          {goalFacts.length === 0 ? (
            <p className="text-[11px] text-slate-500">No active goals</p>
          ) : (
            <div className="flex flex-col gap-1 font-mono text-[11px] text-emerald-200">
              {goalFacts.map((g, i) => (
                <div key={i} className="flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3 text-emerald-400 flex-shrink-0" />
                  <span>{formatFact(g)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Negative Constraints / Invariants */}
        <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 p-3">
          <div className="mb-1.5 flex items-center gap-1.5 font-mono text-[11px] font-bold uppercase text-amber-400">
            <ShieldAlert className="h-3.5 w-3.5" />
            <span>Safety Constraints ({negativeConstraints.length})</span>
          </div>
          {negativeConstraints.length === 0 ? (
            <p className="text-[11px] text-slate-500">No negative constraints</p>
          ) : (
            <div className="flex flex-col gap-1 font-mono text-[11px] text-amber-200">
              {negativeConstraints.map((c, i) => (
                <div key={i} className="flex items-center gap-1">
                  <span className="text-amber-400 font-bold">¬</span>
                  <span>{formatFact(c)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Verified Plan Execution Sequence (if plan exists) */}
      {finalPlan.length > 0 && (
        <div className="rounded-xl border border-cyan-500/30 bg-cyan-950/20 p-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-1.5 font-mono text-[11px] font-bold uppercase text-cyan-300">
              <Cpu className="h-3.5 w-3.5" />
              <span>Verified Plan ({finalPlan.length} Steps)</span>
            </div>
            <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-300">
              VERIFIED
            </span>
          </div>
          <div className="flex flex-col gap-1.5 font-mono text-xs">
            {finalPlan.map((act, stepIdx) => (
              <div
                key={stepIdx}
                className="flex items-center gap-2 rounded-lg border border-cyan-900/40 bg-slate-950/60 px-2.5 py-1 text-slate-200"
              >
                <span className="font-bold text-cyan-400">#{stepIdx + 1}</span>
                <span className="font-semibold text-slate-100">{act.name}</span>
                <span className="text-slate-400">({act.arguments.join(", ")})</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
