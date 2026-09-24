"use client";

import React from "react";
import { ShieldCheck, Cpu, Terminal, Sparkles, BookOpen } from "lucide-react";

interface NavbarProps {
  activeTab: "demo" | "benchmark" | "architecture";
  setActiveTab: (tab: "demo" | "benchmark" | "architecture") => void;
  isStreaming: boolean;
  onOpenDefenseModal: () => void;
}

export function Navbar({ activeTab, setActiveTab, isStreaming, onOpenDefenseModal }: NavbarProps) {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-500 shadow-lg shadow-cyan-500/20">
            <ShieldCheck className="h-6 w-6 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-lg font-bold tracking-tight text-white">RE-PLAN-V</span>
              <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 font-mono text-[10px] font-semibold text-cyan-400">
                NEUROSYMBOLIC CORE
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Formal Plan Verification, Fault Attribution & Counterexample-Guided Repair
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1 rounded-xl border border-slate-800 bg-slate-900/60 p-1">
          <button
            onClick={() => setActiveTab("demo")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
              activeTab === "demo"
                ? "bg-cyan-500/20 text-cyan-300 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Cpu className="h-3.5 w-3.5" />
            Mission Control
          </button>
          <button
            onClick={() => setActiveTab("benchmark")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
              activeTab === "benchmark"
                ? "bg-cyan-500/20 text-cyan-300 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Terminal className="h-3.5 w-3.5" />
            Research Benchmark
          </button>
          <button
            onClick={() => setActiveTab("architecture")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
              activeTab === "architecture"
                ? "bg-cyan-500/20 text-cyan-300 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Sparkles className="h-3.5 w-3.5" />
            10 Inviolable Rules
          </button>
        </nav>

        {/* Live Status & Defense Cheat-Sheet */}
        <div className="flex items-center gap-3">
          <div
            title="Authoritative STRIPS verifier, forward chaining, and CEGIS repair engine active"
            className="flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900 px-3 py-1 text-xs"
          >
            <span
              className={`h-2 w-2 rounded-full ${
                isStreaming ? "animate-ping bg-cyan-400" : "bg-emerald-400"
              }`}
            />
            <span className="font-mono text-[11px] text-slate-300">
              {isStreaming ? "PIPELINE STREAMING..." : "SYMBOLIC CORE: ACTIVE"}
            </span>
          </div>

          <button
            onClick={onOpenDefenseModal}
            className="flex items-center gap-1.5 rounded-lg border border-purple-500/30 bg-purple-500/10 px-3 py-1.5 text-xs font-semibold text-purple-300 transition hover:bg-purple-500/20"
          >
            <BookOpen className="h-3.5 w-3.5 text-purple-400" />
            Viva Defense Guide
          </button>
        </div>
      </div>
    </header>
  );
}
