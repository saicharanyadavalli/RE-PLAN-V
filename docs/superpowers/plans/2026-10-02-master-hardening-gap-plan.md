# RE-PLAN-V Master Hardening Gap Resolution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the remaining gap items identified in the comprehensive audit against `RE-PLAN-V_ANTIGRAVITY_MASTER_HARDENING_PROMPT.md` to ensure 100% specification compliance, mathematical rigor, UI consistency, empirical benchmark validation, and project proposal alignment.

**Architecture:** Neuro-symbolic plan generation and verification system featuring untrusted neural interpretation, classical search (A* with RPG h_max, BFS, Best-First), authoritative first-order STRIPS plan verification, counterexample witness extraction, 5-class evidence-grounded fault attribution, and counterexample-guided negative constraint replanning.

**Tech Stack:** Python 3.10+, Pydantic v2, Pytest, FastAPI, Next.js 14, Tailwind CSS, NumPy/SciPy (metrics).

## Global Constraints

- **No Fabricated Data:** Every figure, table, metric, and percentage must be derived directly from executed code runs.
- **Fair Baseline Design:** Baseline B3 must represent active generic candidate sequence re-sampling under an explicit seed, independent of counterexample-derived repair constraints.
- **Accurate Denominators:** Repair success rate denominator is strictly $N_{\text{successfully\_repaired}} / N_{\text{initially\_invalid}}$.
- **No Marketing Exaggeration:** Prohibit phrases like "100% mathematically safe" or "Enterprise Mission Control"; use precise formal verification guarantees within modeled closed-world semantics.
- **API Key Security:** Never print, log, or hardcode API keys (`NVIDIA_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`).

---

### Task 1: Dedicated 5-Class Fault Attribution & Confusion Matrix Experiment

**Files:**
- Create: `evaluation/experiments/fault_matrix.py`
- Modify: `evaluation/experiments/runner.py:100-121`
- Test: `tests/unit/test_attribution_matrix.py`

**Interfaces:**
- Consumes:
  - `core.attribution.classifier.FaultAttributionEngine`
  - `core.attribution.mutation.FaultInjector`
  - `core.contracts.FaultClass`, `CounterexampleSchema`, `ViolationType`
- Produces:
  - `evaluation/reports/fault_attribution_matrix.json`: Contains overall accuracy, macro precision/recall/F1, per-class metrics, and $5 \times 5$ confusion matrix.

- [ ] **Step 1: Write the failing unit test for fault attribution matrix generation**

Create `tests/unit/test_attribution_matrix.py`:
```python
"""Tests for the 5-Class Fault Attribution Confusion Matrix experiment runner."""

import pytest
from evaluation.experiments.fault_matrix import AttributionMatrixExperiment


def test_attribution_matrix_evaluation_structure():
    runner = AttributionMatrixExperiment()
    results = runner.run_evaluation(instances_per_class=2, seed=42)

    assert "accuracy" in results
    assert "macro_f1" in results
    assert "per_class" in results
    assert "confusion_matrix" in results
    assert len(results["confusion_matrix"]) == 5
    assert results["total_evaluated"] == 10
    assert results["accuracy"] >= 0.70
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_attribution_matrix.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evaluation.experiments.fault_matrix'`

- [ ] **Step 3: Implement AttributionMatrixExperiment**

