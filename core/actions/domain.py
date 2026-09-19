"""Domain definitions and standard domain libraries."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence
from core.actions.definition import ActionDefinition, ActionParameter
from core.actions.instantiation import GroundAction
from core.world.predicates import Fact, PredicateDefinition
from core.world.types import ObjectRegistry, TypeHierarchy


class Domain:
    """Encapsulates a planning domain: types, predicates, and action schemas."""

    def __init__(
        self,
        name: str,
        actions: Sequence[ActionDefinition],
        predicates: Sequence[PredicateDefinition] = (),
        type_hierarchy: Optional[TypeHierarchy] = None,
        description: str = "",
    ) -> None:
        self.name = name.strip().lower()
        self.actions = {a.name: a for a in actions}
        self.predicates = {p.name: p for p in predicates}
        self.type_hierarchy = type_hierarchy or TypeHierarchy()
        self.description = description

    def get_action(self, name: str) -> Optional[ActionDefinition]:
        return self.actions.get(name.strip().lower())

    def get_all_actions(self) -> List[ActionDefinition]:
        return list(self.actions.values())


# ==============================================================================
# Standard Domain Factories
# ==============================================================================

def create_blocks_world_domain() -> Domain:
    """Standard Classical Blocks World Domain."""
    th = TypeHierarchy()
    th.add_type("block", "object")

    preds = [
        PredicateDefinition("on", ["block", "block"]),
        PredicateDefinition("on_table", ["block"]),
        PredicateDefinition("clear", ["block"]),
        PredicateDefinition("holding", ["block"]),
        PredicateDefinition("handempty", []),
    ]

    pick_up = ActionDefinition(
        name="pick_up",
        parameters=[ActionParameter("b", "block")],
        preconditions=[
            Fact("clear", ["?b"]),
            Fact("on_table", ["?b"]),
            Fact("handempty", []),
        ],
        add_effects=[Fact("holding", ["?b"])],
        del_effects=[
            Fact("on_table", ["?b"]),
            Fact("clear", ["?b"]),
            Fact("handempty", []),
        ],
        cost=1.0,
        description="Pick up a block from the table",
    )

    put_down = ActionDefinition(
        name="put_down",
        parameters=[ActionParameter("b", "block")],
        preconditions=[Fact("holding", ["?b"])],
        add_effects=[
            Fact("on_table", ["?b"]),
            Fact("clear", ["?b"]),
            Fact("handempty", []),
        ],
        del_effects=[Fact("holding", ["?b"])],
        cost=1.0,
        description="Put down a block onto the table",
    )

    stack = ActionDefinition(
        name="stack",
        parameters=[ActionParameter("b", "block"), ActionParameter("under", "block")],
        preconditions=[
            Fact("holding", ["?b"]),
            Fact("clear", ["?under"]),
        ],
        add_effects=[
            Fact("on", ["?b", "?under"]),
            Fact("clear", ["?b"]),
            Fact("handempty", []),
        ],
        del_effects=[
            Fact("holding", ["?b"]),
            Fact("clear", ["?under"]),
        ],
        cost=1.0,
        description="Stack block ?b on top of ?under",
    )

    unstack = ActionDefinition(
        name="unstack",
        parameters=[ActionParameter("b", "block"), ActionParameter("under", "block")],
        preconditions=[
            Fact("on", ["?b", "?under"]),
            Fact("clear", ["?b"]),
            Fact("handempty", []),
        ],
        add_effects=[
            Fact("holding", ["?b"]),
            Fact("clear", ["?under"]),
        ],
        del_effects=[
            Fact("on", ["?b", "?under"]),
            Fact("clear", ["?b"]),
            Fact("handempty", []),
        ],
        cost=1.0,
        description="Unstack block ?b from ?under",
    )

    return Domain(
        name="blocks_world",
        actions=[pick_up, put_down, stack, unstack],
        predicates=preds,
        type_hierarchy=th,
        description="Classical 4-operator Blocks World",
    )


def create_gridworld_domain() -> Domain:
    """GridWorld / Navigation and Delivery Domain."""
    th = TypeHierarchy()
    th.add_type("agent", "object")
    th.add_type("location", "object")
    th.add_type("item", "object")

    preds = [
        PredicateDefinition("at", ["agent", "location"]),
        PredicateDefinition("item_at", ["item", "location"]),
        PredicateDefinition("connected", ["location", "location"], is_static=True),
        PredicateDefinition("holding_item", ["agent", "item"]),
        PredicateDefinition("agent_free", ["agent"]),
    ]

    move = ActionDefinition(
        name="move",
        parameters=[
            ActionParameter("ag", "agent"),
            ActionParameter("from_loc", "location"),
            ActionParameter("to_loc", "location"),
        ],
        preconditions=[
            Fact("at", ["?ag", "?from_loc"]),
            Fact("connected", ["?from_loc", "?to_loc"]),
        ],
        add_effects=[Fact("at", ["?ag", "?to_loc"])],
        del_effects=[Fact("at", ["?ag", "?from_loc"])],
        cost=1.0,
        description="Move agent between connected locations",
    )

    pick = ActionDefinition(
        name="pick",
        parameters=[
            ActionParameter("ag", "agent"),
            ActionParameter("it", "item"),
            ActionParameter("loc", "location"),
        ],
        preconditions=[
            Fact("at", ["?ag", "?loc"]),
            Fact("item_at", ["?it", "?loc"]),
            Fact("agent_free", ["?ag"]),
        ],
        add_effects=[Fact("holding_item", ["?ag", "?it"])],
        del_effects=[
            Fact("item_at", ["?it", "?loc"]),
            Fact("agent_free", ["?ag"]),
        ],
        cost=1.0,
        description="Agent picks up an item at current location",
    )

    drop = ActionDefinition(
        name="drop",
        parameters=[
            ActionParameter("ag", "agent"),
            ActionParameter("it", "item"),
            ActionParameter("loc", "location"),
        ],
        preconditions=[
            Fact("at", ["?ag", "?loc"]),
            Fact("holding_item", ["?ag", "?it"]),
        ],
        add_effects=[
            Fact("item_at", ["?it", "?loc"]),
            Fact("agent_free", ["?ag"]),
        ],
        del_effects=[Fact("holding_item", ["?ag", "?it"])],
        cost=1.0,
        description="Agent drops item at current location",
    )

    return Domain(
        name="gridworld",
        actions=[move, pick, drop],
        predicates=preds,
        type_hierarchy=th,
        description="GridWorld navigation and item transfer",
    )
