# RE-PLAN-V: Main Branch Technical Baseline Audit (Stage 1)

**Audit Date**: November 2026  
**Audited Commit Ref**: `4e908f4d8ec12981720e08cbff2d81c3986d03e2`  
**Repository Branch**: `main` (sole canonical branch, fast-forwarded from `2da9938`)  
**Auditing Authority**: Orchestrator & Multi-Agent Inspection Team  

---

## 1. Executive Summary

Following Stage 0 reconciliation, the accepted hardening commit `4e908f4` was successfully integrated directly into `main` via fast-forward merge and pushed to `origin/main`. The obsolete remote and local feature branch `feature/staged-hardening-and-graph-explorer` was cleanly deleted after proving exact SHA parity.

### Executable Verification Summary at Baseline:
1. **Focused Test Suite**: 30/30 passed in 1.52s (`pytest tests/unit/test_state_space_explorer.py tests/unit/test_domain_router.py tests/unit/test_all_domains.py tests/unit/test_multi_domain_benchmarks.py tests/unit/test_attribution_matrix.py tests/integration/test_multi_domain_pipeline.py`).
2. **Full Regression Suite**: 181/181 passed in 31.74s (`pytest`).
3. **Frontend Production Build**: Succeeded (`npm run build` in `frontend/`, Next.js 15.5.25 prerendered 4 static routes with 0 errors).
4. **Benchmark Reproduction**: Succeeded in 1.13s (`python scripts/reproduce_results.py`).
5. **Branch Hygiene**: Only `main` exists locally and on remote `origin`.

While test execution and builds are currently green, deep code inspection reveals load-bearing architectural gaps, synthetic benchmark limitations, and component coupling that must be addressed across Stages 2–9.

---

## 2. Agent 1.1 — Core Architecture Audit

### 2.1 Contracts & State Representations (`core/contracts.py`, `core/world/`)
- **Status**: `VERIFIED` with minor typing redundancies.
- **Findings**:
  - `FactSchema`, `SymbolicStateSchema`, `GroundActionSchema`, `PlanSchema`, and `VerificationResultSchema` are well-structured Pydantic models with frozen configurations for immutability.
  - Logical facts are represented cleanly with `predicate`, `arguments`, and `is_negated`.
  - In `core/world/predicates.py`, a separate `Fact` class exists alongside `FactSchema` in `core/contracts.py`. Round-trip conversions (`Fact.from_schema()` and `Fact.to_schema()`) exist, but bidirectional mapping must remain strictly synchronized to prevent schema drift.

### 2.2 Domain Registry & Semantic Models (`core/domains/`)
- **Status**: `PARTIAL`
- **Findings**:
  - All 6 domains (`blocks_world`, `grid_world`, `household_robotics`, `warehouse`, `scheduling`, `software_workflow`) are registered in `core/domains/registry.py` inheriting from `BaseDomain`.
  - However, transition semantics in `core/actions/domain.py` still contains legacy hardcoded domain definitions (`create_blocks_world_domain()`, `create_gridworld_domain()`), causing a split architecture where some services use `core/domains/registry.py` while others use `core/actions/domain.py`.
  - Invariant and hard-constraint validation is supported on `BaseDomain` and `SymbolicProblem`, but not all 6 domains implement exhaustive negative constraint checks for custom prohibitions.

### 2.3 Graph Enumerator (`core/graph/enumerator.py`)
- **Status**: `IMPLEMENTED_UNVERIFIED` (partially hardened)
- **Findings**:
  - Canonical action sorting (`applicable = sorted(..., key=lambda a: a.to_string())`) ensures deterministic enumeration.
  - Seen edges (`edge_sig = f"{curr_id}::{action.to_string()}::{next_id}"`) prevent duplicate edge creation while preserving multiple edges with distinct actions between the same pair of states.
  - Cycles are detected and counted (`cycles_detected += 1`, `duplicate_states_pruned += 1`).
  - Boundary tagging is implemented: when `is_complete` is `False`, unexpanded nodes in `nodes` are marked `is_boundary = True`.
  - **Edge Case Gap**: When `max_edges` is reached within the inner action loop, truncation occurs, but remaining legal transitions for the current node are skipped without explicitly marking whether that node was partially expanded or fully expanded.
  - Exact limits testing (e.g., node cap reached exactly, edge cap reached exactly, timeout triggering) requires dedicated boundary property tests.

