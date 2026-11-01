"""Unit tests verifying all 6 production planning domains in the registry."""

import pytest
from core.domains import registry
from core.world.predicates import Fact
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry


def test_registry_contains_all_six_domains():
    expected_domains = [
        "blocks_world",
        "grid_world",
        "household_robotics",
        "warehouse",
        "scheduling",
        "software_workflow",
    ]
    for d_id in expected_domains:
        assert registry.has(d_id), f"Domain '{d_id}' must be registered"
        domain = registry.get(d_id)
        assert domain is not None
        assert domain.domain_id == d_id
        assert len(domain.actions) > 0
        assert len(domain.predicates) > 0
        assert len(domain.task_examples) > 0


def test_registry_aliases():
    assert registry.get("blocks").domain_id == "blocks_world"
    assert registry.get("navigation").domain_id == "grid_world"
    assert registry.get("household").domain_id == "household_robotics"
    assert registry.get("logistics").domain_id == "warehouse"
    assert registry.get("schedule").domain_id == "scheduling"
    assert registry.get("cicd").domain_id == "software_workflow"


def test_blocks_world_execution():
    domain = registry.get("blocks_world")
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("b1", "block")
    reg.register_object("b2", "block")

    s0 = SymbolicState([
        Fact("on_table", ["b1"]),
        Fact("on_table", ["b2"]),
        Fact("clear", ["b1"]),
        Fact("clear", ["b2"]),
        Fact("handempty", []),
    ])

    applicable = domain.applicable_actions(s0, reg)
    act_names = [a.to_string() for a in applicable]
    assert "pick_up(b1)" in act_names
    assert "pick_up(b2)" in act_names

    pick_b1 = next(a for a in applicable if a.name == "pick_up" and a.arguments == ("b1",))
    s1, err = domain.apply_action(s0, pick_b1)
    assert err is None
    assert s1.holds(Fact("holding", ["b1"]))
    assert not s1.holds(Fact("on_table", ["b1"]))
    assert not s1.holds(Fact("handempty", []))


def test_grid_world_execution():
    domain = registry.get("grid_world")
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("robot", "agent")
    reg.register_object("c1", "location")
    reg.register_object("c2", "location")

    s0 = SymbolicState([
        Fact("at", ["robot", "c1"]),
        Fact("connected", ["c1", "c2"]),
    ])

    applicable = domain.applicable_actions(s0, reg)
    assert any(a.name == "move" and a.arguments == ("robot", "c1", "c2") for a in applicable)

    move_act = next(a for a in applicable if a.name == "move")
    s1, err = domain.apply_action(s0, move_act)
    assert err is None
    assert s1.holds(Fact("at", ["robot", "c2"]))
    assert not s1.holds(Fact("at", ["robot", "c1"]))


def test_household_robotics_execution():
    domain = registry.get("household_robotics")
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("cleaner", "robot")
    reg.register_object("kitchen", "room")
    reg.register_object("living_room", "room")

    s0 = SymbolicState([
        Fact("robot_at", ["cleaner", "kitchen"]),
        Fact("connected_rooms", ["kitchen", "living_room"]),
        Fact("gripper_empty", ["cleaner"]),
    ])

    applicable = domain.applicable_actions(s0, reg)
    nav_act = next(a for a in applicable if a.name == "navigate_room")
    s1, err = domain.apply_action(s0, nav_act)
    assert err is None
    assert s1.holds(Fact("robot_at", ["cleaner", "living_room"]))


def test_warehouse_execution():
    domain = registry.get("warehouse")
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("agv_1", "carrier")
    reg.register_object("box_a", "sku")
    reg.register_object("shelf_1", "bay")
    reg.register_object("dock", "zone")

    s0 = SymbolicState([
        Fact("carrier_at", ["agv_1", "dock"]),
        Fact("bay_in_zone", ["shelf_1", "dock"]),
        Fact("sku_stored_in", ["box_a", "shelf_1"]),
        Fact("carrier_empty", ["agv_1"]),
        Fact("bay_occupied", ["shelf_1"]),
    ])

    applicable = domain.applicable_actions(s0, reg)
    retrieve = next(a for a in applicable if a.name == "retrieve_sku")
    s1, err = domain.apply_action(s0, retrieve)
    assert err is None
    assert s1.holds(Fact("carrier_loaded_with", ["agv_1", "box_a"]))
    assert s1.holds(Fact("bay_available", ["shelf_1"]))


def test_scheduling_execution():
    domain = registry.get("scheduling")
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("job1", "job")
    reg.register_object("lathe", "resource")
    reg.register_object("slot1", "slot")

    s0 = SymbolicState([
        Fact("job_ready", ["job1"]),
        Fact("resource_available", ["lathe", "slot1"]),
    ])

    applicable = domain.applicable_actions(s0, reg)
    sched = next(a for a in applicable if a.name == "schedule_independent_job")
    s1, err = domain.apply_action(s0, sched)
    assert err is None
    assert s1.holds(Fact("job_completed", ["job1"]))
    assert s1.holds(Fact("resource_busy", ["lathe", "slot1"]))


def test_software_workflow_execution():
    domain = registry.get("software_workflow")
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("v1_commit", "commit")

    s0 = SymbolicState([
        Fact("code_checked_out", ["v1_commit"]),
    ])

    applicable = domain.applicable_actions(s0, reg)
    test_act = next(a for a in applicable if a.name == "run_unit_tests")
    s1, err = domain.apply_action(s0, test_act)
    assert err is None
    assert s1.holds(Fact("tests_passed", ["v1_commit"]))
