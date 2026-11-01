# RE-PLAN-V: Post-Integration Defect Register (Final Closeout)

- **Audit Date**: November 2026
- **Audited Commit**: `4e908f4d8ec12981720e08cbff2d81c3986d03e2` (Baseline) -> `2b0db2b` (Final Main)
- **Classification Taxonomy**: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`
- **Status Taxonomy**: `VERIFIED_CLOSED` (All 11 Defects Remediated & Verified)

---

## Defect Resolution & Verification Matrix

| Defect ID | Severity | Final Status | Module / File Path | Description | Remediation & Verification Evidence | Target Stage |
|:---|:---|:---|:---|:---|:---|:---|
| **DEF-01** | `CRITICAL` | `VERIFIED_CLOSED` | `app/services/pipeline.py:95` | `PipelineOrchestrator` hardcoded to Blocks World. Standard pipeline execution could not plan/verify for other 5 domains. | Implemented dynamic domain resolution in `PipelineOrchestrator` (`d4795e7`). Verified by `test_pipeline_runs_all_domains` across all 6 domains. | **Stage 2 & Stage 5** |
| **DEF-02** | `CRITICAL` | `VERIFIED_CLOSED` | `evaluation/metrics/collector.py:68` | `recovery_advantage_over_regeneration` silently clamped negative advantage to `0.0`. | Removed clamping, computing signed difference `round(repair_rate - self.baseline_regeneration_rate, 4)` (`94f5a18`). Verified by unit tests. | **Stage 7** |
| **DEF-03** | `HIGH` | `VERIFIED_CLOSED` | `evaluation/ablations/configurations.py:66` | `without_verifier` ablation blindly reported `is_valid: True` and 100% success without verification. | Updated to evaluate candidate validity post-hoc with authoritative verifier (`94f5a18`), accurately reporting 0.0% repair success. | **Stage 7** |
| **DEF-04** | `HIGH` | `VERIFIED_CLOSED` | `interpretation/router.py:179-306` | Entity and initial fact extraction in router methods used hardcoded template constants. | Replaced templates with dynamic regex extraction for all entities and facts (`edccfe7`). Verified by 145-prompt multi-domain NLP suite. | **Stage 3** |
| **DEF-05** | `HIGH` | `VERIFIED_CLOSED` | `interpretation/router.py:127-150` | Negative constraints mapped to rigid single predicates without clause isolation. | Implemented clause isolation (`re.split(...)`) and domain-specific prohibition extraction across all 6 domains (`edccfe7`). | **Stage 3** |
| **DEF-06** | `HIGH` | `VERIFIED_CLOSED` | `app/api/routes.py:178` | `/api/llm/formalize` endpoint hardcoded Blocks World domain. | Updated endpoint to resolve domain dynamically from request payload (`724f7d7`). Verified in `test_api_endpoints.py`. | **Stage 5** |
| **DEF-07** | `MEDIUM` | `VERIFIED_CLOSED` | `core/graph/enumerator.py:99-103` | Edge-cap truncation failed to tag whether boundary node was partially expanded. | Added explicit `partially_expanded=True` and `is_boundary=True` tagging upon edge limit hit (`d4795e7`). | **Stage 2** |
| **DEF-08** | `MEDIUM` | `VERIFIED_CLOSED` | `benchmark/generator/multi_domain_generator.py` | Benchmarks lacked measured Model B state-space enumeration across realistic complexity tiers (100–3000 states). | Calibrated all 6 domains across TINY, SMALL, MEDIUM, LARGE tiers with exact Model B measurements (`94f5a18`). | **Stage 7** |
| **DEF-09** | `MEDIUM` | `VERIFIED_CLOSED` | `evaluation/experiments/fault_matrix.py` | 5-class fault attribution benchmark lacked ambiguous boundary cases and multi-cause conflict detection. | Implemented multi-hypothesis conflict arbitration in `FaultAttributionEngine` and diverse ambiguous fixtures (`94f5a18`). | **Stage 7** |
| **DEF-10** | `LOW` | `VERIFIED_CLOSED` | `frontend/components/StateSpaceExplorer.tsx:64` | Hardcoded `http://${host}:8080` fetch URLs prevented deployment behind reverse proxies. | Created `frontend/utils/api.ts` with dynamic `getApiBaseUrl()` and `getWebSocketUrl()` (`de32d7b`). | **Stage 6** |
| **DEF-11** | `LOW` | `VERIFIED_CLOSED` | `core/world/predicates.py` vs `core/contracts.py` | Dual representation of logical facts risked serialization divergence. | Added bijective schema conversion methods `Fact.to_schema()` and `Fact.from_schema()` (`d4795e7`). | **Stage 2** |

---

## Stage 10 Remaining Defect Closure Matrix (DEF-10.1 through DEF-10.11)

