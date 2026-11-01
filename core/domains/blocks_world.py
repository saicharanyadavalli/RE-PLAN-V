"""Classical Blocks World Planning Domain."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from core.actions.definition import ActionDefinition, ActionParameter
from core.domains.base import BaseDomain
from core.world.predicates import Fact, PredicateDefinition
from core.world.types import TypeHierarchy


class BlocksWorldDomain(BaseDomain):
    """Classical 4-operator STRIPS Blocks World domain."""

    def __init__(self) -> None:
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

        examples = [
            {
                "prompt": "Move the red box next to the blue box. Do not move the glass.",
                "domain": "blocks_world",
                "goal": "on(red_box, blue_box)",
            },
            {
                "prompt": "Stack b1 on b2, then stack b2 on b3.",
                "domain": "blocks_world",
                "goal": "on(b1, b2), on(b2, b3)",
            },
            {
                "prompt": "Build a 4-block tower: yellow on green, green on blue, blue on red.",
                "domain": "blocks_world",
                "goal": "on(yellow, green), on(green, blue), on(blue, red)",
            },
        ]

        super().__init__(
            domain_id="blocks_world",
            name="Blocks World",
            version="1.1.0",
            description="Classical 4-operator STRIPS tabletop block stacking and unstacking domain.",
            type_hierarchy=th,
            predicates=preds,
            actions=[pick_up, put_down, stack, unstack],
            default_invariants=[],
            task_examples=examples,
            supported_patterns=[
                "stack", "unstack", "pick up", "put down", "tower", "clear", "table", "block"
            ],
            unsupported_features=[
                "continuous rotation", "sub-millimeter friction", "deformable physics"
            ],
        )
