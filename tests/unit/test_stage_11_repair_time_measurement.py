"""Stage 11 Unit Tests: Isolated Pure Repair Time Measurement and Metric Aggregation."""

from __future__ import annotations

import pytest
from core.actions.domain import create_blocks_world_domain
from core.contracts import GroundActionSchema, PlanSchema
from core.replanning.loop import ReplanningEngine
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry
from evaluation.baselines.runners import BaselineB0_DirectNeural, BaselineB1_FormalizedPlanner, BaselineB3_GenericRegeneration, MethodOurs_CounterexampleRepair
from evaluation.metrics.collector import MetricsCollector


def test_pure_repair_time_zero_when_initially_valid():
    """Verify that pure_repair_time_ms is strictly 0.0 when initial candidate is already valid."""
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    for b in ["b1", "b2"]:
        reg.register_object(b, "block")

    s0 = SymbolicState([
        Fact("on_table", ["b1"]),
        Fact("clear", ["b1"]),
        Fact("on_table", ["b2"]),
        Fact("clear", ["b2"]),
        Fact("handempty", []),
    ])
    goals = [Fact("on", ["b1", "b2"])]
    problem = SymbolicProblem("valid_task", "blocks_world", reg, s0, goals)

    # Valid candidate
    valid_candidate = PlanSchema(
        actions=[
            GroundActionSchema(name="pick_up", arguments=("b1",)),
            GroundActionSchema(name="stack", arguments=("b1", "b2")),
        ]
    )

    engine = ReplanningEngine()
    res = engine.run_repair_loop(problem, domain, initial_candidate=valid_candidate)

    assert res.success is True
    assert res.iterations == 0
    assert res.pure_repair_time_ms == 0.0


def test_pure_repair_time_positive_when_repair_executed():
    """Verify that pure_repair_time_ms is isolated and strictly positive when repair loop runs."""
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    for b in ["b1", "b2"]:
        reg.register_object(b, "block")

    s0 = SymbolicState([
        Fact("on_table", ["b1"]),
        Fact("clear", ["b1"]),
        Fact("on_table", ["b2"]),
        Fact("clear", ["b2"]),
        Fact("handempty", []),
    ])
    goals = [Fact("on", ["b1", "b2"])]
    problem = SymbolicProblem("invalid_task", "blocks_world", reg, s0, goals)

    # Invalid candidate: tries to stack without picking up
    invalid_candidate = PlanSchema(
        actions=[
            GroundActionSchema(name="stack", arguments=("b1", "b2")),
        ]
    )

    engine = ReplanningEngine()
    res = engine.run_repair_loop(problem, domain, initial_candidate=invalid_candidate)

    assert res.success is True
    assert res.iterations > 0
    assert res.pure_repair_time_ms > 0.0
    assert res.pure_repair_time_ms <= res.replanning_time_ms


def test_metrics_collector_handles_none_repair_time_for_baselines():
    """Verify MetricsCollector sets avg_repair_time_ms to None when no repair was run."""
    collector_b0 = MetricsCollector(experiment_id="b0_test")
    collector_b0.record_run({
        "method": "B0_DirectNeural",
        "is_valid": False,
        "success": False,
        "planning_time_ms": 1.5,
        "repair_time_ms": None,
        "repair_iterations": 0,
        "initial_plan_was_invalid": False,
    })
    summary_b0 = collector_b0.compute_summary()
    assert summary_b0.avg_repair_time_ms is None

    # For OURS with repairs, avg_repair_time_ms must be a valid float
    collector_ours = MetricsCollector(experiment_id="ours_test")
    collector_ours.record_run({
        "method": "OURS_CounterexampleRepair",
        "is_valid": True,
        "success": True,
        "planning_time_ms": 12.0,
        "repair_time_ms": 8.5,
        "repair_iterations": 1,
        "initial_plan_was_invalid": True,
    })
    summary_ours = collector_ours.compute_summary()
    assert summary_ours.avg_repair_time_ms == 8.5
