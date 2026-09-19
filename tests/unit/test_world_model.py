"""Unit tests for Stage 1: Unified Symbolic World Model."""

import pytest
from core.world.types import TypeHierarchy, TypedObject, ObjectRegistry
from core.world.predicates import PredicateDefinition, Fact
from core.world.state import SymbolicState
from core.world.constraints import (
    NegativeFactInvariant,
    FunctionalDependencyInvariant,
    ProhibitedEntityActionConstraint,
)
from core.world.problem import SymbolicProblem


def test_type_hierarchy_and_subtyping():
    th = TypeHierarchy()
    th.add_type("location", "object")
    th.add_type("room", "location")
    th.add_type("item", "object")
    th.add_type("fragile_item", "item")

    assert th.is_subtype("room", "location")
    assert th.is_subtype("room", "object")
    assert th.is_subtype("fragile_item", "item")
    assert th.is_subtype("fragile_item", "object")
    assert not th.is_subtype("item", "fragile_item")
    assert not th.is_subtype("room", "item")


def test_object_registry():
    reg = ObjectRegistry()
    reg.register_type("block", "object")
    reg.register_type("surface", "object")

    reg.register_object("b1", "block")
    reg.register_object("b2", "block")
    reg.register_object("table", "surface")

    assert reg.has_object("b1")
    assert reg.get_type_of("b1") == "block"
    assert reg.get_type_of("table") == "surface"
    assert set(reg.get_objects_of_type("block")) == {"b1", "b2"}
    assert reg.get_objects_of_type("surface") == ["table"]


def test_predicate_validation():
    reg = ObjectRegistry()
    reg.register_type("block", "object")
    reg.register_type("surface", "object")
    reg.register_object("b1", "block")
    reg.register_object("table", "surface")

    pred_on = PredicateDefinition("on", ["block", "object"])
    
    # Valid
    ok, err = pred_on.validate_arguments(["b1", "table"], reg)
    assert ok
    assert err is None

    # Arity mismatch
    ok, err = pred_on.validate_arguments(["b1"], reg)
    assert not ok
    assert "expects 2 arguments" in err

    # Type mismatch (table is surface, not block)
    ok, err = pred_on.validate_arguments(["table", "b1"], reg)
    assert not ok
    assert "Type mismatch" in err

    # Unknown entity
    ok, err = pred_on.validate_arguments(["b1", "nonexistent"], reg)
    assert not ok
    assert "Unknown entity" in err


def test_fact_operations_and_immutability():
    f1 = Fact("on", ["b1", "table"])
    f2 = Fact("on", ["b1", "table"])
    f3 = Fact("clear", ["b1"])

    assert f1 == f2
    assert hash(f1) == hash(f2)
    assert f1 != f3

    neg_f1 = f1.negated_version()
    assert neg_f1.is_negated
    assert neg_f1.to_string() == "not(on(b1, table))"
    assert neg_f1.positive_version() == f1


def test_symbolic_state_immutability_and_closed_world():
    f1 = Fact("on", ["b1", "table"])
    f2 = Fact("clear", ["b1"])
    f_absent = Fact("on", ["b2", "b1"])

    state = SymbolicState(facts=[f1, f2], objects={"b1": "block", "table": "surface"})

    assert state.holds(f1)
    assert state.holds(f2)
    assert not state.holds(f_absent)
    # Negated lookup in closed world
    assert state.holds(f_absent.negated_version())
    assert not state.holds(f1.negated_version())

    # Effect application
    add_effect = Fact("on", ["b2", "b1"])
    del_effect = Fact("clear", ["b1"])
    new_state = state.apply_effects(adds=[add_effect], dels=[del_effect])

    # Original state is unmodified (immutability)
    assert state.holds(del_effect)
    assert not state.holds(add_effect)

    # New state has changes
    assert new_state.holds(add_effect)
    assert not new_state.holds(del_effect)
    assert new_state.holds(f1)
    assert new_state.step_index == state.step_index + 1


def test_invariants_and_constraints():
    f_forbidden = Fact("holding", ["glass"])
    inv = NegativeFactInvariant(f_forbidden)

    state_safe = SymbolicState(facts=[Fact("clear", ["b1"])])
    ok, msg = inv.check(state_safe)
    assert ok

    state_unsafe = SymbolicState(facts=[f_forbidden])
    ok, msg = inv.check(state_unsafe)
    assert not ok
    assert "Invariant violation" in msg

    # Functional dependency: block b1 cannot be on both table and b2
    func_inv = FunctionalDependencyInvariant("on", key_arg_idx=0, value_arg_idx=1)
    state_multi = SymbolicState(facts=[Fact("on", ["b1", "table"]), Fact("on", ["b1", "b2"])])
    ok, msg = func_inv.check(state_multi)
    assert not ok
    assert "Functional dependency violated" in msg

    # Hard constraint: protect glass from move
    hc = ProhibitedEntityActionConstraint("glass", ["move", "drop"])
    ok, msg = hc.check_action(state_safe, "move", ["glass", "loc1"])
    assert not ok
    assert "Hard constraint violation" in msg

    ok, msg = hc.check_action(state_safe, "move", ["b1", "loc1"])
    assert ok


def test_symbolic_problem_goal_satisfaction_and_validation():
    reg = ObjectRegistry()
    reg.register_type("block", "object")
    reg.register_object("b1", "block")
    reg.register_object("b2", "block")

    init_facts = [Fact("clear", ["b1"]), Fact("clear", ["b2"])]
    init_state = SymbolicState(facts=init_facts, objects=reg.get_all_objects())

    goal = [Fact("on", ["b1", "b2"])]
    problem = SymbolicProblem(
        name="test_problem",
        domain_name="blocks",
        registry=reg,
        initial_state=init_state,
        goal_conditions=goal,
    )

    assert not problem.is_goal_satisfied(init_state)
    assert problem.find_unmet_goals(init_state) == goal

    solved_state = init_state.apply_effects(adds=[Fact("on", ["b1", "b2"])], dels=[])
    assert problem.is_goal_satisfied(solved_state)
    assert len(problem.find_unmet_goals(solved_state)) == 0

    # Validation should pass
    errors = problem.validate()
    assert errors == []

    # Invalid problem with unknown object in goal
    bad_problem = SymbolicProblem(
        name="bad_problem",
        domain_name="blocks",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("on", ["b1", "unknown_obj"])],
    )
    errors = bad_problem.validate()
    assert len(errors) == 1
    assert "unknown_obj" in errors[0]
