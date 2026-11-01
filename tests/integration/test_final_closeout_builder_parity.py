"""Integration tests for Stage 11 closeout: Authoritative ValidatedProblemBuilder parity and 5 typed prohibition scenarios."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.pipeline import PipelineOrchestrator
from app.services.problem_builder import ProblemBuildResult, ValidatedProblemBuilder
from core.contracts import (
    FactSchema,
    GroundActionSchema,
    PlanSchema,
    TaskConstraintSchema,
    TaskConstraintType,
    TaskProposalSchema,
    ViolationType,
)
from core.domains import registry
from core.search.algorithms import AStarPlanner
from core.verification.verifier import PlanVerifier
from core.world.constraints import (
    ForbidActionBindingConstraint,
    ForbidActionExactBindingConstraint,
    ForbidTransitionConstraint,
    HardConstraint,
    NegativeFactInvariant,
)
from core.world.predicates import Fact
from core.world.state import SymbolicState


@pytest.fixture
def client():
    return TestClient(create_app())


# ==============================================================================
# 1. Unified Path Tests
# ==============================================================================

def test_builder_build_from_proposal_is_unified_path(client: TestClient):
    """Verify ValidatedProblemBuilder.build_from_proposal is the unified problem construction path."""
    prompt = "Stack the red box on the blue box."
    domain_id = "blocks_world"

    # A. ValidatedProblemBuilder.build_problem delegates to build_from_proposal
    builder = ValidatedProblemBuilder(registry=registry)
    with patch.object(builder, "build_from_proposal", wraps=builder.build_from_proposal) as spy_builder_bfp:
        res = builder.build_problem(prompt, domain_id=domain_id)
        assert res.is_success is True
        assert spy_builder_bfp.called is True
        assert spy_builder_bfp.call_count == 1

    # B. PipelineOrchestrator delegates to problem_builder.build_from_proposal
    orchestrator = PipelineOrchestrator(domain_id=domain_id)
    with patch.object(
        orchestrator.problem_builder,
        "build_from_proposal",
        wraps=orchestrator.problem_builder.build_from_proposal,
    ) as spy_pipe_bfp:
        pipe_res = orchestrator.run(prompt, domain_id=domain_id)
        assert pipe_res.status == "COMPLETED"
        assert spy_pipe_bfp.called is True
        assert spy_pipe_bfp.call_count >= 1

    # C. WebSocket pipeline endpoint delegates to ValidatedProblemBuilder.build_from_proposal
    with patch.object(
        ValidatedProblemBuilder,
        "build_from_proposal",
        autospec=True,
        side_effect=ValidatedProblemBuilder.build_from_proposal,
    ) as spy_ws_bfp:
        with client.websocket_connect("/ws/pipeline") as ws:
            ws.send_json({
                "prompt": prompt,
                "domain_id": domain_id,
                "enumerate_graph": False,
                "step_delay": 0.0,
            })
            for _ in range(15):
                try:
                    msg = ws.receive_json()
                    if msg.get("stage") in ("PIPELINE_FINISHED", "ERROR"):
                        break
                except Exception:
                    break

        assert spy_ws_bfp.called is True


# ==============================================================================
# 2. REST, WebSocket, and Pipeline Normalized Problem Parity
# ==============================================================================

def test_rest_websocket_and_pipeline_problem_parity(client: TestClient):
    """Verify REST, WebSocket, and Pipeline produce 100% semantically identical normalized SymbolicProblems.
    
    Compares:
    - domain_id
    - entities and their registered types
    - initial facts
    - goal facts
    - domain default invariants
    - problem invariants
    - hard_constraints
    """
    prompt = "Stack the red box on the blue box."
    domain_id = "blocks_world"

    # 1. REST Problem via authoritative builder
    builder = ValidatedProblemBuilder(registry=registry)
    rest_res = builder.build_problem(prompt, domain_id=domain_id)
    assert rest_res.is_success is True
    p_rest = rest_res.problem

    # 2. Pipeline Problem via PipelineOrchestrator
    pipe = PipelineOrchestrator(domain_id=domain_id)
    captured_pipe_problem = None
    orig_pipe_build = pipe.problem_builder.build_from_proposal

    def spy_pipe_capture(*args, **kwargs):
        nonlocal captured_pipe_problem
        res = orig_pipe_build(*args, **kwargs)
        captured_pipe_problem = res.problem
        return res

    pipe.problem_builder.build_from_proposal = spy_pipe_capture
    pipe.run(prompt, domain_id=domain_id)
    p_pipe = captured_pipe_problem
    assert p_pipe is not None

    # 3. WebSocket Problem via /ws/pipeline
    captured_ws_problem = None
    orig_ws_build = ValidatedProblemBuilder.build_from_proposal

    def spy_ws_capture(self, *args, **kwargs):
        nonlocal captured_ws_problem
        res = orig_ws_build(self, *args, **kwargs)
        captured_ws_problem = res.problem
        return res

    with patch.object(ValidatedProblemBuilder, "build_from_proposal", spy_ws_capture):
        with client.websocket_connect("/ws/pipeline") as ws:
            ws.send_json({
                "prompt": prompt,
                "domain_id": domain_id,
                "enumerate_graph": False,
                "step_delay": 0.0,
            })
            for _ in range(15):
                try:
                    msg = ws.receive_json()
                    if msg.get("stage") in ("PIPELINE_FINISHED", "ERROR"):
                        break
                except Exception:
                    break

    p_ws = captured_ws_problem
    assert p_ws is not None

    # Semantic Parity Assertions across all 3 components:
    # A. Domain identity
    assert p_rest.domain_name == p_ws.domain_name == p_pipe.domain_name

    # B. Entities and object types
    assert p_rest.registry.get_all_objects() == p_ws.registry.get_all_objects() == p_pipe.registry.get_all_objects()

    # C. Initial facts
    norm_rest_init = sorted(f.to_string() for f in p_rest.initial_state.facts)
    norm_ws_init = sorted(f.to_string() for f in p_ws.initial_state.facts)
    norm_pipe_init = sorted(f.to_string() for f in p_pipe.initial_state.facts)
    assert norm_rest_init == norm_ws_init == norm_pipe_init

    # D. Goal facts
    norm_rest_goals = sorted(g.to_string() for g in p_rest.goal_conditions)
    norm_ws_goals = sorted(g.to_string() for g in p_ws.goal_conditions)
    norm_pipe_goals = sorted(g.to_string() for g in p_pipe.goal_conditions)
    assert norm_rest_goals == norm_ws_goals == norm_pipe_goals

    # E. Problem invariants (including domain default invariants transferred)
    norm_rest_invs = sorted(str(i) for i in p_rest.invariants)
    norm_ws_invs = sorted(str(i) for i in p_ws.invariants)
    norm_pipe_invs = sorted(str(i) for i in p_pipe.invariants)
    assert norm_rest_invs == norm_ws_invs == norm_pipe_invs

    # F. Hard constraints
    norm_rest_hc = sorted(str(hc) for hc in p_rest.hard_constraints)
    norm_ws_hc = sorted(str(hc) for hc in p_ws.hard_constraints)
    norm_pipe_hc = sorted(str(hc) for hc in p_pipe.hard_constraints)
    assert norm_rest_hc == norm_ws_hc == norm_pipe_hc


# ==============================================================================
# 3. Five Typed Prohibition Scenarios
# ==============================================================================

def test_scenario_a_blocks_world_exact_stack_prohibition():
    """Scenario A: Blocks World - forbid stack(b1, b2) without forbidding all stack actions."""
    domain = registry.get("blocks_world")
    builder = ValidatedProblemBuilder(registry=registry)
    verifier = PlanVerifier()

    proposal = TaskProposalSchema(
        task_id="t_prop_a",
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
            )
        ],
    )

    build_res = builder.build_from_proposal(proposal, domain)
    assert build_res.is_success is True
    problem = build_res.problem

    # Assert exact binding constraint exists
    exact_hcs = [hc for hc in problem.hard_constraints if isinstance(hc, ForbidActionExactBindingConstraint)]
    assert len(exact_hcs) == 1
    assert exact_hcs[0].forbidden_action == "stack"
    assert list(exact_hcs[0].forbidden_args) == ["b1", "b2"]

    # 1. Permitted stack action stack(b1, b3) verifies successfully
    valid_plan = PlanSchema(actions=[
        GroundActionSchema(name="pick_up", arguments=("b1",)),
        GroundActionSchema(name="stack", arguments=("b1", "b3")),
    ])
    v_valid = verifier.verify(problem, domain, valid_plan)
    assert v_valid.is_valid is True

    # 2. Forbidden stack action stack(b1, b2) fails verification
    forbidden_plan = PlanSchema(actions=[
        GroundActionSchema(name="pick_up", arguments=("b1",)),
        GroundActionSchema(name="stack", arguments=("b1", "b2")),
    ])
    v_forbid = verifier.verify(problem, domain, forbidden_plan)
    assert v_forbid.is_valid is False
    assert v_forbid.violation_type == ViolationType.HARD_CONSTRAINT_VIOLATED
    assert "stack(b1, b2)" in v_forbid.explanation


def test_scenario_b_manipulation_prohibition_touching_glass():
    """Scenario B: Manipulation prohibition - forbid actions touching glass while allowing other blocks."""
    domain = registry.get("blocks_world")
    builder = ValidatedProblemBuilder(registry=registry)
    verifier = PlanVerifier()

    proposal = TaskProposalSchema(
        task_id="t_prop_b",
        domain_id="blocks_world",
        entities={"glass": "block", "b1": "block", "b2": "block"},
        initial_facts=[
            FactSchema(predicate="on_table", arguments=["glass"]),
            FactSchema(predicate="clear", arguments=["glass"]),
            FactSchema(predicate="on_table", arguments=["b1"]),
            FactSchema(predicate="clear", arguments=["b1"]),
            FactSchema(predicate="on_table", arguments=["b2"]),
            FactSchema(predicate="clear", arguments=["b2"]),
            FactSchema(predicate="handempty", arguments=[]),
        ],
        goal_facts=[FactSchema(predicate="on", arguments=["b1", "b2"])],
        typed_constraints=[
            TaskConstraintSchema(
                constraint_type=TaskConstraintType.FORBID_ACTION_BINDING,
                action_name="pick_up",
                entity="glass",
                arg_index=0,
                description="Do not pick up glass",
            ),
            TaskConstraintSchema(
                constraint_type=TaskConstraintType.FORBID_ACTION_BINDING,
                action_name="unstack",
                entity="glass",
                arg_index=0,
                description="Do not unstack glass",
            ),
        ],
    )

    build_res = builder.build_from_proposal(proposal, domain)
    assert build_res.is_success is True
    problem = build_res.problem

    # 1. Candidate manipulating b1 and b2 is allowed and valid
    valid_plan = PlanSchema(actions=[
        GroundActionSchema(name="pick_up", arguments=("b1",)),
        GroundActionSchema(name="stack", arguments=("b1", "b2")),
    ])
    v_valid = verifier.verify(problem, domain, valid_plan)
    assert v_valid.is_valid is True

    # 2. Candidate manipulating glass is strictly rejected with HARD_CONSTRAINT_VIOLATED
    glass_plan = PlanSchema(actions=[
        GroundActionSchema(name="pick_up", arguments=("glass",)),
    ])
    v_glass = verifier.verify(problem, domain, glass_plan)
    assert v_glass.is_valid is False
    assert v_glass.violation_type == ViolationType.HARD_CONSTRAINT_VIOLATED
    assert "glass" in v_glass.explanation


def test_scenario_c_grid_world_cell_trap_prohibition():
    """Scenario C: Grid World - forbid transition to cell_trap while alternate path exists."""
    domain = registry.get("grid_world")
    builder = ValidatedProblemBuilder(registry=registry)
    verifier = PlanVerifier()

    proposal = TaskProposalSchema(
        task_id="t_prop_c",
        domain_id="grid_world",
        entities={"agent": "agent", "cell_a": "location", "cell_b": "location", "cell_trap": "location"},
        initial_facts=[
            FactSchema(predicate="at", arguments=["agent", "cell_a"]),
            FactSchema(predicate="connected", arguments=["cell_a", "cell_trap"]),
            FactSchema(predicate="connected", arguments=["cell_trap", "cell_b"]),
            FactSchema(predicate="connected", arguments=["cell_a", "cell_b"]),
        ],
        goal_facts=[FactSchema(predicate="at", arguments=["agent", "cell_b"])],
        typed_constraints=[
            TaskConstraintSchema(
                constraint_type=TaskConstraintType.FORBID_TRANSITION,
                action_name="move",
                to_entity="cell_trap",
                arg_index=2,
                description="Do not move to cell_trap",
            )
        ],
    )

    build_res = builder.build_from_proposal(proposal, domain)
    assert build_res.is_success is True
    problem = build_res.problem

    # 1. Planner must successfully find alternate path without entering cell_trap
    planner = AStarPlanner()
    plan = planner.search(problem, domain)
    assert plan.is_success is True
    assert len(plan.actions) == 1
    assert plan.actions[0].name == "move"
    assert plan.actions[0].arguments == ("agent", "cell_a", "cell_b")

    # 2. Verifier: moving to cell_trap fails with HARD_CONSTRAINT_VIOLATED
    bad_plan = PlanSchema(actions=[
        GroundActionSchema(name="move", arguments=("agent", "cell_a", "cell_trap")),
        GroundActionSchema(name="move", arguments=("agent", "cell_trap", "cell_b")),
    ])
    v_bad = verifier.verify(problem, domain, bad_plan)
    assert v_bad.is_valid is False
    assert v_bad.violation_type == ViolationType.HARD_CONSTRAINT_VIOLATED
    assert "cell_trap" in v_bad.explanation


def test_scenario_d_software_workflow_production_prohibition():
    """Scenario D: Software Workflow - forbid production deployment without blocking build/test/staging."""
    domain = registry.get("software_workflow")
    builder = ValidatedProblemBuilder(registry=registry)
    verifier = PlanVerifier()

    proposal = TaskProposalSchema(
        task_id="t_prop_d",
        domain_id="software_workflow",
        entities={"c1": "commit", "art1": "artifact", "staging": "environment", "production": "environment"},
        initial_facts=[
            FactSchema(predicate="code_checked_out", arguments=["c1"]),
            FactSchema(predicate="environment_healthy", arguments=["staging"]),
            FactSchema(predicate="environment_healthy", arguments=["production"]),
        ],
        goal_facts=[FactSchema(predicate="deployed_to", arguments=["art1", "staging"])],
        typed_constraints=[
            TaskConstraintSchema(
                constraint_type=TaskConstraintType.FORBID_ACTION_BINDING,
                action_name="deploy_to_environment",
                entity="production",
                arg_index=2,
                description="Do not deploy to production environment",
            )
        ],
    )

    build_res = builder.build_from_proposal(proposal, domain)
    assert build_res.is_success is True
    problem = build_res.problem

    # 1. Pipeline actions for build, test, and staging deployment succeed completely
    staging_plan = PlanSchema(actions=[
        GroundActionSchema(name="run_unit_tests", arguments=("c1",)),
        GroundActionSchema(name="run_security_scan", arguments=("c1",)),
        GroundActionSchema(name="build_artifact", arguments=("c1", "art1")),
        GroundActionSchema(name="grant_approval", arguments=("c1", "staging")),
        GroundActionSchema(name="deploy_to_environment", arguments=("c1", "art1", "staging")),
    ])
    v_staging = verifier.verify(problem, domain, staging_plan)
    assert v_staging.is_valid is True

    # 2. Production deployment is strictly blocked and rejected
    production_plan = PlanSchema(actions=[
        GroundActionSchema(name="run_unit_tests", arguments=("c1",)),
        GroundActionSchema(name="run_security_scan", arguments=("c1",)),
        GroundActionSchema(name="build_artifact", arguments=("c1", "art1")),
        GroundActionSchema(name="grant_approval", arguments=("c1", "production")),
        GroundActionSchema(name="deploy_to_environment", arguments=("c1", "art1", "production")),
    ])
    v_prod = verifier.verify(problem, domain, production_plan)
    assert v_prod.is_valid is False
    assert v_prod.violation_type == ViolationType.HARD_CONSTRAINT_VIOLATED
    assert "production" in v_prod.explanation


def test_scenario_e_negative_state_facts_vs_action_prohibitions_distinct():
    """Scenario E: Negative state facts vs action-level prohibitions are represented and checked distinctly."""
    domain = registry.get("blocks_world")
    builder = ValidatedProblemBuilder(registry=registry)

    proposal = TaskProposalSchema(
        task_id="t_prop_e",
        domain_id="blocks_world",
        entities={"glass": "block", "b1": "block"},
        initial_facts=[
            FactSchema(predicate="on_table", arguments=["glass"]),
            FactSchema(predicate="clear", arguments=["glass"]),
            FactSchema(predicate="on_table", arguments=["b1"]),
            FactSchema(predicate="clear", arguments=["b1"]),
            FactSchema(predicate="handempty", arguments=[]),
        ],
        goal_facts=[FactSchema(predicate="holding", arguments=["b1"])],
        negative_constraints=[
            FactSchema(predicate="holding", arguments=["glass"], is_negated=True),
        ],
        typed_constraints=[
            TaskConstraintSchema(
                constraint_type=TaskConstraintType.FORBID_ACTION_BINDING,
                action_name="pick_up",
                entity="glass",
                arg_index=0,
                description="Do not execute pick_up on glass",
            )
        ],
    )

    build_res = builder.build_from_proposal(proposal, domain)
    assert build_res.is_success is True
    problem = build_res.problem

    # 1. Negative state facts are stored as NegativeFactInvariant in problem.invariants
    neg_invariants = [inv for inv in problem.invariants if isinstance(inv, NegativeFactInvariant)]
    assert len(neg_invariants) == 1
    assert neg_invariants[0].forbidden_fact.predicate == "holding"
    assert tuple(neg_invariants[0].forbidden_fact.arguments) == ("glass",)

    # 2. Action prohibitions are stored as HardConstraint subclasses in problem.hard_constraints
    action_hcs = [hc for hc in problem.hard_constraints if isinstance(hc, ForbidActionBindingConstraint)]
    assert len(action_hcs) == 1
    assert action_hcs[0].forbidden_action == "pick_up"
    assert action_hcs[0].entity == "glass"
    assert action_hcs[0].arg_index == 0

    # 3. Invariants are checked against states (problem.check_invariants)
    violating_state = SymbolicState([
        Fact("holding", ["glass"]),
    ])
    inv_ok, inv_msg = problem.check_invariants(violating_state)
    assert inv_ok is False
    assert "holding(glass)" in inv_msg

    # 4. Action constraints are checked against ground actions (problem.check_hard_constraints)
    act_ok, act_msg = problem.check_hard_constraints(
        state=problem.initial_state,
        action_name="pick_up",
        action_args=["glass"],
    )
    assert act_ok is False
    assert "glass" in act_msg
