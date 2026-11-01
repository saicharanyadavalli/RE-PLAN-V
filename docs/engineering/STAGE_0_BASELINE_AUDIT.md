# STAGE 0: BASELINE AUDIT & ARCHITECTURE INVENTORY

**Date:** 2026-11-01  
**Current HEAD SHA:** `2da99387a4fd1a4f4f1cb3734eafac820da4b711`  
**Active Branch:** `main`  
**Python Runtime:** Python 3.12.10 (virtual environment: `.venv`)  
**Frontend Runtime:** Next.js 15.5.25 App Router, React 19, TypeScript 5, Tailwind CSS 3.4  
**Audit Purpose:** Comprehensive evidence-based inventory of repository capabilities, architecture, tests, and priority defects before staged execution.

---

## 1. System Inventory & Module Responsibilities

### 1.1 Core Symbolic Engine (`core/`)
- `core/contracts.py`: Canonical Pydantic data schemas for facts, ground actions, plans, counterexamples, repairs, and evaluation metrics.
- `core/domains/`:
  - `base.py`: `BaseDomain` abstract class governing declarative action schemas, preconditions, STRIPS positive/negative effects, state invariants, and canonical SHA-256 state hashing.
  - `registry.py`: Thread-safe `DomainRegistry` managing registered domain instances and metadata summaries.
  - `blocks_world.py`: Classical 4-operator Blocks World (`pick_up`, `put_down`, `stack`, `unstack`).
  - `grid_world.py`: 2D spatial coordinate navigation and item transfer (`move`, `pick`, `drop`).
  - `household.py`: Multi-room domestic service agent with container doors and surfaces (`navigate_room`, `open_container`, `close_container`, etc.).
  - `warehouse.py`: AGV transit and shelf SKU management (`transit`, `retrieve_sku`, `deposit_sku`).
  - `scheduling.py`: Discrete machine allocation with DAG job prerequisites (`schedule_independent_job`, `schedule_dependent_job`).
  - `software_workflow.py`: Software CI/CD release governance (`run_unit_tests`, `run_security_scan`, `build_artifact`, `grant_approval`, `deploy_to_environment`).
- `core/graph/`:
  - `models.py`: Data Transfer Objects for `GraphNode`, `GraphEdge`, `GraphStats`, and `ReachableStateGraph` with Cytoscape export.
  - `enumerator.py`: Model B worklist BFS state-space enumerator with SHA-256 state deduplication, cycle detection, and dead-end discovery.
  - `tracer.py`: Search algorithm tracer (`A*`, `BFS`, `Greedy Best-First`).
  - `exporter.py`: Cytoscape and JSON export utilities.
- `core/search/`: Implementations of $A^*$ with RPG $h_{\max}$ heuristic, Breadth-First Search (BFS), and Greedy Best-First Search.
- `core/verification/`: Independent STRIPS verifier simulating ground action sequences against domain preconditions and invariants.
- `core/counterexamples/`: Minimal witness generator identifying earliest action violations.
- `core/attribution/`: 5-class fault classification engine (`PLANNING_ERROR`, `PERCEPTION_ERROR`, `FORMALIZATION_ERROR`, `ENVIRONMENT_CHANGE`, `UNKNOWN_AMBIGUOUS`).
- `core/repair/`: CEGIS constraint synthesis engine producing state-scoped and action-scoped repair constraints.
- `core/replanning/`: Bounded replanning loop with loop detection and cycle prevention.

### 1.2 Interpretation & Formalisation (`interpretation/`)
- `interpretation/router.py`: Domain Router categorizing natural-language instructions across the 6 canonical domains, checking for missing information, and detecting out-of-scope tasks.
- `interpretation/llm/`: LLM adapters for deterministic mock mode, Ollama, LM Studio, and live Gemini/OpenAI endpoints.
- `interpretation/validator/`: Schema consistency validation between proposals and domain definitions.

