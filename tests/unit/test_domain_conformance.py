"""Authoritative STRIPS Conformance, Planning, Verification, and Model B Enumeration Suite.

Validates all 6 registered planning domains:
1. Blocks World
2. Grid World
3. Household Robotics
4. Warehouse Operations
5. Scheduling & Resource Allocation
6. Software Automation / CI/CD Workflow
"""

import pytest
from core.actions.definition import ActionDefinition
from core.actions.instantiation import GroundAction
from core.contracts import GroundActionSchema, PlanSchema, ViolationType
from core.domains import registry
from core.graph.enumerator import CompleteReachableGraphEnumerator
from core.search.algorithms import AStarPlanner, BFSPlanner
from core.verification.verifier import PlanVerifier
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry


ALL_DOMAINS = [
    "blocks_world",
    "grid_world",
    "household_robotics",
    "warehouse",
    "scheduling",
    "software_workflow",
]


@pytest.mark.parametrize("d_id", ALL_DOMAINS)
def test_domain_contract_invariants_and_types(d_id: str):
    domain = registry.get(d_id)
    assert domain is not None
    assert domain.domain_id == d_id
    assert len(domain.actions) > 0
    assert len(domain.predicates) > 0
    assert len(domain.task_examples) > 0
    assert len(domain.default_invariants) > 0

    # Type hierarchy validation: all types must inherit from object
    all_types = domain.type_hierarchy.get_all_types()
    assert "object" in all_types
    for t in all_types:
        assert domain.type_hierarchy.is_subtype(t, "object")

    # Check to_dict() serialization
    d_dict = domain.to_dict()
    assert d_dict["domain_id"] == d_id
    assert len(d_dict["actions"]) == len(domain.actions)
    assert len(d_dict["predicates"]) == len(domain.predicates)


@pytest.mark.parametrize("d_id", ALL_DOMAINS)
def test_canonical_state_key_determinism_and_uniqueness(d_id: str):
    domain = registry.get(d_id)
    # Build two states with same facts in different order
    f1 = Fact("pred_test", ["arg_a", "arg_b"])
    f2 = Fact("pred_other", ["arg_c"])
    s_order1 = SymbolicState([f1, f2])
    s_order2 = SymbolicState([f2, f1])
    s_diff = SymbolicState([f1])

    key1 = domain.canonical_state_key(s_order1)
    key2 = domain.canonical_state_key(s_order2)
    key_diff = domain.canonical_state_key(s_diff)

    assert key1 == key2, "Canonical state key must be order-invariant"
    assert key1 != key_diff, "Canonical state key must differentiate different states"


def test_blocks_world_end_to_end_planning_and_verification():
    domain = registry.get("blocks_world")
    reg = ObjectRegistry(domain.type_hierarchy)
    for b in ("b1", "b2", "b3"):
        reg.register_object(b, "block")

    s0 = SymbolicState([
        Fact("on_table", ["b1"]),
        Fact("on_table", ["b2"]),
        Fact("on_table", ["b3"]),
        Fact("clear", ["b1"]),
        Fact("clear", ["b2"]),
        Fact("clear", ["b3"]),
        Fact("handempty", []),
    ])
    goals = [Fact("on", ["b1", "b2"]), Fact("on", ["b2", "b3"])]
    problem = SymbolicProblem("bw_tower", domain.name, reg, s0, goals, invariants=domain.default_invariants)

    # 1. Plan using A*
    planner = AStarPlanner()
    plan = planner.search(problem, domain)
    assert plan.is_success, f"A* failed to solve 3-block tower: {plan.failure_reason}"
    assert len(plan.actions) > 0

    # 2. Verify with PlanVerifier
    verifier = PlanVerifier()
    res = verifier.verify(problem, domain, plan)
    assert res.is_valid, f"Valid plan failed verification: {res.violation_type}"

    # 3. Corrupt plan and verify detection
    corrupted_actions = list(plan.actions[:-1])  # remove final step
    bad_plan = PlanSchema(actions=corrupted_actions, is_success=True)
    bad_res = verifier.verify(problem, domain, bad_plan)
    assert not bad_res.is_valid
    assert bad_res.violation_type == ViolationType.GOAL_UNMET

    # 4. Model B Graph Enumeration
    enumerator = CompleteReachableGraphEnumerator(max_nodes=100)
    graph = enumerator.enumerate_graph(problem, domain)
    assert len(graph.nodes) > 1
    assert len(graph.edges) > 1
    for edge in graph.edges:
        assert edge.source_id in graph.nodes
        assert edge.target_id in graph.nodes


