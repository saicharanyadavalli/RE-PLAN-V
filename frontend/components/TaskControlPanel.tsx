"use client";

import React, { useState, useEffect } from "react";
import { Play, Sparkles, AlertTriangle, Layers, Wand2, Compass, Network } from "lucide-react";
import { PipelineRunRequest } from "../types/pipeline";

interface TaskControlPanelProps {
  onRun: (req: PipelineRunRequest) => void;
  isStreaming: boolean;
  onPromptChange?: (prompt: string) => void;
  externalPrompt?: string;
  externalDomainId?: string;
}

const PRESETS = [
  {
    id: 1,
    domain: "blocks_world",
    domainLabel: "Blocks",
    title: "Safe Relocation",
    prompt: "Move the red box next to the blue box. Do not move the glass.",
    forceFault: false,
  },
  {
    id: 2,
    domain: "blocks_world",
    domainLabel: "Blocks",
    title: "Stack 3 Blocks",
    prompt: "Stack the red box on the green box, then put the blue box on the red box.",
    forceFault: false,
  },
  {
    id: 3,
    domain: "blocks_world",
    domainLabel: "Blocks",
    title: "Fragile Fault Injection",
    prompt: "Stack the blue box on the green box. Do not touch the fragile glass.",
    forceFault: true,
  },
  {
    id: 4,
    domain: "grid_world",
    domainLabel: "Grid",
    title: "Grid 2D Key Transfer",
    prompt: "Move robot from loc_0_0 to loc_2_2 and pick key_1.",
    forceFault: false,
  },
  {
    id: 5,
    domain: "household",
    domainLabel: "House",
    title: "Household Mug Retrieval",
    prompt: "Navigate to kitchen, open cabinet, and pick mug.",
    forceFault: false,
  },
  {
    id: 6,
    domain: "warehouse",
    domainLabel: "Logistics",
    title: "AGV Inventory Transit",
    prompt: "Transit agv_1 to shelf_b and retrieve sku_02.",
    forceFault: false,
  },
  {
    id: 7,
    domain: "scheduling",
    domainLabel: "Schedule",
    title: "Dual Machine Dispatch",
    prompt: "Schedule job_a on m1 and job_b on m2.",
    forceFault: false,
  },
  {
    id: 8,
    domain: "software_workflow",
    domainLabel: "CI/CD",
    title: "Gated Release Pipeline",
    prompt: "Run unit tests, run security scan, build artifact, and deploy to staging.",
    forceFault: false,
  },
];

