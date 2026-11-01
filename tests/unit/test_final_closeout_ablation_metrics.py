"""Unit tests for Stage 11 closeout: Ablation metrics, repair timing isolation, and ground-truth attribution evaluation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from benchmark.generator.generator import BenchmarkGenerator
from core.actions.domain import create_blocks_world_domain
from core.contracts import (
    FaultAttributionSchema,
    FaultClass,
    GroundActionSchema,
    PlanSchema,
)
from evaluation.ablations.configurations import AblationStudyRunner


@pytest.fixture
def test_setup():
    domain = create_blocks_world_domain()
    gen = BenchmarkGenerator(seed=42)
    inst = gen.generate_suite("blocks_world", count=1, inject_faults=False)[0]
    runner = AblationStudyRunner()
    first_goal = inst.goal_facts[0]
    invalid_candidate = PlanSchema(
        actions=[GroundActionSchema(name="stack", arguments=tuple(first_goal.arguments))],
        algorithm="InvalidCandidate",
    )
    return domain, inst, runner, invalid_candidate


def test_repair_time_not_aliased_to_planning_time(test_setup):
    """Assert repair_time_ms is NOT equal to planning_time_ms when planning time and pure repair time differ."""
    domain, inst, runner, invalid_candidate = test_setup

    res = runner.run_ablation("full", inst, domain, initial_candidate=invalid_candidate)

    assert res["ablation"] == "full"
    assert res["repair_attempted"] is True
    assert "planning_time_ms" in res
    assert "repair_time_ms" in res
    assert res["repair_time_ms"] is not None
    assert res["planning_time_ms"] is not None

    # Verify that planning_time_ms and repair_time_ms are isolated separate timers
    assert res["repair_time_ms"] != res["planning_time_ms"], (
        f"repair_time_ms ({res['repair_time_ms']}) was aliased to planning_time_ms ({res['planning_time_ms']})"
    )
    assert res["pure_repair_time_ms"] == res["repair_time_ms"]


def test_without_verifier_and_without_repair_have_repair_attempted_false(test_setup):
    """Assert without_verifier and without_repair have repair_attempted == False and repair_time_ms is None."""
    domain, inst, runner, invalid_candidate = test_setup

    # 1. without_verifier
    res_no_verif = runner.run_ablation("without_verifier", inst, domain, initial_candidate=invalid_candidate)
    assert res_no_verif["ablation"] == "without_verifier"
    assert res_no_verif["repair_attempted"] is False
    assert res_no_verif["repair_time_ms"] is None
    assert res_no_verif["attribution_correct"] is None

    # 2. without_repair
    res_no_repair = runner.run_ablation("without_repair", inst, domain, initial_candidate=invalid_candidate)
    assert res_no_repair["ablation"] == "without_repair"
    assert res_no_repair["repair_attempted"] is False
    assert res_no_repair["repair_time_ms"] is None
    assert res_no_repair["attribution_correct"] is None


def test_without_attribution_has_attribution_correct_none(test_setup):
    """Assert without_attribution has attribution_correct is None."""
    domain, inst, runner, invalid_candidate = test_setup

    res_no_attr = runner.run_ablation("without_attribution", inst, domain, initial_candidate=invalid_candidate)
    assert res_no_attr["ablation"] == "without_attribution"
    assert res_no_attr["repair_attempted"] is True
    assert res_no_attr["attribution_correct"] is None


def test_full_variant_evaluates_attribution_against_ground_truth(test_setup):
    """Assert full variant evaluates attribution against ground truth (not hardcoded True).
    
    Mock predicted attribution to PERCEPTION_ERROR when ground truth is PLANNING_ERROR -> assert attribution_correct is False!
    Mock predicted attribution to PLANNING_ERROR -> assert attribution_correct is True!
    """
    domain, inst, runner, invalid_candidate = test_setup

    dummy_perception_error = FaultAttributionSchema(
        fault_class=FaultClass.PERCEPTION_ERROR,
        affected_stage="perception",
        confidence=0.85,
        explanation="Simulated false perception attribution",
    )

    dummy_planning_error = FaultAttributionSchema(
        fault_class=FaultClass.PLANNING_ERROR,
        affected_stage="planning",
        confidence=0.95,
        explanation="Simulated true planning attribution",
    )

    # Sub-case A: Mock attribution as PERCEPTION_ERROR (mismatch against ground-truth PLANNING_ERROR)
    recorded_runs_a = []

    def mock_ablation_perception(v, *args, **kwargs):
        return {
            "ablation": v,
            "is_valid": True,
            "success": True,
            "plan_cost": 2.0,
            "planning_time_ms": 10.0,
            "verification_time_ms": 1.0,
            "repair_time_ms": 4.0 if v != "without_repair" else None,
            "pure_repair_time_ms": 4.0 if v != "without_repair" else 0.0,
            "nodes_expanded": 12,
            "repair_iterations": 1,
            "attribution": dummy_perception_error if v == "full" else None,
            "repair_attempted": (v not in ("without_verifier", "without_repair")),
        }

    with patch.object(runner, "run_ablation", side_effect=mock_ablation_perception):
        with patch("evaluation.metrics.collector.MetricsCollector.record_run", side_effect=lambda r: recorded_runs_a.append(dict(r))):
            runner.run_ablation_experiment(num_instances=1, seed=42)
            full_runs = [r for r in recorded_runs_a if r.get("ablation") == "full"]
            assert len(full_runs) == 1
            assert full_runs[0]["attribution_correct"] is False, "Expected attribution_correct to be False for PERCEPTION_ERROR mismatch"

    # Sub-case B: Mock attribution as PLANNING_ERROR (matches ground-truth PLANNING_ERROR)
    recorded_runs_b = []

    def mock_ablation_planning(v, *args, **kwargs):
        return {
            "ablation": v,
            "is_valid": True,
            "success": True,
            "plan_cost": 2.0,
            "planning_time_ms": 10.0,
            "verification_time_ms": 1.0,
            "repair_time_ms": 4.0 if v != "without_repair" else None,
            "pure_repair_time_ms": 4.0 if v != "without_repair" else 0.0,
            "nodes_expanded": 12,
            "repair_iterations": 1,
            "attribution": dummy_planning_error if v == "full" else None,
            "repair_attempted": (v not in ("without_verifier", "without_repair")),
        }

    with patch.object(runner, "run_ablation", side_effect=mock_ablation_planning):
        with patch("evaluation.metrics.collector.MetricsCollector.record_run", side_effect=lambda r: recorded_runs_b.append(dict(r))):
            runner.run_ablation_experiment(num_instances=1, seed=42)
            full_runs = [r for r in recorded_runs_b if r.get("ablation") == "full"]
            assert len(full_runs) == 1
            assert full_runs[0]["attribution_correct"] is True, "Expected attribution_correct to be True for PLANNING_ERROR match"