| Defect ID | Severity | Final Status | Module / File Path | Description | Remediation & Verification Evidence | Target Stage |
|:---|:---|:---|:---|:---|:---|:---|
| **DEF-10.1** | `CRITICAL` | `VERIFIED_CLOSED` | `app/services/pipeline.py`, `app/api/websocket.py` | Pipeline & WebSocket fallbacks failed open on unsupported / invalid routing, executing planning on ungrounded problems. | Implemented strict fail-closed behavior emitting `VALIDATION_FAILED` / `INTERPRETATION_FAILED` (`2b52b20`). Verified by `tests/integration/test_stage_10_fail_closed_pipeline.py` (11 passed). | **Stage 10.1** |
| **DEF-10.2** | `CRITICAL` | `VERIFIED_CLOSED` | `core/world/constraints.py` | Negative constraints using `ProhibitedEntityActionConstraint` with empty actions list inadvertently blocked all actions on an entity. | Fixed constraint to require non-empty actions, added `ForbidActionConstraint` and `ForbidActionBindingConstraint` (`747e8b9`). Verified by `tests/unit/test_stage_10_negative_constraint_semantics.py` (5 passed). | **Stage 10.2** |
| **DEF-10.3** | `HIGH` | `VERIFIED_CLOSED` | `interpretation/validator/validator.py` | Domain default invariants and type hierarchy arg-types were bypassed during proposal validation and problem conversion. | Enforced `domain.default_invariants` and predicate `arg_types` subtyping in validator (`747e8b9`). Verified by `tests/integration/test_stage_10_domain_invariants_pipeline.py` (4 passed). | **Stage 10.3** |
| **DEF-10.4** | `HIGH` | `VERIFIED_CLOSED` | `core/search/algorithms.py`, `core/contracts.py` | A* search lacked an admissible optimal heuristic configuration and did not report optimality status. | Configured `ZeroHeuristic()` (uniform-cost search) as admissible default, added `is_optimal` field (`584b49c`). Verified by `tests/unit/test_stage_10_astar_optimality.py` (3 passed). | **Stage 10.4** |
| **DEF-10.5** | `HIGH` | `VERIFIED_CLOSED` | `core/graph/models.py`, `frontend/types/pipeline.ts` | Graph DTO field naming asymmetry (`node_id`/`id`, `is_boundary`/`is_truncated_boundary`, `max_depth`/`max_depth_reached`) caused UI parsing inconsistencies. | Standardized bidirectional fields and WebSocket normalizers (`1925124`). Verified by `tests/integration/test_stage_10_graph_transport_contract.py` (3 passed). | **Stage 10.5** |
| **DEF-10.6** | `MEDIUM` | `VERIFIED_CLOSED` | `frontend/components/StateSpaceExplorer.tsx` | UI contained fabricated fallback constants (`enumeration_time_ms: 120`) and lacked non-blocks domain inspection. | Removed synthetic constants and introduced `SymbolicStateInspector.tsx` for all non-blocks domains (`1925124`). Verified by Next.js build. | **Stage 10.6** |
| **DEF-10.7** | `MEDIUM` | `VERIFIED_CLOSED` | `frontend/components/BenchmarkTab.tsx`, `app/api/routes.py` | Benchmark tab rendered hardcoded 5x5 confusion matrix and unsigned advantage. | Added `/api/benchmark/attribution` endpoint and wired dynamic confusion matrix and signed advantage rendering (`1925124`). Verified by Next.js build. | **Stage 10.7** |
| **DEF-10.8** | `HIGH` | `VERIFIED_CLOSED` | `evaluation/metrics/collector.py`, `core/contracts.py` | When zero invalid candidate plans existed (B0/B1), repair success rate falsely reported 100% or `valid_count/n`. | Updated denominator to strictly `len(invalid_cases)`, reporting `None` (`"N/A"`) when denominator is 0 (`4937466`). Verified by `test_stage_10_evaluation_metrics_denominators.py`. | **Stage 10.8** |
| **DEF-10.9** | `HIGH` | `VERIFIED_CLOSED` | `evaluation/experiments/runner.py` | Research experiment runner hardcoded `attribution_correct = True` without evaluating ground truth. | Updated to evaluate `attribution_correct` against ground truth `PLANNING_ERROR` from `r_ours["attribution"]` (`4937466`). Verified by unit tests. | **Stage 10.8** |
| **DEF-10.10** | `MEDIUM` | `VERIFIED_CLOSED` | `scripts/reproduce_results.py`, `README.md` | Truncated Model B state spaces were not clearly qualified as empirical lower bounds. | Added explicit `(empirical lower bound, edge-capped)` labels in CLI outputs and documentation (`4937466`). | **Stage 10.8** |
| **DEF-10.11** | `MEDIUM` | `VERIFIED_CLOSED` | `app/api/routes.py`, `tests/unit/test_stage_10_security_resource_bounds.py` | Non-positive resource limits were not strictly rejected with HTTP 422. | Added `ge=1` and `gt=0.0` Pydantic bounds and prompt injection containment test suite (`dd411ce`). Verified by 26 passed tests. | **Stage 10.9** |

---

## Verification Summary
- **Total Defects Identified (Stage 0 - Stage 9)**: 11 (100% Remediated)
- **Total Remaining Defects Remediated (Stage 10)**: 11 (100% Remediated)
- **Cumulative Defect Closeout**: 22 / 22 Defects `VERIFIED_CLOSED` (100%)
- **Total Backend Regression Suite**: 432 passing tests in `pytest` (0 failures, 2 warnings).
- **Benchmark Reproduction**: `python scripts/reproduce_results.py` confirms 100% execution integrity and zero fabricated metrics.
- **Frontend Production Build**: `npm --prefix frontend run build` clean (exit code 0).
