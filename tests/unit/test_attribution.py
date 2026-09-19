"""Unit tests for Stage 7: Evidence-Guided Fault Attribution & Mutation Framework."""

import pytest
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
from core.world.constraints import ProhibitedEntityActionConstraint
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry


def test_attribute_planning_error():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("b1", "block")
    reg.register_object("b2", "block")

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
        name="planning_err_test",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("on", ["b1", "b2"])],
    )

    # Invalid plan chosen by planner
    invalid_plan = [GroundActionSchema(name="stack", arguments=("b1", "b2"))]

    verifier = PlanVerifier()
    v_res = verifier.verify(problem, domain, invalid_plan)
    cex = CounterexampleGenerator().generate(v_res, problem)

    engine = FaultAttributionEngine()
    attribution = engine.attribute(counterexample=cex, problem=problem)

    assert attribution.fault_class == FaultClass.PLANNING_ERROR
    assert attribution.confidence >= 0.8
    assert "Search / Planner" in attribution.affected_stage
    assert len(attribution.evidence) > 0


def test_attribute_perception_error():
    cex = CounterexampleSchema(
        counterexample_id="CEX-PERC",
        action_index=0,
        offending_action=GroundActionSchema(name="pick_up", arguments=("b1",)),
        violated_condition=FactSchema(predicate="clear", arguments=("b1",)),
        expected_truth=True,
        actual_truth=False,
        failure_category=ViolationType.PRECONDITION_UNMET,
        affected_entities=["b1"],
        state_snapshot=SymbolicStateSchema(),
    )

    # Observed facts claimed clear(b1) was True, but ground truth didn't have it
    observed = [FactSchema(predicate="clear", arguments=("b1",))]
    ground_truth = [FactSchema(predicate="on", arguments=("b2", "b1"))]

    engine = FaultAttributionEngine()
    attribution = engine.attribute(
        counterexample=cex,
        observed_facts=observed,
        ground_truth_facts=ground_truth,
    )

    assert attribution.fault_class == FaultClass.PERCEPTION_ERROR
    assert attribution.confidence >= 0.85
    assert "Perception / Vision" in attribution.affected_stage


def test_attribute_formalization_error():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("red_box", "block")
    reg.register_object("glass", "block")

    init_state = SymbolicState(
        facts=[
            Fact("on_table", ["red_box"]),
            Fact("clear", ["red_box"]),
            Fact("on_table", ["glass"]),
            Fact("clear", ["glass"]),
            Fact("handempty", []),
        ],
        objects=reg.get_all_objects(),
    )

    # Problem omitted hard constraint on glass
    problem = SymbolicProblem(
        name="formalization_test",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("holding", ["glass"])],
    )

    prompt = "Move the red box next to the blue box. Do not touch glass."
    cex = CounterexampleSchema(
        counterexample_id="CEX-FORMAL",
        action_index=0,
        offending_action=GroundActionSchema(name="pick_up", arguments=("glass",)),
        violated_condition=FactSchema(predicate="holding", arguments=("glass",)),
        expected_truth=False,
        actual_truth=True,
        failure_category=ViolationType.PRECONDITION_UNMET,
        affected_entities=["glass"],
        state_snapshot=init_state.to_schema(),
    )

    engine = FaultAttributionEngine()
    attribution = engine.attribute(
        counterexample=cex,
        problem=problem,
        natural_language_prompt=prompt,
    )

    assert attribution.fault_class == FaultClass.FORMALIZATION_ERROR
    assert "Formalization" in attribution.affected_stage


def test_attribute_environment_change():
    cex = CounterexampleSchema(
        counterexample_id="CEX-ENV",
        action_index=1,
        offending_action=GroundActionSchema(name="pick_up", arguments=("b1",)),
        violated_condition=FactSchema(predicate="clear", arguments=("b1",)),
        expected_truth=True,
        actual_truth=False,
        failure_category=ViolationType.PRECONDITION_UNMET,
        affected_entities=["b1"],
        state_snapshot=SymbolicStateSchema(),
    )

    delta = WorldDeltaSchema(
        delta_id="DELTA-01",
        added_facts=[FactSchema(predicate="on", arguments=("intruder", "b1"))],
        removed_facts=[FactSchema(predicate="clear", arguments=("b1",))],
        affected_entities=["b1"],
        is_plan_invalidating=True,
    )

    engine = FaultAttributionEngine()
    attribution = engine.attribute(
        counterexample=cex,
        environment_deltas=[delta],
    )

    assert attribution.fault_class == FaultClass.ENVIRONMENT_CHANGE
    assert "Environment" in attribution.affected_stage


def test_attribute_unknown_ambiguous():
    cex = CounterexampleSchema(
        counterexample_id="CEX-UNKNOWN",
        action_index=0,
        offending_action=GroundActionSchema(name="noop", arguments=()),
        violated_condition=FactSchema(predicate="unknown", arguments=()),
        expected_truth=True,
        actual_truth=False,
        failure_category=ViolationType.NONE,
        affected_entities=[],
        state_snapshot=SymbolicStateSchema(),
    )

    engine = FaultAttributionEngine()
    attribution = engine.attribute(counterexample=cex)

    assert attribution.fault_class == FaultClass.UNKNOWN_AMBIGUOUS
    assert attribution.confidence <= 0.5


def test_fault_injector_mutations():
    injector = FaultInjector(seed=123)

    # 1. Planning error mutation
    orig_plan = PlanSchema(
        actions=[
            GroundActionSchema(name="pick_up", arguments=("b1",)),
            GroundActionSchema(name="stack", arguments=("b1", "b2")),
        ]
    )
    mutated_plan = injector.inject_planning_error(orig_plan)
    assert mutated_plan.actions[0].name == "stack"
    assert mutated_plan.actions[1].name == "pick_up"

    # 2. Environment delta mutation
    s0 = SymbolicState(facts=[Fact("clear", ["b1"])])
    new_s, delta = injector.inject_environment_change(s0, Fact("clear", ["b1"]))
    assert not new_s.holds(Fact("clear", ["b1"]))
    assert delta.is_plan_invalidating
