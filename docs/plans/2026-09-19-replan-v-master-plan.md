# RE-PLAN-V Implementation Plan

> **Goal:** Build RE-PLAN-V (Reliable Explainable Multimodal Planning with Formal Verification and Counterexample-Guided Repair), a research-grade, demo-ready application with authoritative symbolic core, formal verification, counterexample generation, evidence-based fault attribution, automatic repair/replanning, untrusted neural interpretation, controlled vision, dynamic environment replanning, procedural benchmark generation, baseline comparisons, and an interactive UI.
>
> **Central Research Question:**
> *"Can counterexample-guided fault attribution and automatic repair improve recovery from initially invalid plans compared with generic plan regeneration?"*
>
> **Architecture:** A symbolic-first pipeline where neural and vision components act as untrusted proposers constrained by strict schemas. The symbolic core (states, predicates, authoritative action transitions, search algorithms) generates candidate plans. An independent formal verifier checks precondition, invariant, and constraint satisfaction. Failed plans generate structured counterexamples, feed an evidence-based fault attribution taxonomy, yield repair constraints, and trigger bounded replanning loops.
>
> **Tech Stack:** Python 3.12, Pydantic v2 (data contracts), Pytest (testing), NetworkX / custom graph search, Pillow & NumPy (controlled vision / scenes), FastAPI & Uvicorn (backend API), HTML5/Canvas/CSS/JS (interactive visualization UI).

---

## Global Architectural Rules

1. **Symbolic-First:** The symbolic system is authoritative for state representation, action semantics, planning, verification, constraint enforcement, counterexample generation, fault attribution, repair, and replanning.
2. **Neural Components Are Untrusted:** LLMs/VLMs only propose structured interpretations; they never validate plans, invent actions, or bypass constraints.
3. **One Authoritative Transition Semantics:** Planner and verifier share the exact same action definitions, preconditions, effects, and transition logic. No duplicated or divergent semantics.
4. **Explicit Data Contracts:** Every stage communicates via strongly typed Pydantic models. No raw string passing.
5. **Explainable Failure:** Failures output earliest step, state, action, violated condition, counterexample, fault class, repair action, and replan trace.
6. **Evidence-Guided Repair:** No blind LLM regeneration; repair must follow `Candidate -> Verifier -> Counterexample -> Attribution -> Repair -> Replan -> Verifier`.
7. **No Forced Attribution:** Insufficient evidence returns `UNKNOWN/AMBIGUOUS`.
8. **No Fabricated Results:** All reported metrics (success rates, times, nodes, costs) are strictly measured from actual execution.
9. **Zero-API Core:** Tier-1 core runs entirely locally without external API dependencies; deterministic mocks are provided.
10. **Reproducibility:** Fixed seeds, configuration versioning, structured JSON logs, and determinism.

---

## Module Directory Structure

```text
RE-PLAN-V/
├── app/
│   ├── api/                  # FastAPI REST API endpoints
│   ├── services/             # Pipeline orchestration service
│   ├── static/               # Interactive UI frontend (HTML5/Canvas/Tailwind-styled CSS/JS)
│   └── main.py               # Application entry point
├── core/
│   ├── contracts.py          # Universal Pydantic data schemas across all stages
│   ├── logger.py             # Structured JSON & console logger
│   ├── world/                # Types, Objects, Predicates, Facts, SymbolicState
│   ├── actions/              # Action definitions, Instantiated actions, Authoritative transitions
│   ├── search/               # BFS, Best-First, A* search and heuristics
│   ├── krr/                  # Knowledge representation, Unification, Horn clause reasoning
│   ├── verification/         # Deterministic plan verifier
│   ├── counterexamples/      # Structured counterexample generator & witness
│   ├── attribution/          # Evidence-based fault attribution & mutation tester
│   ├── repair/               # Repair constraints, generators, and guards
│   └── replanning/           # Local and global replanning loop
├── interpretation/
│   ├── schemas/              # Task proposal & validation schemas
│   ├── validator/            # Schema & consistency validator
│   ├── llm/                  # Provider interface, MockLLMProvider, Optional live providers
│   └── vision/               # Controlled scene generator, OpenCV/Pillow perception, VLM adapter
├── dynamic/
│   ├── monitor.py            # World observation comparator & delta calculator
│   └── replanner.py          # Relevant-change detector & reactive replanner
├── benchmark/
│   ├── generator/            # Procedural problem generator (Blocks, Logistics, Manipulation)
│   ├── mutations/            # Fault injection engine (Perception, Formalization, Planning, Env)
│   └── datasets/             # Serialized test benchmark instances
├── evaluation/
│   ├── baselines/            # B0 (Neural), B1 (Formalized), B2 (No Repair), B3 (Regen), OURS
│   ├── ablations/            # Ablation configurations (-verifier, -cex, -attrib, -repair)
│   ├── metrics/              # Accurate metric collectors (success, iterations, time, nodes)
│   ├── experiments/          # Runner for the central research question
│   └── reports/              # Summary and CSV/JSON exporter
├── configs/
│   └── default.py            # Configuration dataclasses & environment settings
├── docs/                     # Documentation and architecture diagrams
└── tests/
    ├── unit/                 # Stage-by-stage unit tests
    ├── integration/          # Multi-stage integration tests
    └── e2e/                  # End-to-end full pipeline tests
```

