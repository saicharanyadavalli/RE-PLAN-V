"""Unit tests for Stage 2: Action Definitions, Grounding, Legal Generation, and Authoritative Transitions."""

import pytest
from core.actions.definition import ActionDefinition, ActionParameter
from core.actions.instantiation import GroundAction
from core.actions.transition import apply_transition
from core.actions.generator import LegalActionGenerator
from core.actions.domain import create_blocks_world_domain, create_gridworld_domain
from core.world.predicates import Fact
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry


def test_action_parameter_and_instantiation():
    param = ActionParameter("b", "block")
    assert param.name == "?b"
    assert param.type_name == "block"

    domain = create_blocks_world_domain()
    pick_up_def = domain.get_action("pick_up")
    assert pick_up_def is not None

    ground_act = pick_up_def.instantiate({"?b": "blockA"})
    assert ground_act.name == "pick_up"
    assert ground_act.arguments == ("blockA",)
    assert Fact("clear", ["blockA"]) in ground_act.preconditions
    assert Fact("holding", ["blockA"]) in ground_act.add_effects
    assert Fact("clear", ["blockA"]) in ground_act.del_effects


def test_authoritative_transition_success_and_failure():
    domain = create_blocks_world_domain()
    pick_up_def = domain.get_action("pick_up")
    ground_pick = pick_up_def.instantiate({"?b": "b1"})

    # State where b1 is on table, clear, and hand is empty
    init_state = SymbolicState(
        facts=[
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("handempty", []),
        ],
        objects={"b1": "block"},
    )

    # Transition success
    new_state, err = apply_transition(init_state, ground_pick)
    assert err is None
    assert new_state.holds(Fact("holding", ["b1"]))
    assert not new_state.holds(Fact("on_table", ["b1"]))
    assert not new_state.holds(Fact("clear", ["b1"]))
    assert not new_state.holds(Fact("handempty", []))
    assert new_state.step_index == 1

    # Transition failure: attempting pick_up again when hand is not empty
    fail_state, err = apply_transition(new_state, ground_pick)
    assert err is not None
    assert "Precondition unmet" in err
    assert fail_state == new_state  # State unchanged on failure


def test_legal_action_generation():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("b1", "block")
    reg.register_object("b2", "block")

    generator = LegalActionGenerator(domain.get_all_actions(), reg)
    all_ground = generator.generate_all_ground_actions()
    
    # pick_up(2) + put_down(2) + stack(4) + unstack(4) = 12 total ground actions
    assert len(all_ground) == 12

    # Initial state: b1 and b2 on table, clear, hand empty
    state = SymbolicState(
        facts=[
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("on_table", ["b2"]),
            Fact("clear", ["b2"]),
            Fact("handempty", []),
        ],
        objects=reg.get_all_objects(),
    )

    applicable = generator.get_applicable_actions(state)
    # Only pick_up(b1) and pick_up(b2) are applicable
    assert len(applicable) == 2
    applicable_names = {a.to_string() for a in applicable}
    assert applicable_names == {"pick_up(b1)", "pick_up(b2)"}


def test_full_blocks_world_trace():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("b1", "block")
    reg.register_object("b2", "block")

    # Initial: b1 and b2 on table
    s0 = SymbolicState(
        facts=[
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("on_table", ["b2"]),
            Fact("clear", ["b2"]),
            Fact("handempty", []),
        ],
        objects=reg.get_all_objects(),
    )

    # 1. pick_up(b1)
    act1 = domain.get_action("pick_up").instantiate({"?b": "b1"})
    s1, err = apply_transition(s0, act1)
    assert err is None
    assert s1.holds(Fact("holding", ["b1"]))

    # 2. stack(b1, b2)
    act2 = domain.get_action("stack").instantiate({"?b": "b1", "?under": "b2"})
    s2, err = apply_transition(s1, act2)
    assert err is None
    assert s2.holds(Fact("on", ["b1", "b2"]))
    assert s2.holds(Fact("clear", ["b1"]))
    assert not s2.holds(Fact("clear", ["b2"]))
    assert s2.holds(Fact("handempty", []))

    # 3. unstack(b1, b2)
    act3 = domain.get_action("unstack").instantiate({"?b": "b1", "?under": "b2"})
    s3, err = apply_transition(s2, act3)
    assert err is None
    assert s3.holds(Fact("holding", ["b1"]))
    assert s3.holds(Fact("clear", ["b2"]))

    # 4. put_down(b1)
    act4 = domain.get_action("put_down").instantiate({"?b": "b1"})
    s4, err = apply_transition(s3, act4)
    assert err is None
    assert s4.holds(Fact("on_table", ["b1"]))
    assert s4.holds(Fact("handempty", []))