### 2.4 Search Algorithms & Planners (`core/search/`)
- **Status**: `VERIFIED`
- **Findings**:
  - `AStarPlanner`, `BFSPlanner`, and `BestFirstPlanner` correctly inherit from `BasePlanner`.
  - A* uses admissible heuristics (`GoalCountHeuristic`), properly updates `g_score`, and maintains open and closed sets.
  - Graph enumeration (Model B) is cleanly separated from individual planner search trajectories.

### 2.5 Verification, Counterexamples, and Repair (`core/verification/`, `core/counterexamples/`, `core/attribution/`, `core/repair/`, `core/replanning/`)
- **Status**: `PARTIAL`
- **Findings**:
  - `PlanVerifier` replays plan actions step-by-step against STRIPS preconditions and effects, generating precise `VerificationResultSchema`.
  - `CounterexampleGenerator` extracts minimal witness states with offending actions and violated predicates.
  - `RepairGenerator` produces state/action-scoped `RepairConstraint` instances (`FORBID_ACTION_IN_STATE`, `FORBID_GROUND_ACTION`, `STATE_BELIEF_CORRECTION`, etc.).
  - **Ablation Inconsistency**: When `without_attribution` is evaluated, the fallback repair logic in `RepairGenerator` generates `FORBID_ACTION_IN_STATE`. In simple benchmark problems, forbidding the action in that state happens to successfully repair the plan, causing the ablation to show 100% repair success even without attribution.
  - In `without_verifier`, the ablation configuration blindly returns `is_valid: True` and `success: True`, which is a misleading definition of success rather than a true measurement of validity.

---

## 3. Agent 1.2 — NLP and Pipeline Audit

### 3.1 Domain Router (`interpretation/router.py`)
- **Status**: `PARTIAL` / `MISLEADING`
- **Findings**:
  - `DomainRouter.route()` maps text prompts using keyword matching against `supported_patterns`.
  - Explicit domain selection (`explicit_domain_id`) properly bypasses scoring and respects user selection.
  - Clarification detection exists for missing package origin/destination or ambiguous moves.
  - **Critical Gap**: In `_extract_household`, `_extract_warehouse`, `_extract_scheduling`, and `_extract_software`, entities and initial facts are largely hardcoded template defaults (e.g. `mug`, `kitchen`, `shelf_1`, `commit_v1`) rather than dynamically extracted from the natural language prompt.
  - **Negative Constraint Scoping**: Negation regex maps "do not move/touch/visit X" to hardcoded positive predicates (e.g. `holding(X)` for blocks, `at(agent, X)` for grid, `carrier_at(carrier_1, X)` for warehouse). This is a convenient surrogate, but not a general logical negation encoding.

### 3.2 Pipeline Orchestration (`app/services/pipeline.py`)
- **Status**: `BROKEN` (for multi-domain direct execution)
- **Findings**:
  - `PipelineOrchestrator` is hardcoded to `self.domain = create_blocks_world_domain()`.
  - It does not accept a `domain_id` parameter or query `DomainRegistry` during standard `run()`.
  - While `websocket.py` and `routes.py` contain multi-domain adapters for graph enumeration and routing, the core `PipelineOrchestrator.run()` pipeline cannot execute the other 5 domains without blocks world hardcoding.

### 3.3 Endpoints & API Contracts (`app/api/routes.py`, `app/api/websocket.py`)
- **Status**: `PARTIAL`
- **Findings**:
  - `/api/pipeline/run`: Executes only blocks world via `PipelineOrchestrator`.
  - `/api/graph/enumerate`: Correctly interfaces with `DomainRegistry` and `CompleteReachableGraphEnumerator` across all 6 domains.
  - `/api/llm/formalize`: Hardcoded to `create_blocks_world_domain()`.
  - WebSocket `/ws/pipeline`: Includes domain auto-routing, but passes `orchestrator.domain` (blocks world) to `active_provider.interpret_with_retry()` and validator.

---

## 4. Agent 1.3 — Frontend Audit

### 4.1 Mission Control & Task Control (`frontend/components/TaskControlPanel.tsx`)
- **Status**: `VERIFIED`
- **Findings**:
  - Provides a natural-language textbox input, domain selector (Auto + 6 domains), algorithm selector (A*, BFS, Best-First), provider selector (Mock, LM Studio, Gemini, OpenAI), and graph enumeration toggle.
  - Presets exist for all 6 domains.
  - Properly communicates with parent page via `onRun(req)`.

