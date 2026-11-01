# Multi-Domain Planning, State-Space Graph Explorer, and Research Demo Redesign Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve RE-PLAN-V into a multi-domain, text-first neuro-symbolic planning platform featuring a generic domain registry across 6 domains, a complete reachable-state graph enumerator (Model B), NLP domain routing with ambiguity clarification, and an AI research mission-control frontend.

**Architecture:** A pluggable domain interface (`core/domains/`) decouples domain definitions from search algorithms and verifiers. The state-space explorer (`core/graph/`) operates directly on canonical semantic state keys to enumerate reachable states and valid transitions under strict resource budgets. An NLP domain router (`interpretation/router.py`) maps natural language instructions into domain candidates, while the WebSocket streaming layer chunks graph nodes and search events directly to an interactive Next.js 15 dashboard.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, Next.js 15, React 19, Tailwind CSS, Lucide Icons, Canvas / SVG Graph Renderer, Pytest, Asyncio.

---

## Global Constraints

- Text-only primary interaction: main user flow takes natural-language text input only; vision workflows remain isolated/optional.
- No silent world-state invention: missing preconditions or unknown locations trigger `NEEDS_CLARIFICATION`, never assumed facts.
- Model B is primary: complete reachable-state graph enumeration subject to explicit resource budgets (max nodes, max edges, timeout).
- Honest graph status: a graph is marked `COMPLETE` only when its worklist is exhausted; otherwise marked `TRUNCATED` or `LIMIT_REACHED`.
- Zero hardcoded metrics: all benchmark figures, node/edge counts, and confusion matrices must derive directly from executed runs.
- Absolute secret safety: never expose API keys or tokens in git, logs, frontend bundles, or client responses.
- Accurate safety claims: all outputs declare "verified under symbolic model assumptions", never "100% safe" or "physically guaranteed".

---

## File Structure & Module Ownership

```
core/
├── domains/
│   ├── __init__.py           # Domain registry and common exports
│   ├── base.py               # Abstract BaseDomain interface and canonical schemas
│   ├── registry.py           # DomainRegistry singleton and decorator
│   ├── blocks_world.py       # Blocks World domain implementation
│   ├── grid_world.py         # Grid World / Navigation domain implementation
│   ├── household.py          # Household Robotics abstract symbolic domain
│   ├── warehouse.py          # Warehouse Operations & Inventory Movement domain
│   ├── scheduling.py         # Scheduling & Resource Allocation domain
│   └── software_workflow.py  # Software Automation & CI/CD Workflow domain
├── graph/
│   ├── __init__.py           # Graph module exports
│   ├── models.py             # ReachableStateGraph, GraphNode, GraphEdge, GraphStats schemas
│   ├── enumerator.py         # CompleteReachableGraphEnumerator (Model B worklist algorithm)
│   ├── tracer.py             # AlgorithmSearchTracer (records actual A*/BFS expansion steps)
│   └── exporter.py           # Graph artifact exporter (JSON / Cytoscape format)
interpretation/
│   ├── router.py             # DomainRouter: NLP intent routing, ambiguity & clarification detection
│   └── schemas/              # Extended TaskProposal schemas supporting all 6 domains
app/
├── api/
│   ├── routes.py             # REST endpoints for domains, graph enumeration, and runs
│   └── websocket.py          # Chunked batch WebSocket protocol for live graph streaming
frontend/
├── app/page.tsx              # Redesigned Research Mission Control entry point
├── components/
│   ├── Navbar.tsx            # Redesigned top navigation with live status
│   ├── TaskControlPanel.tsx  # Text-only input, domain selector, algorithm & graph mode controls
│   ├── StateSpaceExplorer.tsx# Central interactive complete reachable graph visualizer (pan/zoom)
│   ├── DomainStudio.tsx      # Domain library with capabilities, actions, predicates & examples
│   ├── BenchmarkTab.tsx      # Multi-domain empirical evaluations & complexity tiers
│   ├── TabletopCanvas.tsx    # Multi-domain abstract state preview adapter
│   ├── ExecutionStepper.tsx  # Live pipeline progress stepper
│   ├── CounterexampleCard.tsx# Witness and attribution display
│   └── RepairCard.tsx        # Repair constraint and replanned sequence display
└── types/pipeline.ts         # TypeScript interfaces matching backend graph & domain DTOs
```

---

## Task Decomposition

### Task 1: Generic Domain Framework & Common Interface
**Files:**
- Create: `core/domains/base.py`
- Create: `core/domains/registry.py`
- Create: `core/domains/__init__.py`
- Test: `tests/unit/test_domain_framework.py`