Create `evaluation/experiments/fault_matrix.py`:
```python
"""Dedicated 5-Class Fault Attribution & Confusion Matrix Experiment Runner.

Evaluates FaultAttributionEngine on controlled ground-truth injected faults across all 5 classes:
1. PLANNING_ERROR
2. PERCEPTION_ERROR
3. FORMALIZATION_ERROR
4. ENVIRONMENT_CHANGE
5. UNKNOWN_AMBIGUOUS
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core.actions.domain import create_blocks_world_domain
from core.attribution.classifier import FaultAttributionEngine
from core.attribution.mutation import FaultInjector
from core.contracts import (
    CounterexampleSchema,
    FactSchema,
    FaultClass,
    GroundActionSchema,
    PlanSchema,
    SymbolicStateSchema,
    ViolationType,
    WorldDeltaSchema,
)
from core.counterexamples.generator import CounterexampleGenerator
from core.verification.verifier import PlanVerifier
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry


class AttributionMatrixExperiment:
    """Evaluates attribution accuracy, per-class precision/recall/F1, and confusion matrix."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or Path(__file__).resolve().parent.parent / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.engine = FaultAttributionEngine()
        self.classes = [
            FaultClass.PLANNING_ERROR,
            FaultClass.PERCEPTION_ERROR,
            FaultClass.FORMALIZATION_ERROR,
            FaultClass.ENVIRONMENT_CHANGE,
            FaultClass.UNKNOWN_AMBIGUOUS,
        ]

    def _create_sample_problem(self, suffix: str = "") -> Tuple[SymbolicProblem, Any]:
        domain = create_blocks_world_domain()
        reg = ObjectRegistry(domain.type_hierarchy)
        reg.register_object(f"b1{suffix}", "block")
        reg.register_object(f"b2{suffix}", "block")
        reg.register_object(f"b3{suffix}", "block")

        init_facts = [
            Fact("on_table", [f"b1{suffix}"]),
            Fact("clear", [f"b1{suffix}"]),
            Fact("on_table", [f"b2{suffix}"]),
            Fact("clear", [f"b2{suffix}"]),
            Fact("on_table", [f"b3{suffix}"]),
            Fact("clear", [f"b3{suffix}"]),
            Fact("handempty", []),
        ]
        s0 = SymbolicState(facts=init_facts, objects=reg.get_all_objects())
        problem = SymbolicProblem(
            name=f"AttrProblem{suffix}",
            domain_name=domain.name,
            registry=reg,
            initial_state=s0,
            goal_conditions=[Fact("on", [f"b1{suffix}", f"b2{suffix}"])],
        )
        return problem, domain

    def _generate_test_case(self, fault_class: FaultClass, idx: int) -> Dict[str, Any]:
        suffix = f"_{fault_class.value[:3]}_{idx}"
        problem, domain = self._create_sample_problem(suffix)
        b1, b2, b3 = f"b1{suffix}", f"b2{suffix}", f"b3{suffix}"

        if fault_class == FaultClass.PLANNING_ERROR:
            broken_plan = [GroundActionSchema(name="stack", arguments=(b1, b2))]
            verifier = PlanVerifier()
            v_res = verifier.verify(problem, domain, broken_plan)
            cex = CounterexampleGenerator().generate(v_res, problem)
            return {
                "ground_truth": FaultClass.PLANNING_ERROR,
                "counterexample": cex,
                "problem": problem,
            }

        elif fault_class == FaultClass.PERCEPTION_ERROR:
            cex = CounterexampleSchema(
                counterexample_id=f"CEX-PERC-{idx}",
                action_index=0,
                offending_action=GroundActionSchema(name="pick_up", arguments=(b1,)),
                violated_condition=FactSchema(predicate="clear", arguments=(b1,)),
                expected_truth=True,
                actual_truth=False,
                failure_category=ViolationType.PRECONDITION_UNMET,
                affected_entities=[b1],
                state_snapshot=SymbolicStateSchema(),
            )
            observed = [FactSchema(predicate="clear", arguments=(b1,))]
            ground_truth = [FactSchema(predicate="on", arguments=(b2, b1))]
            return {
                "ground_truth": FaultClass.PERCEPTION_ERROR,
                "counterexample": cex,
                "observed_facts": observed,
                "ground_truth_facts": ground_truth,
            }

        elif fault_class == FaultClass.FORMALIZATION_ERROR:
            prompt = f"Stack {b1} on {b2}. Do not move {b3}."
            cex = CounterexampleSchema(
                counterexample_id=f"CEX-FORM-{idx}",
                action_index=0,
                offending_action=GroundActionSchema(name="pick_up", arguments=(b3,)),
                violated_condition=FactSchema(predicate="holding", arguments=(b3,)),
                expected_truth=False,
                actual_truth=True,
                failure_category=ViolationType.PRECONDITION_UNMET,
                affected_entities=[b3],
                state_snapshot=problem.initial_state.to_schema(),
            )
            return {
                "ground_truth": FaultClass.FORMALIZATION_ERROR,
                "counterexample": cex,
                "problem": problem,
                "natural_language_prompt": prompt,
            }

        elif fault_class == FaultClass.ENVIRONMENT_CHANGE:
            cex = CounterexampleSchema(
                counterexample_id=f"CEX-ENV-{idx}",
                action_index=1,
                offending_action=GroundActionSchema(name="pick_up", arguments=(b1,)),
                violated_condition=FactSchema(predicate="clear", arguments=(b1,)),
                expected_truth=True,
                actual_truth=False,
                failure_category=ViolationType.PRECONDITION_UNMET,
                affected_entities=[b1],
                state_snapshot=SymbolicStateSchema(),
            )
            delta = WorldDeltaSchema(
                delta_id=f"DELTA-{idx}",
                added_facts=[FactSchema(predicate="on", arguments=(b3, b1))],
                removed_facts=[FactSchema(predicate="clear", arguments=(b1,))],
                affected_entities=[b1],
                is_plan_invalidating=True,
            )
            return {
                "ground_truth": FaultClass.ENVIRONMENT_CHANGE,
                "counterexample": cex,
                "environment_deltas": [delta],
            }

        else:  # UNKNOWN_AMBIGUOUS
            cex = CounterexampleSchema(
                counterexample_id=f"CEX-UNK-{idx}",
                action_index=0,
                offending_action=GroundActionSchema(name="noop", arguments=()),
                violated_condition=FactSchema(predicate="undefined_condition", arguments=()),
                expected_truth=True,
                actual_truth=False,
                failure_category=ViolationType.NONE,
                affected_entities=[],
                state_snapshot=SymbolicStateSchema(),
            )
            return {
                "ground_truth": FaultClass.UNKNOWN_AMBIGUOUS,
                "counterexample": cex,
            }

    def run_evaluation(self, instances_per_class: int = 5, seed: int = 42) -> Dict[str, Any]:
        """Runs the attribution matrix evaluation across all 5 classes."""
        class_names = [c.value for c in self.classes]
        matrix: Dict[str, Dict[str, int]] = {
            gt: {pred: 0 for pred in class_names} for gt in class_names
        }

        total = 0
        correct = 0

        for fault_cls in self.classes:
            for idx in range(instances_per_class):
                case = self._generate_test_case(fault_cls, idx)
                gt_label = case["ground_truth"].value

                # Note: Ground truth label is strictly withheld from the attribution call
                attr = self.engine.attribute(
                    counterexample=case["counterexample"],
                    problem=case.get("problem"),
                    natural_language_prompt=case.get("natural_language_prompt"),
                    observed_facts=case.get("observed_facts"),
                    ground_truth_facts=case.get("ground_truth_facts"),
                    environment_deltas=case.get("environment_deltas"),
                )
                pred_label = attr.fault_class.value

                matrix[gt_label][pred_label] += 1
                total += 1
                if gt_label == pred_label:
                    correct += 1

        accuracy = correct / max(1, total)

        per_class: Dict[str, Dict[str, float]] = {}
        for c in class_names:
            tp = matrix[c][c]
            fp = sum(matrix[other][c] for other in class_names if other != c)
            fn = sum(matrix[c][other] for other in class_names if other != c)

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

            per_class[c] = {
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1_score": round(f1, 4),
                "support": tp + fn,
            }

        macro_prec = sum(p["precision"] for p in per_class.values()) / len(class_names)
        macro_rec = sum(p["recall"] for p in per_class.values()) / len(class_names)
        macro_f1 = sum(p["f1_score"] for p in per_class.values()) / len(class_names)

        results = {
            "experiment": "5-Class Fault Attribution Matrix & Precision-Recall Analysis",
            "total_evaluated": total,
            "accuracy": round(accuracy, 4),
            "macro_precision": round(macro_prec, 4),
            "macro_recall": round(macro_rec, 4),
            "macro_f1": round(macro_f1, 4),
            "per_class": per_class,
            "confusion_matrix": matrix,
        }

        report_file = self.output_dir / "fault_attribution_matrix.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        return results


if __name__ == "__main__":
    exp = AttributionMatrixExperiment()
    res = exp.run_evaluation(instances_per_class=10, seed=42)
    print(json.dumps(res, indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_attribution_matrix.py -v`