---

## Staged Implementation Roadmap

### Stage 0: Repository Foundation & Core Architecture
- **Deliverables:**
  - Initialize git repository and directory hierarchy.
  - Setup virtual environment, dependencies (`pydantic`, `pytest`, `fastapi`, `uvicorn`, `pillow`, `numpy`, `networkx`).
  - Create `core/contracts.py`: defining all universal schemas: `Predicate`, `Fact`, `SymbolicState`, `ActionDef`, `GroundAction`, `Plan`, `VerificationResult`, `Counterexample`, `FaultAttribution`, `RepairAction`, `ReplanningResult`, `TaskProposal`, `WorldDelta`, `BenchmarkInstance`, `EvaluationMetrics`.
  - Create `configs/default.py` and `core/logger.py`.
  - Add `main.py` minimal CLI and test suite scaffolding.
- **Verification:** `pytest` runs and passes with zero warnings.

### Stage 1: Unified Symbolic World Model
- **Deliverables:**
  - `core/world/types.py`: Type hierarchy (`Type`, `Object`).
  - `core/world/predicates.py`: `PredicateDefinition`, `Fact` (positive & negated), static vs dynamic categorization.
  - `core/world/state.py`: `SymbolicState` (immutable, hashable, deterministic set-of-facts representation, equality, clone, JSON serialize/deserialize).
  - `core/world/constraints.py`: State invariants and hard constraints (global safety conditions).
  - `core/world/problem.py`: `SymbolicProblem` (objects, initial state, goal conditions, domain constraints).
- **Verification:** Unit tests verifying state hashing, equality, immutable updates, fact lookups, goal checking, serialization round-trips.

### Stage 2: Authoritative Action Definitions & Transitions
- **Deliverables:**
  - `core/actions/definition.py`: `ActionDefinition` with typed parameters, positive/negative preconditions, add effects, del effects, cost.
  - `core/actions/instantiation.py`: `GroundAction` instantiation with parameter binding and legal ground action generation given state and objects.
  - `core/actions/transition.py`: Authoritative `apply_action(state, ground_action) -> SymbolicState`. The **single** source of truth for both planner and verifier.
  - Example domains: Blocks World, GridWorld/Logistics, Robot Manipulation.
- **Verification:** Unit tests testing valid transitions, precondition failures, frame preservation, delete-before-add semantics, cost computation.

### Stage 3: Classical Search Algorithms
- **Deliverables:**
  - `core/search/node.py`: `SearchNode` with g-cost, h-cost, f-cost, parent pointer, state hash caching.
  - `core/search/heuristics.py`: `Heuristic` base class, `GoalCountHeuristic`, `RelaxedPlanningGraphHeuristic` (FF/delete-relaxation heuristic).
  - `core/search/algorithms.py`: Deterministic implementations of BFS, Best-First (Greedy), and A*.
  - Closed-set cycle prevention, frontier metrics, expanded/generated node tracking, planning timeout handling.
  - `PlanningResult` contract reporting plan, metrics, and failure diagnostics.
- **Verification:** Benchmark against known optimal solutions in Blocks World and GridWorld; test unsolvable problems returning graceful failure.

