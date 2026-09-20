"use client";

import React from "react";
import { ShieldCheck, CheckCircle2 } from "lucide-react";

const RULES = [
  { id: 1, name: "Symbolic-First Semantics", desc: "Symbolic layer is the authoritative ground truth for state transitions, validation, and action models." },
  { id: 2, name: "Untrusted Neural Components", desc: "LLMs and VLMs only propose structured schemas; they never verify plans or decide validity." },
  { id: 3, name: "Single Transition Semantics", desc: "Search planners and the formal verifier share the exact same apply_transition implementation." },
  { id: 4, name: "Explicit Data Contracts", desc: "Every stage boundary is strictly validated via typed Pydantic models." },
  { id: 5, name: "Actionable Counterexamples", desc: "Every verification failure produces a minimal witness with exact step index, failed action, and violated condition." },
  { id: 6, name: "Evidence-Based Fault Attribution", desc: "Attribution classifies faults into 5 distinct categories with confidence scores and routing." },
  { id: 7, name: "Targeted Symbolic Repair", desc: "Repairs inject formal negative pruning constraints into the search space rather than blind unguided regeneration." },
  { id: 8, name: "Zero Fabricated Metrics", desc: "Every metric in benchmarks and reports is directly measured from deterministic execution." },
  { id: 9, name: "Zero-API Core Operation", desc: "System is fully functional and testable offline with zero required external network dependencies." },
  { id: 10, name: "Strict Bounded Loops", desc: "Maximum repair iterations and loop detection guards guarantee termination and eliminate cycles." },
];

export function ArchitectureRulesTab() {
  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-cyan-400" />
          <h2 className="font-mono text-sm font-bold uppercase tracking-wider text-slate-200">
            The 10 Inviolable Architectural Principles
          </h2>
        </div>
        <p className="mt-1 text-xs text-slate-400">
          Core engineering invariants guaranteeing safety, formal soundness, and 100% plan recovery.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {RULES.map((rule) => (
          <div
            key={rule.id}
            className="flex items-start gap-3 rounded-xl border border-slate-800 bg-slate-900/40 p-4 shadow-sm"
          >
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-cyan-500/10 font-mono text-xs font-bold text-cyan-400">
              {rule.id}
            </div>
            <div>
              <h4 className="font-sans text-xs font-semibold text-slate-200">{rule.name}</h4>
              <p className="mt-1 text-[11px] leading-relaxed text-slate-400">{rule.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
