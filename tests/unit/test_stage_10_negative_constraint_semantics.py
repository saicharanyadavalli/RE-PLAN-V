"""Unit tests for Stage 10 DEF-10.2: Exact Negative Constraint Semantics & Constraints."""

from __future__ import annotations

import pytest
from core.contracts import FactSchema, TaskProposalSchema
from core.domains import registry
from core.world.constraints import (
    ForbidActionBindingConstraint,
    ForbidActionConstraint,
    NegativeFactInvariant,
    ProhibitedEntityActionConstraint,
)
from core.world.predicates import Fact
from core.world.state import SymbolicState
from interpretation.validator.validator import ConsistencyValidator


def test_prohibited_entity_action_constraint_does_not_block_arbitrary_actions():
    state = SymbolicState(facts=[])
    # Prohibit ONLY "drop" on "glass"
    c = ProhibitedEntityActionConstraint(protected_entity="glass", prohibited_actions=["drop"])
    # "pick_up" with glass should be permitted
    allowed, msg = c.check_action(state, "pick_up", ["glass"])
    assert allowed is True
    assert msg is None

    # "drop" with glass should be blocked
    allowed2, msg2 = c.check_action(state, "drop", ["glass"])
    assert allowed2 is False
    assert "strictly forbidden" in msg2

    # Empty prohibited_actions must NOT block all actions
    c_empty = ProhibitedEntityActionConstraint(protected_entity="agent", prohibited_actions=[])
    allowed3, _ = c_empty.check_action(state, "move", ["agent", "cell_1", "cell_2"])
    assert allowed3 is True


def test_forbid_action_constraint():
    state = SymbolicState(facts=[])
    c = ForbidActionConstraint(forbidden_action="nuke_database")
    allowed, msg = c.check_action(state, "query", ["users"])
    assert allowed is True

    blocked, msg_b = c.check_action(state, "nuke_database", [])
    assert blocked is False
    assert "action 'nuke_database' is strictly forbidden" in msg_b


def test_forbid_action_binding_constraint():
    state = SymbolicState(facts=[])
    # Forbid deploy when target env is "production"
    c = ForbidActionBindingConstraint(forbidden_action="deploy", entity="production", arg_index=1)

    # Deploying to staging is permitted
    allowed, _ = c.check_action(state, "deploy", ["pkg_1", "staging"])
    assert allowed is True

    # Deploying to production is blocked
    blocked, msg = c.check_action(state, "deploy", ["pkg_1", "production"])
    assert blocked is False
    assert "production" in msg


def test_scenario_5_gridworld_negative_constraint_preserves_movement():
    gw_domain = registry.get("grid_world")
    validator = ConsistencyValidator()

    # Proposal with negative constraint: Do not enter cell_trap
    proposal = TaskProposalSchema(
        task_id="gw_safe_route",
        raw_prompt="Move agent from cell_a to cell_b. Avoid cell_trap.",
        entities={"agent": "agent", "cell_a": "location", "cell_b": "location", "cell_trap": "location"},
        initial_facts=[
            FactSchema(predicate="at", arguments=("agent", "cell_a")),
            FactSchema(predicate="connected", arguments=("cell_a", "cell_b")),
            FactSchema(predicate="connected", arguments=("cell_a", "cell_trap")),
            FactSchema(predicate="empty_hand", arguments=()),
        ],
        goal_facts=[FactSchema(predicate="at", arguments=("agent", "cell_b"))],
        negative_constraints=[FactSchema(predicate="at", arguments=("agent", "cell_trap"))],
    )

    problem = validator.convert_to_problem(proposal, gw_domain)

    # Must contain NegativeFactInvariant for at(agent, cell_trap)
    assert any(isinstance(inv, NegativeFactInvariant) and "cell_trap" in inv.name for inv in problem.invariants)

    # Must NOT contain a wildcard ProhibitedEntityActionConstraint that freezes the agent
    for hc in problem.hard_constraints:
        if isinstance(hc, ProhibitedEntityActionConstraint):
            assert len(hc.prohibited_actions) > 0

    # Moving to safe cell_b must satisfy hard constraints and invariants
    safe_state = SymbolicState([Fact("at", ["agent", "cell_b"])])
    ok_inv, _ = problem.check_invariants(safe_state)
    assert ok_inv is True

    # Moving to cell_trap must violate invariants
    trap_state = SymbolicState([Fact("at", ["agent", "cell_trap"])])
    ok_trap, trap_msg = problem.check_invariants(trap_state)
    assert ok_trap is False
    assert "cell_trap" in trap_msg


def test_scenario_7_software_workflow_negative_constraint_preserves_pipeline():
    sw_domain = registry.get("software_workflow")
    validator = ConsistencyValidator()

    proposal = TaskProposalSchema(
        task_id="sw_staging_only",
        raw_prompt="Build commit_v1 and deploy to staging. Do not deploy to production.",
        entities={
            "commit_v1": "commit",
            "pkg_v1": "artifact",
            "staging": "environment",
            "production": "environment",
        },
        initial_facts=[
            FactSchema(predicate="code_checked_out", arguments=("commit_v1",)),
            FactSchema(predicate="environment_healthy", arguments=("staging",)),
            FactSchema(predicate="environment_healthy", arguments=("production",)),
        ],
        goal_facts=[FactSchema(predicate="deployed_to", arguments=("pkg_v1", "staging"))],
        negative_constraints=[FactSchema(predicate="deployed_to", arguments=("pkg_v1", "production"))],
    )

    problem = validator.convert_to_problem(proposal, sw_domain)

    # Must preserve domain default invariants (e.g. single deployment functional dependency)
    assert any("functional_deployed_to" in inv.name for inv in problem.invariants)

    # Staging state is safe
    staging_state = SymbolicState([Fact("deployed_to", ["pkg_v1", "staging"])])
    ok_staging, _ = problem.check_invariants(staging_state)
    assert ok_staging is True

    # Production state is prohibited
    prod_state = SymbolicState([Fact("deployed_to", ["pkg_v1", "production"])])
    ok_prod, prod_msg = problem.check_invariants(prod_state)
    assert ok_prod is False
    assert "production" in prod_msg
