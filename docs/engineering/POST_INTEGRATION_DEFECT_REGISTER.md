# RE-PLAN-V: Post-Integration Defect Register (Stage 1)

**Audit Date**: November 2026  
**Audited Commit**: `4e908f4d8ec12981720e08cbff2d81c3986d03e2` on `main`  
**Classification Taxonomy**: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`  
**Status Taxonomy**: `VERIFIED`, `IMPLEMENTED_UNVERIFIED`, `PARTIAL`, `BROKEN`, `MISSING`, `MISLEADING`  

---

## Prioritized Defect Register

| Defect ID | Severity | Status | Module / File Path | Description | Reproduction / Evidence | Target Stage |
|:---|:---|:---|:---|:---|:---|:---|
| **DEF-01** | `CRITICAL` | `BROKEN` | `app/services/pipeline.py:95` | `PipelineOrchestrator` is hardcoded to `self.domain = create_blocks_world_domain()`. Standard pipeline execution (`run()`) cannot plan or verify for the other 5 registered domains. | Calling `PipelineOrchestrator.run(prompt)` on warehouse or scheduling prompts attempts to validate against Blocks World predicates and fails or misinterprets. | **Stage 2 & Stage 5** |
| **DEF-02** | `CRITICAL` | `BROKEN` | `evaluation/metrics/collector.py:68` | `recovery_advantage_over_regeneration` silently clamps negative advantage to `0.0` using `max(0.0, repair_rate - self.baseline_regeneration_rate)`. | If baseline regeneration rate is 0.8 and repair is 0.5, reported advantage is 0.0 instead of -0.3. Violates signed difference requirement. | **Stage 7** |
| **DEF-03** | `HIGH` | `MISLEADING` | `evaluation/ablations/configurations.py:66` | `without_verifier` ablation blindly returns `is_valid: True` and `success: True` regardless of actual plan correctness. | The ablation table reports 100% repair success rate for `without_verifier` because the unverified candidate is assumed valid. | **Stage 7** |
| **DEF-04** | `HIGH` | `PARTIAL` | `interpretation/router.py:179-306` | Entity and initial fact extraction in router methods (`_extract_household`, `_extract_warehouse`, `_extract_scheduling`, `_extract_software`) use hardcoded template constants rather than general NLP entity extraction. | Prompting with different room names or task IDs results in default template entities (`mug`, `kitchen_shelf`, `task_b`) being extracted instead of user-specified entities. | **Stage 3** |
| **DEF-05** | `HIGH` | `PARTIAL` | `interpretation/router.py:127-150` | Negative constraints are mapped via rigid regex to single surrogate positive predicates (`holding(X)`, `at("agent", X)`, `carrier_at("carrier_1", X)`) rather than generic action or state prohibitions. | Prompt "never deliver sku_a to dispatch_dock" or "avoid stacking red on blue" is either missed or inappropriately mapped. | **Stage 3** |
| **DEF-06** | `HIGH` | `BROKEN` | `app/api/routes.py:178` | `/api/llm/formalize` endpoint hardcodes `create_blocks_world_domain()`, preventing live formalization testing for the other 5 domains. | POST `/api/llm/formalize` with a Grid World prompt forces blocks world schema validation. | **Stage 5** |
| **DEF-07** | `MEDIUM` | `IMPLEMENTED_UNVERIFIED` | `core/graph/enumerator.py:99-103` | In `CompleteReachableGraphEnumerator`, edge-cap truncation breaks out of the applicable action loop without explicitly tagging whether the current node was fully or partially expanded. | If `max_edges` is reached on action 2 of 5, the node has `expanded=True` despite remaining legal edges being skipped. | **Stage 2** |
| **DEF-08** | `MEDIUM` | `PARTIAL` | `benchmark/generator/multi_domain_generator.py` | Benchmark generator supports `measure_state_space()` on TINY instances, but larger complexity tiers (MEDIUM 200–1000, LARGE 1000–3000) rely on unverified estimates in code without proven complete graph enumeration across all 6 domains. | Review of generator code shows `estimated_state_space` placeholder values for higher tiers. | **Stage 7** |
| **DEF-09** | `MEDIUM` | `IMPLEMENTED_UNVERIFIED` | `evaluation/experiments/fault_matrix.py` | 5-class fault attribution benchmark uses strictly orthogonal, non-overlapping synthetic fixtures, resulting in artificial 100% precision/recall across all classes without testing ambiguous boundary cases. | In `_generate_test_case`, each class passes unique parameters (e.g. `environment_deltas` only for ENVIRONMENT_CHANGE) directly matching classifier if-branches. | **Stage 7** |
| **DEF-10** | `LOW` | `PARTIAL` | `frontend/components/StateSpaceExplorer.tsx:64` | StateSpaceExplorer uses hardcoded `http://${host}:8080` fetch URL for standalone enumeration instead of a unified API base configuration. | Running the frontend on non-standard backend ports or reverse proxies causes standalone graph enumeration to fail. | **Stage 6** |
| **DEF-11** | `LOW` | `PARTIAL` | `core/world/predicates.py` vs `core/contracts.py` | Dual representation of logical facts (`core.world.predicates.Fact` vs `core.contracts.FactSchema`) creates potential serialization/deserialization divergence. | Both classes implement similar predicate/argument storage with manual translation methods. | **Stage 2** |

---

## Remediation Roadmap

1. **Stage 2 (Core Correctness & Contracts)**:
   - Remediate DEF-01, DEF-07, DEF-11.
   - Unify domain contracts and transition semantics across `core/domains/` and `core/actions/`.
   - Harden graph enumerator boundary conditions, exact limits, and partial-expansion status tagging.
2. **Stage 3 (Text-First NLP & Formalisation)**:
   - Remediate DEF-04, DEF-05.
   - Refactor router to support general entity extraction and semantic negation scoping.
   - Author 20+ NLP test cases per domain.
3. **Stage 4 (Six Domain Conformance)**:
   - Validate all 6 domains against a shared conformance suite.
4. **Stage 5 (Graph, Search Trace, API & Streaming)**:
   - Remediate DEF-06.
   - Ensure REST and WebSocket endpoints dynamically accept domain selection and handle streaming batches.
5. **Stage 6 (Frontend Product Hardening)**:
   - Remediate DEF-10.
   - Ensure resilient API routing, node/edge inspector, and complete/truncated status honesty.
6. **Stage 7 (Research Benchmarks & Methodology)**:
   - Remediate DEF-02, DEF-03, DEF-08, DEF-09.
   - Fix recovery advantage calculation to preserve signed difference.
   - Fix ablation definitions so that `without_verifier` tests actual validity without blind assertion.
   - Expand measured multi-domain benchmarks to realistic complexity tiers.
7. **Stage 8 & 9 (End-to-End Verification & Independent Review)**:
   - Verify all defects are closed with executable command evidence.