Expected: PASS

- [ ] **Step 5: Run standalone experiment to generate `evaluation/reports/fault_attribution_matrix.json`**

Run: `.venv\Scripts\python.exe evaluation/experiments/fault_matrix.py`
Verify report file exists and is populated with verified metrics.

---

### Task 2: Property-Based Test Suite Hardening

**Files:**
- Modify: `tests/property/test_properties.py:180-210`

**Interfaces:**
- Consumes:
  - `core.world.state.SymbolicState`
  - `core.world.predicates.Fact`
  - `core.search.heuristics.RPGHeuristic`
  - `core.actions.transition.apply_transition`
- Produces:
  - Verified formal invariants for closed-world hashing, transition determinism, heuristic admissibility at goal, and constraint pruning.

- [ ] **Step 1: Write property tests for state hash invariance, heuristic admissibility, and transition determinism**

Add to `tests/property/test_properties.py`:
```python
    def test_property_state_hash_invariance_to_step_index(self):
        """Property: Closed-world state equality and hash are invariant to step_index."""
        f1 = Fact("on_table", ["b1"])
        f2 = Fact("clear", ["b1"])
        s_step0 = SymbolicState([f1, f2], objects={"b1": "block"}, step_index=0)
        s_step5 = SymbolicState([f1, f2], objects={"b1": "block"}, step_index=5)

        assert s_step0 == s_step5
        assert hash(s_step0) == hash(s_step5)
        # Verify set containment respects closed-world equivalence
        state_set = {s_step0}
        assert s_step5 in state_set

    def test_property_transition_function_strict_determinism(self):
        """Property: STRIPS transition function is deterministic and idempotent."""
        domain = create_blocks_world_domain()
        s0 = SymbolicState(
            [Fact("on_table", ["b1"]), Fact("clear", ["b1"]), Fact("handempty", [])],
            objects={"b1": "block"},
        )
        pickup_op = domain.get_action("pick_up")
        ground_pickup = GroundAction(
            name="pick_up",
            arguments=("b1",),
            preconditions=pickup_op.preconditions,
            add_effects=pickup_op.add_effects,
            del_effects=pickup_op.del_effects,
        )

        res1_state, err1 = apply_transition(s0, ground_pickup)
        res2_state, err2 = apply_transition(s0, ground_pickup)

        assert err1 is None and err2 is None
        assert res1_state == res2_state
        assert hash(res1_state) == hash(res2_state)

    def test_property_rpg_heuristic_goal_state_is_zero(self):
        """Property: RPG heuristic is strictly 0 at any state that satisfies the goal."""
        from core.search.heuristics import RPGHeuristic
        domain = create_blocks_world_domain()
        goal = [Fact("on", ["b1", "b2"])]
        reg = ObjectRegistry(domain.type_hierarchy)
        reg.register_object("b1", "block")
        reg.register_object("b2", "block")
        
        goal_state = SymbolicState(
            [Fact("on", ["b1", "b2"]), Fact("clear", ["b1"]), Fact("on_table", ["b2"])],
            objects=reg.get_all_objects(),
        )
        problem = SymbolicProblem(
            name="HeuristicCheck",
            domain_name=domain.name,
            registry=reg,
            initial_state=goal_state,
            goal_conditions=goal,
        )
        h = RPGHeuristic(problem, domain)
        assert h(goal_state) == 0.0
```

