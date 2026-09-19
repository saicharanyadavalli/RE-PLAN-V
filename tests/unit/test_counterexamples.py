"""Unit tests for Stage 6: Counterexample Generation."""

import pytest
from core.actions.domain import create_blocks_world_domain
from core.contracts import GroundActionSchema, ViolationType
from core.counterexamples.generator import CounterexampleGenerator
from core.verification.verifier import PlanVerifier
from core.world.constraints import NegativeFactInvariant, ProhibitedEntityActionConstraint
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry


def test_no_counterexample_for_valid_plan():
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
        name="valid_test",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("on", ["b1", "b2"])],
    )

    plan = [
        GroundActionSchema(name="pick_up", arguments=("b1",)),
        GroundActionSchema(name="stack", arguments=("b1", "b2")),
    ]

    verifier = PlanVerifier()
    v_res = verifier.verify(problem, domain, plan)
    assert v_res.is_valid

    gen = CounterexampleGenerator()
    cex = gen.generate(v_res, problem)
    assert cex is None


def test_counterexample_for_precondition_failure():
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
        name="pre_fail",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("on", ["b1", "b2"])],
    )

    # Invalid: try to stack immediately without holding b1
    plan = [GroundActionSchema(name="stack", arguments=("b1", "b2"))]

    verifier = PlanVerifier()
    v_res = verifier.verify(problem, domain, plan)
    assert not v_res.is_valid

    gen = CounterexampleGenerator()
    cex = gen.generate(v_res, problem, counterexample_id="CEX-PRE-001")

    assert cex is not None
    assert cex.counterexample_id == "CEX-PRE-001"
    assert cex.action_index == 0
    assert cex.offending_action.name == "stack"
    assert cex.offending_action.arguments == ("b1", "b2")
    assert cex.violated_condition.predicate == "holding"
    assert "b1" in cex.affected_entities
    assert cex.failure_category == ViolationType.PRECONDITION_UNMET
    assert "precondition" in cex.explanation.lower()


def test_counterexample_for_hard_constraint_failure():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("glass_box", "block")

    init_state = SymbolicState(
        facts=[
            Fact("on_table", ["glass_box"]),
            Fact("clear", ["glass_box"]),
            Fact("handempty", []),
        ],
        objects=reg.get_all_objects(),
    )

    hc = ProhibitedEntityActionConstraint("glass_box", ["pick_up"])
    problem = SymbolicProblem(
        name="hc_test",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("holding", ["glass_box"])],
        hard_constraints=[hc],
    )

    plan = [GroundActionSchema(name="pick_up", arguments=("glass_box",))]

    verifier = PlanVerifier()
    v_res = verifier.verify(problem, domain, plan)
    assert not v_res.is_valid

    gen = CounterexampleGenerator()
    cex = gen.generate(v_res, problem)

    assert cex is not None
    assert cex.failure_category == ViolationType.HARD_CONSTRAINT_VIOLATED
    assert "glass_box" in cex.affected_entities
    assert "prohibited by hard safety constraints" in cex.explanation
