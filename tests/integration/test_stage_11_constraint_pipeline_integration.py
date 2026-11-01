"""Stage 11 Integration Tests: End-to-End Typed Action Constraints across Pipeline, Search, Verifier, and Graph."""

from __future__ import annotations

import pytest
from core.actions.domain import create_blocks_world_domain
from core.domains.grid_world import GridWorldDomain
from core.contracts import (
    FactSchema,
    GroundActionSchema,
    PlanSchema,
    TaskConstraintSchema,
    TaskConstraintType,
    TaskProposalSchema,
    ViolationType,
)
from core.graph.enumerator import CompleteReachableGraphEnumerator
from core.search.algorithms import AStarPlanner
from core.verification.verifier import PlanVerifier
from core.world.constraints import (
    ForbidActionBindingConstraint,
    ForbidActionConstraint,
    ForbidActionExactBindingConstraint,
    ForbidTransitionConstraint,
    NegativeFactInvariant,
)
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry
from interpretation.validator.validator import ConsistencyValidator
from app.services.pipeline import PipelineOrchestrator


def test_scenario_1_exact_action_binding_prohibition():
    """Scenario 1: not(on(b1, b2)) produces ForbidActionExactBindingConstraint and blocks stack(b1, b2)."""
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    for b in ["b1", "b2", "b3"]:
        reg.register_object(b, "block")

    # Initial state: b1, b2, b3 on table, clear, handempty
    s0 = SymbolicState([
        Fact("on_table", ["b1"]),
        Fact("clear", ["b1"]),
        Fact("on_table", ["b2"]),
        Fact("clear", ["b2"]),
        Fact("on_table", ["b3"]),
        Fact("clear", ["b3"]),
        Fact("handempty", []),
    ])
    goals = [Fact("on", ["b1", "b2"])]  # Target stack b1 on b2

    # Construct problem with exact prohibition: forbid stack(b1, b2)
    exact_hc = ForbidActionExactBindingConstraint("stack", ["b1", "b2"])
    problem = SymbolicProblem(
        name="test_exact_prohibition",
        domain_name=domain.name,
        registry=reg,
        initial_state=s0,
        goal_conditions=goals,
        hard_constraints=[exact_hc],
    )

    # 1. Search must fail to find a plan because only stack(b1, b2) satisfies the goal and it is strictly forbidden
    planner = AStarPlanner()
    plan = planner.search(problem, domain)
    assert plan.is_success is False

    # 2. Verifier: any candidate containing stack(b1, b2) must fail with HARD_CONSTRAINT_VIOLATION
    verifier = PlanVerifier()
    candidate = PlanSchema(
        actions=[
            GroundActionSchema(name="pick_up", arguments=("b1",)),
            GroundActionSchema(name="stack", arguments=("b1", "b2")),
        ]
    )
    v_res = verifier.verify(problem, domain, candidate)
    assert v_res.is_valid is False
    assert v_res.violation_type == ViolationType.HARD_CONSTRAINT_VIOLATED
    assert "strictly forbidden" in v_res.explanation

    # 3. Model B Reachable Graph: no edge with stack(b1, b2) can exist in the graph
    enumerator = CompleteReachableGraphEnumerator(max_nodes=100, max_edges=300)
    graph = enumerator.enumerate_graph(problem, domain)
    assert graph.stats.is_complete is True
    forbidden_edges = [
        e for e in graph.edges
        if e.action_name == "stack" and e.action_args == ["b1", "b2"]
    ]
    assert len(forbidden_edges) == 0


def test_scenario_2_entity_action_binding_prohibition():
    """Scenario 2: not(holding(glass)) produces ForbidActionBindingConstraint and forbids pick_up/unstack on glass."""
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    for b in ["glass", "red_box"]:
        reg.register_object(b, "block")

    s0 = SymbolicState([
        Fact("on_table", ["glass"]),
        Fact("clear", ["glass"]),
        Fact("on_table", ["red_box"]),
        Fact("clear", ["red_box"]),
        Fact("handempty", []),
    ])
    goals = [Fact("on", ["glass", "red_box"])]

    hc_pickup = ForbidActionBindingConstraint("pick_up", "glass", arg_index=0)
    hc_unstack = ForbidActionBindingConstraint("unstack", "glass", arg_index=0)
    problem = SymbolicProblem(
        name="test_glass_prohibition",
        domain_name=domain.name,
        registry=reg,
        initial_state=s0,
        goal_conditions=goals,
        hard_constraints=[hc_pickup, hc_unstack],
    )

    planner = AStarPlanner()
    plan = planner.search(problem, domain)
    assert plan.is_success is False

    verifier = PlanVerifier()
    candidate = PlanSchema(
        actions=[
            GroundActionSchema(name="pick_up", arguments=("glass",)),
            GroundActionSchema(name="stack", arguments=("glass", "red_box")),
        ]
    )
    v_res = verifier.verify(problem, domain, candidate)
    assert v_res.is_valid is False
    assert v_res.violation_type == ViolationType.HARD_CONSTRAINT_VIOLATED

    enumerator = CompleteReachableGraphEnumerator(max_nodes=100, max_edges=300)
    graph = enumerator.enumerate_graph(problem, domain)
    for e in graph.edges:
        if e.action_name == "pick_up":
            assert e.action_args[0] != "glass"
        elif e.action_name == "unstack":
            assert e.action_args[0] != "glass"