- [ ] **Step 2: Run property test suite**

Run: `pytest tests/property/test_properties.py -v`
Expected: PASS (all 12 property tests pass).

---

### Task 3: Frontend & Static UI Terminology & Metrics Synchronization

**Files:**
- Modify: `frontend/components/BenchmarkTab.tsx:125-144`
- Modify: `frontend/components/AcademicDefenseModal.tsx:55-95`
- Modify: `app/static/index.html:1180-1194`

**Interfaces:**
- Consumes: Live JSON from `/api/benchmark/run`
- Produces: Dynamically rendered recovery advantage (+50.0%) and precise academic terminology without strawman baselines.

- [ ] **Step 1: Update `frontend/components/BenchmarkTab.tsx`**

Replace static "< 5 ms" and "0% recovery" with dynamic values computed from the live experiment:
```tsx
          {/* Research Finding Highlight */}
          <div className="mt-6 rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-4">
            <div className="flex items-center gap-2 text-emerald-400">
              <CheckCircle2 className="h-5 w-5" />
              <span className="font-mono text-xs font-bold uppercase tracking-wider">
                Hypothesis Empirically Evaluated
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-300">
              Generic regeneration (Baseline B3: active candidate sequence re-sampling) achieves partial recovery,
              whereas RE-PLAN-V's counterexample-guided pruning systematically recovers from initially invalid plans
              by eliminating the specific verified failure branch from the search tree.
            </p>
          </div>
```

- [ ] **Step 2: Update `frontend/components/AcademicDefenseModal.tsx`**