### 1.3 Web & API Layer (`app/`)
- `app/api/routes.py`: FastAPI REST routes including `/api/domains`, `/api/graph/enumerate`, `/api/pipeline/run`, and benchmark endpoints.
- `app/api/websocket.py`: WebSocket endpoint `/ws/pipeline` streaming execution stages, domain routing, and chunked graph node/edge batches.
- `app/services/pipeline.py`: Main `PipelineOrchestrator` integrating interpretation, validation, planning, verification, and repair.

### 1.4 Frontend Mission Control (`frontend/`)
- Next.js 15 App Router web client with 5 major tabs:
  1. **Mission Control (`demo`)**: Text-first input, tabletop visualizer, and execution stepper.
  2. **State Space Explorer (`graph`)**: Model B 2D pan/zoom interactive reachable-state visualizer with fact inspector.
  3. **Domain Studio (`domains`)**: Domain specifications, operators, predicates, and sample instructions.
  4. **Research Benchmark (`benchmark`)**: Evaluation metrics and confusion matrices.
  5. **10 Inviolable Rules (`architecture`)**: Formal principles.

---

## 2. Baseline Test Execution Results

- **Command:** `.venv\Scripts\python.exe -m pytest tests/ -q`
- **Result:** **175 passed, 2 warnings in 40.23s**
- **Test Suite Breakdown:**
  - `tests/unit/test_domain_framework.py`: 3 passed
  - `tests/unit/test_all_domains.py`: 8 passed
  - `tests/unit/test_domain_router.py`: 8 passed
  - `tests/unit/test_state_space_explorer.py`: 2 passed
  - `tests/unit/test_multi_domain_benchmarks.py`: 2 passed
  - `tests/unit/test_attribution_matrix.py`: 4 passed
  - `tests/unit/test_krr.py`: 12 passed
  - `tests/property/test_properties.py`: 10 passed
  - `tests/integration/test_multi_domain_pipeline.py`: 3 passed
  - `tests/integration/test_websocket_streaming.py`: 2 passed
  - `tests/integration/test_pipeline_e2e.py`: 13 passed
  - Legacy regression suites: 108 passed

---

## 3. Priority Defect Register & Resolution Plan

| Defect ID | Severity | Module | Description | Resolution Plan |
| :--- | :--- | :--- | :--- | :--- |
| **D-01** | High | `app/api/routes.py` | Standalone graph enumeration calls router without respecting explicit `domain_id`. | If `domain_id != "auto"`, use explicit domain directly and do not re-route to another domain. |
| **D-02** | High | `interpretation/router.py` | Negative constraints hardcode `holding(...)` regardless of domain/action; router uses simplistic keyword regex. | Parse negative constraints into proper typed predicates and action prohibitions; handle conjunctions, explicit initial facts, and targeted clarifications. |
| **D-03** | High | `core/graph/enumerator.py` | Frontier budget checking at loop start can trigger false `MAX_NODES_EXCEEDED` on an already-exhausted worklist; actions are unsorted. | Canonicalize action ordering; check whether worklist was truly exhausted before flagging budget truncation; tag unexpanded boundary states accurately. |
| **D-04** | Medium | `benchmark/generator/multi_domain_generator.py` | Fixed state estimates used instead of Model B measured counts across complexity tiers. | Integrate Model B graph enumeration to measure actual reachable state and transition counts per tier. |
| **D-05** | Medium | `evaluation/metrics/collector.py` | `recovery_advantage_over_regeneration` hardcoded to `0.0`. | Compute empirical recovery advantage dynamically: $\text{Advantage} = \text{Rate}_{\text{Ours}} - \text{Rate}_{\text{Regen}}$. |
| **D-06** | Medium | `README.md` | Stale test count badge (143 vs 175) and overstated absolute safety claims ("100% Safe Robotic Dispatch"). | Update badge to 175; replace absolute claims with precise model-relative verification language. |
| **D-07** | Medium | `frontend/components/StateSpaceExplorer.tsx` | Optimistic `is_complete: true` fallback if backend stats are missing. | Set `is_complete: false` when backend stats are undefined; display truthful status. |

---

## 4. Gate 0 Acceptance

The baseline audit is complete and verified against reproducible command executions. We proceed to Stage 1.