export function TaskControlPanel({
  onRun,
  isStreaming,
  onPromptChange,
  externalPrompt,
  externalDomainId,
}: TaskControlPanelProps) {
  const [prompt, setPrompt] = useState(PRESETS[0].prompt);
  const [domainId, setDomainId] = useState<string>("auto");
  const [algorithm, setAlgorithm] = useState("A*");
  const [forceFault, setForceFault] = useState(false);
  const [enumerateGraph, setEnumerateGraph] = useState(true);
  const [maxNodes, setMaxNodes] = useState(150);
  const [providerType, setProviderType] = useState("mock");
  const [llmModel, setLlmModel] = useState("gemma2:2b");

  // Synchronize external prompt if changed from DomainStudio
  useEffect(() => {
    if (externalPrompt) {
      setPrompt(externalPrompt);
      onPromptChange?.(externalPrompt);
    }
  }, [externalPrompt, onPromptChange]);

  useEffect(() => {
    if (externalDomainId) {
      setDomainId(externalDomainId);
    }
  }, [externalDomainId]);

  const handleSelectPreset = (p: (typeof PRESETS)[0]) => {
    setPrompt(p.prompt);
    setDomainId(p.domain);
    setForceFault(p.forceFault);
    onPromptChange?.(p.prompt);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onRun({
      prompt,
      algorithm,
      domain_id: domainId,
      force_fault: forceFault,
      provider_type: providerType,
      llm_model: llmModel,
      enumerate_graph: enumerateGraph,
      max_nodes: maxNodes,
      max_edges: maxNodes * 3,
      graph_timeout: 4.0,
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
          {domainId === "auto" ? "Auto-Routed Domain" : domainId}
        </span>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {/* Natural Language Prompt */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-medium text-slate-300">
              Natural Language Instruction
            </label>
            <span className="text-[10px] text-slate-500">Text-First NLP Input</span>
          </div>
          <textarea
            value={prompt}
            onChange={(e) => {
              setPrompt(e.target.value);
              onPromptChange?.(e.target.value);
            }}
            rows={2}
            className="w-full resize-none rounded-xl border border-slate-800 bg-slate-950 p-3 font-mono text-xs text-slate-200 placeholder-slate-600 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
            placeholder="Type your domain instruction (e.g. Move red box, Navigate kitchen, Transit AGV)..."
          />

          {/* Preset Chips */}
          <div className="mt-2.5">
            <span className="mb-1.5 block text-[11px] font-medium text-slate-400">
              Multi-Domain Preset Library:
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
                  <span className="text-[9px] uppercase font-bold text-slate-500 mr-1">
                    [{p.domainLabel}]
                  </span>
                  {p.title}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Configuration Row 1: Target Domain & Planner */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {/* Domain Selector */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-300">
              Target Planning Domain
            </label>
            <select
              value={domainId}
              onChange={(e) => setDomainId(e.target.value)}
              className="w-full rounded-xl border border-slate-800 bg-slate-950 p-2.5 text-xs text-slate-200 focus:border-cyan-500 focus:outline-none"
            >
              <option value="auto">&rarr; Auto-Route via NLP Router</option>
              <option value="blocks_world">Blocks World (4 Classical Operators)</option>
              <option value="grid_world">Grid World (2D Spatial Navigation)</option>
              <option value="household">Household Robotics (Multi-Room / Storage)</option>
              <option value="warehouse">Warehouse Logistics (AGVs / Storage Racks)</option>
              <option value="scheduling">Discrete Job Scheduling (Machine Allocation)</option>
              <option value="software_workflow">Software Workflow (Gated CI/CD Release)</option>
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
              <option value="A*">A* Search (Optimal Uniform-Cost / Admissible)</option>
              <option value="BFS">Breadth-First Search (BFS)</option>
              <option value="BEST_FIRST">Greedy Best-First Search</option>
            </select>
          </div>
        </div>

        {/* Configuration Row 2: Neural Formalizer & Graph Exploration */}
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

          {/* State-Space Graph Enumeration Budget */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-slate-300">
                Graph Explorer Budget
              </label>
              <span className="font-mono text-xs text-cyan-400">{maxNodes} states</span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min="30"
                max="400"
                step="10"
                value={maxNodes}
                onChange={(e) => setMaxNodes(Number(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-500"
              />
            </div>
          </div>
        </div>

        {/* Fault Injection & State Graph Toggles */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-2.5 text-xs text-cyan-300">
            <input
              type="checkbox"
              id="graph-toggle"
              checked={enumerateGraph}
              onChange={(e) => setEnumerateGraph(e.target.checked)}
              className="h-4 w-4 rounded border-cyan-500/50 bg-slate-950 text-cyan-500 focus:ring-cyan-400"
            />
            <label htmlFor="graph-toggle" className="cursor-pointer font-medium">
              Stream Complete Reachable State-Space Graph (Model B) to Explorer
            </label>
          </div>

          <div className="flex items-center gap-2 rounded-xl border border-amber-500/20 bg-amber-500/5 p-2.5 text-xs text-amber-300">
            <input
              type="checkbox"
              id="fault-toggle"
              checked={forceFault}
              onChange={(e) => setForceFault(e.target.checked)}
              className="h-4 w-4 rounded border-amber-500/50 bg-slate-950 text-amber-500 focus:ring-amber-400"
            />
            <label htmlFor="fault-toggle" className="cursor-pointer font-medium">
              Simulate Initial Planning Fault (Extracts Counterexample Witness & Repair)
            </label>
          </div>
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
              Streaming Neurosymbolic Pipeline...
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