Replace absolute claims and outdated 0% recovery text with:
```tsx
            {/* Why 2B Model */}
            <div className="rounded-xl border border-cyan-500/30 bg-cyan-950/20 p-4">
              <h4 className="font-mono text-xs font-bold uppercase text-cyan-300">
                2. "Why a 2-Billion Parameter Model Excels Here"
              </h4>
              <p className="mt-1 leading-relaxed text-slate-300">
                Stand-alone large LLMs fail up to 65% of the time on complex planning benchmarks (PlanBench). 
                In RE-PLAN-V, pairing a local <strong>2B model (Gemma 2 2B / Qwen 2.5) with our authoritative verifier</strong> provides 
                formal plan validity guarantees within modeled domain semantics at zero cloud cost.
              </p>
            </div>
```
And in Section 4:
```tsx
                <div>
                  <strong className="text-cyan-300">Q: What gives RE-PLAN-V a recovery advantage over generic regeneration (B3)?</strong>
                  <p className="mt-0.5 text-slate-400">
                    B3 regenerates alternative candidate sequences without structured failure information, leaving it vulnerable to re-sampling invalid branches. RE-PLAN-V extracts an exact counterexample witness and injects negative pruning constraints, systematically blocking the failing state transition during replanning.
                  </p>
                </div>
```

- [ ] **Step 3: Update `app/static/index.html`**

Update conclusion text:
```javascript
        conclusion.style.display = 'block';
        const oursRec = (runs['OURS_CounterexampleRepair']?.repair_success_rate * 100).toFixed(1);
        const b3Rec = (runs['B3_GenericRegeneration']?.repair_success_rate * 100).toFixed(1);
        const adv = (runs['OURS_CounterexampleRepair']?.recovery_advantage_over_regeneration * 100).toFixed(1) || (oursRec - b3Rec).toFixed(1);
        conclusionText.innerHTML = `
          <strong>Empirical Finding:</strong> Across benchmark instances, 
          <strong>OURS (RE-PLAN-V)</strong> achieved a recovery rate of <strong>${oursRec}%</strong> by injecting formal symbolic constraints derived from counterexample witnesses, outperforming generic candidate re-sampling (B3: <strong>${b3Rec}%</strong>) with a measured recovery advantage of <strong>+${adv}%</strong>.
        `;
```

---

### Task 4: Project Proposal Audit & Alignment Document

**Files:**
- Create: `docs/PROPOSAL_AUDIT_AND_PARITY.md`

**Interfaces:**
- Consumes: `proposal_extracted_text.txt`, `RESEARCH_REPORT.md`, current codebase status
- Produces: Concrete audit report comparing proposal commitments with implemented codebase, providing an Overview Page template and exact required fill-in values.

- [ ] **Step 1: Create `docs/PROPOSAL_AUDIT_AND_PARITY.md`**

Document:
1. Overview Page with Team Details template (Team Name: Path_X, Track: Research, Project: RE-PLAN-V, Topic Areas, GitHub link placeholder, 8-member roster table, Short Description).
2. Section-by-Section Parity Check:
   - Search & Problem Solving: 100% matched (BFS, Best-First, A* with RPG h_max).
   - Knowledge Representation & Reasoning: 100% matched (predicates, MGU unification, resolution, constraints).
   - Verification & Counterexamples: 100% matched (independent plan checking, minimal witness extraction).
   - Fault Attribution: 100% matched (5-class taxonomy with confusion matrix).
   - Baselines: Proposal references B0-B3; matched with active candidate re-sampling.
   - Empirical Results: Synchronize proposal draft with actual +50.0% recovery advantage.
3. Information needed from user:
   - Full names and BITS IDs of team members 1 to 8.
   - Specific role assignments if desired on the overview page.
   - GitHub repository URL.

---

### Task 5: Full Verification, Reproduction & Release Readiness

**Files:**
- Run: `pytest -v`
- Run: `scripts/reproduce_results.py`
- Run: `evaluation/experiments/fault_matrix.py`
- Modify: `.planning/MASTER_HARDENING_PLAN.md`
- Modify: `.superpowers/sdd/master-hardening/progress.md`

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`
Expected: 100% tests pass (across unit, integration, edge cases, properties, scenarios).

- [ ] **Step 2: Run benchmark reproduction and fault matrix generation**

Run:
```bash
.venv\Scripts\python.exe scripts/reproduce_results.py
.venv\Scripts\python.exe evaluation/experiments/fault_matrix.py
```
Expected: `evaluation/reports/primary_research_experiment.json` and `evaluation/reports/fault_attribution_matrix.json` are cleanly generated.

- [ ] **Step 3: Update tracking ledgers**

Mark all stages completed in `.planning/MASTER_HARDENING_PLAN.md` and `.superpowers/sdd/master-hardening/progress.md`.
