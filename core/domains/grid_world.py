"""Grid World Navigation and Item Transfer Domain."""

from __future__ import annotations

from typing import Any, Dict, List
from core.actions.definition import ActionDefinition, ActionParameter
from core.domains.base import BaseDomain
from core.world.constraints import FunctionalDependencyInvariant
from core.world.predicates import Fact, PredicateDefinition
from core.world.types import TypeHierarchy


class GridWorldDomain(BaseDomain):
    """Grid World navigation and item delivery domain."""

    def __init__(self) -> None:
        th = TypeHierarchy()
        th.add_type("agent", "object")
        th.add_type("location", "object")
        th.add_type("item", "object")

        preds = [
            PredicateDefinition("at", ["agent", "location"]),
            PredicateDefinition("item_at", ["item", "location"]),
            PredicateDefinition("connected", ["location", "location"], is_static=True),
            PredicateDefinition("blocked", ["location"], is_static=True),
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

        examples = [
            {
                "prompt": "Move the agent from cell_a to cell_d avoiding blocked cells.",
                "domain": "grid_world",
                "goal": "at(agent, cell_d)",
            },
            {
                "prompt": "Pick up package_1 at cell_b and deliver it to cell_f.",
                "domain": "grid_world",
                "goal": "item_at(package_1, cell_f)",
            },
        ]

        super().__init__(
            domain_id="grid_world",
            name="Grid World / Navigation",
            version="1.1.0",
            description="Symbolic 2D cell topological navigation, obstacle avoidance, and package delivery.",
            type_hierarchy=th,
            predicates=preds,
            actions=[move, pick, drop],
            default_invariants=[FunctionalDependencyInvariant("at", 0, 1)],
            task_examples=examples,
            supported_patterns=[
                "navigate", "move", "cell", "grid", "travel", "deliver", "waypoint", "location"
            ],
            unsupported_features=[
                "continuous physics", "acceleration curves", "diagonal slip"
            ],
        )
