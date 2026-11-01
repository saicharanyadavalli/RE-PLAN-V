# RE-PLAN-V: Stage 10 Pre-Execution Baseline Audit

- **Audit Timestamp**: 2026-11-01
- **Audited Public Main Commit**: `a61e828f8ed26a800e71b3ce742e0f30625aa0f0`
- **Remote `refs/heads/main` SHA**: `a61e828f8ed26a800e71b3ce742e0f30625aa0f0`
- **Branch Inventory**: Exactly one branch (`main`). No active feature or release branches.
- **Working Tree Integrity**: Untracked user PDFs and documents preserved in root. Zero untracked code modifications.
- **Pre-Execution Baseline Test Suite**: `pytest tests/ -q` -> **393 passed**, 2 warnings in 19.35s.
- **Pre-Execution Frontend Build**: `npm --prefix frontend run build` -> **Clean production build** (4/4 static pages, 0 errors).

---

## Source-Level Confirmation of Stage 10 Findings

### DEF-10.1: Pipeline does not fail closed on unsupported or unknown tasks
- **Confirmed in**: `app/services/pipeline.py:101`, `app/services/pipeline.py:140-152`, `app/api/websocket.py:87-90`, `app/api/routes.py:191-195`, `interpretation/llm/mock.py:179-204`.
- **Finding**:
  1. `PipelineOrchestrator.__init__` falls back to Blocks World for unknown `domain_id`.
  2. `PipelineOrchestrator.run` ignores non-supported routing outcomes (`UNSUPPORTED`, `NEEDS_CLARIFICATION`, `INVALID_PROPOSAL`), leaving `active_domain` as Blocks World and calling the interpreter.
  3. `MockLLMProvider.interpret` falls back to `mock_fallback_task` (stacking b1 on b2 in Blocks World) when extraction fails.
  4. `/api/llm/formalize` falls back to Blocks World for unknown domain rather than returning 404/422.
  5. WebSocket explicit unknown domain falls back to Blocks World.

### DEF-10.2: Negative constraint semantics are not precise enough
- **Confirmed in**: `interpretation/validator/validator.py:199-205`, `core/world/constraints.py:86-89`.
- **Finding**:
  1. `ConsistencyValidator.convert_to_problem` attaches `ProhibitedEntityActionConstraint(protected_entity=fact.arguments[0], prohibited_actions=[])`.
  2. In `ProhibitedEntityActionConstraint.check_action`, `not self.prohibited_actions` evaluates to `True`, which blocks **all actions** referencing `protected_entity`.
  3. For `at(agent, loc_trap)`, this blocks all movement actions of `agent`. For `deployed_to(pkg, prod)`, this blocks all actions referencing `pkg`.
  4. Router maps natural-language prohibitions to single fact predicates with surrogate entity names (`pkg_v1`, `carrier_1`, etc.).

### DEF-10.3: Domain default invariants are not consistently enforced in the real pipeline
- **Confirmed in**: `interpretation/validator/validator.py:192-214`.
- **Finding**:
  1. `convert_to_problem` initializes `invariants = []` without importing `domain.default_invariants`.
  2. The actual runtime pipeline problem omits domain invariants; only hand-crafted test fixtures were providing them.

### DEF-10.4: A* optimality claim does not match the actual default heuristic
- **Confirmed in**: `core/search/algorithms.py:326`, `frontend/components/TaskControlPanel.tsx`, `README.md`, `RESEARCH_REPORT.md`.
- **Finding**:
  1. `AStarPlanner.search` defaults to `GoalCountHeuristic()`, which is not admissible for general multi-goal or non-unit cost problems.
  2. The UI and documentation claimed "A* Search (Optimal RPG h_max)".

### DEF-10.5: Backend graph schema and frontend graph types are inconsistent
- **Confirmed in**: `core/graph/models.py`, `frontend/types/pipeline.ts`, `frontend/hooks/usePipelineWebSocket.ts:60`, `frontend/components/StateSpaceExplorer.tsx:101`.
- **Finding**:
  1. Backend emits `node_id`, `is_boundary`, `facts: List[str]`, `max_depth`.
  2. Frontend expects `id`, `is_truncated_boundary`, `facts: FactSchema[]`, `max_depth_reached`.
  3. WebSocket hook appends raw Pydantic dictionaries directly into state without field normalization.
  4. `StateSpaceExplorer.tsx` has a fabricated `enumeration_time_ms: 120` fallback.

### DEF-10.6: Mission Control uses the Blocks World tabletop view for every domain
- **Confirmed in**: `frontend/app/page.tsx:112-118`.
- **Finding**:
  1. `page.tsx` unconditionally renders `TabletopCanvas` regardless of the active or selected domain.
  2. Stacking blocks visuals are shown for Grid World, Warehouse, Scheduling, Household, and Software tasks.

### DEF-10.7: Benchmark UI contains hardcoded attribution results
- **Confirmed in**: `frontend/components/BenchmarkTab.tsx:155-199`.
- **Finding**:
  1. The 5x5 confusion matrix is hardcoded with literal JSX elements containing `10` and `0`.
  2. `Macro Accuracy: 100.0%` and `Macro F1: 1.00` are hardcoded strings.
  3. Unconditional `+` sign is prepended to recovery advantage.

### DEF-10.8: Stage 8 reliability tests do not prove all security/resource claims
- **Confirmed in**: `tests/integration/test_stage_8_reliability.py:177, 196`.
- **Finding**:
  1. `test_invalid_negative_resource_limits` accepts both `200` and `422`.
  2. Prompt-injection tests assert output keys exist, but not semantic isolation or execution denial.
  3. Safety test only checks for missing attribute names on `PlanVerifier`.

### DEF-10.9: Research metrics contain self-asserted attribution and denominator problems
- **Confirmed in**: `evaluation/experiments/runner.py:81, 87-88`, `evaluation/metrics/collector.py:38-39`.
- **Finding**:
  1. `r_ours["attribution_correct"] = True` is assigned unconditionally.
  2. B1 is credited with 100% repair success rate using fallback `valid_count / n` despite having 0 invalid cases.
  3. `repair_time_ms` is assigned from total `planning_time_ms`.

### DEF-10.10: Complexity coverage does not establish complete 100–3000+ state graphs
- **Confirmed in**: `scripts/reproduce_results.py`, `evaluation/reports/full_reproduction_summary.json`.
- **Finding**:
  1. Software workflow tier was truncated at 14,000 edges and reported as 1317 states without clearly marking it as a lower bound.
  2. No complete 3000+ state graph was proven.

### DEF-10.11: Documentation contains stale or unsupported claims
- **Confirmed in**: `README.md`, `RESEARCH_REPORT.md`, `docs/engineering/FINAL_ENGINEERING_DELIVERY_REPORT.md:52`.
- **Finding**:
  1. Delivery report test breakdown summed to 392 because `test_nlp_corpus.py` had 146 tests but was listed as 145.
  2. Delivery report contained literal `<FINAL_SHA>` in git ls-remote output block.
  3. Local `file:///C:/Users/...` links in README.
  4. Unsupported claims: "95% symbolic / 5% LLM", VRAM / latency claims.