def test_grid_world_end_to_end_planning_and_verification():
    domain = registry.get("grid_world")
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("agent_1", "agent")
    reg.register_object("loc_0_0", "location")
    reg.register_object("loc_0_1", "location")
    reg.register_object("loc_1_1", "location")

    s0 = SymbolicState([
        Fact("at", ["agent_1", "loc_0_0"]),
        Fact("connected", ["loc_0_0", "loc_0_1"]),
        Fact("connected", ["loc_0_1", "loc_1_1"]),
        Fact("agent_free", ["agent_1"]),
    ])
    goals = [Fact("at", ["agent_1", "loc_1_1"])]
    problem = SymbolicProblem("gw_nav", domain.name, reg, s0, goals, invariants=domain.default_invariants)

    planner = AStarPlanner()
    plan = planner.search(problem, domain)
    assert plan.is_success
    assert len(plan.actions) == 2

    verifier = PlanVerifier()
    res = verifier.verify(problem, domain, plan)
    assert res.is_valid

    # Corrupt plan by inserting an illegal skip
    bad_actions = [GroundActionSchema(name="move", arguments=("agent_1", "loc_0_0", "loc_1_1"))]
    bad_res = verifier.verify(problem, domain, bad_actions)
    assert not bad_res.is_valid
    assert bad_res.violation_type == ViolationType.PRECONDITION_UNMET


def test_household_robotics_end_to_end_planning_and_verification():
    domain = registry.get("household_robotics")
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("bot", "robot")
    reg.register_object("mug", "item")
    reg.register_object("kitchen", "room")
    reg.register_object("living_room", "room")
    reg.register_object("counter", "surface")
    reg.register_object("table", "surface")

    s0 = SymbolicState([
        Fact("robot_at", ["bot", "kitchen"]),
        Fact("connected_rooms", ["kitchen", "living_room"]),
        Fact("surface_in_room", ["counter", "kitchen"]),
        Fact("surface_in_room", ["table", "living_room"]),
        Fact("item_on", ["mug", "counter"]),
        Fact("gripper_empty", ["bot"]),
    ])
    goals = [Fact("item_on", ["mug", "table"])]
    problem = SymbolicProblem("hh_move_mug", domain.name, reg, s0, goals, invariants=domain.default_invariants)

    planner = BFSPlanner()
    plan = planner.search(problem, domain)
    assert plan.is_success
    assert len(plan.actions) >= 3  # pick, navigate, place

    verifier = PlanVerifier()
    res = verifier.verify(problem, domain, plan)
    assert res.is_valid


def test_warehouse_end_to_end_planning_and_verification():
    domain = registry.get("warehouse")
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("agv", "carrier")
    reg.register_object("sku_1", "sku")
    reg.register_object("bay_a", "bay")
    reg.register_object("bay_b", "bay")
    reg.register_object("zone_1", "zone")
    reg.register_object("zone_2", "zone")

    s0 = SymbolicState([
        Fact("carrier_at", ["agv", "zone_1"]),
        Fact("zone_connected", ["zone_1", "zone_2"]),
        Fact("bay_in_zone", ["bay_a", "zone_1"]),
        Fact("bay_in_zone", ["bay_b", "zone_2"]),
        Fact("sku_stored_in", ["sku_1", "bay_a"]),
        Fact("carrier_empty", ["agv"]),
        Fact("bay_available", ["bay_b"]),
    ])
    goals = [Fact("sku_stored_in", ["sku_1", "bay_b"])]
    problem = SymbolicProblem("wh_transfer", domain.name, reg, s0, goals, invariants=domain.default_invariants)

    planner = AStarPlanner()
    plan = planner.search(problem, domain)
    assert plan.is_success
    assert len(plan.actions) >= 3  # retrieve, transit, deposit

    verifier = PlanVerifier()
    res = verifier.verify(problem, domain, plan)
    assert res.is_valid