**Interfaces:**
- Produces: `BaseDomain` abstract class with methods `validate_initial_state()`, `validate_goal()`, `applicable_actions()`, `apply_action()`, `check_invariants()`, `canonical_state_key()`, `render_state_summary()`.
- Produces: `DomainRegistry` with `register(domain)`, `get(domain_id)`, `list_domains()`.

- [ ] **Step 1: Write failing unit test for `BaseDomain` and `DomainRegistry`**
  Verify registering, retrieving, and validating domains.
- [ ] **Step 2: Implement `core/domains/base.py`**
  Define `BaseDomain` ABC and typed schema dataclasses.
- [ ] **Step 3: Implement `core/domains/registry.py`**
  Implement the thread-safe `DomainRegistry` with backward compatibility for `core.actions.domain`.
- [ ] **Step 4: Run tests and verify 100% pass**
  Run `.venv\Scripts\pytest.exe tests/unit/test_domain_framework.py`.

---

### Task 2: Core Domain Implementations (6 Domains)
**Files:**
- Create: `core/domains/blocks_world.py` (migrated & formalized from existing actions)
- Create: `core/domains/grid_world.py` (agent, cells, obstacles, weighted move)
- Create: `core/domains/household.py` (rooms, surfaces, containers, fragile items)
- Create: `core/domains/warehouse.py` (zones, SKUs, inventory, delivery targets)
- Create: `core/domains/scheduling.py` (jobs, machines, windows, precedence)
- Create: `core/domains/software_workflow.py` (build, test, package, deploy, approval gates)
- Test: `tests/unit/test_all_domains.py`

**Interfaces:**
- Consumes: `BaseDomain` from `core/domains/base.py`.
- Produces: 6 self-contained domain implementations registered in `DomainRegistry`.

- [ ] **Step 1: Write unit tests covering action applicability, effects, and invariants for each domain**
- [ ] **Step 2: Implement `blocks_world.py` and `grid_world.py`**
- [ ] **Step 3: Implement `household.py` and `warehouse.py`**
- [ ] **Step 4: Implement `scheduling.py` and `software_workflow.py`**
- [ ] **Step 5: Run tests and verify all 6 domains execute valid transitions deterministically**

---

### Task 3: Complete State-Space Graph Explorer (Model B)
**Files:**
- Create: `core/graph/models.py`
- Create: `core/graph/enumerator.py`
- Create: `core/graph/tracer.py`
- Create: `core/graph/exporter.py`
- Create: `core/graph/__init__.py`
- Test: `tests/unit/test_state_space_explorer.py`

**Interfaces:**
- Consumes: `BaseDomain` from `core/domains/base.py` and `SymbolicProblem` from `core/world/problem.py`.
- Produces: `CompleteReachableGraphEnumerator` computing `ReachableStateGraph` with node/edge deduplication, cycle handling, truncation detection, and stable SHA-256 IDs.
- Produces: `AlgorithmSearchTracer` tracking exact nodes expanded/generated by $A^*$, BFS, and Best-First.

- [ ] **Step 1: Write test for complete reachable graph enumeration on small instance**
  Verify exact node counts, edge counts, cycle avoidance, and goal node detection.
- [ ] **Step 2: Write test for graph truncation upon reaching node/edge limits**
  Verify status is `TRUNCATED` when budget is exceeded.
- [ ] **Step 3: Implement `core/graph/models.py`**
  Define `GraphNode`, `GraphEdge`, `GraphStats`, and `ReachableStateGraph`.
- [ ] **Step 4: Implement `core/graph/enumerator.py`**
  Implement worklist queue enumeration with canonical semantic keys, invariant validation, and limit checks.
- [ ] **Step 5: Implement `core/graph/tracer.py` and `core/graph/exporter.py`**
- [ ] **Step 6: Run tests and verify graph enumeration correctness**

---

### Task 4: Text-First NLP Domain Router & Clarification Engine
**Files:**
- Create: `interpretation/router.py`
- Modify: `interpretation/llm/mock.py`
- Modify: `interpretation/llm/live.py`
- Test: `tests/unit/test_domain_router.py`

**Interfaces:**
- Consumes: `DomainRegistry` and raw text instructions.
- Produces: `DomainRoutingResult` with status `SUPPORTED`, `NEEDS_CLARIFICATION`, `UNSUPPORTED`, or `INVALID_PROPOSAL`.
- Produces: Contextual clarification question when key facts are missing (e.g. unknown initial room, missing start cell).

- [ ] **Step 1: Write unit tests for domain candidate routing across all 6 domains**
- [ ] **Step 2: Write unit tests for ambiguity and missing-information clarification generation**
- [ ] **Step 3: Implement `interpretation/router.py`**
  Rule-based and semantic classification into candidate domains with capability check.
- [ ] **Step 4: Update `interpretation/llm/mock.py` & `live.py` to route multi-domain prompts without fact invention**
- [ ] **Step 5: Run tests and verify domain routing and clarification behavior**