### Stage 4: Knowledge Representation and Reasoning (KR&R)
- **Deliverables:**
  - `core/krr/terms.py`: Constants, Variables, Substitutions.
  - `core/krr/unification.py`: Robinson's unification algorithm for first-order literals.
  - `core/krr/rules.py`: Horn-clause rules (`head :- body_1, body_2, ...`).
  - `core/krr/inference.py`: Forward-chaining deduction engine to infer derived predicates (e.g. `clear(x)`, `above(x, y)`, `adjacent(l1, l2)`) without modifying physical action semantics.
- **Verification:** Unit tests for unification, substitution, deductive closure, and cycle detection in recursive rules.

### Stage 5: Formal Plan Verification
- **Deliverables:**
  - `core/verification/verifier.py`: Independent, deterministic `PlanVerifier`.
  - Sequential step checking:
    1. Validate action belongs to domain.
    2. Check action preconditions in state $s_t$.
    3. Apply authoritative transition $s_{t+1} = \text{apply}(s_t, a_t)$.
    4. Validate global invariants on $s_{t+1}$.
    5. Validate hard constraints.
    6. Check goal conditions on final state $s_T$.
  - Output rich `VerificationResult`: `is_valid`, `failed_step_index`, `failed_action`, `pre_state`, `post_state`, `violated_condition`, `violation_type`, `trace`, `verification_time_ms`.
- **Verification:** Unit tests with valid plans, precondition violation at various steps, invariant violation during execution, goal unmet at termination.

### Stage 6: Counterexample Generation
- **Deliverables:**
  - `core/counterexamples/generator.py`: Converts failed `VerificationResult` into a structured, machine-readable `Counterexample`.
  - Extracts earliest meaningful failure witness: action index, offending ground action, violated formula/condition, state snapshot, actual vs expected truth values, affected entity bindings, natural explanation.
  - Serialization, replay, and JSON export.
- **Verification:** Unit tests verifying counterexample accuracy, deterministic witness generation across diverse failure types.

### Stage 7: Fault Attribution & Mutation Framework
- **Deliverables:**
  - `core/attribution/classifier.py`: Controlled taxonomy engine:
    - `PERCEPTION_ERROR`: Observation discrepancy with true environment.
    - `FORMALIZATION_ERROR`: Discrepancy in goal or constraint specification from user task.
    - `PLANNING_ERROR`: Valid model, but planner picked invalid action sequence.
    - `ENVIRONMENT_CHANGE`: World state diverged mid-plan due to external event.
    - `UNKNOWN/AMBIGUOUS`: Insufficient evidence to disambiguate.
  - Evidence-based attribution logic analyzing candidate plan, verification trace, problem definition, and task input.
  - `core/attribution/mutation.py`: Fault injection suite for controlled testing and ground-truth validation.
- **Verification:** Measure attribution accuracy over injected mutations; confirm ambiguous cases produce `UNKNOWN/AMBIGUOUS`.

### Stage 8: Repair and Replanning Loop
- **Deliverables:**
  - `core/repair/models.py`: Explicit `RepairConstraint` types (`FORBID_GROUND_ACTION`, `FORBID_ACTION_IN_STATE`, `ADD_ORDERING_CONSTRAINT`, `STATE_BELIEF_CORRECTION`, `REFRESH_OBSERVATION`).
  - `core/repair/generator.py`: Derives targeted repairs from `Counterexample` and `FaultAttribution`.
  - `core/replanning/loop.py`: Executes the iterative loop:
    `Candidate -> Verifier -> Counterexample -> Attribution -> Repair -> Replan -> Verifier`.
  - Loop guards: `max_repair_iterations`, cycle/repeated-repair detection, no-progress detection.
  - Alternative baseline: `generic_regeneration` (B3) for controlled comparison.
- **Verification:** Unit tests demonstrating successful plan repair within bounded iterations, loop termination on unfixable tasks.

### Stage 9: Neural Interpretation & Untrusted Schema Validation
- **Deliverables:**
  - `interpretation/schemas/task_spec.py`: Strict Pydantic models for neural proposals (`TaskProposal`).
  - `interpretation/validator/validator.py`: Consistency validator checking entity existence, type correctness, predicate arity, and contradiction detection.
  - `interpretation/llm/base.py`: Provider interface `BaseLLMProvider`.
  - `interpretation/llm/mock.py`: Deterministic `MockLLMProvider` for offline testing.
  - `interpretation/llm/live.py`: Optional live API provider (Google GenAI) with graceful fallback.
