"use client";

import React, { useState } from "react";
import { Play, Sparkles, AlertTriangle, Layers, Wand2 } from "lucide-react";
import { PipelineRunRequest } from "../types/pipeline";

interface TaskControlPanelProps {
  onRun: (req: PipelineRunRequest) => void;
  isStreaming: boolean;
  onPromptChange?: (prompt: string) => void;
}

const PRESETS = [
  {
    id: 1,
    title: "1. Safe Relocation (DoD)",
    prompt: "Move the red box next to the blue box. Do not move the glass.",
    forceFault: false,
    tag: "Safety Constraint",
  },
  {
    id: 2,
    title: "2. 3-Block Tower",
    prompt: "Stack the red box on the green box, then put the blue box on the red box.",
    forceFault: false,
    tag: "Multi-tier",
  },
  {
    id: 3,
    title: "3. Tower Inversion",
    prompt: "The red box is on the green box. Unstack the red box, place it on the table, and stack the green box on the red box.",
    forceFault: false,
    tag: "Deconstruction",
  },
  {
    id: 4,
    title: "4. 4-Block Assembly",
    prompt: "Build a 4-block tower: yellow box on green box, green box on blue box, and blue box on red box.",
    forceFault: false,
    tag: "Deep Search",
  },
  {
    id: 5,
    title: "5. Clear Obstacle",
    prompt: "Clear the obstacle blocking the target position before placing the blue box on the green box.",
    forceFault: false,
    tag: "Prerequisite",
  },
  {
    id: 6,
    title: "6. Fragile Object Violation",
    prompt: "Stack the blue box on the green box. Do not touch the fragile glass.",
    forceFault: true,
    tag: "Fault Injection",
  },
  {
    id: 7,
    title: "7. Single-Arm Capacity",
    prompt: "Pick up the red box while keeping workspace clear and respecting single-arm capacity.",
    forceFault: false,
    tag: "Capacity Mutex",
  },
  {
    id: 8,
    title: "8. Deadlock Conflict",
    prompt: "Put the red box on the green box and the green box on the red box simultaneously.",
    forceFault: false,
    tag: "Deadlock Detection",
  },
];

