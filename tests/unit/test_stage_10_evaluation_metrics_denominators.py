"""Unit tests for Stage 10 research evaluation denominators, attribution checks, and complexity labels (DEF-10.8, DEF-10.9, DEF-10.10)."""

import pytest
from core.contracts import (
    EvaluationMetricsSchema,
    FaultAttributionSchema,
    FaultClass,
    PlanSchema,
    ReplanningResultSchema,
)
from evaluation.metrics.collector import MetricsCollector
from benchmark.generator.multi_domain_generator import (
    ComplexityTier,
    MultiDomainBenchmarkInstance,
)


def test_metrics_collector_denominator_none_when_zero_invalid_cases():
    """Verify that when 0 initial plans were invalid, repair_success_rate is None (N/A) rather than 100%."""
    collector = MetricsCollector(experiment_id="test_b1_denom", baseline_regeneration_rate=0.5)

    # 5 runs where all initial plans were valid (e.g. B1 classical planner)
    for _ in range(5):
        collector.record_run({
            "is_valid": True,
            "success": True,
            "initial_plan_was_invalid": False,
            "repair_iterations": 0,
            "planning_time_ms": 10.0,
            "verification_time_ms": 1.0,
            "nodes_expanded": 15,
            "plan_cost": 3.0,
        })

    summary = collector.compute_summary()
    assert summary.valid_plan_rate == 1.0
    assert summary.goal_success_rate == 1.0
    # Must be None, not 1.0
    assert summary.repair_success_rate is None
    # Recovery advantage over regeneration must be None when repair rate is undefined
    assert summary.recovery_advantage_over_regeneration is None


def test_metrics_collector_denominator_strictly_invalid_cases():
    """Verify that when invalid cases exist, denominator is len(invalid_cases)."""
    collector = MetricsCollector(experiment_id="test_repair_denom", baseline_regeneration_rate=0.2)

    # 4 runs: 2 initially valid (no repair needed), 2 initially invalid (1 repaired, 1 failed)
    collector.record_run({"is_valid": True, "success": True, "initial_plan_was_invalid": False})
    collector.record_run({"is_valid": True, "success": True, "initial_plan_was_invalid": False})
    collector.record_run({"is_valid": True, "success": True, "initial_plan_was_invalid": True, "repair_time_ms": 25.0})
    collector.record_run({"is_valid": False, "success": False, "initial_plan_was_invalid": True, "repair_time_ms": 30.0})

    summary = collector.compute_summary()
    assert summary.total_instances == 4
    # 1 out of 2 initially invalid cases was successfully repaired
    assert summary.repair_success_rate == pytest.approx(0.5)
    # Advantage = 0.5 - 0.2 = 0.3
    assert summary.recovery_advantage_over_regeneration == pytest.approx(0.3)
    assert summary.avg_repair_time_ms == pytest.approx(27.5)


def test_replanning_result_contains_attribution():
    """Verify ReplanningResultSchema schema supports and preserves attribution."""
    attr = FaultAttributionSchema(
        fault_class=FaultClass.PLANNING_ERROR,
        confidence=0.95,
        affected_stage="PLAN",
        explanation="Action failed precondition",
        evidence=["stack(a,b)"],
    )
    dummy_plan = PlanSchema(actions=[], algorithm="test")
    res = ReplanningResultSchema(
        success=True,
        original_plan=dummy_plan,
        repaired_plan=dummy_plan,
        iterations=1,
        final_verification=None,
        attribution=attr,
        replanning_time_ms=12.5,
        status="VERIFIED",
    )
    assert res.attribution is not None
    assert res.attribution.fault_class == FaultClass.PLANNING_ERROR


def test_multi_domain_benchmark_instance_complexity_labels():
    """Verify that complete vs truncated state spaces are distinguished."""
    inst_complete = MultiDomainBenchmarkInstance(
        instance_id="inst_1",
        domain_id="blocks_world",
        tier=ComplexityTier.TINY,
        prompt="Stack a on b",
        estimated_state_space=5,
        measured_unique_states=5,
        measured_edges=8,
        is_complete=True,
    )
    inst_truncated = MultiDomainBenchmarkInstance(
        instance_id="inst_2",
        domain_id="software_workflow",
        tier=ComplexityTier.LARGE,
        prompt="Deploy app",
        estimated_state_space=1317,
        measured_unique_states=3000,
        measured_edges=12000,
        is_complete=False,
    )

    assert inst_complete.is_complete is True
    assert inst_truncated.is_complete is False
    assert inst_complete.measured_unique_states == 5
    assert inst_truncated.measured_unique_states == 3000