def test_scheduling_end_to_end_planning_and_verification():
    domain = registry.get("scheduling")
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("job_a", "job")
    reg.register_object("job_b", "job")
    reg.register_object("machine_1", "resource")
    reg.register_object("slot_1", "slot")
    reg.register_object("slot_2", "slot")

    s0 = SymbolicState([
        Fact("job_ready", ["job_a"]),
        Fact("job_ready", ["job_b"]),
        Fact("precedes", ["job_a", "job_b"]),
        Fact("resource_available", ["machine_1", "slot_1"]),
        Fact("resource_available", ["machine_1", "slot_2"]),
    ])
    goals = [Fact("job_completed", ["job_a"]), Fact("job_completed", ["job_b"])]
    problem = SymbolicProblem("sched_pipeline", domain.name, reg, s0, goals, invariants=domain.default_invariants)

    planner = AStarPlanner()
    plan = planner.search(problem, domain)
    assert plan.is_success
    assert len(plan.actions) == 2

    verifier = PlanVerifier()
    res = verifier.verify(problem, domain, plan)
    assert res.is_valid


def test_software_workflow_end_to_end_planning_and_verification():
    domain = registry.get("software_workflow")
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("c_v1", "commit")
    reg.register_object("pkg_v1", "artifact")
    reg.register_object("staging", "environment")

    s0 = SymbolicState([
        Fact("code_checked_out", ["c_v1"]),
        Fact("environment_healthy", ["staging"]),
    ])
    goals = [Fact("deployed_to", ["pkg_v1", "staging"])]
    problem = SymbolicProblem("cicd_pipeline", domain.name, reg, s0, goals, invariants=domain.default_invariants)

    planner = AStarPlanner()
    plan = planner.search(problem, domain)
    assert plan.is_success
    assert len(plan.actions) >= 4  # test, scan, build, approve, deploy

    verifier = PlanVerifier()
    res = verifier.verify(problem, domain, plan)
    assert res.is_valid


@pytest.mark.parametrize("d_id", ALL_DOMAINS)
def test_all_domains_model_b_enumeration_and_truncation(d_id: str):
    domain = registry.get(d_id)
    # Run small complete graph enumeration on each domain's example
    from interpretation.router import DomainRouter
    router = DomainRouter(registry=registry)
    routing = router.route(domain.task_examples[0]["prompt"], explicit_domain_id=d_id)

    from interpretation.validator.validator import ConsistencyValidator
    validator = ConsistencyValidator()
    from core.contracts import TaskProposalSchema
    proposal = TaskProposalSchema(
        task_id=f"test_graph_{d_id}",
        raw_prompt=domain.task_examples[0]["prompt"],
        entities=routing.entities,
        initial_facts=routing.initial_facts,
        goal_facts=routing.goal_facts,
        negative_constraints=routing.negative_constraints,
    )
    val = validator.validate(proposal, domain)
    assert val.is_valid, f"Validation failed for domain {d_id}: {val.errors}"
    problem = validator.convert_to_problem(proposal, domain)

    # 1. Enumerate with small cap
    capped_enumerator = CompleteReachableGraphEnumerator(max_nodes=4)
    capped_graph = capped_enumerator.enumerate_graph(problem, domain)
    assert len(capped_graph.nodes) <= 4
    # All edge endpoints must exist in nodes
    for edge in capped_graph.edges:
        assert edge.source_id in capped_graph.nodes
        assert edge.target_id in capped_graph.nodes