export function TaskControlPanel({ onRun, isStreaming, onPromptChange }: TaskControlPanelProps) {
  const [prompt, setPrompt] = useState(PRESETS[0].prompt);
  const [algorithm, setAlgorithm] = useState("A*");
  const [forceFault, setForceFault] = useState(false);
  const [providerType, setProviderType] = useState("mock");
  const [llmModel, setLlmModel] = useState("gemma2:2b");

  const handleSelectPreset = (p: (typeof PRESETS)[0]) => {
    setPrompt(p.prompt);
    setForceFault(p.forceFault);
    onPromptChange?.(p.prompt);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onRun({
      prompt,
      algorithm,
      force_fault: forceFault,
      provider_type: providerType,
      llm_model: llmModel,
    });
  };

  return (
    <div className="flex flex-col rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-xl backdrop-blur-sm">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Wand2 className="h-4 w-4 text-cyan-400" />
          <h2 className="font-mono text-sm font-semibold uppercase tracking-wider text-slate-200">
            Task Specification & Control
          </h2>
        </div>
        <span className="rounded-full border border-slate-700 bg-slate-800/80 px-2.5 py-0.5 font-mono text-[10px] text-cyan-300">
          {providerType === "mock"
            ? "Offline Rule-Based Mock"
            : providerType === "lmstudio"
            ? "LM Studio (127.0.0.1:1234)"
            : providerType === "ollama"
            ? "Local 2B Model (Ollama)"
            : providerType === "gemini"
            ? "Google Gemini 1.5 Flash"
            : "Cloud API"}
        </span>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {/* Natural Language Prompt */}
        <div>
          <label className="mb-1.5 block text-xs font-medium text-slate-300">
            Natural Language Instruction
          </label>
          <textarea
            value={prompt}
            onChange={(e) => {
              setPrompt(e.target.value);
              onPromptChange?.(e.target.value);
            }}
            rows={2}
            className="w-full resize-none rounded-xl border border-slate-800 bg-slate-950 p-3 font-mono text-xs text-slate-200 placeholder-slate-600 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
            placeholder="Type your robotic instruction..."
          />

          {/* Preset Chips */}
          <div className="mt-2.5">
            <span className="mb-1.5 block text-[11px] font-medium text-slate-400">
              Capability Preset Library:
            </span>
            <div className="flex flex-wrap gap-1.5">
              {PRESETS.map((p) => (
                <button
                  type="button"
                  key={p.id}
                  onClick={() => handleSelectPreset(p)}
                  className={`rounded-lg border px-2.5 py-1 text-[11px] font-medium transition ${
                    prompt === p.prompt
                      ? "border-cyan-500/50 bg-cyan-500/15 text-cyan-300 shadow-sm"
                      : "border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700 hover:text-slate-200"
                  }`}
                >
                  {p.title}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Configuration Row */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {/* Neural Engine */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-300">
              Neural Formalizer Engine
            </label>
            <select
              value={providerType}
              onChange={(e) => setProviderType(e.target.value)}
              className="w-full rounded-xl border border-slate-800 bg-slate-950 p-2.5 text-xs text-slate-200 focus:border-cyan-500 focus:outline-none"
            >
              <option value="mock">Deterministic Zero-API (Offline)</option>
              <option value="lmstudio">LM Studio Local Model (http://127.0.0.1:1234)</option>
              <option value="ollama">Local 2B Model (Ollama: gemma2:2b / qwen2.5)</option>
              <option value="gemini">Google Gemini 1.5 Flash (via API Key)</option>
              <option value="openai">OpenAI Endpoint (gpt-4o-mini)</option>
            </select>
          </div>

          {/* Planning Algorithm */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-300">
              Authoritative Planner
            </label>
            <select
              value={algorithm}
              onChange={(e) => setAlgorithm(e.target.value)}
              className="w-full rounded-xl border border-slate-800 bg-slate-950 p-2.5 text-xs text-slate-200 focus:border-cyan-500 focus:outline-none"
            >
              <option value="A*">A* Search (Optimal RPG h_max)</option>
              <option value="BFS">Breadth-First Search (BFS)</option>
              <option value="BEST_FIRST">Greedy Best-First Search</option>
            </select>
          </div>
        </div>

        {/* Fault Injection Toggle */}
        <div className="flex items-center gap-2 rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-300">
          <input
            type="checkbox"
            id="fault-toggle"
            checked={forceFault}
            onChange={(e) => setForceFault(e.target.checked)}
            className="h-4 w-4 rounded border-amber-500/50 bg-slate-950 text-amber-500 focus:ring-amber-400"
          />
          <label htmlFor="fault-toggle" className="cursor-pointer font-medium">
            Simulate Initial Planning Fault (Showcases Counterexample Witness & Repair Loop)
          </label>
        </div>

        {/* Action Button */}
        <button
          type="submit"
          disabled={isStreaming}
          className={`flex items-center justify-center gap-2 rounded-xl py-3 text-xs font-bold uppercase tracking-wider transition-all shadow-lg ${
            isStreaming
              ? "cursor-not-allowed bg-slate-800 text-slate-500"
              : "bg-gradient-to-r from-cyan-500 to-blue-600 text-white hover:from-cyan-400 hover:to-blue-500 shadow-cyan-500/25"
          }`}
        >
          {isStreaming ? (
            <>
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-400 border-t-white" />
              Streaming Formal Pipeline...
            </>
          ) : (
            <>
              <Play className="h-4 w-4 fill-white" />
              Run Neurosymbolic Pipeline
            </>
          )}
        </button>
      </form>
    </div>
  );
}
