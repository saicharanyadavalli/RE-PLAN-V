"use client";

import React, { useState, useEffect } from "react";
import { DomainMetadata } from "../types/pipeline";
import { getApiBaseUrl } from "../utils/api";

interface DomainStudioProps {
  onSelectPrompt?: (prompt: string, domainId: string) => void;
}

export function DomainStudio({ onSelectPrompt }: DomainStudioProps) {
  const [domains, setDomains] = useState<DomainMetadata[]>([]);
  const [selectedDomainId, setSelectedDomainId] = useState<string>("blocks_world");
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    async function fetchDomains() {
      try {
        const resp = await fetch(`${getApiBaseUrl()}/api/domains`);
        if (resp.ok) {
          const data = await resp.json();
          setDomains(data);
          if (data.length > 0) {
            setSelectedDomainId(data[0].domain_id);
          }
        }
      } catch (err) {
        console.warn("Failed to fetch domains from backend, using canonical fallback:", err);
        // Fallback canonical metadata
        setDomains([
          {
            domain_id: "blocks_world",
            display_name: "Blocks World",
            description: "Classical multi-object stacking and unstacking domain with table and gripper physics.",
            complexity_rating: "Small (50-200 states)",
            entity_types: ["block", "gripper", "surface"],
            action_names: ["pick_up", "put_down", "stack", "unstack"],
            predicate_names: ["on", "ontable", "clear", "holding", "handempty"],
            example_tasks: [
              "Stack the red box on the blue box.",
              "Put block a on block b, and block b on block c.",
              "Clear the red box and place it on the table.",
            ],
            supported_features: ["Discrete STRIPS logic", "Clear invariant enforcement", "Cycle detection"],
            unsupported_features: ["Continuous rotational dynamics", "Friction simulation"],
          },
          {
            domain_id: "grid_world",
            display_name: "Grid World (2D Transfer)",
            description: "2D spatial navigation with item collection and delivery across discrete coordinates.",
            complexity_rating: "Medium (200-1000 states)",
            entity_types: ["robot", "location", "item"],
            action_names: ["move", "pick", "drop"],
            predicate_names: ["at_robot", "at_item", "carrying", "empty_hand", "connected"],
            example_tasks: [
              "Move robot from loc_0_0 to loc_2_2 and pick key_1.",
              "Navigate to loc_1_0, pick package, and deliver to loc_0_1.",
            ],
            supported_features: ["4-way grid topology", "Single inventory slot", "Reachability verification"],
            unsupported_features: ["Diagonal movements", "Dynamic moving obstacles"],
          },
          {
            domain_id: "household",
            display_name: "Household Robotics",
            description: "Abstract multi-room domestic service agent with container storage and surface placement.",
            complexity_rating: "Medium (200-1000 states)",
            entity_types: ["robot", "room", "item", "surface", "container"],
            action_names: ["navigate_room", "open_container", "close_container", "pick_from_surface", "place_on_surface", "pick_from_container", "place_in_container"],
            predicate_names: ["robot_at", "item_at_surface", "item_in_container", "container_at", "container_open", "holding", "hand_empty"],
            example_tasks: [
              "Navigate to kitchen, open cabinet, and pick mug.",
              "Move mug from counter to dining_table in dining_room.",
            ],
            supported_features: ["Container containment logic", "Door status preconditions", "Room graph navigation"],
            unsupported_features: ["Fluid pouring", "Thermal state modeling"],
          },
          {
            domain_id: "warehouse",
            display_name: "Warehouse Logistics",
            description: "Automated guided vehicles (AGV) managing storage racks, pick stations, and inventory transport.",
            complexity_rating: "Large (1000-3000 states)",
            entity_types: ["agv", "zone", "shelf", "sku"],
            action_names: ["transit", "retrieve_sku", "deposit_sku"],
            predicate_names: ["agv_at", "shelf_at", "sku_on_shelf", "agv_loaded", "agv_free"],
            example_tasks: [
              "Transit agv_1 to shelf_b and retrieve sku_02.",
              "Move sku_01 from shelf_a to packing_dock.",
            ],
            supported_features: ["Multi-zone routing", "SKU capacity verification", "Deterministic slot tracking"],
            unsupported_features: ["Battery charge depletion", "AGV wheel slip"],
          },
          {
            domain_id: "scheduling",
            display_name: "Discrete Job Scheduling",
            description: "Precedence-constrained job shop scheduling across heterogeneous execution machines.",
            complexity_rating: "Small (50-200 states)",
            entity_types: ["job", "machine"],
            action_names: ["schedule_independent_job", "schedule_dependent_job"],
            predicate_names: ["available", "completed", "scheduled_on", "prerequisite_met"],
            example_tasks: [
              "Schedule job_a on m1 and job_b on m2.",
              "Execute prerequisite job_init before deploying job_compute.",
            ],
            supported_features: ["Strict DAG precedence", "Machine exclusivity", "Deadlock detection"],
            unsupported_features: ["Preemption", "Fractional millisecond clock"],
          },
          {
            domain_id: "software_workflow",
            display_name: "Software CI/CD Automation",
            description: "Multi-stage release governance requiring tests, security scans, artifacts, and approval gates.",
            complexity_rating: "Tiny (<50 states)",
            entity_types: ["commit", "artifact", "environment"],
            action_names: ["run_unit_tests", "run_security_scan", "build_artifact", "grant_approval", "deploy_to_environment"],
            predicate_names: ["tests_passed", "security_scanned", "artifact_built", "approved_for_deploy", "deployed_to"],
            example_tasks: [
              "Run unit tests, run security scan, build artifact, and deploy to staging.",
              "Complete security scan and obtain manager approval before deploying to production.",
            ],
            supported_features: ["Gated policy enforcement", "Compliance pipeline verification", "Audit trace generation"],
            unsupported_features: ["Arbitrary shell code execution", "External webhook polling"],
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    }
    fetchDomains();
  }, []);

  const activeDomain = domains.find((d) => d.domain_id === selectedDomainId) || domains[0];

  return (
    <div className="flex flex-col gap-6">
      {/* Studio Header */}
      <div className="rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-900 via-slate-900/90 to-slate-950 p-6 shadow-2xl backdrop-blur-md">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-cyan-500/10 px-3 py-1 text-xs font-semibold text-cyan-400 border border-cyan-500/20 mb-2">
              Domain Framework v2
            </div>
            <h2 className="text-xl font-bold text-white tracking-tight sm:text-2xl">
              Canonical Planning Domain Studio
            </h2>
            <p className="mt-1 text-xs text-slate-400 max-w-2xl">
              RE-PLAN-V is a generic neuro-symbolic platform. All action semantics, type hierarchies, and state invariants are specified declaratively without hardcoded domain logic.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400 font-medium">Registered Domains:</span>
            <span className="font-mono text-sm font-bold text-cyan-400 bg-slate-800 px-2.5 py-1 rounded-lg border border-slate-700">
              {domains.length} / 6 Active
            </span>
          </div>
        </div>
      </div>

      {/* Domain Selection Tabs */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {domains.map((dom) => {
          const isSelected = dom.domain_id === selectedDomainId;
          return (
            <button
              key={dom.domain_id}
              type="button"
              onClick={() => setSelectedDomainId(dom.domain_id)}
              className={`flex flex-col items-start rounded-xl border p-3.5 text-left transition-all ${
                isSelected
                  ? "border-cyan-500 bg-slate-850/90 shadow-lg shadow-cyan-950/30 ring-1 ring-cyan-500"
                  : "border-slate-800 bg-slate-900/60 hover:border-slate-700 hover:bg-slate-850/60"
              }`}
            >
              <span className={`text-xs font-bold ${isSelected ? "text-cyan-300" : "text-slate-200"}`}>
                {dom.display_name}
              </span>
              <span className="mt-1 font-mono text-[10px] text-slate-500">
                {dom.domain_id}
              </span>
              <span className="mt-2 text-[10px] rounded bg-slate-800/80 px-1.5 py-0.5 text-slate-400 border border-slate-700/60">
                {dom.action_names.length} Actions
              </span>
            </button>
          );
        })}
      </div>

      {/* Active Domain Detail Panel */}
      {activeDomain && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Left Column: Domain Specs & Actions */}
          <div className="flex flex-col gap-6 lg:col-span-7">
            {/* Description Card */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
                <div>
                  <h3 className="text-base font-bold text-white">
                    {activeDomain.display_name}
                  </h3>
                  <span className="font-mono text-xs text-cyan-400">
                    ID: {activeDomain.domain_id}
                  </span>
                </div>
                <span className="rounded-lg bg-indigo-500/15 px-2.5 py-1 text-xs font-semibold text-indigo-300 border border-indigo-500/30">
                  {activeDomain.complexity_rating}
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                {activeDomain.description}
              </p>
            </div>

            {/* Entity Types & Predicates */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4 shadow-xl">
                <span className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                  Entity Types ({activeDomain.entity_types.length})
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {activeDomain.entity_types.map((type, idx) => (
                    <span
                      key={idx}
                      className="font-mono text-xs rounded bg-slate-800 px-2 py-0.5 text-cyan-300 border border-slate-700"
                    >
                      {type}
                    </span>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4 shadow-xl">
                <span className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                  State Predicates ({activeDomain.predicate_names.length})
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {activeDomain.predicate_names.map((pred, idx) => (
                    <span
                      key={idx}
                      className="font-mono text-xs rounded bg-slate-800 px-2 py-0.5 text-emerald-300 border border-slate-700"
                    >
                      {pred}()
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Action Schemas (Operators) */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl">
              <span className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
                Ground Action Operators ({activeDomain.action_names.length})
              </span>
              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                {activeDomain.action_names.map((actionName, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950 p-3"
                  >
                    <span className="font-mono text-xs font-bold text-indigo-400">
                      {actionName}
                    </span>
                    <span className="text-[10px] rounded bg-indigo-950/40 px-2 py-0.5 text-indigo-300 border border-indigo-800/40">
                      STRIPS op
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column: Example Tasks & Capability Boundaries */}
          <div className="flex flex-col gap-6 lg:col-span-5">
            {/* Example Tasks */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl">
              <span className="block text-xs font-bold uppercase tracking-wider text-cyan-400 mb-3">
                Pre-Tested Example Instructions
              </span>
              <div className="flex flex-col gap-2.5">
                {activeDomain.example_tasks.map((task, idx) => (
                  <div
                    key={idx}
                    className="group flex flex-col gap-2 rounded-xl border border-slate-800 bg-slate-950 p-3.5 hover:border-cyan-500/50 transition"
                  >
                    <p className="text-xs text-slate-200 font-medium">
                      &quot;{task}&quot;
                    </p>
                    <div className="flex justify-end">
                      <button
                        type="button"
                        onClick={() => onSelectPrompt?.(task, activeDomain.domain_id)}
                        className="rounded-lg bg-slate-800 px-3 py-1 text-[11px] font-semibold text-cyan-400 hover:bg-cyan-600 hover:text-white transition"
                      >
                        Try in Mission Control &rarr;
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Rigorous Capabilities & Boundaries */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl">
              <span className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
                Capability Matrix & Honest Boundaries
              </span>
              <div className="flex flex-col gap-3">
                <div>
                  <span className="text-[11px] font-bold text-emerald-400 block mb-1.5">
                    Guaranteed Formal Guarantees:
                  </span>
                  <ul className="flex flex-col gap-1 text-xs text-slate-300">
                    {activeDomain.supported_features.map((feat, idx) => (
                      <li key={idx} className="flex items-center gap-2">
                        <span className="text-emerald-400 font-bold">&check;</span>
                        <span>{feat}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="border-t border-slate-800 pt-3">
                  <span className="text-[11px] font-bold text-amber-400 block mb-1.5">
                    Explicit Out-of-Scope (No Hallucinations):
                  </span>
                  <ul className="flex flex-col gap-1 text-xs text-slate-400">
                    {activeDomain.unsupported_features.map((feat, idx) => (
                      <li key={idx} className="flex items-center gap-2">
                        <span className="text-amber-500 font-bold">&times;</span>
                        <span>{feat}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