### 4.2 State Space Explorer (`frontend/components/StateSpaceExplorer.tsx`)
- **Status**: `VERIFIED` with minor port hardcoding.
- **Findings**:
  - Stratified hierarchical layout by depth with panning, zooming, and node selection.
  - Supports dual modes: streamed WebSocket nodes/edges and standalone REST `/api/graph/enumerate`.
  - Correctly colors initial (emerald), goal (amber), dead-end (rose), boundary (sky dashed), and standard (slate) nodes.
  - Fallback logic sets `is_complete: false` with `truncation_reason: "STATS_OMITTED_BY_BACKEND"` when stats are not provided, avoiding optimistic completeness claims.
  - Hardcoded URL `http://${host}:8080/api/graph/enumerate` should respect configurable API base URLs.

### 4.3 Domain Studio & Academic Defense (`frontend/components/DomainStudio.tsx`, `frontend/components/AcademicDefenseModal.tsx`)
- **Status**: `VERIFIED`
- **Findings**:
  - Fetches registered domain schemas dynamically from `/api/domains`.
  - "Try Example" populates TaskControlPanel prompt and domain selection.

---

## 5. Agent 1.4 — Benchmark and Evidence Audit

### 5.1 Multi-Domain Benchmark Generator (`benchmark/generator/multi_domain_generator.py`)
- **Status**: `PARTIAL`
- **Findings**:
  - Defines `ComplexityTier`: `TINY` (<50 states), `SMALL` (50–200), `MEDIUM` (200–1000), `LARGE` (1000–3000), `STRESS` (>3000).
  - Includes `measure_state_space()` using `CompleteReachableGraphEnumerator`.
  - Problem instances generated for `TINY` produced measured state counts across all 6 domains (4 to 9 states).
  - Higher tiers (`MEDIUM`, `LARGE`, `STRESS`) have estimated state counts in code, but the generator has not yet generated and verified complete reachability models for all 6 domains at 100–3000+ states.

### 5.2 Metrics Collector & Recovery Advantage (`evaluation/metrics/collector.py`)
- **Status**: `BROKEN` (silent negative clamping)
- **Findings**:
  - Line 68: `rec_adv = max(0.0, repair_rate - self.baseline_regeneration_rate)`.
  - Clamping recovery advantage to `0.0` prevents detecting negative recovery advantage (when repair performs worse than regeneration). This violates the requirement to preserve signed difference.

### 5.3 Ablation Study Rigor (`evaluation/ablations/configurations.py`)
- **Status**: `MISLEADING`
- **Findings**:
  - `without_verifier` returns hardcoded `is_valid: True` and `success: True`. This is not a measured evaluation of plan validity; it measures acceptance without checking.

### 5.4 Fault Attribution Study (`evaluation/experiments/fault_matrix.py`)
- **Status**: `IMPLEMENTED_UNVERIFIED` (synthetic perfection)
- **Findings**:
  - 100% accuracy on 50 instances (10/class) is achieved because each class is constructed with perfectly disjoint synthetic signals (e.g. `environment_deltas` present only for ENVIRONMENT_CHANGE; `observed_facts != ground_truth_facts` only for PERCEPTION_ERROR).
  - Lacks realistic ambiguous/overlapping failure scenarios.

---

## 6. Agent 1.5 — Independent Test Audit

### 6.1 Test Coverage Analysis
- **Current Total**: 181 backend tests passing.
- **Coverage Areas**:
  - Actions, world model, predicates, resolution KRR: strong unit coverage.
  - Search algorithms (A*, BFS, Best-First): regression tests verify node counts and costs.
  - Graph enumerator: 3 tests in `test_state_space_explorer.py` verify cytoscape export, cycle preservation, and action edge uniqueness.
  - Multi-domain pipeline: 5 tests in `test_multi_domain_pipeline.py` verify graph enumeration on all 6 domains.
  - Domain router: 10 tests verify routing, clarification, and negative constraints.

### 6.2 Missing Test Coverage & Edge Cases
1. **Graph Enumerator Limits**: No property tests verifying exact behavior when `max_nodes` or `max_edges` is reached at boundary conditions (e.g. `max_nodes=1`, `max_nodes=len(reachable)`).
2. **Multi-Domain Pipeline Execution**: No end-to-end test verifying full plan synthesis and independent verification through `PipelineOrchestrator` for all 6 domains (due to blocks world hardcoding).
3. **Signed Recovery Advantage**: No test ensuring negative recovery advantage is preserved when baseline outperforms repair.
4. **General Negation Parsing**: No tests for non-template negative constraints (e.g. "never stack b1 on b3", "avoid room kitchen").

---

## 7. Baseline Audit Verdict & Stage Gate 1 Assessment

- **Overall Baseline Status**: `PARTIAL`
- **Gate 1 Decision**: AUDIT COMPLETE. Baseline established. Ready to publish defect register and execute Stages 2–9.