---

### Task 5: Pipeline & Backend WebSocket Chunked Graph Streaming
**Files:**
- Modify: `app/services/pipeline.py`
- Modify: `app/api/routes.py`
- Modify: `app/api/websocket.py`
- Test: `tests/integration/test_multi_domain_pipeline.py`

**Interfaces:**
- Consumes: `DomainRegistry`, `DomainRouter`, `CompleteReachableGraphEnumerator`, `PipelineOrchestrator`.
- Produces: REST endpoints (`/api/domains`, `/api/graph/enumerate`, `/api/pipeline/run`).
- Produces: Chunked WebSocket events (`GRAPH_NODE_BATCH`, `GRAPH_EDGE_BATCH`, `GRAPH_ENUMERATION_COMPLETED`, `GRAPH_ENUMERATION_TRUNCATED`).

- [ ] **Step 1: Write integration tests for REST endpoints and WebSocket chunk streaming**
- [ ] **Step 2: Update `app/services/pipeline.py` to integrate generic domain registry and graph enumeration**
- [ ] **Step 3: Add new routes in `app/api/routes.py`**
- [ ] **Step 4: Update `app/api/websocket.py` with chunked node/edge emission and cancellation handling**
- [ ] **Step 5: Run tests and verify pipeline execution across all domains**

---

### Task 6: Multi-Domain Benchmarking with Complexity Tiers (100–3000 States)
**Files:**
- Create: `benchmark/generator/multi_domain_generator.py`
- Modify: `evaluation/experiments/runner.py`
- Modify: `scripts/reproduce_results.py`
- Test: `tests/unit/test_multi_domain_benchmarks.py`

**Interfaces:**
- Produces: Complexity tiers: Tiny (<50), Small (50–200), Medium (200–1000), Large (1000–3000), Stress (>3000).
- Produces: Reproducible empirical metrics per domain with fixed random seeds.

- [ ] **Step 1: Write unit tests for generating problems in each complexity tier**
- [ ] **Step 2: Implement `benchmark/generator/multi_domain_generator.py`**
- [ ] **Step 3: Update `evaluation/experiments/runner.py` and `scripts/reproduce_results.py`**
- [ ] **Step 4: Run benchmark reproduction script and verify real state generation**

---

### Task 7: Frontend Product Redesign (AI Research Mission Control)
**Files:**
- Create: `frontend/components/StateSpaceExplorer.tsx` (Central Model B 2D visualizer)
- Create: `frontend/components/DomainStudio.tsx` (Domain library cards & inspection)
- Modify: `frontend/components/Navbar.tsx`
- Modify: `frontend/components/TaskControlPanel.tsx`
- Modify: `frontend/components/BenchmarkTab.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/types/pipeline.ts`

**Interfaces:**
- Consumes: Backend WebSocket graph batches and REST API endpoints.
- Produces: 5-tab research mission control:
  1. Mission Control (text-only prompt, execution stepper, verification, repair)
  2. State Space Explorer (pan/zoom graph viewer, node inspector, complete vs truncated badge)
  3. Domain Studio (interactive library of 6 domains)
  4. Research Benchmarks (multi-domain empirical results & complexity tiers)
  5. Academic Defense (viva guide, KRR theorem proving, formal verification)

- [ ] **Step 1: Update `frontend/types/pipeline.ts` with graph, domain, and routing types**
- [ ] **Step 2: Implement `frontend/components/StateSpaceExplorer.tsx` with pan/zoom and detail panel**
- [ ] **Step 3: Implement `frontend/components/DomainStudio.tsx` displaying all 6 domains**
- [ ] **Step 4: Redesign `TaskControlPanel.tsx`, `Navbar.tsx`, and `app/page.tsx`**
- [ ] **Step 5: Verify production build: `npm run build` in `frontend/`**

---

### Task 8: Full Regression, Verification & Documentation
**Files:**
- Create: `docs/ARCHITECTURE.md`
- Create: `docs/STATE_SPACE_GRAPH.md`
- Create: `docs/DOMAIN_AUTHORING_GUIDE.md`
- Modify: `README.md`
- Modify: `VIVA_GUIDE.md`
- Modify: `docs/PROPOSAL_AUDIT_AND_PARITY.md`

- [ ] **Step 1: Run full pytest suite across all unit, property, scenario, edge, and integration tests**
- [ ] **Step 2: Run benchmark reproduction script `scripts/reproduce_results.py`**
- [ ] **Step 3: Verify backend and frontend launch cleanly**
- [ ] **Step 4: Update all documentation with multi-domain semantics and state-space graph methodology**
- [ ] **Step 5: Final acceptance verification against all 80 criteria in the prompt**
