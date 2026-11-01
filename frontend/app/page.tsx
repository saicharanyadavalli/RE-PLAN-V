"use client";

import React, { useState } from "react";
import { Navbar, NavTab } from "../components/Navbar";
import { TaskControlPanel } from "../components/TaskControlPanel";
import { TabletopCanvas } from "../components/TabletopCanvas";
import { SymbolicStateInspector } from "../components/SymbolicStateInspector";
import { ExecutionStepper } from "../components/ExecutionStepper";
import { StateSpaceExplorer } from "../components/StateSpaceExplorer";
import { DomainStudio } from "../components/DomainStudio";
import { BenchmarkTab } from "../components/BenchmarkTab";
import { ArchitectureRulesTab } from "../components/ArchitectureRulesTab";
import { AcademicDefenseModal } from "../components/AcademicDefenseModal";
import { usePipelineWebSocket } from "../hooks/usePipelineWebSocket";
import { HelpCircle, AlertOctagon, Network } from "lucide-react";

export default function Home() {
  const [activeTab, setActiveTab] = useState<NavTab>("demo");
  const [isDefenseModalOpen, setIsDefenseModalOpen] = useState(false);
  const [currentPrompt, setCurrentPrompt] = useState(
    "Move the red box next to the blue box. Do not move the glass."
  );
  const [selectedDomain, setSelectedDomain] = useState<string>("auto");

  const { isStreaming, events, state, error, runPipeline, reset } = usePipelineWebSocket();

  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-slate-100">
      {/* Top Navigation */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        isStreaming={isStreaming}
        onOpenDefenseModal={() => setIsDefenseModalOpen(true)}
      />

      {/* Main Container */}
      <main className="mx-auto flex-1 w-full max-w-7xl p-4 sm:p-6">
        {error && (
          <div className="mb-4 rounded-xl border border-rose-500/30 bg-rose-950/20 p-3 text-xs text-rose-300">
            <strong>System Error:</strong> {error}
          </div>
        )}

        {/* Clarification Required Notification Banner */}
        {state.clarificationQuestion && (
          <div className="mb-5 flex items-start gap-3 rounded-2xl border border-amber-500/40 bg-amber-950/30 p-4 shadow-xl backdrop-blur-md">
            <HelpCircle className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <span className="text-xs font-bold uppercase tracking-wider text-amber-400 block mb-1">
                Router: Clarification Required (No Silent Fact Invention)
              </span>
              <p className="text-xs text-amber-200/90 leading-relaxed">
                {state.clarificationQuestion}
              </p>
              <span className="mt-2 block text-[11px] text-amber-400/70 italic">
                RE-PLAN-V requires explicit target objects or locations rather than hallucinating assumptions.
              </span>
            </div>
          </div>
        )}

        {/* Task Unsupported Notification Banner */}
        {state.unsupportedReason && (
          <div className="mb-5 flex items-start gap-3 rounded-2xl border border-rose-500/40 bg-rose-950/30 p-4 shadow-xl backdrop-blur-md">
            <AlertOctagon className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <span className="text-xs font-bold uppercase tracking-wider text-rose-400 block mb-1">
                Router: Task Outside Supported Formal Domain Bounds
              </span>
              <p className="text-xs text-rose-200/90 leading-relaxed">
                {state.unsupportedReason}
              </p>
              <span className="mt-2 block text-[11px] text-rose-400/70 italic">
                Physical impossibility or unsupported domains (e.g. quantum dynamics, painting) are rejected honestly.
              </span>
            </div>
          </div>
        )}

        {/* Tab 1: Mission Control (Interactive Live Pipeline) */}
        {activeTab === "demo" && (
          <div className="flex flex-col gap-5">
            {/* Quick State-Space Graph Jump Bar (if graph nodes streamed) */}
            {state.graphNodes.length > 0 && (
              <div className="flex items-center justify-between rounded-xl border border-cyan-500/30 bg-cyan-950/20 px-4 py-2.5 text-xs">
                <div className="flex items-center gap-2">
                  <Network className="h-4 w-4 text-cyan-400" />
                  <span className="text-slate-300">
                    Model B State-Space Graph: <strong className="text-cyan-300 font-mono">{state.graphNodes.length}</strong> reachable states &amp; <strong className="text-cyan-300 font-mono">{state.graphEdges.length}</strong> transitions discovered.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab("graph")}
                  className="rounded-lg bg-cyan-600 px-3 py-1 text-xs font-semibold text-white shadow hover:bg-cyan-500 transition"
                >
                  Inspect in State Space Explorer &rarr;
                </button>
              </div>
            )}

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
              {/* Left Column: Input Panel & Simulation Canvas */}
              <div className="flex flex-col gap-6 lg:col-span-5">
                <TaskControlPanel
                  onRun={runPipeline}
                  isStreaming={isStreaming}
                  onPromptChange={setCurrentPrompt}
                  externalPrompt={currentPrompt}
                  externalDomainId={selectedDomain}
                />
                {selectedDomain === "blocks_world" || (selectedDomain === "auto" && (!state.domainId || state.domainId === "blocks_world")) ? (
                  <TabletopCanvas
                    entities={state.entities}
                    initialFacts={state.initialFacts}
                    finalPlan={state.finalPlan}
                    isStreaming={isStreaming}
                    prompt={currentPrompt}
                  />
                ) : (
                  <SymbolicStateInspector
                    domainId={selectedDomain !== "auto" ? selectedDomain : (state.domainId || "blocks_world")}
                    entities={state.entities}
                    initialFacts={state.initialFacts}
                    goalFacts={state.goalFacts}
                    negativeConstraints={state.negativeConstraints}
                    finalPlan={state.finalPlan}
                    isStreaming={isStreaming}
                  />
                )}
              </div>

              {/* Right Column: Live Execution Trace Stepper */}
              <div className="lg:col-span-7">
                <ExecutionStepper state={state} isStreaming={isStreaming} />
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: State Space Explorer (Model B Complete Reachable Graph) */}
        {activeTab === "graph" && (
          <StateSpaceExplorer
            streamedNodes={state.graphNodes}
            streamedEdges={state.graphEdges}
            streamedStats={state.graphStats}
            streamedStatus={state.graphStatus}
          />
        )}

        {/* Tab 3: Domain Studio (6 Canonical Planning Domains) */}
        {activeTab === "domains" && (
          <DomainStudio
            onSelectPrompt={(p, d) => {
              setCurrentPrompt(p);
              setSelectedDomain(d);
              setActiveTab("demo");
            }}
          />
        )}

        {/* Tab 4: Research Benchmark */}
        {activeTab === "benchmark" && <BenchmarkTab />}

        {/* Tab 5: Architecture & Rules */}
        {activeTab === "architecture" && <ArchitectureRulesTab />}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/60 py-4 text-center text-xs text-slate-500">
        RE-PLAN-V Research Platform &bull; CS F407 Artificial Intelligence &bull; Neurosymbolic Verification Engine
      </footer>

      {/* Viva Defense Cheat-Sheet Modal */}
      <AcademicDefenseModal
        isOpen={isDefenseModalOpen}
        onClose={() => setIsDefenseModalOpen(false)}
      />
    </div>
  );
}
