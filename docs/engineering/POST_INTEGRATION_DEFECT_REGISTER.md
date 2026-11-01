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

## Verification Summary
- **Total Defects Identified**: 11
- **Total Defects Remediated**: 11 (100%)
- **Regression Test Suite**: 393 passing tests in `pytest`.
- **Benchmark Reproduction**: `python scripts/reproduce_results.py` confirms 100% execution integrity.
- **Frontend Production Build**: `npm --prefix frontend run build` clean (exit code 0).