def test_scenario_3_forbid_transition_constraint_grid_world():
    """Scenario 3: ForbidTransitionConstraint prevents moving to cell_trap."""
    domain = GridWorldDomain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("agent", "agent")
    for c in ["cell_a", "cell_b", "cell_trap"]:
        reg.register_object(c, "location")

    s0 = SymbolicState([
        Fact("at", ["agent", "cell_a"]),
        Fact("connected", ["cell_a", "cell_trap"]),
        Fact("connected", ["cell_trap", "cell_b"]),
        Fact("connected", ["cell_a", "cell_b"]),
    ])
    goals = [Fact("at", ["agent", "cell_b"])]

    # Prohibit moving into cell_trap (arg_index=2 is destination 'to' cell)
    trap_hc = ForbidTransitionConstraint("move", to_entity="cell_trap", arg_index=2)
    problem = SymbolicProblem(
        name="test_grid_trap",
        domain_name=domain.name,
        registry=reg,
        initial_state=s0,
        goal_conditions=goals,
        hard_constraints=[trap_hc],
    )

    # 1. Search must find alternative route cell_a -> cell_b without cell_trap
    planner = AStarPlanner()
    plan = planner.search(problem, domain)
    assert plan.is_success is True
    assert len(plan.actions) == 1
    assert plan.actions[0].name == "move"
    assert plan.actions[0].arguments == ("agent", "cell_a", "cell_b")

    # 2. Verifier: moving to cell_trap must fail
    verifier = PlanVerifier()
    bad_plan = PlanSchema(
        actions=[
            GroundActionSchema(name="move", arguments=("agent", "cell_a", "cell_trap")),
            GroundActionSchema(name="move", arguments=("agent", "cell_trap", "cell_b")),
        ]
    )
    v_res = verifier.verify(problem, domain, bad_plan)
    assert v_res.is_valid is False
    assert v_res.violation_type == ViolationType.HARD_CONSTRAINT_VIOLATED
    assert "cell_trap" in v_res.explanation


def test_scenario_4_proposal_conversion_typed_constraints():
    """Scenario 4: ConsistencyValidator.convert_to_problem maps typed_constraints into HardConstraint objects."""
    domain = create_blocks_world_domain()
    validator = ConsistencyValidator()

    proposal = TaskProposalSchema(
        task_id="t_typed_01",
        domain_id="blocks_world",
        entities={"b1": "block", "b2": "block", "b3": "block"},
        initial_facts=[
            FactSchema(predicate="on_table", arguments=["b1"]),
            FactSchema(predicate="clear", arguments=["b1"]),
            FactSchema(predicate="on_table", arguments=["b2"]),
            FactSchema(predicate="clear", arguments=["b2"]),
            FactSchema(predicate="on_table", arguments=["b3"]),
            FactSchema(predicate="clear", arguments=["b3"]),
            FactSchema(predicate="handempty", arguments=[]),
        ],
        goal_facts=[FactSchema(predicate="on", arguments=["b1", "b3"])],
        typed_constraints=[
            TaskConstraintSchema(
                constraint_type=TaskConstraintType.FORBID_ACTION_BINDING,
                action_name="stack",
                arguments=["b1", "b2"],
                description="Do not stack b1 on b2",
            ),
            TaskConstraintSchema(
                constraint_type=TaskConstraintType.FORBID_ACTION,
                action_name="unstack",
                description="Do not unstack any block",
            ),
        ],
    )

    val_res = validator.validate(proposal, domain)
    assert val_res.is_valid is True

    problem = validator.convert_to_problem(proposal, domain)
    assert len(problem.hard_constraints) == 2
    hc_types = [type(hc).__name__ for hc in problem.hard_constraints]
    assert "ForbidActionExactBindingConstraint" in hc_types
    assert "ForbidActionConstraint" in hc_types


def test_scenario_5_end_to_end_orchestrator_pipeline_with_prohibitions():
    """Scenario 5: PipelineOrchestrator runs end-to-end with natural language prohibition."""
    orchestrator = PipelineOrchestrator()
    prompt = "Move the red box next to the blue box. Do not move the glass."
    res = orchestrator.run(prompt=prompt, domain_id="blocks_world")

    assert res.status == "COMPLETED"
    assert res.final_plan is not None
    assert len(res.final_plan.actions) > 0
    assert res.final_verification.is_valid is True

    # Confirm glass was never manipulated in the final plan
    for act in res.final_plan.actions:
        assert "glass" not in act.arguments
