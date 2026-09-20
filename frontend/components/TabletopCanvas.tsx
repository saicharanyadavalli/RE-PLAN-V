"use client";

import React, { useEffect, useRef } from "react";
import { GroundActionSchema } from "../types/pipeline";

interface TabletopCanvasProps {
  entities: Record<string, string>;
  initialFacts: any[];
  finalPlan: GroundActionSchema[];
  isStreaming: boolean;
}

export function TabletopCanvas({
  entities,
  initialFacts,
  finalPlan,
  isStreaming,
}: TabletopCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;

    // Clear
    ctx.clearRect(0, 0, w, h);

    // Background gradient
    const bgGrad = ctx.createLinearGradient(0, 0, 0, h);
    bgGrad.addColorStop(0, "#0b0f19");
    bgGrad.addColorStop(1, "#020617");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);

    // Grid lines for high-tech CAD/Mission Control feel
    ctx.strokeStyle = "rgba(51, 65, 85, 0.25)";
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
    ctx.fillRect(30, h - 35, w - 60, 10);
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(30, h - 35, w - 60, 10);

    // Table legs
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(50, h - 25, 14, 25);
    ctx.fillRect(w - 64, h - 25, 14, 25);

    // Surface label
    ctx.fillStyle = "#64748b";
    ctx.font = "9px 'Courier New', monospace";
    ctx.fillText("TABLE SURFACE (Z=0.0)", 40, h - 40);

    const colorMap: Record<string, string> = {
      red_box: "#ef4444",
      blue_box: "#3b82f6",
      green_box: "#10b981",
      yellow_box: "#eab308",
      obstacle: "#f97316",
      glass: "#a855f7",
    };

    const xPositions: Record<string, number> = {
      red_box: 60,
      blue_box: 130,
      green_box: 200,
      yellow_box: 270,
      obstacle: 270,
      glass: 340,
    };

    const entityList = Object.keys(entities).length > 0
      ? Object.keys(entities)
      : ["red_box", "blue_box", "green_box", "glass"];

    entityList.forEach((name, idx) => {
      const x = xPositions[name] || 60 + idx * 70;
      const y = h - 75;
      const color = colorMap[name] || "#94a3b8";

      // Shadow
      ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
      ctx.fillRect(x + 4, y + 4, 38, 38);

      // Block body
      ctx.fillStyle = color;
      ctx.fillRect(x, y, 38, 38);

      // Border highlight
      ctx.strokeStyle = "rgba(255, 255, 255, 0.7)";
      ctx.lineWidth = 1.5;
      ctx.strokeRect(x, y, 38, 38);

      // Label
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 9px -apple-system, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(name.replace("_box", "").toUpperCase(), x + 19, y + 23);
    });

    // Robotic Gripper Assembly
    const gripperX = w / 2;
    const gripperY = isStreaming ? 50 + Math.sin(Date.now() / 200) * 10 : 45;

    // Gantry Rail
    ctx.strokeStyle = "#475569";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(30, 20);
    ctx.lineTo(w - 30, 20);
    ctx.stroke();

    // Telescopic Arm
    ctx.strokeStyle = "#fbbf24";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(gripperX, 20);
    ctx.lineTo(gripperX, gripperY);
    // Two fingers
    ctx.lineTo(gripperX - 16, gripperY + 16);
    ctx.moveTo(gripperX, gripperY);
    ctx.lineTo(gripperX + 16, gripperY + 16);
    ctx.stroke();

    // Gripper status badge
    ctx.fillStyle = "#fbbf24";
    ctx.font = "9px 'Courier New', monospace";
    ctx.textAlign = "center";
    ctx.fillText(isStreaming ? "ACTUATING" : "GRIPPER READY", gripperX, 15);
  }, [entities, initialFacts, finalPlan, isStreaming]);

  return (
    <div className="flex flex-col rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-xl backdrop-blur-sm">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-cyan-400" />
          <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-slate-300">
            Tabletop World State Simulation
          </h3>
        </div>
        <span className="font-mono text-[11px] text-slate-400">
          Entities: {Object.keys(entities).length || 4}
        </span>
      </div>

      <div className="relative overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
        <canvas
          ref={canvasRef}
          width={440}
          height={220}
          className="w-full object-contain"
        />
      </div>
      <div className="mt-2 flex items-center justify-between px-1 text-[11px] text-slate-400">
        <span>Coordinate frame: 2D Spatial Tabletop</span>
        <span className="font-mono text-cyan-400">State: Synchronized</span>
      </div>
    </div>
  );
}
