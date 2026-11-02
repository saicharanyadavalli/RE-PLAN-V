"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import { GraphNode, GraphEdge, GraphStats, FactSchema } from "../types/pipeline";
import { getApiBaseUrl } from "../utils/api";

export type SearchAlgorithmType = "astar" | "bfs" | "greedy";

export interface SearchSimulationStep {
  stepIndex: number;
  currentNodeId: string;
  frontierNodeIds: string[];
  closedNodeIds: string[];
  solutionPathNodeIds: string[];
  solutionEdgeKeys: Set<string>;
  g: number;
  h: number;
  f: number;
  explanation: string;
  queueSnapshot: Array<{ id: string; g: number; h: number; f: number }>;
}

interface StateSpaceExplorerProps {
  streamedNodes?: GraphNode[];
  streamedEdges?: GraphEdge[];
  streamedStats?: GraphStats;
  streamedStatus?: "IDLE" | "ENUMERATING" | "COMPLETED" | "TRUNCATED";
}

export function StateSpaceExplorer({
  streamedNodes = [],
  streamedEdges = [],
  streamedStats,
  streamedStatus = "IDLE",
}: StateSpaceExplorerProps) {
  // Domain & Standalone exploration state
  const [selectedDomain, setSelectedDomain] = useState<string>("blocks_world");
  const [prompt, setPrompt] = useState<string>("Stack the red box on the blue box.");
  const [maxNodesLimit, setMaxNodesLimit] = useState<number>(150);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [activeSource, setActiveSource] = useState<"stream" | "standalone">("stream");

  // Standalone graph data
  const [standaloneNodes, setStandaloneNodes] = useState<GraphNode[]>([]);
  const [standaloneEdges, setStandaloneEdges] = useState<GraphEdge[]>([]);
  const [standaloneStats, setStandaloneStats] = useState<GraphStats | null>(null);

  // Filter & Search
  const [searchFilter, setSearchFilter] = useState<string>("");
  const [filterType, setFilterType] = useState<"all" | "goal" | "dead_end" | "boundary">("all");

  // Selection & Hover (no scale transform, stable tracking)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  // Pan and Zoom
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 200, y: 40 });
  const [zoom, setZoom] = useState<number>(0.85);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  // Search Algorithm Simulation State
  const [selectedAlgorithm, setSelectedAlgorithm] = useState<SearchAlgorithmType>("astar");
  const [currentSimStepIndex, setCurrentSimStepIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(800); // ms per step

  // Use stream data if active and present, otherwise standalone
  const hasStreamData = streamedNodes.length > 0;
  const currentNodes = (activeSource === "stream" && hasStreamData) ? streamedNodes : standaloneNodes;
  const currentEdges = (activeSource === "stream" && hasStreamData) ? streamedEdges : standaloneEdges;
  const currentStats = (activeSource === "stream" && hasStreamData) ? streamedStats : standaloneStats;
  const currentStatus = (activeSource === "stream" && hasStreamData) ? streamedStatus : (isLoading ? "ENUMERATING" : (standaloneStats ? (standaloneStats.is_complete ? "COMPLETED" : "TRUNCATED") : "IDLE"));

  // Automatically switch to stream source if live nodes arrive
  useEffect(() => {
    if (streamedNodes.length > 0) {
      setActiveSource("stream");
    }
  }, [streamedNodes.length]);

  // Fetch standalone enumeration from backend
  const handleEnumerateStandalone = async () => {
    setIsLoading(true);
    setActiveSource("standalone");
    try {
      const resp = await fetch(`${getApiBaseUrl()}/api/graph/enumerate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain_id: selectedDomain,
          prompt: prompt,
          max_nodes: maxNodesLimit,
          max_edges: maxNodesLimit * 3,
          timeout_seconds: 5.0,
        }),
      });

      if (!resp.ok) {
        throw new Error(`Enumerate failed: ${await resp.text()}`);
      }

      const cytoscape = await resp.json();
      const rawElements: Array<{ data: any }> = cytoscape.elements || [];

      const parsedNodes: GraphNode[] = [];
      const parsedEdges: GraphEdge[] = [];

      for (const el of rawElements) {
        const d = el.data;
        if (d.source && d.target) {
          parsedEdges.push({
            source: String(d.source),
            target: String(d.target),
            action_name: d.label || d.action || "action",
            action_args: [],
            cost: d.cost ?? 1,
            is_cycle: Boolean(d.is_cycle),
          });
        } else {
          parsedNodes.push({
            id: String(d.id),
            state_hash: d.state_hash || String(d.id),
            depth: d.depth ?? 0,
            is_initial: Boolean(d.is_initial),
            is_goal: Boolean(d.is_goal),
            is_dead_end: Boolean(d.is_dead_end),
            is_truncated_boundary: Boolean(d.is_truncated_boundary),
            facts: (d.facts || []).map((f: any) => {
              if (typeof f === "string") {
                const match = f.match(/([a-zA-Z_]+)\((.*)\)/);
                return match
                  ? { predicate: match[1], arguments: match[2].split(",").map((s) => s.trim()) }
                  : { predicate: f, arguments: [] };
              }
              return f;
            }),
            facts_summary: Array.isArray(d.facts) ? d.facts : [],
          });
        }
      }

      setStandaloneNodes(parsedNodes);
      setStandaloneEdges(parsedEdges);
      setStandaloneStats(cytoscape.stats || {
        total_nodes: parsedNodes.length,
        total_edges: parsedEdges.length,
        max_depth_reached: Math.max(0, ...parsedNodes.map(n => n.depth)),
        goal_node_ids: parsedNodes.filter(n => n.is_goal).map(n => n.id),
        dead_end_node_ids: parsedNodes.filter(n => n.is_dead_end).map(n => n.id),
        is_complete: false,
        truncation_reason: "STATS_OMITTED_BY_BACKEND",
        enumeration_time_ms: 0.0,
      });

      if (parsedNodes.length > 0) {
        setSelectedNodeId(parsedNodes[0].id);
      }
    } catch (err) {
      console.error("State Space standalone enumeration failed:", err);
    } finally {
      setIsLoading(false);
    }
  };

  // Node position calculation: Stratified Hierarchical Layout
  const nodePositions = useMemo(() => {
    const positions: Record<string, { x: number; y: number }> = {};
    if (currentNodes.length === 0) return positions;

    // Group by depth
    const levels: Record<number, GraphNode[]> = {};
    let maxDepth = 0;
    for (const node of currentNodes) {
      const d = node.depth ?? 0;
      if (!levels[d]) levels[d] = [];
      levels[d].push(node);
      if (d > maxDepth) maxDepth = d;
    }

    const ySpacing = 120;
    const minXSpacing = 110;

    for (let d = 0; d <= maxDepth; d++) {
      const nodesAtLevel = levels[d] || [];
      const count = nodesAtLevel.length;
      const totalWidth = Math.max(800, (count + 1) * minXSpacing);
      const step = totalWidth / (count + 1);

      nodesAtLevel.forEach((node, idx) => {
        positions[node.id] = {
          x: Math.round((idx + 1) * step),
          y: Math.round(60 + d * ySpacing),
        };
      });
    }

    return positions;
  }, [currentNodes]);

  // Selected node details
  const selectedNode = useMemo(() => {
    return currentNodes.find((n) => n.id === selectedNodeId) || null;
  }, [currentNodes, selectedNodeId]);

  // Incoming and outgoing transitions for selected node
  const { incomingTransitions, outgoingTransitions } = useMemo(() => {
    if (!selectedNodeId) return { incomingTransitions: [], outgoingTransitions: [] };
    const incoming = currentEdges.filter((e) => e.target === selectedNodeId);
    const outgoing = currentEdges.filter((e) => e.source === selectedNodeId);
    return { incomingTransitions: incoming, outgoingTransitions: outgoing };
  }, [currentEdges, selectedNodeId]);

  // Filtered nodes
  const filteredNodeIds = useMemo(() => {
    const ids = new Set<string>();
    const query = searchFilter.toLowerCase().trim();

    for (const node of currentNodes) {
      if (filterType === "goal" && !node.is_goal) continue;
      if (filterType === "dead_end" && !node.is_dead_end) continue;
      if (filterType === "boundary" && !node.is_truncated_boundary) continue;

      if (query) {
        const matchesId = node.id.toLowerCase().includes(query);
        const matchesHash = Boolean(node.state_hash && node.state_hash.toLowerCase().includes(query));
        const matchesFacts = (node.facts_summary || []).some((f) =>
          f.toLowerCase().includes(query)
        );
        if (!matchesId && !matchesHash && !matchesFacts) continue;
      }

      ids.add(node.id);
    }
    return ids;
  }, [currentNodes, searchFilter, filterType]);

  // Mouse pan handling
  const handleMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).tagName === "circle" || (e.target as HTMLElement).tagName === "text") {
      return; // Clicking a node
    }
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPan({
      x: e.clientX - dragStartRef.current.x,
      y: e.clientY - dragStartRef.current.y,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    setZoom((prev) => Math.min(2.5, Math.max(0.2, prev * zoomFactor)));
  };

  const resetView = () => {
    setPan({ x: 200, y: 40 });
    setZoom(0.85);
  };

  // ==========================================
  // SEARCH ALGORITHM SIMULATION ENGINE (Russell & Norvig Ch 3 & 4)
  // ==========================================
  const heuristicDistances = useMemo(() => {
    const hDist: Record<string, number> = {};
    if (currentNodes.length === 0) return hDist;

    // Build reverse adjacency list
    const reversedAdj: Record<string, string[]> = {};
    for (const n of currentNodes) reversedAdj[n.id] = [];
    for (const e of currentEdges) {
      if (!reversedAdj[e.target]) reversedAdj[e.target] = [];
      reversedAdj[e.target].push(e.source);
    }

    // Identify goal nodes
    const goalNodeIds = currentNodes.filter((n) => n.is_goal).map((n) => n.id);
    for (const n of currentNodes) hDist[n.id] = Infinity;

    // Multi-source reverse BFS from all goals
    const queue: string[] = [];
    for (const gId of goalNodeIds) {
      hDist[gId] = 0;
      queue.push(gId);
    }

    while (queue.length > 0) {
      const curr = queue.shift()!;
      const currDist = hDist[curr];
      for (const pred of reversedAdj[curr] || []) {
        if (hDist[pred] === Infinity) {
          hDist[pred] = currDist + 1;
          queue.push(pred);
        }
      }
    }

    // Fallback for disconnected / dead-end states
    const maxDepth = Math.max(0, ...currentNodes.map((n) => n.depth));
    for (const n of currentNodes) {
      if (hDist[n.id] === Infinity) {
        hDist[n.id] = Math.max(1, (maxDepth - n.depth) + 1);
      }
    }

    return hDist;
  }, [currentNodes, currentEdges]);

  // Precompute full simulation steps whenever algorithm or graph changes
  const simulationSteps = useMemo(() => {
    const steps: SearchSimulationStep[] = [];
    if (currentNodes.length === 0) return steps;

    const startNode = currentNodes.find((n) => n.is_initial) || currentNodes[0];
    const goalNodeIds = new Set(currentNodes.filter((n) => n.is_goal).map((n) => n.id));

    // Forward adjacency
    const forwardAdj: Record<string, Array<{ target: string; action: string; edgeKey: string; cost: number }>> = {};
    for (const n of currentNodes) forwardAdj[n.id] = [];
    for (const e of currentEdges) {
      if (!forwardAdj[e.source]) forwardAdj[e.source] = [];
      forwardAdj[e.source].push({
        target: e.target,
        action: e.action_name,
        edgeKey: `${e.source}->${e.target}`,
        cost: e.cost ?? 1,
      });
    }

    // Helper to reconstruct solution path
    const buildPath = (parentMap: Record<string, { parent: string; edgeKey: string }>, endNodeId: string) => {
      const pathNodes: string[] = [];
      const pathEdges = new Set<string>();
      let curr = endNodeId;
      pathNodes.push(curr);
      while (parentMap[curr]) {
        const { parent, edgeKey } = parentMap[curr];
        pathEdges.add(edgeKey);
        curr = parent;
        pathNodes.unshift(curr);
      }
      return { pathNodes, pathEdges };
    };

    if (selectedAlgorithm === "astar") {
      // A* Search: priority f(n) = g(n) + h(n)
      interface AStarItem {
        id: string;
        g: number;
        h: number;
        f: number;
      }
      const openSet: Map<string, AStarItem> = new Map();
      const closedSet: Set<string> = new Set();
      const parentMap: Record<string, { parent: string; edgeKey: string }> = {};

      const startH = heuristicDistances[startNode.id] ?? 0;
      openSet.set(startNode.id, { id: startNode.id, g: 0, h: startH, f: startH });

      // Step 0: Initial frontier
      steps.push({
        stepIndex: 0,
        currentNodeId: startNode.id,
        frontierNodeIds: [startNode.id],
        closedNodeIds: [],
        solutionPathNodeIds: [],
        solutionEdgeKeys: new Set(),
        g: 0,
        h: startH,
        f: startH,
        explanation: `A* initialized at initial state ${startNode.id}. Evaluation: g=0, h=${startH}, f(n)=g+h=${startH}. Placed in Open Set (Frontier).`,
        queueSnapshot: [{ id: startNode.id, g: 0, h: startH, f: startH }],
      });

      let stepCounter = 1;
      while (openSet.size > 0 && stepCounter < 60) {
        // Pick node with lowest f (tie-break lowest h, then lowest g)
        let bestItem: AStarItem | null = null;
        for (const item of openSet.values()) {
          if (!bestItem || item.f < bestItem.f || (item.f === bestItem.f && item.h < bestItem.h)) {
            bestItem = item;
          }
        }
        if (!bestItem) break;

        openSet.delete(bestItem.id);
        closedSet.add(bestItem.id);

        // Check if goal reached
        if (goalNodeIds.has(bestItem.id)) {
          const { pathNodes, pathEdges } = buildPath(parentMap, bestItem.id);
          steps.push({
            stepIndex: stepCounter,
            currentNodeId: bestItem.id,
            frontierNodeIds: Array.from(openSet.keys()),
            closedNodeIds: Array.from(closedSet),
            solutionPathNodeIds: pathNodes,
            solutionEdgeKeys: pathEdges,
            g: bestItem.g,
            h: 0,
            f: bestItem.g,
            explanation: `Goal satisfied at ${bestItem.id}! A* achieved optimality with path cost g=${bestItem.g} across ${pathNodes.length} states. Zero heuristic remaining (h=0).`,
            queueSnapshot: Array.from(openSet.values()),
          });
          break;
        }

        // Expand successors
        const neighbors = forwardAdj[bestItem.id] || [];
        let addedCount = 0;
        for (const nbr of neighbors) {
          if (closedSet.has(nbr.target)) continue;
          const tentativeG = bestItem.g + nbr.cost;
          const existing = openSet.get(nbr.target);

          if (!existing || tentativeG < existing.g) {
            const hVal = heuristicDistances[nbr.target] ?? 0;
            openSet.set(nbr.target, {
              id: nbr.target,
              g: tentativeG,
              h: hVal,
              f: tentativeG + hVal,
            });
            parentMap[nbr.target] = { parent: bestItem.id, edgeKey: nbr.edgeKey };
            addedCount++;
          }
        }

        steps.push({
          stepIndex: stepCounter++,
          currentNodeId: bestItem.id,
          frontierNodeIds: Array.from(openSet.keys()),
          closedNodeIds: Array.from(closedSet),
          solutionPathNodeIds: [],
          solutionEdgeKeys: new Set(),
          g: bestItem.g,
          h: bestItem.h,
          f: bestItem.f,
          explanation: `A* expanded ${bestItem.id} (f=${bestItem.f} = g:${bestItem.g} + h:${bestItem.h}). Moved to Closed Set; generated ${addedCount} successor(s) in Frontier.`,
          queueSnapshot: Array.from(openSet.values()).sort((a, b) => a.f - b.f),
        });
      }
    } else if (selectedAlgorithm === "bfs") {
      // Breadth-First Search (FIFO queue)
      const queue: string[] = [startNode.id];
      const seen: Set<string> = new Set([startNode.id]);
      const closedSet: Set<string> = new Set();
      const parentMap: Record<string, { parent: string; edgeKey: string }> = {};
      const depthMap: Record<string, number> = { [startNode.id]: 0 };

      steps.push({
        stepIndex: 0,
        currentNodeId: startNode.id,
        frontierNodeIds: [startNode.id],
        closedNodeIds: [],
        solutionPathNodeIds: [],
        solutionEdgeKeys: new Set(),
        g: 0,
        h: heuristicDistances[startNode.id] ?? 0,
        f: 0,
        explanation: `BFS initialized with start node ${startNode.id} at depth 0 into FIFO Queue.`,
        queueSnapshot: [{ id: startNode.id, g: 0, h: heuristicDistances[startNode.id] ?? 0, f: 0 }],
      });

      let stepCounter = 1;
      while (queue.length > 0 && stepCounter < 60) {
        const curr = queue.shift()!;
        closedSet.add(curr);
        const currDepth = depthMap[curr] ?? 0;

        if (goalNodeIds.has(curr)) {
          const { pathNodes, pathEdges } = buildPath(parentMap, curr);
          steps.push({
            stepIndex: stepCounter,
            currentNodeId: curr,
            frontierNodeIds: [...queue],
            closedNodeIds: Array.from(closedSet),
            solutionPathNodeIds: pathNodes,
            solutionEdgeKeys: pathEdges,
            g: currDepth,
            h: 0,
            f: currDepth,
            explanation: `BFS reached goal node ${curr} at depth ${currDepth}. Optimal step count guaranteed for uniform edge costs.`,
            queueSnapshot: queue.map((id) => ({ id, g: depthMap[id] ?? 0, h: heuristicDistances[id] ?? 0, f: depthMap[id] ?? 0 })),
          });
          break;
        }

        const neighbors = forwardAdj[curr] || [];
        let addedCount = 0;
        for (const nbr of neighbors) {
          if (!seen.has(nbr.target)) {
            seen.add(nbr.target);
            depthMap[nbr.target] = currDepth + 1;
            parentMap[nbr.target] = { parent: curr, edgeKey: nbr.edgeKey };
            queue.push(nbr.target);
            addedCount++;
          }
        }

        steps.push({
          stepIndex: stepCounter++,
          currentNodeId: curr,
          frontierNodeIds: [...queue],
          closedNodeIds: Array.from(closedSet),
          solutionPathNodeIds: [],
          solutionEdgeKeys: new Set(),
          g: currDepth,
          h: heuristicDistances[curr] ?? 0,
          f: currDepth,
          explanation: `BFS popped ${curr} from FIFO queue at depth ${currDepth}. Enqueued ${addedCount} unvisited successor(s).`,
          queueSnapshot: queue.map((id) => ({ id, g: depthMap[id] ?? 0, h: heuristicDistances[id] ?? 0, f: depthMap[id] ?? 0 })),
        });
      }
    } else {
      // Greedy Best-First Search (priority queue by heuristic h(n) only)
      interface GreedyItem {
        id: string;
        g: number;
        h: number;
        f: number;
      }
      const openSet: Map<string, GreedyItem> = new Map();
      const closedSet: Set<string> = new Set();
      const parentMap: Record<string, { parent: string; edgeKey: string }> = {};

      const startH = heuristicDistances[startNode.id] ?? 0;
      openSet.set(startNode.id, { id: startNode.id, g: 0, h: startH, f: startH });

      steps.push({
        stepIndex: 0,
        currentNodeId: startNode.id,
        frontierNodeIds: [startNode.id],
        closedNodeIds: [],
        solutionPathNodeIds: [],
        solutionEdgeKeys: new Set(),
        g: 0,
        h: startH,
        f: startH,
        explanation: `Greedy Best-First Search initialized at ${startNode.id}. Guided solely by heuristic estimate h(n)=${startH}.`,
        queueSnapshot: [{ id: startNode.id, g: 0, h: startH, f: startH }],
      });

      let stepCounter = 1;
      while (openSet.size > 0 && stepCounter < 60) {
        let bestItem: GreedyItem | null = null;
        for (const item of openSet.values()) {
          if (!bestItem || item.h < bestItem.h) {
            bestItem = item;
          }
        }
        if (!bestItem) break;

        openSet.delete(bestItem.id);
        closedSet.add(bestItem.id);

        if (goalNodeIds.has(bestItem.id)) {
          const { pathNodes, pathEdges } = buildPath(parentMap, bestItem.id);
          steps.push({
            stepIndex: stepCounter,
            currentNodeId: bestItem.id,
            frontierNodeIds: Array.from(openSet.keys()),
            closedNodeIds: Array.from(closedSet),
            solutionPathNodeIds: pathNodes,
            solutionEdgeKeys: pathEdges,
            g: bestItem.g,
            h: 0,
            f: 0,
            explanation: `Greedy Best-First reached goal ${bestItem.id} with h=0! Path found quickly, though not necessarily cost-minimal.`,
            queueSnapshot: Array.from(openSet.values()),
          });
          break;
        }

        const neighbors = forwardAdj[bestItem.id] || [];
        let addedCount = 0;
        for (const nbr of neighbors) {
          if (closedSet.has(nbr.target)) continue;
          if (!openSet.has(nbr.target)) {
            const hVal = heuristicDistances[nbr.target] ?? 0;
            openSet.set(nbr.target, {
              id: nbr.target,
              g: bestItem.g + nbr.cost,
              h: hVal,
              f: hVal,
            });
            parentMap[nbr.target] = { parent: bestItem.id, edgeKey: nbr.edgeKey };
            addedCount++;
          }
        }

        steps.push({
          stepIndex: stepCounter++,
          currentNodeId: bestItem.id,
          frontierNodeIds: Array.from(openSet.keys()),
          closedNodeIds: Array.from(closedSet),
          solutionPathNodeIds: [],
          solutionEdgeKeys: new Set(),
          g: bestItem.g,
          h: bestItem.h,
          f: bestItem.h,
          explanation: `Greedy Best-First expanded ${bestItem.id} with lowest h(n)=${bestItem.h}. Ignoring historical path cost g(n).`,
          queueSnapshot: Array.from(openSet.values()).sort((a, b) => a.h - b.h),
        });
      }
    }

    return steps;
  }, [currentNodes, currentEdges, selectedAlgorithm, heuristicDistances]);

  // Reset simulation when algorithm or graph changes
  useEffect(() => {
    setCurrentSimStepIndex(0);
    setIsPlaying(false);
  }, [selectedAlgorithm, currentNodes.length]);

  // Playback timer loop
  useEffect(() => {
    if (!isPlaying) return;
    if (currentSimStepIndex >= simulationSteps.length - 1) {
      setIsPlaying(false);
      return;
    }
    const timer = setTimeout(() => {
      setCurrentSimStepIndex((prev) => Math.min(simulationSteps.length - 1, prev + 1));
    }, playbackSpeed);
    return () => clearTimeout(timer);
  }, [isPlaying, currentSimStepIndex, simulationSteps.length, playbackSpeed]);

  // Active step
  const activeSimStep = simulationSteps[currentSimStepIndex] || null;

  return (
    <div className="flex flex-col gap-4">
      {/* Top Controls & Standalone Enumerator Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-900/80 p-4 shadow-xl backdrop-blur-md">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-cyan-400">
              Source:
            </span>
            <div className="inline-flex rounded-lg border border-slate-700 bg-slate-800/80 p-0.5">
              <button
                type="button"
                onClick={() => setActiveSource("stream")}
                className={`rounded-md px-3 py-1 text-xs font-medium transition ${
                  activeSource === "stream"
                    ? "bg-cyan-500 text-slate-950 shadow"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Live Pipeline ({streamedNodes.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveSource("standalone")}
                className={`rounded-md px-3 py-1 text-xs font-medium transition ${
                  activeSource === "standalone"
                    ? "bg-cyan-500 text-slate-950 shadow"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Standalone Explorer
              </button>
            </div>
          </div>

          {activeSource === "standalone" && (
            <>
              <select
                value={selectedDomain}
                onChange={(e) => {
                  setSelectedDomain(e.target.value);
                  if (e.target.value === "blocks_world") setPrompt("Stack the red box on the blue box.");
                  if (e.target.value === "grid_world") setPrompt("Move robot from loc_0_0 to loc_2_2 and pick key_1.");
                  if (e.target.value === "household") setPrompt("Navigate to kitchen, open cabinet, and pick mug.");
                  if (e.target.value === "warehouse") setPrompt("Transit agv_1 to shelf_b and retrieve sku_02.");
                  if (e.target.value === "scheduling") setPrompt("Schedule job_a on m1 and job_b on m2.");
                  if (e.target.value === "software_workflow") setPrompt("Run unit tests, run security scan, build artifact, and deploy to staging.");
                }}
                style={{ colorScheme: "dark" }}
                className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-100 focus:border-cyan-500 focus:outline-none cursor-pointer [&>option]:bg-slate-900 [&>option]:text-slate-100"
              >
                <option value="blocks_world" className="bg-slate-900 text-slate-100 py-1.5">Blocks World (4 Actions)</option>
                <option value="grid_world" className="bg-slate-900 text-slate-100 py-1.5">Grid World (2D Transfer)</option>
                <option value="household" className="bg-slate-900 text-slate-100 py-1.5">Household Robotics (Multi-Room)</option>
                <option value="warehouse" className="bg-slate-900 text-slate-100 py-1.5">Warehouse Operations (AGV / SKU)</option>
                <option value="scheduling" className="bg-slate-900 text-slate-100 py-1.5">Job Shop Scheduling (Resource Allocation)</option>
                <option value="software_workflow" className="bg-slate-900 text-slate-100 py-1.5">Software Workflow (CI/CD Gates)</option>
              </select>

              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Domain instruction..."
                className="w-64 rounded-lg border border-slate-700 bg-slate-850 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-cyan-500 focus:outline-none"
              />

              <div className="flex items-center gap-1.5 text-xs text-slate-400">
                <span>Max:</span>
                <input
                  type="number"
                  min="20"
                  max="600"
                  step="20"
                  value={maxNodesLimit}
                  onChange={(e) => setMaxNodesLimit(Number(e.target.value))}
                  className="w-16 rounded border border-slate-700 bg-slate-850 px-2 py-1 text-center text-xs text-cyan-300"
                />
              </div>

              <button
                type="button"
                onClick={handleEnumerateStandalone}
                disabled={isLoading}
                className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-md hover:from-cyan-400 hover:to-blue-500 transition disabled:opacity-50"
              >
                {isLoading ? (
                  <span className="animate-spin inline-block h-3 w-3 border-2 border-white border-t-transparent rounded-full" />
                ) : (
                  <span>Explore State Space</span>
                )}
              </button>
            </>
          )}
        </div>

        {/* View Controls */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setZoom((z) => Math.min(2.5, z * 1.2))}
            title="Zoom In"
            className="rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-300 hover:bg-slate-700"
          >
            +
          </button>
          <button
            type="button"
            onClick={() => setZoom((z) => Math.max(0.2, z * 0.8))}
            title="Zoom Out"
            className="rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-300 hover:bg-slate-700"
          >
            -
          </button>
          <button
            type="button"
            onClick={resetView}
            title="Reset Pan and Zoom"
            className="rounded border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-300 hover:bg-slate-700"
          >
            Reset
          </button>
          <span className="text-[11px] font-mono text-slate-400">
            {Math.round(zoom * 100)}%
          </span>
        </div>
      </div>

      {/* SEARCH ALGORITHM NODE-BY-NODE ANIMATION TOOLBAR */}
      <div className="flex flex-col gap-2.5 rounded-2xl border border-cyan-500/30 bg-slate-900/90 p-4 shadow-xl backdrop-blur-md">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Algorithm Switcher */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">
              Algorithm:
            </span>
            <div className="inline-flex rounded-lg border border-slate-700 bg-slate-950 p-0.5">
              <button
                type="button"
                onClick={() => setSelectedAlgorithm("astar")}
                className={`rounded-md px-3 py-1 text-xs font-semibold transition ${
                  selectedAlgorithm === "astar"
                    ? "bg-cyan-500 text-slate-950 shadow"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                A* Search (f = g + h)
              </button>
              <button
                type="button"
                onClick={() => setSelectedAlgorithm("bfs")}
                className={`rounded-md px-3 py-1 text-xs font-semibold transition ${
                  selectedAlgorithm === "bfs"
                    ? "bg-cyan-500 text-slate-950 shadow"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                BFS (FIFO Layer)
              </button>
              <button
                type="button"
                onClick={() => setSelectedAlgorithm("greedy")}
                className={`rounded-md px-3 py-1 text-xs font-semibold transition ${
                  selectedAlgorithm === "greedy"
                    ? "bg-cyan-500 text-slate-950 shadow"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Greedy Best-First (h only)
              </button>
            </div>
          </div>

          {/* Playback Controls */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setCurrentSimStepIndex(0)}
              disabled={simulationSteps.length === 0}
              title="Reset to Step 0"
              className="rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-300 hover:bg-slate-700 disabled:opacity-40"
            >
              ↺ Reset
            </button>
            <button
              type="button"
              onClick={() => setCurrentSimStepIndex((s) => Math.max(0, s - 1))}
              disabled={currentSimStepIndex === 0 || simulationSteps.length === 0}
              className="rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-300 hover:bg-slate-700 disabled:opacity-40"
            >
              ⏮ Step
            </button>
            <button
              type="button"
              onClick={() => {
                if (currentSimStepIndex >= simulationSteps.length - 1) {
                  setCurrentSimStepIndex(0);
                  setIsPlaying(true);
                } else {
                  setIsPlaying(!isPlaying);
                }
              }}
              disabled={simulationSteps.length === 0}
              className={`rounded-lg px-3.5 py-1 text-xs font-bold shadow transition ${
                isPlaying
                  ? "bg-amber-500 text-slate-950 hover:bg-amber-400"
                  : "bg-emerald-600 text-white hover:bg-emerald-500"
              } disabled:opacity-40`}
            >
              {isPlaying ? "⏸ Pause" : "▶ Play"}
            </button>
            <button
              type="button"
              onClick={() => setCurrentSimStepIndex((s) => Math.min(simulationSteps.length - 1, s + 1))}
              disabled={currentSimStepIndex >= simulationSteps.length - 1 || simulationSteps.length === 0}
              className="rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-300 hover:bg-slate-700 disabled:opacity-40"
            >
              Step ⏭
            </button>

            {/* Speed Selector */}
            <select
              value={playbackSpeed}
              onChange={(e) => setPlaybackSpeed(Number(e.target.value))}
              style={{ colorScheme: "dark" }}
              className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-300 focus:outline-none cursor-pointer"
            >
              <option value={1400}>0.5x</option>
              <option value={800}>1.0x</option>
              <option value={400}>2.0x</option>
              <option value={150}>5.0x</option>
            </select>
          </div>
        </div>

        {/* Step Scrubber and Real-time Metric Strip */}
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 pt-1 border-t border-slate-800/80">
          <div className="flex items-center gap-2 flex-1">
            <span className="text-[11px] font-mono text-cyan-300 whitespace-nowrap">
              Step {simulationSteps.length > 0 ? currentSimStepIndex + 1 : 0} / {simulationSteps.length}
            </span>
            <input
              type="range"
              min={0}
              max={Math.max(0, simulationSteps.length - 1)}
              value={currentSimStepIndex}
              onChange={(e) => setCurrentSimStepIndex(Number(e.target.value))}
              disabled={simulationSteps.length === 0}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
            />
          </div>

          {activeSimStep && (
            <div className="flex items-center gap-3 text-xs">
              <span className="font-mono text-slate-300">
                Focus: <strong className="text-cyan-400">{activeSimStep.currentNodeId}</strong>
              </span>
              <span className="font-mono text-slate-400">
                g(n)=<strong className="text-indigo-300">{activeSimStep.g}</strong>
              </span>
              <span className="font-mono text-slate-400">
                h(n)=<strong className="text-amber-300">{activeSimStep.h}</strong>
              </span>
              <span className="font-mono text-slate-400">
                f(n)=<strong className="text-emerald-300">{activeSimStep.f}</strong>
              </span>
              <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] font-mono text-slate-400 border border-slate-700">
                |Open|={activeSimStep.frontierNodeIds.length} |Closed|={activeSimStep.closedNodeIds.length}
              </span>
            </div>
          )}
        </div>

        {/* Explanatory Banner */}
        {activeSimStep && (
          <div className="rounded-xl border border-cyan-500/20 bg-cyan-950/20 p-2.5 text-xs text-cyan-200/90 leading-relaxed">
            <span className="font-bold text-cyan-300 mr-1.5">🎓 Search Concept:</span>
            {activeSimStep.explanation}
          </div>
        )}
      </div>

      {/* HUD Bar */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-6 rounded-xl border border-slate-800 bg-slate-900/60 p-3">
        <div className="flex flex-col">
          <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500">
            Reachable States
          </span>
          <span className="text-lg font-bold font-mono text-slate-100">
            {currentNodes.length}
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500">
            Valid Transitions
          </span>
          <span className="text-lg font-bold font-mono text-cyan-400">
            {currentEdges.length}
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500">
            Max Depth
          </span>
          <span className="text-lg font-bold font-mono text-indigo-400">
            {currentStats?.max_depth_reached ?? 0}
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500">
            Goal States
          </span>
          <span className="text-lg font-bold font-mono text-emerald-400">
            {currentNodes.filter((n) => n.is_goal).length}
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500">
            Dead Ends
          </span>
          <span className="text-lg font-bold font-mono text-rose-400">
            {currentNodes.filter((n) => n.is_dead_end).length}
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500">
            State Space Status
          </span>
          <span className="inline-flex items-center mt-1">
            {currentStatus === "COMPLETED" && (
              <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[11px] font-semibold text-emerald-300 border border-emerald-500/30">
                Complete DAG
              </span>
            )}
            {currentStatus === "TRUNCATED" && (
              <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[11px] font-semibold text-amber-300 border border-amber-500/30" title={currentStats?.truncation_reason || "Truncated"}>
                Truncated Budget
              </span>
            )}
            {currentStatus === "ENUMERATING" && (
              <span className="rounded-full bg-cyan-500/20 px-2 py-0.5 text-[11px] font-semibold text-cyan-300 border border-cyan-500/30 animate-pulse">
                Enumerating...
              </span>
            )}
            {currentStatus === "IDLE" && (
              <span className="rounded-full bg-slate-700/40 px-2 py-0.5 text-[11px] font-medium text-slate-400 border border-slate-700">
                Ready
              </span>
            )}
          </span>
        </div>
      </div>

      {/* Main Exploration Workspace */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 min-h-[580px]">
        {/* Interactive SVG Graph Canvas */}
        <div
          className="relative lg:col-span-8 flex flex-col rounded-2xl border border-slate-800 bg-slate-950 overflow-hidden shadow-2xl select-none"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onWheel={handleWheel}
        >
          {/* Legend and Filter Bar Overlay */}
          <div className="absolute top-3 left-3 z-10 flex flex-wrap items-center gap-2 rounded-xl bg-slate-900/90 p-2 text-xs border border-slate-800 backdrop-blur-md">
            <span className="font-semibold text-slate-400">Filter:</span>
            <button
              type="button"
              onClick={() => setFilterType("all")}
              className={`rounded px-2 py-0.5 text-[11px] transition ${
                filterType === "all" ? "bg-slate-700 text-white font-medium" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              All ({currentNodes.length})
            </button>
            <button
              type="button"
              onClick={() => setFilterType("goal")}
              className={`rounded px-2 py-0.5 text-[11px] transition ${
                filterType === "goal" ? "bg-emerald-600 text-white font-medium" : "text-emerald-400 hover:text-emerald-300"
              }`}
            >
              Goals ({currentNodes.filter((n) => n.is_goal).length})
            </button>
            <button
              type="button"
              onClick={() => setFilterType("dead_end")}
              className={`rounded px-2 py-0.5 text-[11px] transition ${
                filterType === "dead_end" ? "bg-rose-600 text-white font-medium" : "text-rose-400 hover:text-rose-300"
              }`}
            >
              Dead Ends ({currentNodes.filter((n) => n.is_dead_end).length})
            </button>
            <input
              type="text"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Search facts (e.g. on, clear)..."
              className="rounded border border-slate-700 bg-slate-800 px-2 py-0.5 text-[11px] text-slate-200 placeholder-slate-500 focus:outline-none"
            />
          </div>

          {/* Color Key Legend Overlay */}
          <div className="absolute bottom-3 left-3 z-10 flex flex-wrap items-center gap-3 rounded-lg bg-slate-900/90 px-3 py-1.5 text-[11px] border border-slate-800 backdrop-blur-sm text-slate-300">
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-cyan-400 shadow-sm" /> Initial
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-sm" /> Goal
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-400 shadow-sm" /> Dead End
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full border-2 border-dashed border-amber-400" /> Frontier (Open)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full border-2 border-cyan-400" /> Explored (Closed)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 ring-2 ring-emerald-300" /> Optimal Path
            </span>
          </div>

          {/* SVG Canvas */}
          <svg className="w-full h-full flex-1 cursor-grab active:cursor-grabbing">
            <defs>
              <marker
                id="arrowhead"
                markerWidth="8"
                markerHeight="6"
                refX="18"
                refY="3"
                orient="auto"
              >
                <polygon points="0 0, 8 3, 0 6" fill="#475569" />
              </marker>
              <marker
                id="arrowhead-cycle"
                markerWidth="8"
                markerHeight="6"
                refX="18"
                refY="3"
                orient="auto"
              >
                <polygon points="0 0, 8 3, 0 6" fill="#c084fc" />
              </marker>
              <marker
                id="arrowhead-solution"
                markerWidth="10"
                markerHeight="8"
                refX="20"
                refY="4"
                orient="auto"
              >
                <polygon points="0 0, 10 4, 0 8" fill="#10b981" />
              </marker>
            </defs>

            <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
              {/* Edges */}
              {currentEdges.map((edge, idx) => {
                const s = nodePositions[edge.source];
                const t = nodePositions[edge.target];
                if (!s || !t) return null;

                const edgeKey = `${edge.source}->${edge.target}`;
                const isSolutionEdge = activeSimStep ? activeSimStep.solutionEdgeKeys.has(edgeKey) : false;
                const isCycle = edge.is_cycle;

                // Curved Bézier path for cycles or straight for forward transitions
                const pathData = isCycle
                  ? `M ${s.x} ${s.y} Q ${(s.x + t.x) / 2 + 35} ${(s.y + t.y) / 2 - 35} ${t.x} ${t.y}`
                  : `M ${s.x} ${s.y} L ${t.x} ${t.y}`;

                return (
                  <g key={`edge-${idx}`}>
                    <path
                      d={pathData}
                      fill="none"
                      stroke={
                        isSolutionEdge
                          ? "#10b981"
                          : isCycle
                          ? "#c084fc"
                          : "#334155"
                      }
                      strokeWidth={isSolutionEdge ? 3.5 : isCycle ? 1.8 : 1.2}
                      strokeDasharray={isCycle ? "4 3" : undefined}
                      markerEnd={
                        isSolutionEdge
                          ? "url(#arrowhead-solution)"
                          : isCycle
                          ? "url(#arrowhead-cycle)"
                          : "url(#arrowhead)"
                      }
                      className={isSolutionEdge ? "filter drop-shadow-[0_0_6px_rgba(16,185,129,0.7)]" : undefined}
                    />
                  </g>
                );
              })}

              {/* Nodes */}
              {currentNodes.map((node) => {
                const pos = nodePositions[node.id];
                if (!pos) return null;

                const isSelected = node.id === selectedNodeId;
                const isMatchingFilter = filteredNodeIds.has(node.id);

                // Simulation highlights
                const isCurrentSimNode = activeSimStep ? activeSimStep.currentNodeId === node.id : false;
                const isFrontierSimNode = activeSimStep ? activeSimStep.frontierNodeIds.includes(node.id) : false;
                const isClosedSimNode = activeSimStep ? activeSimStep.closedNodeIds.includes(node.id) : false;
                const isSolutionSimNode = activeSimStep ? activeSimStep.solutionPathNodeIds.includes(node.id) : false;

                let fillColor = "#475569"; // slate default
                let strokeColor = "#334155";
                let radius = 13;

                if (node.is_initial) {
                  fillColor = "#0284c7"; // cyan/blue
                  strokeColor = "#38bdf8";
                  radius = 16;
                } else if (node.is_goal) {
                  fillColor = "#059669"; // emerald
                  strokeColor = "#34d399";
                  radius = 17;
                } else if (node.is_dead_end) {
                  fillColor = "#e11d48"; // rose
                  strokeColor = "#f43f5e";
                  radius = 14;
                } else if (node.is_truncated_boundary) {
                  fillColor = "#d97706"; // amber
                  strokeColor = "#fbbf24";
                  radius = 14;
                }

                return (
                  <g
                    key={`node-${node.id}`}
                    transform={`translate(${pos.x}, ${pos.y})`}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedNodeId(node.id);
                    }}
                    onMouseEnter={() => setHoveredNodeId(node.id)}
                    onMouseLeave={() => setHoveredNodeId(null)}
                    className="cursor-pointer"
                    opacity={isMatchingFilter ? 1 : 0.25}
                  >
                    {/* Stable Selection or Hover Halo (NO transform scale vibration) */}
                    {(isSelected || hoveredNodeId === node.id) && (
                      <circle
                        r={radius + 5}
                        fill="none"
                        stroke={isSelected ? "#38bdf8" : "#94a3b8"}
                        strokeWidth={2}
                        strokeDasharray={isSelected ? undefined : "3 3"}
                        className="pointer-events-none"
                      />
                    )}

                    {/* Active Expanding Node Halo */}
                    {isCurrentSimNode && (
                      <circle
                        r={radius + 6}
                        fill="none"
                        stroke="#06b6d4"
                        strokeWidth={2.5}
                        strokeDasharray="4 2"
                        className="pointer-events-none"
                      />
                    )}

                    {/* Frontier / Open Set Ring */}
                    {isFrontierSimNode && !isCurrentSimNode && (
                      <circle
                        r={radius + 3.5}
                        fill="none"
                        stroke="#f59e0b"
                        strokeWidth={2}
                        strokeDasharray="3 2"
                        className="pointer-events-none"
                      />
                    )}

                    {/* Explored / Closed Set Ring */}
                    {isClosedSimNode && !isCurrentSimNode && !isSolutionSimNode && (
                      <circle
                        r={radius + 3}
                        fill="none"
                        stroke="#38bdf8"
                        strokeWidth={1.5}
                        opacity={0.65}
                        className="pointer-events-none"
                      />
                    )}

                    {/* Optimal Solution Path Halo */}
                    {isSolutionSimNode && (
                      <circle
                        r={radius + 4.5}
                        fill="none"
                        stroke="#10b981"
                        strokeWidth={2.5}
                        className="pointer-events-none filter drop-shadow-[0_0_5px_rgba(16,185,129,0.8)]"
                      />
                    )}

                    {/* Main Node Body */}
                    <circle
                      r={radius}
                      fill={
                        isSolutionSimNode
                          ? "#059669"
                          : isCurrentSimNode
                          ? "#0284c7"
                          : fillColor
                      }
                      stroke={
                        isSelected
                          ? "#ffffff"
                          : isCurrentSimNode
                          ? "#38bdf8"
                          : isSolutionSimNode
                          ? "#34d399"
                          : strokeColor
                      }
                      strokeWidth={isSelected ? 3 : 1.5}
                      className="filter drop-shadow-md"
                    />

                    <text
                      textAnchor="middle"
                      dy="4"
                      fontSize="9"
                      fill="#ffffff"
                      fontWeight="bold"
                      fontFamily="monospace"
                      className="pointer-events-none select-none"
                    >
                      {node.depth}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>

          {currentNodes.length === 0 && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-6 bg-slate-950/70 backdrop-blur-sm">
              <span className="text-sm font-semibold text-slate-300 mb-1">
                No Reachable States Loaded
              </span>
              <p className="max-w-md text-xs text-slate-400 mb-4">
                Execute a task from the Mission Control tab, or choose a domain above and click &quot;Explore State Space&quot; to compute the reachable DAG.
              </p>
              <button
                type="button"
                onClick={handleEnumerateStandalone}
                className="rounded-lg bg-cyan-600 px-4 py-2 text-xs font-semibold text-white shadow-lg hover:bg-cyan-500 transition"
              >
                Enumerate Sample State Space
              </button>
            </div>
          )}
        </div>

        {/* Side Inspector & Local Transition Subgraph Panel */}
        <div className="lg:col-span-4 flex flex-col rounded-2xl border border-slate-800 bg-slate-900/90 p-5 shadow-2xl backdrop-blur-md overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
            <h3 className="text-sm font-bold uppercase tracking-wider text-cyan-400">
              State & Search Inspector
            </h3>
            {selectedNode && (
              <span className="font-mono text-xs rounded bg-slate-800 px-2 py-0.5 text-slate-300">
                {selectedNode.id}
              </span>
            )}
          </div>

          {selectedNode ? (
            <div className="flex flex-col gap-4 overflow-y-auto pr-1">
              {/* Node Metadata Badges */}
              <div className="flex flex-wrap gap-1.5">
                {selectedNode.is_initial && (
                  <span className="rounded bg-cyan-500/20 px-2 py-0.5 text-[10px] font-bold text-cyan-300 border border-cyan-500/30">
                    INITIAL STATE (s0)
                  </span>
                )}
                {selectedNode.is_goal && (
                  <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] font-bold text-emerald-300 border border-emerald-500/30">
                    GOAL SATISFIED
                  </span>
                )}
                {selectedNode.is_dead_end && (
                  <span className="rounded bg-rose-500/20 px-2 py-0.5 text-[10px] font-bold text-rose-300 border border-rose-500/30">
                    DEAD END STATE
                  </span>
                )}
                {selectedNode.is_truncated_boundary && (
                  <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-500/30">
                    FRONTIER BOUNDARY
                  </span>
                )}
                <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-semibold text-slate-400">
                  Depth: {selectedNode.depth}
                </span>
              </div>

              {/* HEURISTIC & EVALUATION CARD */}
              <div className="rounded-xl border border-slate-700/60 bg-slate-950 p-3 flex flex-col gap-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-cyan-400">
                  Search Evaluation Function (f = g + h)
                </span>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="rounded bg-slate-900 p-2 border border-slate-800">
                    <span className="block text-[10px] text-slate-400">g(n) Cost</span>
                    <span className="font-mono text-sm font-bold text-indigo-300">
                      {selectedNode.depth}
                    </span>
                  </div>
                  <div className="rounded bg-slate-900 p-2 border border-slate-800">
                    <span className="block text-[10px] text-slate-400">h(n) Heuristic</span>
                    <span className="font-mono text-sm font-bold text-amber-300">
                      {heuristicDistances[selectedNode.id] === Infinity ? "∞" : heuristicDistances[selectedNode.id] ?? 0}
                    </span>
                  </div>
                  <div className="rounded bg-slate-900 p-2 border border-slate-800">
                    <span className="block text-[10px] text-slate-400">f(n) Total</span>
                    <span className="font-mono text-sm font-bold text-emerald-300">
                      {heuristicDistances[selectedNode.id] === Infinity
                        ? "∞"
                        : selectedNode.depth + (heuristicDistances[selectedNode.id] ?? 0)}
                    </span>
                  </div>
                </div>
                <p className="text-[10px] text-slate-400 italic">
                  Admissible backward distance estimate to nearest goal. Guarantees A* optimality under tree/graph search.
                </p>
              </div>

              {/* LOCAL TOPOLOGY SUBGRAPH (Flow beside the state space graph) */}
              <div className="flex flex-col gap-2 rounded-xl border border-slate-800 bg-slate-950 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Local Transition Subgraph
                  </span>
                  <span className="text-[10px] font-mono text-cyan-400">
                    {incomingTransitions.length} in · {outgoingTransitions.length} out
                  </span>
                </div>
                
                {/* SVG Mini Neighborhood Diagram */}
                <div className="w-full h-24 bg-slate-900/60 rounded-lg border border-slate-800/80 flex items-center justify-center relative overflow-hidden">
                  <svg className="w-full h-full">
                    {/* Incoming links */}
                    {incomingTransitions.slice(0, 3).map((e, idx) => {
                      const y = 20 + idx * 24;
                      return (
                        <g key={`in-${idx}`}>
                          <line x1={40} y1={y} x2={130} y2={48} stroke="#0ea5e9" strokeWidth={1.5} markerEnd="url(#arrowhead)" />
                          <circle cx={40} cy={y} r={8} fill="#0369a1" stroke="#38bdf8" strokeWidth={1} />
                          <text x={40} y={y + 3} textAnchor="middle" fontSize={8} fill="#fff" fontFamily="monospace">
                            {e.source.replace("state_", "s")}
                          </text>
                        </g>
                      );
                    })}

                    {/* Central selected node */}
                    <circle cx={145} cy={48} r={14} fill="#0284c7" stroke="#ffffff" strokeWidth={2.5} className="filter drop-shadow-md" />
                    <text x={145} y={52} textAnchor="middle" fontSize={9} fill="#fff" fontWeight="bold" fontFamily="monospace">
                      {selectedNode.id.replace("state_", "s")}
                    </text>

                    {/* Outgoing links */}
                    {outgoingTransitions.slice(0, 3).map((e, idx) => {
                      const y = 20 + idx * 24;
                      return (
                        <g key={`out-${idx}`}>
                          <line x1={160} y1={48} x2={250} y2={y} stroke="#6366f1" strokeWidth={1.5} markerEnd="url(#arrowhead)" />
                          <circle cx={250} cy={y} r={8} fill="#4338ca" stroke="#818cf8" strokeWidth={1} />
                          <text x={250} y={y + 3} textAnchor="middle" fontSize={8} fill="#fff" fontFamily="monospace">
                            {e.target.replace("state_", "s")}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                </div>
              </div>

              {/* State SHA-256 Hash */}
              <div className="rounded-lg border border-slate-800 bg-slate-950 p-2.5">
                <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                  Canonical SHA-256 Hash
                </span>
                <span className="font-mono text-[11px] text-cyan-300 break-all select-all">
                  {selectedNode.state_hash || selectedNode.id}
                </span>
              </div>

              {/* Active Symbolic Facts */}
              <div className="flex flex-col gap-1.5">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Active Symbolic Facts ({(selectedNode.facts_summary || []).length})
                </span>
                <div className="max-h-40 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950 p-2.5 flex flex-col gap-1">
                  {(selectedNode.facts_summary || []).length > 0 ? (
                    (selectedNode.facts_summary || []).map((factStr, idx) => (
                      <span
                        key={idx}
                        className="font-mono text-xs text-emerald-300 bg-emerald-950/20 px-2 py-0.5 rounded border border-emerald-900/30"
                      >
                        {factStr}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-500 italic">No facts recorded.</span>
                  )}
                </div>
              </div>

              {/* Incoming Transitions */}
              <div className="flex flex-col gap-1.5">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Incoming Transitions ({incomingTransitions.length})
                </span>
                <div className="max-h-32 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950 p-2 flex flex-col gap-1.5">
                  {incomingTransitions.length > 0 ? (
                    incomingTransitions.map((e, idx) => (
                      <div
                        key={idx}
                        onClick={() => setSelectedNodeId(e.source)}
                        className="cursor-pointer flex items-center justify-between rounded bg-slate-900 p-1.5 text-xs hover:bg-slate-800 transition"
                      >
                        <span className="font-mono font-medium text-cyan-400">
                          {e.action_name}
                        </span>
                        <span className="font-mono text-[10px] text-slate-500">
                          from {e.source}
                        </span>
                      </div>
                    ))
                  ) : (
                    <span className="text-xs text-slate-500 italic p-1">
                      {selectedNode.is_initial ? "Initial root node (no parent)." : "None recorded."}
                    </span>
                  )}
                </div>
              </div>

              {/* Outgoing Transitions */}
              <div className="flex flex-col gap-1.5">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Enabled Actions ({outgoingTransitions.length})
                </span>
                <div className="max-h-32 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950 p-2 flex flex-col gap-1.5">
                  {outgoingTransitions.length > 0 ? (
                    outgoingTransitions.map((e, idx) => (
                      <div
                        key={idx}
                        onClick={() => setSelectedNodeId(e.target)}
                        className="cursor-pointer flex items-center justify-between rounded bg-slate-900 p-1.5 text-xs hover:bg-slate-800 transition"
                      >
                        <span className="font-mono font-medium text-indigo-400">
                          {e.action_name}
                        </span>
                        <span className="font-mono text-[10px] text-slate-500">
                          to {e.target} {e.is_cycle && "(cycle)"}
                        </span>
                      </div>
                    ))
                  ) : (
                    <span className="text-xs text-rose-400/90 italic p-1">
                      No outgoing actions (Dead End or Frontier).
                    </span>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-1 items-center justify-center text-center p-6 text-slate-500 text-xs">
              Click any node in the graph to inspect its symbolic state facts, search heuristics (g, h, f), incoming transitions, and enabled actions.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
