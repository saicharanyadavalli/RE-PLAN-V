"use client";

import React, { useEffect, useRef, useState, useMemo } from "react";
import { GroundActionSchema } from "../types/pipeline";
import { Eye, Layers, RotateCcw } from "lucide-react";

interface TabletopCanvasProps {
  entities: Record<string, string>;
  initialFacts: any[];
  finalPlan: GroundActionSchema[];
  isStreaming: boolean;
  prompt?: string;
}

export function TabletopCanvas({
  entities,
  initialFacts,
  finalPlan,
  isStreaming,
  prompt = "",
}: TabletopCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [viewMode, setViewMode] = useState<"initial" | "planned">("planned");
  const [animFrame, setAnimFrame] = useState(0);

  // Animation loop when streaming
  useEffect(() => {
    if (!isStreaming) return;
    let frameId: number;
    const loop = () => {
      setAnimFrame((prev) => prev + 1);
      frameId = requestAnimationFrame(loop);
    };
    frameId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(frameId);
  }, [isStreaming]);

  // Derive active objects from state entities or dynamically parse from prompt
  const activeObjects = useMemo(() => {
    if (Object.keys(entities).length > 0) {
      return Object.keys(entities);
    }
    // Fallback: extract entities from current natural language prompt
    const p = prompt.toLowerCase();
    const detected: string[] = [];
    if (p.includes("red")) detected.push("red_box");
    if (p.includes("blue")) detected.push("blue_box");
    if (p.includes("green")) detected.push("green_box");
    if (p.includes("yellow")) detected.push("yellow_box");
    if (p.includes("obstacle")) detected.push("obstacle");
    if (p.includes("glass") || p.includes("prism") || p.includes("cup") || p.includes("bowl")) detected.push("glass");
    return detected.length > 0 ? detected : ["red_box", "blue_box", "green_box", "glass"];
  }, [entities, prompt]);

  // Compute spatial block locations (x, y levels)
  const blockPositions = useMemo(() => {
    // Initial column assignments
    const columns: Record<string, number> = {
      red_box: 65,
      blue_box: 145,
      green_box: 225,
      yellow_box: 305,
      obstacle: 305,
      glass: 380,
    };

    // Stacking relations: on(top, bottom)
    const onRelations: Record<string, string> = {}; // top -> bottom

    // 1. Initial facts
    if (initialFacts && initialFacts.length > 0) {
      initialFacts.forEach((f) => {
        const pred = f.predicate || (typeof f === "string" ? f : "");
        const args = f.arguments || [];
        if (pred === "on" && args.length === 2) {
          onRelations[args[0]] = args[1];
        }
      });
    } else {
      // Parse heuristic initial stack from prompt if mentioned (e.g. "red box is on green box")
      const p = prompt.toLowerCase();
      if (p.includes("red") && p.includes("on") && p.includes("green") && p.includes("is on")) {
        onRelations["red_box"] = "green_box";
      }
    }

    // 2. If viewing planned result, simulate finalPlan actions
    if (viewMode === "planned" && finalPlan && finalPlan.length > 0) {
      finalPlan.forEach((act) => {
        const name = (act.name || "").toLowerCase();
        const args = act.arguments || [];
        if (name === "stack" && args.length >= 2) {
          onRelations[args[0]] = args[1];
        } else if (name === "unstack" && args.length >= 2) {
          delete onRelations[args[0]];
        } else if (name === "put_down" || name === "place_on_table") {
          delete onRelations[args[0]];
        }
      });
    }

    // Calculate levels: 0 = on table, 1 = on top of level 0, etc.
    const levels: Record<string, number> = {};
    const effectiveX: Record<string, number> = {};

    const getLevel = (obj: string, visited = new Set<string>()): number => {
      if (visited.has(obj)) return 0; // prevent cycle
      visited.add(obj);
      const bottom = onRelations[obj];
      if (!bottom) return 0;
      return 1 + getLevel(bottom, visited);
    };

    const getRootX = (obj: string, visited = new Set<string>()): number => {
      if (visited.has(obj)) return columns[obj] || 100;
      visited.add(obj);
      const bottom = onRelations[obj];
      if (!bottom) return columns[obj] || 100;
      return getRootX(bottom, visited);
    };

    activeObjects.forEach((obj) => {
      levels[obj] = getLevel(obj);
      effectiveX[obj] = onRelations[obj] ? getRootX(obj) : (columns[obj] || 100);
    });

    return { levels, effectiveX, onRelations };
  }, [activeObjects, initialFacts, finalPlan, viewMode, prompt]);

  // Render Canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;

    // Clear background
    ctx.clearRect(0, 0, w, h);
    const bgGrad = ctx.createLinearGradient(0, 0, 0, h);
    bgGrad.addColorStop(0, "#090d16");
    bgGrad.addColorStop(1, "#020617");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);

    // High-tech CAD grid
    ctx.strokeStyle = "rgba(51, 65, 85, 0.2)";
    ctx.lineWidth = 1;
    for (let x = 20; x < w; x += 30) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 20; y < h; y += 30) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Tabletop surface
    ctx.fillStyle = "#1e293b";
    ctx.fillRect(25, h - 35, w - 50, 10);
    ctx.strokeStyle = "#0284c7";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(25, h - 35, w - 50, 10);

    // Table legs
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(45, h - 25, 14, 25);
    ctx.fillRect(w - 59, h - 25, 14, 25);

    // Tabletop label
    ctx.fillStyle = "#64748b";
    ctx.font = "bold 9px 'Courier New', monospace";
    ctx.fillText("TABLETOP SURFACE [Z = 0.0]", 35, h - 40);

    const colorMap: Record<string, { fill: string; border: string; label: string }> = {
      red_box: { fill: "#ef4444", border: "#fca5a5", label: "RED" },
      blue_box: { fill: "#3b82f6", border: "#93c5fd", label: "BLUE" },
      green_box: { fill: "#10b981", border: "#6ee7b7", label: "GREEN" },
      yellow_box: { fill: "#eab308", border: "#fde047", label: "YELLOW" },
      obstacle: { fill: "#f97316", border: "#fdba74", label: "OBSTACLE" },
      glass: { fill: "#a855f7", border: "#d8b4fe", label: "GLASS (FRAGILE)" },
    };

    const { levels, effectiveX } = blockPositions;

    // Sort objects so lower levels draw first
    const sortedObjects = [...activeObjects].sort((a, b) => (levels[a] || 0) - (levels[b] || 0));

    sortedObjects.forEach((name) => {
      const colX = effectiveX[name] ?? 100;
      const level = levels[name] ?? 0;
      const x = colX;
      // Each block is 38x38, stacked vertically with 40px offset
      const y = h - 75 - level * 42;

      const style = colorMap[name] || {
        fill: "#64748b",
        border: "#cbd5e1",
        label: name.replace("_box", "").toUpperCase(),
      };

      // Drop shadow
      ctx.fillStyle = "rgba(0, 0, 0, 0.45)";
      ctx.fillRect(x + 3, y + 3, 38, 38);

      // Block Body
      ctx.fillStyle = style.fill;
      ctx.fillRect(x, y, 38, 38);

      // Chamfered highlight
      ctx.strokeStyle = style.border;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(x, y, 38, 38);

      // Internal bevel line
      ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
      ctx.beginPath();
      ctx.moveTo(x + 2, y + 2);
      ctx.lineTo(x + 36, y + 2);
      ctx.stroke();

      // Block Name
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 8.5px -apple-system, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(style.label, x + 19, y + 23);
    });

    // Robotic Gripper Assembly
    let gripperTargetX = w / 2;
    if (activeObjects.length > 0) {
      const activeObj = activeObjects[0];
      gripperTargetX = (effectiveX[activeObj] ?? (w / 2)) + 19;
    }

    const sway = isStreaming ? Math.sin(animFrame * 0.1) * 20 : 0;
    const gripperX = (isStreaming ? gripperTargetX + sway : w / 2);
    const gripperY = isStreaming ? 48 + Math.sin(animFrame * 0.15) * 8 : 42;

    // Gantry Rail
    ctx.strokeStyle = "#334155";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(25, 18);
    ctx.lineTo(w - 25, 18);
    ctx.stroke();

    // Trolley carriage
    ctx.fillStyle = "#475569";
    ctx.fillRect(gripperX - 14, 12, 28, 12);
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 1;
    ctx.strokeRect(gripperX - 14, 12, 28, 12);

    // Telescopic Shaft
    ctx.strokeStyle = "#f59e0b";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(gripperX, 24);
    ctx.lineTo(gripperX, gripperY);
    // Left Finger
    ctx.lineTo(gripperX - 14, gripperY + 14);
    // Right Finger
    ctx.moveTo(gripperX, gripperY);
    ctx.lineTo(gripperX + 14, gripperY + 14);
    ctx.stroke();

    // Gripper status badge
    ctx.fillStyle = isStreaming ? "#38bdf8" : "#f59e0b";
    ctx.font = "bold 9px 'Courier New', monospace";
    ctx.textAlign = "center";
    ctx.fillText(isStreaming ? "ACTUATING..." : "GRIPPER IDLE", gripperX, 10);
  }, [activeObjects, blockPositions, isStreaming, animFrame]);

  return (
    <div className="flex flex-col rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-xl backdrop-blur-sm">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-cyan-400" />
          <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-slate-300">
            Tabletop World State Simulation
          </h3>
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center gap-1 rounded-lg border border-slate-800 bg-slate-950/80 p-0.5 text-[11px]">
          <button
            type="button"
            onClick={() => setViewMode("initial")}
            className={`flex items-center gap-1 rounded px-2 py-0.5 transition ${
              viewMode === "initial"
                ? "bg-cyan-500/20 text-cyan-300 font-bold"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <RotateCcw className="h-3 w-3" />
            Initial
          </button>
          <button
            type="button"
            onClick={() => setViewMode("planned")}
            className={`flex items-center gap-1 rounded px-2 py-0.5 transition ${
              viewMode === "planned"
                ? "bg-cyan-500/20 text-cyan-300 font-bold"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Layers className="h-3 w-3" />
            Planned Stack
          </button>
        </div>
      </div>

      <div className="relative overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
        <canvas
          ref={canvasRef}
          width={450}
          height={230}
          className="w-full object-contain"
        />
      </div>

      <div className="mt-2 flex items-center justify-between px-1 text-[11px] text-slate-400">
        <div className="flex items-center gap-1.5">
          <span>Active Objects:</span>
          <span className="font-mono font-semibold text-cyan-300">
            {activeObjects.join(", ")}
          </span>
        </div>
        <span className="font-mono text-slate-500">
          View: {viewMode === "planned" ? "Planned Target State" : "Initial World Setup"}
        </span>
      </div>
    </div>
  );
}
