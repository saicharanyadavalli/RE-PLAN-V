"use client";

import React, { useState } from "react";
import { Navbar } from "../components/Navbar";
import { TaskControlPanel } from "../components/TaskControlPanel";
import { TabletopCanvas } from "../components/TabletopCanvas";
import { ExecutionStepper } from "../components/ExecutionStepper";
import { BenchmarkTab } from "../components/BenchmarkTab";
import { ArchitectureRulesTab } from "../components/ArchitectureRulesTab";
import { AcademicDefenseModal } from "../components/AcademicDefenseModal";
import { usePipelineWebSocket } from "../hooks/usePipelineWebSocket";

export default function Home() {
  const [activeTab, setActiveTab] = useState<"demo" | "benchmark" | "architecture">("demo");
  const [isDefenseModalOpen, setIsDefenseModalOpen] = useState(false);

  const { isStreaming, events, state, error, runPipeline, reset } = usePipelineWebSocket();

  return (
    <div className="flex min-h-screen flex-col bg-slate-950">
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

        {/* Tab 1: Mission Control (Interactive Live Pipeline) */}
        {activeTab === "demo" && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            {/* Left Column: Input Panel & Simulation Canvas */}
            <div className="flex flex-col gap-6 lg:col-span-5">
              <TaskControlPanel onRun={runPipeline} isStreaming={isStreaming} />
              <TabletopCanvas
                entities={state.entities}
                initialFacts={state.initialFacts}
                finalPlan={state.finalPlan}
                isStreaming={isStreaming}
              />
            </div>

            {/* Right Column: Live Execution Trace Stepper */}
            <div className="lg:col-span-7">
              <ExecutionStepper state={state} isStreaming={isStreaming} />
            </div>
          </div>
        )}

        {/* Tab 2: Research Benchmark */}
        {activeTab === "benchmark" && <BenchmarkTab />}

        {/* Tab 3: Architecture & Rules */}
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
