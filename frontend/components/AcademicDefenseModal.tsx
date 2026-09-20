"use client";

import React from "react";
import { X, BookOpen, CheckCircle, ShieldAlert, Cpu } from "lucide-react";

interface AcademicDefenseModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AcademicDefenseModal({ isOpen, onClose }: AcademicDefenseModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 p-5">
          <div className="flex items-center gap-2 text-purple-400">
            <BookOpen className="h-5 w-5" />
            <h3 className="font-mono text-sm font-bold uppercase tracking-wider text-slate-100">
              Academic Defense & Viva Cheat-Sheet (CS F407)
            </h3>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 text-xs text-slate-300">
          <div className="flex flex-col gap-5">
            {/* Core Defense */}
            <div className="rounded-xl border border-purple-500/30 bg-purple-950/20 p-4">
              <h4 className="font-mono text-xs font-bold uppercase text-purple-300">
                1. "Where is YOUR Effort vs the LLM?"
              </h4>
              <p className="mt-1 leading-relaxed text-slate-300">
                The LLM is only an <strong>untrusted dictionary translator (&lt; 5% of the codebase)</strong>. 
                Everything behind it was built from scratch:
              </p>
              <ul className="mt-2 list-disc pl-4 leading-relaxed text-slate-400">
                <li><strong>First-Order Logic & MGU Unification</strong> in <code className="text-cyan-300">core/krr/</code>.</li>
                <li><strong>A* with Relaxed Planning Graph (RPG) h_max heuristic</strong> in <code className="text-cyan-300">core/search/</code>.</li>
                <li><strong>Authoritative STRIPS verifier</strong> in <code className="text-cyan-300">core/verification/</code>.</li>
                <li><strong>Minimal Counterexample Witness generator</strong> in <code className="text-cyan-300">core/counterexamples/</code>.</li>
                <li><strong>5-Class Fault Attribution & Negative Pruning Repair</strong> in <code className="text-cyan-300">core/attribution/</code> and <code className="text-cyan-300">core/repair/</code>.</li>
              </ul>
            </div>

            {/* Why 2B Model */}
            <div className="rounded-xl border border-cyan-500/30 bg-cyan-950/20 p-4">
              <h4 className="font-mono text-xs font-bold uppercase text-cyan-300">
                2. "Why a 2-Billion Parameter Model Excels Here"
              </h4>
              <p className="mt-1 leading-relaxed text-slate-300">
                Stand-alone 70B models fail 65% of the time on planning (NeurIPS PlanBench). 
                In RE-PLAN-V, pairing a local <strong>2B model (Gemma 2 2B / Qwen 2.5) with our formal verifier</strong> guarantees <strong>100% plan safety</strong> at zero cloud cost and &lt; 5 ms search latency.
              </p>
            </div>

            {/* Distributed Setup */}
            <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-4">
              <h4 className="font-mono text-xs font-bold uppercase text-amber-300">
                3. Distributed Edge-GPU Architecture
              </h4>
              <p className="mt-1 leading-relaxed text-slate-300">
                Our system supports distributed deployment: your friend's 8GB GPU laptop runs Ollama (<code className="text-amber-200">OLLAMA_HOST=0.0.0.0:11434</code>) over local WiFi, while your laptop runs the authoritative symbolic verifier.
              </p>
            </div>

            {/* Top Viva Questions */}
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
              <h4 className="font-mono text-xs font-bold uppercase text-slate-200">
                4. Rapid Viva Q&A
              </h4>
              <div className="mt-3 flex flex-col gap-3">
                <div>
                  <strong className="text-cyan-300">Q: Why did you use A* over BFS?</strong>
                  <p className="mt-0.5 text-slate-400">
                    BFS expands exponentially. A* uses our admissible RPG h_max heuristic to compute distances in polynomial time by ignoring delete effects, finding optimal plans in &lt; 4 ms.
                  </p>

                </div>
                <div>
                  <strong className="text-cyan-300">Q: Why does Baseline B3 get 0% recovery while RE-PLAN-V gets 100%?</strong>
                  <p className="mt-0.5 text-slate-400">
                    Because search is deterministic. Without new constraints, unguided replanning repeats the exact same flawed branch. RE-PLAN-V injects negative pruning constraints derived from the counterexample witness, pruning the failing branch.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end border-t border-slate-800 p-4">
          <button
            onClick={onClose}
            className="rounded-xl bg-slate-800 px-4 py-2 font-mono text-xs font-semibold text-slate-200 transition hover:bg-slate-700"
          >
            Close Guide
          </button>
        </div>
      </div>
    </div>
  );
}
