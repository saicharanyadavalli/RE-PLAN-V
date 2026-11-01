"""Integration tests for Stage 10 DEF-10.3: Domain Default Invariants & Validation."""

from __future__ import annotations

import pytest
from core.contracts import FactSchema, TaskProposalSchema, ValidationStatus
from core.domains import registry
from core.verification.verifier import PlanVerifier
from core.world.predicates import Fact
from core.world.state import SymbolicState
from interpretation.validator.validator import ConsistencyValidator


def test_domain_default_invariants_preserved_in_all_six_domains():
    validator = ConsistencyValidator()
    for domain in registry.list_domains():
        proposal = TaskProposalSchema(
            task_id=f"test_{domain.domain_id}",
            raw_prompt="minimal test",
            entities={},
            initial_facts=[],
            goal_facts=[],
        )
        problem = validator.convert_to_problem(proposal, domain)
        # Verify that all domain default invariants are present in problem invariants
        for default_inv in domain.default_invariants:
            assert any(inv.name == default_inv.name for inv in problem.invariants), (
                f"Domain '{domain.domain_id}' default invariant '{default_inv.name}' missing from converted problem."
            )


def test_verifier_catches_functional_dependency_violation_in_blocks_world():
    bw = registry.get("blocks_world")
    validator = ConsistencyValidator()
    proposal = TaskProposalSchema(
        task_id="bw_mutex",
        raw_prompt="stack",
        entities={"b1": "block", "b2": "block", "b3": "block"},
        initial_facts=[
            FactSchema(predicate="on_table", arguments=("b2",)),
            FactSchema(predicate="on_table", arguments=("b3",)),
            FactSchema(predicate="clear", arguments=("b2",)),
            FactSchema(predicate="clear", arguments=("b3",)),
            FactSchema(predicate="holding", arguments=("b1",)),
        ],
        goal_facts=[FactSchema(predicate="on", arguments=("b1", "b2"))],
    )
    problem = validator.convert_to_problem(proposal, bw)
    # Default invariant functional_on_0->1 must be in problem
    assert any("functional_on" in inv.name for inv in problem.invariants)

    # In a state where b1 is simultaneously on b2 AND b3, invariant must fail
    invalid_state = SymbolicState([
        Fact("on", ["b1", "b2"]),
        Fact("on", ["b1", "b3"]),
    ])
    satisfied, msg = problem.check_invariants(invalid_state)
    assert satisfied is False
    assert "Functional dependency violated" in msg


def test_validator_rejects_initial_state_violating_domain_invariants():
    gw = registry.get("grid_world")
    validator = ConsistencyValidator()
    # Agent simultaneously at cell_1 and cell_2 violates functional dependency on "at"
    proposal = TaskProposalSchema(
        task_id="gw_double_at",
        raw_prompt="move agent",
        entities={"agent": "agent", "cell_1": "location", "cell_2": "location"},
        initial_facts=[
            FactSchema(predicate="at", arguments=("agent", "cell_1")),
            FactSchema(predicate="at", arguments=("agent", "cell_2")),
            FactSchema(predicate="agent_free", arguments=("agent",)),
        ],
        goal_facts=[FactSchema(predicate="at", arguments=("agent", "cell_2"))],
    )
    val_res = validator.validate(proposal, gw)
    assert val_res.is_valid is False
    assert val_res.status == ValidationStatus.CONTRADICTION
    assert any("Domain invariant violation" in e for e in val_res.errors)


def test_validator_rejects_type_hierarchy_mismatch():
    bw = registry.get("blocks_world")
    validator = ConsistencyValidator()
    # Registering an entity with an incompatible type
    proposal = TaskProposalSchema(
        task_id="bw_type_mismatch",
        raw_prompt="stack table on block",
        entities={"my_obj": "location", "b1": "block"},
        initial_facts=[
            FactSchema(predicate="on_table", arguments=("my_obj",)),  # on_table expects block
            FactSchema(predicate="clear", arguments=("b1",)),
            FactSchema(predicate="handempty", arguments=()),
        ],
        goal_facts=[FactSchema(predicate="on", arguments=("b1", "my_obj"))],
    )
    val_res = validator.validate(proposal, bw)
    assert val_res.is_valid is False
    assert val_res.status == ValidationStatus.TYPE_MISMATCH
    assert any("Type mismatch" in e for e in val_res.errors)
