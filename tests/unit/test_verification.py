"""Unit tests for Stage 5: Independent Formal Plan Verification."""

import pytest
from core.actions.domain import create_blocks_world_domain
from core.actions.instantiation import GroundAction
from core.contracts import GroundActionSchema, PlanSchema, ViolationType
from core.verification.verifier import PlanVerifier
from core.world.constraints import NegativeFactInvariant, ProhibitedEntityActionConstraint
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry


def test_verify_valid_plan():
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
    res = verifier.verify(problem, domain, plan)

    assert res.is_valid
    assert res.violation_type == ViolationType.NONE
    assert res.failed_step_index is None
    assert len(res.trace) == 2
    assert res.trace[0].is_valid
    assert res.trace[1].is_valid


def test_verify_precondition_failure_step_0():
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
        name="pre_fail_step0",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("on", ["b1", "b2"])],
    )

    # Immediately try to stack without picking up
    plan = [GroundActionSchema(name="stack", arguments=("b1", "b2"))]

    verifier = PlanVerifier()
    res = verifier.verify(problem, domain, plan)

    assert not res.is_valid
    assert res.failed_step_index == 0
    assert res.violation_type == ViolationType.PRECONDITION_UNMET
    assert res.failed_action.name == "stack"
    assert res.violated_condition.predicate == "holding"


def test_verify_precondition_failure_step_1():
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
        name="pre_fail_step1",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("on", ["b1", "b2"])],
    )

    # pick_up(b1), then pick_up(b2) while holding b1 (fails because hand is not empty)
    plan = [
        GroundActionSchema(name="pick_up", arguments=("b1",)),
        GroundActionSchema(name="pick_up", arguments=("b2",)),
    ]

    verifier = PlanVerifier()
    res = verifier.verify(problem, domain, plan)

    assert not res.is_valid
    assert res.failed_step_index == 1
    assert res.violation_type == ViolationType.PRECONDITION_UNMET
    assert res.failed_action.arguments == ("b2",)
    assert len(res.trace) == 2
    assert res.trace[0].is_valid
    assert not res.trace[1].is_valid


def test_verify_invariant_violation():
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

    # Invariant: can NEVER hold glass_box
    inv = NegativeFactInvariant(Fact("holding", ["glass_box"]))
    problem = SymbolicProblem(
        name="inv_fail",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("on_table", ["glass_box"])],
        invariants=[inv],
    )

    plan = [GroundActionSchema(name="pick_up", arguments=("glass_box",))]

    verifier = PlanVerifier()
    res = verifier.verify(problem, domain, plan)

    assert not res.is_valid
    assert res.failed_step_index == 0
    assert res.violation_type == ViolationType.INVARIANT_VIOLATED
    assert "holding(glass_box)" in res.explanation


def test_verify_hard_constraint_violation():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("b1", "block")

    init_state = SymbolicState(
        facts=[
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("handempty", []),
        ],
        objects=reg.get_all_objects(),
    )

    hc = ProhibitedEntityActionConstraint("b1", ["pick_up"])
    problem = SymbolicProblem(
        name="hc_fail",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("on_table", ["b1"])],
        hard_constraints=[hc],
    )

    plan = [GroundActionSchema(name="pick_up", arguments=("b1",))]

    verifier = PlanVerifier()
    res = verifier.verify(problem, domain, plan)

    assert not res.is_valid
    assert res.failed_step_index == 0
    assert res.violation_type == ViolationType.HARD_CONSTRAINT_VIOLATED


def test_verify_invalid_action_operator():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("b1", "block")

    init_state = SymbolicState(facts=[Fact("clear", ["b1"])], objects=reg.get_all_objects())
    problem = SymbolicProblem(
        name="invalid_op",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("clear", ["b1"])],
    )

    plan = [GroundActionSchema(name="teleport", arguments=("b1",))]
    verifier = PlanVerifier()
    res = verifier.verify(problem, domain, plan)

    assert not res.is_valid
    assert res.failed_step_index == 0
    assert res.violation_type == ViolationType.INVALID_ACTION


def test_verify_goal_unmet():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("b1", "block")

    init_state = SymbolicState(
        facts=[
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("handempty", []),
        ],
        objects=reg.get_all_objects(),
    )

    # Goal is to hold b1, but plan puts it down or does nothing
    problem = SymbolicProblem(
        name="goal_unmet",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("holding", ["b1"])],
    )

    # Empty plan
    verifier = PlanVerifier()
    res = verifier.verify(problem, domain, [])

    assert not res.is_valid
    assert res.violation_type == ViolationType.GOAL_UNMET
    assert res.violated_condition.predicate == "holding"