- **Verification:** Unit tests verifying rejection of malformed entities, arity mismatches, contradictory constraints, and valid parsing with deterministic mock.

### Stage 10: Controlled Vision Perception
- **Deliverables:**
  - `interpretation/vision/scene_generator.py`: Synthetic 2D/3D grid & tabletop scene renderer generating controlled images with ground-truth object properties (color, shape, coordinates, bounding box).
  - `interpretation/vision/detector.py`: Deterministic perception engine using color/contour/spatial thresholding to extract objects and spatial relations (`on`, `clear`, `left_of`, `next_to`, `holding`).
  - `interpretation/vision/vlm_adapter.py`: Optional VLM provider using the identical structured schema.
  - Evaluation harness measuring detection precision, recall, and relation accuracy against ground truth.
- **Verification:** Tests on synthetic test images verifying exact extraction of objects and spatial relations matching ground truth.

### Stage 11: Dynamic Environment & Reactive Replanning
- **Deliverables:**
  - `dynamic/monitor.py`: Computes `WorldDelta` between previous belief state and new observation (added facts, removed facts, changed relations).
  - `dynamic/replanner.py`: Relevancy filter checking if delta intersects preconditions or invariants of remaining plan steps.
  - Reactive trigger: skips replanning if change is irrelevant; invalidates plan and invokes repair/replanning loop if relevant.
- **Verification:** Deterministic tests demonstrating that irrelevant changes do not trigger replanning while relevant disruptions (e.g. obstacle placed on target) trigger replanning.

### Stage 12: Benchmark Suite & Empirical Evaluation
- **Deliverables:**
  - `benchmark/generator/generator.py`: Parameterized problem generator (domain, object count, horizon, constraint density, distractors).
  - `evaluation/baselines/`:
    - `B0`: Direct neural generation (mock/prompted).
    - `B1`: Neural formalization + classical planner.
    - `B2`: Classical planner + verifier (reject without repair).
    - `B3`: Planner + generic plan regeneration.
    - `OURS`: Planner + verifier + counterexample + fault attribution + repair.
  - `evaluation/ablations/`: Configurations for -verifier, -counterexample, -attribution, -repair.
  - `evaluation/experiments/runner.py`: Benchmark runner collecting metrics: valid-plan rate, repair success rate, constraint violation rate, planning time, verification time, repair time, nodes expanded, repair iterations.
  - Export to JSON and CSV reports answering the central research question.
- **Verification:** End-to-end benchmark run producing concrete, un-fabricated empirical comparisons.

### Stage 13: Interactive Demo Application & End-to-End Integration
- **Deliverables:**
  - `app/services/pipeline.py`: Unified end-to-end pipeline orchestrator connecting all stages.
  - `app/api/routes.py`: FastAPI endpoints for planning, verification, repair, dynamic updates, and benchmark execution.
  - `app/static/`: Interactive UI visualizing:
    1. Input task (NL + visual canvas)
    2. Neural interpretation & validated symbolic problem
    3. Candidate plan & search metrics
    4. Verification step trace
    5. Counterexample witness & failure highlight
    6. Fault attribution diagnosis
    7. Repair constraint & replanning evolution
    8. Final verified plan
    9. Live benchmark & comparative baseline evaluation chart
  - CLI runner `main.py` supporting both headless benchmark runs and server launch.
- **Verification:** Full end-to-end tests exercising the complete pipeline through API and CLI.

### Stage 14: Skeptical Research Audit & Hardening
- **Deliverables:**
  - Complete code audit: verify single transition function shared between planner and verifier.
  - Verify no neural component can bypass verification or inject untrusted actions.
  - Verify zero hard-coded or fabricated metrics.
  - Run full test suite (`pytest`) across all unit, integration, and e2e tests.
  - Comprehensive `README.md` with installation, architecture, reproduction instructions, and CLI examples.
- **Verification:** All tests pass, 100% reproducible results, zero lint/import errors.

---
