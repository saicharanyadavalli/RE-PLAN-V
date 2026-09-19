"""Unit tests for Stage 11: Dynamic Environment & Reactive Replanning."""

import pytest
from core.actions.domain import create_blocks_world_domain
from core.contracts import FactSchema, GroundActionSchema, PlanSchema
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry
from dynamic.monitor import WorldDeltaMonitor
from dynamic.replanner import DynamicReplanner


def test_world_delta_monitor():
    s0 = SymbolicState(
        facts=[
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("on_table", ["b2"]),
        ],
        objects={"b1": "block", "b2": "block"},
    )

    new_obs = [
        FactSchema(predicate="on_table", arguments=("b1",)),
        FactSchema(predicate="clear", arguments=("b1",)),
        # b2 is no longer on table; instead on(b2, b1)
        FactSchema(predicate="on", arguments=("b2", "b1")),
    ]

    monitor = WorldDeltaMonitor()
    delta = monitor.compute_delta(s0, new_obs)

    assert len(delta.added_facts) == 1
    assert delta.added_facts[0].predicate == "on"
    assert len(delta.removed_facts) == 1
    assert delta.removed_facts[0].predicate == "on_table"
    assert "b2" in delta.affected_entities


def test_irrelevant_environment_change_no_replanning():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("b1", "block")
    reg.register_object("b2", "block")
    reg.register_object("distractor", "block")

    init_state = SymbolicState(
        facts=[
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("on_table", ["b2"]),
            Fact("clear", ["b2"]),
            Fact("on_table", ["distractor"]),
            Fact("clear", ["distractor"]),
            Fact("handempty", []),
        ],
        objects=reg.get_all_objects(),
    )

    problem = SymbolicProblem(
        name="irrelevant_test",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("on", ["b1", "b2"])],
    )

    plan = PlanSchema(
        actions=[
            GroundActionSchema(name="pick_up", arguments=("b1",)),
            GroundActionSchema(name="stack", arguments=("b1", "b2")),
        ]
    )

    # Observation: distractor changed attribute/color or moved to another spot
    # (b1 and b2 remain on_table, clear, and hand is empty)
    new_obs = [
        FactSchema(predicate="on_table", arguments=("b1",)),
        FactSchema(predicate="clear", arguments=("b1",)),
        FactSchema(predicate="on_table", arguments=("b2",)),
        FactSchema(predicate="clear", arguments=("b2",)),
        FactSchema(predicate="handempty", arguments=()),
        # distractor moved
        FactSchema(predicate="clear", arguments=("distractor",)),
    ]

    replanner = DynamicReplanner()
    replan_triggered, active_plan, delta = replanner.process_observation(
        current_state=init_state,
        remaining_plan=plan,
        problem=problem,
        domain=domain,
        new_observation_facts=new_obs,
    )

    # Must NOT trigger replanning for irrelevant change
    assert not replan_triggered
    assert not delta.is_plan_invalidating
    assert active_plan == plan


def test_relevant_environment_change_triggers_replanning():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("b1", "block")
    reg.register_object("b2", "block")
    reg.register_object("obstacle", "block")

    init_state = SymbolicState(
        facts=[
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("on_table", ["b2"]),
            Fact("clear", ["b2"]),
            Fact("handempty", []),
        ],
        objects=reg.get_all_objects(),
    )

    problem = SymbolicProblem(
        name="relevant_test",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("on", ["b1", "b2"])],
    )

    plan = PlanSchema(
        actions=[
            GroundActionSchema(name="pick_up", arguments=("b1",)),
            GroundActionSchema(name="stack", arguments=("b1", "b2")),
        ]
    )

    # Disruption: obstacle placed directly on b2! Now b2 is NOT clear!
    new_obs = [
        FactSchema(predicate="on_table", arguments=("b1",)),
        FactSchema(predicate="clear", arguments=("b1",)),
        FactSchema(predicate="on_table", arguments=("b2",)),
        FactSchema(predicate="on", arguments=("obstacle", "b2")),
        FactSchema(predicate="clear", arguments=("obstacle",)),
        FactSchema(predicate="handempty", arguments=()),
    ]

    replanner = DynamicReplanner()
    replan_triggered, new_plan, delta = replanner.process_observation(
        current_state=init_state,
        remaining_plan=plan,
        problem=problem,
        domain=domain,
        new_observation_facts=new_obs,
    )

    # Must detect that change is RELEVANT and triggers replan
    assert replan_triggered
    assert delta.is_plan_invalidating
    assert new_plan.is_success
    # New plan must unstack/remove obstacle before stacking b1 on b2
    act_names = [a.name for a in new_plan.actions]
    assert "unstack" in act_names or "put_down" in act_names
    assert new_plan.actions[-1].name == "stack"
    assert new_plan.actions[-1].arguments == ("b1", "b2")
