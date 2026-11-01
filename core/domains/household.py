"""Household Robotics Abstract Planning Domain."""

from __future__ import annotations

from typing import Any, Dict, List
from core.actions.definition import ActionDefinition, ActionParameter
from core.domains.base import BaseDomain
from core.world.predicates import Fact, PredicateDefinition
from core.world.types import TypeHierarchy


class HouseholdRoboticsDomain(BaseDomain):
    """Abstract symbolic domestic robotics domain for high-level manipulation and navigation."""

    def __init__(self) -> None:
        th = TypeHierarchy()
        th.add_type("robot", "object")
        th.add_type("room", "object")
        th.add_type("surface", "object")
        th.add_type("container", "object")
        th.add_type("item", "object")

        preds = [
            PredicateDefinition("robot_at", ["robot", "room"]),
            PredicateDefinition("connected_rooms", ["room", "room"], is_static=True),
            PredicateDefinition("surface_in_room", ["surface", "room"], is_static=True),
            PredicateDefinition("container_in_room", ["container", "room"], is_static=True),
            PredicateDefinition("item_on", ["item", "surface"]),
            PredicateDefinition("item_in", ["item", "container"]),
            PredicateDefinition("container_open", ["container"]),
            PredicateDefinition("container_closed", ["container"]),
            PredicateDefinition("holding", ["robot", "item"]),
            PredicateDefinition("gripper_empty", ["robot"]),
        ]

        navigate = ActionDefinition(
            name="navigate_room",
            parameters=[
                ActionParameter("r", "robot"),
                ActionParameter("from_rm", "room"),
                ActionParameter("to_rm", "room"),
            ],
            preconditions=[
                Fact("robot_at", ["?r", "?from_rm"]),
                Fact("connected_rooms", ["?from_rm", "?to_rm"]),
            ],
            add_effects=[Fact("robot_at", ["?r", "?to_rm"])],
            del_effects=[Fact("robot_at", ["?r", "?from_rm"])],
            cost=1.5,
            description="Robot navigates between connected rooms",
        )

        open_c = ActionDefinition(
            name="open_container",
            parameters=[
                ActionParameter("r", "robot"),
                ActionParameter("c", "container"),
                ActionParameter("rm", "room"),
            ],
            preconditions=[
                Fact("robot_at", ["?r", "?rm"]),
                Fact("container_in_room", ["?c", "?rm"]),
                Fact("container_closed", ["?c"]),
                Fact("gripper_empty", ["?r"]),
            ],
            add_effects=[Fact("container_open", ["?c"])],
            del_effects=[Fact("container_closed", ["?c"])],
            cost=1.0,
            description="Open a closed cabinet or drawer",
        )

        close_c = ActionDefinition(
            name="close_container",
            parameters=[
                ActionParameter("r", "robot"),
                ActionParameter("c", "container"),
                ActionParameter("rm", "room"),
            ],
            preconditions=[
                Fact("robot_at", ["?r", "?rm"]),
                Fact("container_in_room", ["?c", "?rm"]),
                Fact("container_open", ["?c"]),
                Fact("gripper_empty", ["?r"]),
            ],
            add_effects=[Fact("container_closed", ["?c"])],
            del_effects=[Fact("container_open", ["?c"])],
            cost=1.0,
            description="Close an open cabinet or drawer",
        )

        pick_surface = ActionDefinition(
            name="pick_from_surface",
            parameters=[
                ActionParameter("r", "robot"),
                ActionParameter("it", "item"),
                ActionParameter("s", "surface"),
                ActionParameter("rm", "room"),
            ],
            preconditions=[
                Fact("robot_at", ["?r", "?rm"]),
                Fact("surface_in_room", ["?s", "?rm"]),
                Fact("item_on", ["?it", "?s"]),
                Fact("gripper_empty", ["?r"]),
            ],
            add_effects=[Fact("holding", ["?r", "?it"])],
            del_effects=[
                Fact("item_on", ["?it", "?s"]),
                Fact("gripper_empty", ["?r"]),
            ],
            cost=1.0,
            description="Pick item from a surface (table, counter, shelf)",
        )

        place_surface = ActionDefinition(
            name="place_on_surface",
            parameters=[
                ActionParameter("r", "robot"),
                ActionParameter("it", "item"),
                ActionParameter("s", "surface"),
                ActionParameter("rm", "room"),
            ],
            preconditions=[
                Fact("robot_at", ["?r", "?rm"]),
                Fact("surface_in_room", ["?s", "?rm"]),
                Fact("holding", ["?r", "?it"]),
            ],
            add_effects=[
                Fact("item_on", ["?it", "?s"]),
                Fact("gripper_empty", ["?r"]),
            ],
            del_effects=[Fact("holding", ["?r", "?it"])],
            cost=1.0,
            description="Place item on a surface",
        )

        pick_container = ActionDefinition(
            name="pick_from_container",
            parameters=[
                ActionParameter("r", "robot"),
                ActionParameter("it", "item"),
                ActionParameter("c", "container"),
                ActionParameter("rm", "room"),
            ],
            preconditions=[
                Fact("robot_at", ["?r", "?rm"]),
                Fact("container_in_room", ["?c", "?rm"]),
                Fact("container_open", ["?c"]),
                Fact("item_in", ["?it", "?c"]),
                Fact("gripper_empty", ["?r"]),
            ],
            add_effects=[Fact("holding", ["?r", "?it"])],
            del_effects=[
                Fact("item_in", ["?it", "?c"]),
                Fact("gripper_empty", ["?r"]),
            ],
            cost=1.0,
            description="Pick item from inside an open container",
        )

        place_container = ActionDefinition(
            name="place_in_container",
            parameters=[
                ActionParameter("r", "robot"),
                ActionParameter("it", "item"),
                ActionParameter("c", "container"),
                ActionParameter("rm", "room"),
            ],
            preconditions=[
                Fact("robot_at", ["?r", "?rm"]),
                Fact("container_in_room", ["?c", "?rm"]),
                Fact("container_open", ["?c"]),
                Fact("holding", ["?r", "?it"]),
            ],
            add_effects=[
                Fact("item_in", ["?it", "?c"]),
                Fact("gripper_empty", ["?r"]),
            ],
            del_effects=[Fact("holding", ["?r", "?it"])],
            cost=1.0,
            description="Place item inside an open container",
        )

        examples = [
            {
                "prompt": "Move the mug from the desk to the kitchen shelf.",
                "domain": "household_robotics",
                "goal": "item_on(mug, kitchen_shelf)",
            },
            {
                "prompt": "Put the book in the living-room cabinet. Do not move the fragile vase.",
                "domain": "household_robotics",
                "goal": "item_in(book, living_room_cabinet)",
            },
        ]

        super().__init__(
            domain_id="household_robotics",
            name="Household Robotics (Abstract)",
            version="1.0.0",
            description="Abstract high-level domestic service robot navigation, container manipulation, and object transport.",
            type_hierarchy=th,
            predicates=preds,
            actions=[navigate, open_c, close_c, pick_surface, place_surface, pick_container, place_container],
            default_invariants=[],
            task_examples=examples,
            supported_patterns=[
                "room", "kitchen", "living room", "bedroom", "mug", "cabinet", "shelf", "counter", "drawer", "robot", "cup"
            ],
            unsupported_features=[
                "real hardware motor control", "joint torque estimation", "RGB-D point cloud registration"
            ],
        )
